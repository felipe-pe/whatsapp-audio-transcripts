import os
import platform
import subprocess
import logging
import torch
from flask import Flask, request, jsonify, send_from_directory, render_template_string
from queue import Queue
from threading import Thread, Lock
import time
import pysrt

# Inicialização do app Flask
app = Flask(__name__)

logging.basicConfig(level=logging.INFO)

# Variáveis globais de diretório
UPLOAD_FOLDER = 'audios'
OUTPUT_FOLDER = 'transcriptions'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

# Inicialização da fila de transcrição
transcription_queue = Queue()
queue_lock = Lock()

# Lock para garantir que apenas uma transcrição ocorra por vez
transcription_lock = Lock()

# Função para detectar o sistema operacional e a arquitetura
def detect_system():
    system = platform.system()
    architecture = platform.machine()

    if system == "Windows":
        os_type = "windows"
    elif system == "Linux":
        os_type = "linux"
    elif system == "Darwin":  # macOS
        os_type = "macos"
    else:
        sys.exit(f"Sistema operacional {system} não suportado.")

    if architecture.startswith("x86_64"):
        arch_type = "x64"
    elif architecture.startswith("arm"):
        arch_type = "arm"
    else:
        sys.exit(f"Arquitetura {architecture} não suportada.")

    return os_type, arch_type

# Função para verificar se a GPU Nvidia está disponível
def is_gpu_available():
    try:
        if torch.cuda.is_available():
            logging.info(f"GPU Nvidia detectada: {torch.cuda.get_device_name(0)}")
            return True
        else:
            logging.info("Nenhuma GPU Nvidia disponível. Usando CPU.")
            return False
    except ImportError:
        logging.info("PyTorch não está instalado. Usando CPU.")
        return False

# Função para criar os diretórios de transcrição do usuário
def create_directories(user_id, request_id):
    user_folder = os.path.join(OUTPUT_FOLDER, user_id)
    request_folder = os.path.join(user_folder, request_id)
    os.makedirs(request_folder, exist_ok=True)
    return request_folder
# Função para ajustar o comando de execução do Whisper dependendo do sistema operacional e arquitetura
def adjust_command_for_platform(audio_path, config):
    os_type, arch_type = detect_system()

    # Se estiver no macOS ARM ou qualquer outro sistema onde o executável não seja suportado
    if os_type == "macos" and arch_type == "arm":
        logging.info("Executando Whisper no macOS ARM (sem GPU)")
        command = [
            'python3', '-m', 'whisper',
            audio_path,
            '--model', config.get('model', 'medium'),
            '--output_dir', config['request_folder']
        ]
        # Adiciona beam_size e chunk_length se configurados
        if config.get('beam_size'):
            command.extend(['--beam_size', str(config['beam_size'])])
        if config.get('chunk_length'):
            command.extend(['--chunk_length', str(config['chunk_length'])])
    
    # Se for Windows ou Linux, tentar usar o executável pré-compilado ou fallback para Python
    elif os_type in ["windows", "linux"]:
        logging.info(f"Executando no {os_type} ({arch_type})")
        
        # Verifica se há GPU disponível e configura o comando adequado
        if is_gpu_available():
            logging.info("Usando GPU para transcrição.")
            command = [
                'faster-whisper-xxl.exe',  # Executável pré-baixado
                audio_path,
                '--language', 'Portuguese',
                '--model', config.get('model', 'medium'),
                '--output_dir', config['request_folder']
            ]
            if config.get('torch_dtype'):
                command.extend(['--torch_dtype', config['torch_dtype']])
            if config.get('beam_size'):
                command.extend(['--beam_size', str(config['beam_size'])])
            if config.get('chunk_length'):
                command.extend(['--chunk_length', str(config['chunk_length'])])

        # Se não houver GPU, usar a versão Python do Whisper
        else:
            logging.info("Usando CPU para transcrição (fallback para Python Whisper).")
            command = [
                'python3', '-m', 'whisper',
                audio_path,
                '--model', config.get('model', 'medium'),
                '--device', 'cpu',  # Especifica CPU como dispositivo
                '--output_dir', config['request_folder']
            ]
            if config.get('beam_size'):
                command.extend(['--beam_size', str(config['beam_size'])])
            if config.get('chunk_length'):
                command.extend(['--chunk_length', str(config['chunk_length'])])

    else:
        sys.exit(f"Sistema {os_type} com arquitetura {arch_type} não é suportado no momento.")

    return command

# Função para transcrever áudio (com fallback para CPU ou Whisper em Python se necessário)
def transcribe_audio(audio_path, request_folder, config):
    start_time = time.time()  # Marca o início da transcrição
    config['request_folder'] = request_folder  # Adiciona o diretório de saída à configuração
    
    try:
        # Configura o comando adequado para CPU ou GPU baseado no sistema
        command = adjust_command_for_platform(audio_path, config)
        logging.info(f"Executando comando: {' '.join(command)}")
        subprocess.run(command, check=True)
        logging.info(f"Transcrição concluída e salva em {request_folder}")
        
        end_time = time.time()  # Marca o fim da transcrição e calcula o tempo total
        elapsed_time = end_time - start_time
        logging.info(f"Tempo total de transcrição: {elapsed_time:.2f} segundos")
        
        return True
    except subprocess.CalledProcessError as e:
        logging.error(f"Erro ao transcrever: {e}")
        return False
# Função para processar a fila de transcrições
def process_queue():
    while True:
        audio_path, request_folder, config = transcription_queue.get()
        if audio_path is None:
            break
        try:
            with transcription_lock:  # Garantindo que apenas uma transcrição ocorra por vez
                transcribe_audio(audio_path, request_folder, config)
        finally:
            transcription_queue.task_done()

# Inicia a thread para processamento de transcrições em segundo plano
thread = Thread(target=process_queue, daemon=True)
thread.start()

# Função para gerar HTML a partir de um arquivo SRT
def generate_html_paragraph(srt_path, html_path):
    try:
        subs = pysrt.open(srt_path, encoding='utf-8')
        paragraph = " ".join([sub.text.replace('\n', ' ') for sub in subs])

        html_content = f"<html><body><p>{paragraph}</p></body></html>"

        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(html_content)

        logging.info(f"Arquivo HTML criado com sucesso em {html_path}")
        return True
    except Exception as e:
        logging.error(f"Falha ao criar HTML: {e}")
        return False

# Função para encontrar um arquivo com base na extensão
def find_file_by_extension(directory, extension):
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.endswith(extension):
                return os.path.join(root, file)
    return None

# Rota para upload de arquivo de áudio com diferentes configurações
@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({"error": "Nenhum arquivo enviado"}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "Nenhum arquivo selecionado"}), 400

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
                raise Exception("Falha ao gerar HTML")

            return jsonify({
                "message": "Transcrição concluída com sucesso",
                "srt_path": srt_path,
                "html_path": html_path
            })
        else:
            logging.error(f"Arquivo SRT não encontrado ou está vazio para a requisição {request_id}")
            return jsonify({"error": "Arquivo SRT não encontrado ou está vazio"}), 500

    except Exception as e:
        logging.error(f"Ocorreu um erro inesperado: {e}")
        return jsonify({"error": f"Ocorreu um erro inesperado: {str(e)}"}), 500

    finally:
        if os.path.exists(file_path):
            os.remove(file_path)

# Rota para servir arquivos em qualquer subdiretório de transcriptions
@app.route('/transcriptions/', defaults={'subpath': ''})
@app.route('/transcriptions/<path:subpath>')
def serve_transcriptions(subpath):
    directory = os.path.join(OUTPUT_FOLDER, subpath)

    if os.path.isdir(directory):
        # Se for um diretório, listar o conteúdo
        files = os.listdir(directory)
        html_content = f"<h2>Navegando em: /transcriptions/{subpath}</h2><ul>"
        for file_name in files:
            file_path = os.path.join(subpath, file_name)
            if os.path.isdir(os.path.join(directory, file_name)):
                html_content += f'<li><a href="/transcriptions/{file_path}/">{file_name}/</a></li>'
            else:
                html_content += f'<li><a href="/transcriptions/{file_path}">{file_name}</a></li>'
        html_content += "</ul>"
        return render_template_string(html_content)
    elif os.path.isfile(directory):
        # Se for um arquivo, retornar o arquivo
        return send_from_directory(OUTPUT_FOLDER, subpath)
    else:
        return jsonify({"error": "Caminho não encontrado"}), 404

# Inicia o servidor Flask
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5502)
