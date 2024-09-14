from flask import Flask, request, jsonify, send_from_directory, render_template_string
import os
import subprocess
import logging
import pysrt
from queue import Queue
from threading import Thread, Lock
import time
import shutil  # Import necessário para remover vídeos após a extração do áudio
from lock import acquire_lock, release_lock


app = Flask(__name__)

logging.basicConfig(level=logging.INFO)

# Caminho para o executável
FASTER_WHISPER_PATH = r"faster-whisper-xxl.exe"
UPLOAD_FOLDER = 'uploads'  # Alterei o nome da pasta para refletir melhor que ela lida com áudios e vídeos
OUTPUT_FOLDER = 'transcriptions'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

# Configuração da fila de transcrição
transcription_queue = Queue()
queue_lock = Lock()

# Lock para garantir que apenas uma transcrição ocorra por vez
transcription_lock = Lock()

# Função para processar a fila de transcrições
def process_queue():
    while True:
        media_path, request_folder, config = transcription_queue.get()
        if media_path is None:
            break
        try:
            with transcription_lock:  # Garantindo que apenas uma transcrição ocorra por vez
                handle_media(media_path, request_folder, config)
        finally:
            transcription_queue.task_done()

# Inicia a thread para processamento de transcrições em segundo plano
thread = Thread(target=process_queue, daemon=True)
thread.start()
# Função para extrair áudio de vídeos de maneira robusta

def extract_audio_from_video(video_path, audio_output_path):
    """Extrai o áudio de um vídeo e salva no formato .wav, com suporte a múltiplos formatos."""
    try:
        acquire_lock()  # Adquirir o lock antes de usar a GPU
        
        # Verifica o formato e codecs do vídeo
        ffprobe_command = [
            'ffprobe', 
            '-v', 'error', 
            '-select_streams', 'a:0', 
            '-show_entries', 'stream=codec_name', 
            '-of', 'default=noprint_wrappers=1:nokey=1', 
            video_path
        ]
        result = subprocess.run(ffprobe_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        audio_codec = result.stdout.strip()
        logging.info(f"Codec de áudio detectado: {audio_codec}")

        # Se o codec de áudio não for suportado, tenta reencapsular o arquivo para um formato compatível
        if audio_codec not in ['aac', 'mp3', 'pcm_s16le']:
            logging.warning(f"Codec de áudio {audio_codec} pode ser incompatível, reencapsulando para formato compatível.")
            reencapsulated_path = video_path.replace('.mp4', '_reencapsulated.mp4')
            reencapsulate_command = [
                'ffmpeg', '-i', video_path, '-c:v', 'copy', '-c:a', 'aac', reencapsulated_path
            ]
            subprocess.run(reencapsulate_command, check=True)
            video_path = reencapsulated_path
            logging.info(f"Arquivo reencapsulado com sucesso: {reencapsulated_path}")

        # Extração do áudio para WAV com parâmetros ajustados
        command = [
            'ffmpeg', '-i', video_path, '-vn', '-acodec', 'pcm_s16le', '-ar', '44100', '-ac', '2', audio_output_path
        ]
        subprocess.run(command, shell=False, check=True)
        logging.info(f"Áudio extraído com sucesso de {video_path} para {audio_output_path}.")
        
    except subprocess.CalledProcessError as e:
        logging.error(f"Erro ao extrair áudio de {video_path}: {e}")
        raise
    finally:
        release_lock()  # Libera o lock após o uso da GPU



# Função para remover o arquivo de vídeo após extração
def remove_file(file_path):
    """Remove o arquivo especificado."""
    if os.path.exists(file_path):
        os.remove(file_path)
        logging.info(f"Arquivo {file_path} removido com sucesso.")
    else:
        logging.warning(f"Arquivo {file_path} não encontrado para remoção.")

# Função que decide se o arquivo é áudio ou vídeo e processa adequadamente
def handle_media(media_path, request_folder, config):
    """Processa arquivos de áudio ou vídeo para transcrição."""
    file_ext = os.path.splitext(media_path)[-1].lower()

    if file_ext in ['.mp4', '.mkv', '.avi']:
        # Tratamento de vídeo: extrair áudio
        audio_output_path = media_path.replace(file_ext, '.wav')
        extract_audio_from_video(media_path, audio_output_path)
        
        # Remover o vídeo após a extração do áudio
        remove_file(media_path)
        
        # Chamar a transcrição com o áudio extraído
        transcribe_audio(audio_output_path, request_folder, config)
        
        # Remover o arquivo de áudio após a transcrição, se necessário
        if config.get('remove_audio_after_transcription', False):
            remove_file(audio_output_path)

    elif file_ext in ['.wav', '.mp3', '.aac']:
        # Tratamento de áudio direto: transcrever
        transcribe_audio(media_path, request_folder, config)
    else:
        logging.error(f"Formato de arquivo não suportado: {file_ext}")
        raise ValueError(f"Formato de arquivo não suportado: {file_ext}")

        
def is_srt_valid(srt_path):
    try:
        subs = pysrt.open(srt_path, encoding='utf-8')
        # Verifica se há alguma legenda com conteúdo significativo
        for sub in subs:
            # Remove espaços, novas linhas e caracteres irrelevantes para validar o conteúdo
            cleaned_text = sub.text.strip().replace('\n', ' ')
            if len(cleaned_text) > 0:
                return True
        return False
    except Exception as e:
        logging.error(f"Erro ao validar o arquivo SRT: {e}")
        return False
# Função para transcrever o áudio (mesma função existente)
def transcribe_audio(audio_path, request_folder, config):
    start_time = time.time()  # Marca o início da transcrição
    
    try:
        acquire_lock()  # Adquirir o lock antes de utilizar a GPU

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
        
        logging.info(f"Executando comando: {' '.join(command)}")
        subprocess.run(command, check=True)
        logging.info(f"Transcrição concluída e salva em {request_folder}")
        
        # Marca o fim da transcrição e calcula o tempo total
        end_time = time.time()
        elapsed_time = end_time - start_time
        logging.info(f"Tempo total de transcrição: {elapsed_time:.2f} segundos")
        
        return True
    except subprocess.CalledProcessError as e:
        logging.error(f"Erro durante a transcrição: {e}")
        return False
    finally:
        release_lock()  # Libera o lock após finalizar o uso da GPU


# Rota para upload do arquivo de áudio ou vídeo com diferentes configurações
@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({"error": "Nenhum arquivo enviado"}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "Nenhum arquivo selecionado"}), 400

    user_id = request.form.get('user_id')
    request_id = request.form.get('request_id')

    if not user_id or not request_id:
        return jsonify({"error": "ID de usuário ou de requisição ausente"}), 400

    # Configurações opcionais para as variações
    config = {
        'model': request.form.get('model', 'medium'),
        'beam_size': request.form.get('beam_size'),
        'chunk_length': request.form.get('chunk_length'),
        'torch_dtype': request.form.get('torch_dtype'),
        'remove_audio_after_transcription': request.form.get('remove_audio_after_transcription', 'false').lower() == 'true'
    }

    # Salva o arquivo na pasta de uploads
    file_ext = os.path.splitext(file.filename)[-1].lower()
    if file_ext not in ['.mp4', '.mkv', '.avi', '.wav', '.mp3', '.aac']:
        return jsonify({"error": f"Formato de arquivo não suportado: {file_ext}"}), 400

    file_path = os.path.join(UPLOAD_FOLDER, file.filename)
    file.save(file_path)

    # Cria os diretórios do usuário e da requisição
    request_folder = create_directories(user_id, request_id)

    # Adiciona a transcrição à fila
    try:
        with queue_lock:
            transcription_queue.put((file_path, request_folder, config))

        # Espera o processamento da fila para garantir a conclusão
        transcription_queue.join()

        # Renomeia o arquivo SRT gerado
        srt_path = os.path.join(request_folder, f'{request_id}.srt')
        srt_file_path = find_file_by_extension(request_folder, ".srt")
        if srt_file_path:
            os.rename(srt_file_path, srt_path)

        # Verifica se o SRT contém texto válido
        if os.path.exists(srt_path) and is_srt_valid(srt_path):
            # Gera o HTML em formato de parágrafo único a partir do SRT
            html_path = os.path.join(request_folder, f'{request_id}.html')
            if not generate_html_paragraph(srt_path, html_path):
                raise Exception("Falha ao gerar o HTML")

            return jsonify({
                "message": "Transcrição concluída com sucesso",
                "srt_path": srt_path,
                "html_path": html_path
            })
        else:
            logging.error(f"Arquivo SRT vazio ou inválido para a requisição {request_id}")
            # Gera um HTML indicando que não há conteúdo transcritível
            html_path = os.path.join(request_folder, f'{request_id}_no_transcription.html')
            with open(html_path, 'w', encoding='utf-8') as f:
                f.write("<html><body><p>Sem conteúdo transcritível detectado.</p></body></html>")
            
            return jsonify({
                "message": "Nenhum conteúdo transcritível detectado",
                "srt_path": None,
                "html_path": html_path
            })

    except Exception as e:
        logging.error(f"Erro inesperado: {e}")
        return jsonify({"error": f"Erro inesperado: {str(e)}"}), 500

    finally:
        if os.path.exists(file_path):
            os.remove(file_path)
# Função para criar os diretórios do usuário e da requisição
def create_directories(user_id, request_id):
    """Cria os diretórios do usuário e da requisição, se não existirem."""
    user_folder = os.path.join(OUTPUT_FOLDER, user_id)
    request_folder = os.path.join(user_folder, request_id)
    os.makedirs(request_folder, exist_ok=True)
    return request_folder

# Função para encontrar um arquivo com base na extensão
def find_file_by_extension(directory, extension):
    """Busca um arquivo em um diretório com uma determinada extensão."""
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.endswith(extension):
                return os.path.join(root, file)
    return None

# Função para gerar HTML em formato de parágrafo único a partir do arquivo SRT
def generate_html_paragraph(srt_path, html_path):
    """Converte o arquivo SRT em um HTML de parágrafo único."""
    try:
        subs = pysrt.open(srt_path, encoding='utf-8')
        paragraph = " ".join([sub.text.replace('\n', ' ') for sub in subs])

        html_content = f"<html><body><p>{paragraph}</p></body></html>"

        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(html_content)

        logging.info(f"Arquivo HTML criado com sucesso em {html_path}")
        return True
    except Exception as e:
        logging.error(f"Falha ao criar o HTML: {e}")
        return False

# Rota para servir arquivos em qualquer subdiretório de transcrições
@app.route('/transcriptions/', defaults={'subpath': ''})
@app.route('/transcriptions/<path:subpath>')
def serve_transcriptions(subpath):
    """Serve arquivos das transcrições ou lista o conteúdo de diretórios."""
    directory = os.path.join(OUTPUT_FOLDER, subpath)

    if os.path.isdir(directory):
        # Se for um diretório, listar o conteúdo
        files = os.listdir(directory)
        html_content = f"<h2>Navegando: /transcriptions/{subpath}</h2><ul>"
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

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5502)
