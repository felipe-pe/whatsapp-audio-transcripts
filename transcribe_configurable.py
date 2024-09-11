from flask import Flask, request, jsonify, send_from_directory
import os
import subprocess
import logging
import pysrt
from queue import Queue
from threading import Thread, Lock
import time

app = Flask(__name__)

logging.basicConfig(level=logging.INFO)

# Caminho para o executável
FASTER_WHISPER_PATH = r"faster-whisper-xxl.exe"
UPLOAD_FOLDER = 'audios'
OUTPUT_FOLDER = 'transcriptions'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

# Configuração da fila de transcrição
transcription_queue = Queue()
queue_lock = Lock()

# Função para processar a fila de transcrições
def process_queue():
    while True:
        audio_path, request_folder, config = transcription_queue.get()
        if audio_path is None:
            break
        try:
            transcribe_audio(audio_path, request_folder, config)
        finally:
            transcription_queue.task_done()

# Inicia a thread para processamento de transcrições em segundo plano
thread = Thread(target=process_queue, daemon=True)
thread.start()

# Função para transcrever com variações
def transcribe_audio(audio_path, request_folder, config):
    start_time = time.time()  # Marca o início da transcrição
    
    try:
        # Configuração base do comando
        command = [
            FASTER_WHISPER_PATH,
            audio_path,
            '--language', 'Portuguese',
            '--model', config.get('model', 'medium'),  # Modelo configurável
            '--output_dir', request_folder
        ]

        # Adiciona beam_size se configurado
        if config.get('beam_size'):
            command.extend(['--beam_size', str(config['beam_size'])])

        # Adiciona chunking se configurado
        if config.get('chunk_length'):
            command.extend(['--chunk_length', str(config['chunk_length'])])
        
        # Adiciona torch_dtype se configurado
        if config.get('torch_dtype'):
            command.extend(['--torch_dtype', config['torch_dtype']])
        
        logging.info(f"Executing command: {' '.join(command)}")
        subprocess.run(command, check=True)
        logging.info(f"Transcription completed and saved to {request_folder}")
        
        # Marca o fim da transcrição e calcula o tempo total
        end_time = time.time()
        elapsed_time = end_time - start_time
        logging.info(f"Tempo total de transcrição: {elapsed_time:.2f} segundos")
        
        return True
    except subprocess.CalledProcessError as e:
        logging.error(f"Error while transcribing: {e}")
        return False

# Criação dos diretórios para o usuário e requisição
def create_directories(user_id, request_id):
    user_folder = os.path.join(OUTPUT_FOLDER, user_id)
    request_folder = os.path.join(user_folder, request_id)
    os.makedirs(request_folder, exist_ok=True)
    return request_folder

# Função para encontrar um arquivo com base na extensão
def find_file_by_extension(directory, extension):
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.endswith(extension):
                return os.path.join(root, file)
    return None

# Geração de HTML em formato de parágrafo único sem marcações de tempo
def generate_html_paragraph(srt_path, html_path):
    try:
        subs = pysrt.open(srt_path, encoding='utf-8')
        paragraph = " ".join([sub.text.replace('\n', ' ') for sub in subs])

        html_content = f"<html><body><p>{paragraph}</p></body></html>"

        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(html_content)

        logging.info(f"HTML file created successfully at {html_path}")
        return True
    except Exception as e:
        logging.error(f"Failed to create HTML: {e}")
        return False

# Rota para upload do arquivo de áudio com diferentes configurações
@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400

    user_id = request.form.get('user_id')
    request_id = request.form.get('request_id')

    # Configurações opcionais para as variações
    config = {
        'model': request.form.get('model', 'medium'),
        'beam_size': request.form.get('beam_size'),
        'chunk_length': request.form.get('chunk_length'),
        'torch_dtype': request.form.get('torch_dtype')
    }

    file_path = os.path.join(UPLOAD_FOLDER, file.filename)
    file.save(file_path)

    request_folder = create_directories(user_id, request_id)
    srt_path = os.path.join(request_folder, f'{request_id}.srt')
    html_path = os.path.join(request_folder, f'{request_id}.html')

    try:
        # Adiciona a transcrição à fila
        with queue_lock:
            transcription_queue.put((file_path, request_folder, config))

        # Espera o processamento da fila para garantir a conclusão
        transcription_queue.join()

        # Renomeia o arquivo SRT gerado
        srt_file_path = find_file_by_extension(request_folder, ".srt")
        if srt_file_path:
            os.rename(srt_file_path, srt_path)

        if os.path.exists(srt_path) and os.path.getsize(srt_path) > 0:
            # Gera o HTML em formato de parágrafo único a partir do SRT
            if not generate_html_paragraph(srt_path, html_path):
                raise Exception("Failed to generate HTML")

            return jsonify({
                "message": "Transcription completed successfully",
                "srt_path": srt_path,
                "html_path": html_path
            })
        else:
            logging.error(f"SRT file not found or is empty for request {request_id}")
            return jsonify({"error": "SRT file not found or is empty"}), 500

    except Exception as e:
        logging.error(f"An unexpected error occurred: {e}")
        return jsonify({"error": f"An unexpected error occurred: {str(e)}"}), 500

    finally:
        if os.path.exists(file_path):
            os.remove(file_path)

# Rota para servir transcrições
@app.route('/transcriptions/<path:subpath>', methods=['GET'])
def serve_transcriptions(subpath):
    directory = os.path.join(OUTPUT_FOLDER)
    file_path = os.path.join(directory, subpath)
    
    if os.path.exists(file_path):
        return send_from_directory(directory, subpath)
    else:
        return jsonify({"error": "File not found"}), 404

# Rota para listar transcrições
@app.route('/list_transcriptions/<user_id>/<request_id>', methods=['GET'])
def list_transcriptions(user_id, request_id):
    request_folder = os.path.join(OUTPUT_FOLDER, user_id, request_id)
    
    if os.path.exists(request_folder):
        files = []
        for root, dirs, file_list in os.walk(request_folder):
            for file_name in file_list:
                relative_path = os.path.relpath(os.path.join(root, file_name), OUTPUT_FOLDER)
                files.append(relative_path)
        return jsonify(files)
    else:
        return jsonify({"error": "Request folder not found"}), 404

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5502)
