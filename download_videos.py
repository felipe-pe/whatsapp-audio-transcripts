import os
import subprocess
import logging
import sqlite3
import json
import unicodedata
import re
import urllib
from pathvalidate import sanitize_filename
from logging.handlers import RotatingFileHandler
from concurrent.futures import ThreadPoolExecutor
from flask import Flask, request, jsonify, render_template, send_from_directory
from flask import render_template_string

app = Flask(__name__)

# Diretórios e caminhos principais
if not os.path.exists("logs"):
    os.makedirs("logs")
if not os.path.exists("downloads"):
    os.makedirs("downloads")

# Caminho dos binários de ffmpeg, ffprobe e ffplay para download de vídeos
ffmpeg_download_package_dir = os.path.join(os.getcwd(), 'ffmpeg_download_videos_package', 'ffmpeg-2024-09-12-git-504c1ffcd8-full_build', 'bin')

# Caminho atualizado para ffmpeg, ffprobe e ffplay
ffmpeg_path = os.path.join(ffmpeg_download_package_dir, 'ffmpeg.exe')
ffprobe_path = os.path.join(ffmpeg_download_package_dir, 'ffprobe.exe')
ffplay_path = os.path.join(ffmpeg_download_package_dir, 'ffplay.exe')

# Configuração de Logging com rotação de arquivos
logger = logging.getLogger('transcoder')
logger.setLevel(logging.DEBUG)

fh = RotatingFileHandler("logs/transcode.log", maxBytes=10 * 1024 * 1024, backupCount=5)
ch = logging.StreamHandler()

formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
fh.setFormatter(formatter)
ch.setFormatter(formatter)

logger.addHandler(fh)
logger.addHandler(ch)

MAX_WORKERS = 3
executor = ThreadPoolExecutor(max_workers=MAX_WORKERS)

DATABASE = 'tasks.db'

def init_db():
    """Função para inicializar o banco de dados SQLite"""
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            id_request TEXT,
            id_user TEXT,
            status TEXT,
            error_message TEXT,
            log_filename TEXT
        )
    ''')
    conn.commit()
    conn.close()

def update_task_status(id_request, id_user, status, error_message=None, log_filename=None):
    """Atualiza o status de uma tarefa no banco de dados"""
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO tasks (id_request, id_user, status, error_message, log_filename)
        VALUES (?, ?, ?, ?, ?)
    ''', (id_request, id_user, status, error_message, log_filename))
    conn.commit()
    conn.close()

def configure_individual_logging(id_request, id_user):
    """Configura o logging individual para cada tarefa"""
    log_filename = f"{id_user}_{id_request}.log"
    handler = logging.FileHandler(f"logs/{log_filename}")
    handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s - %(message)s')
    handler.setFormatter(formatter)
    task_logger = logging.getLogger(log_filename)
    task_logger.addHandler(handler)
    task_logger.setLevel(logging.DEBUG)
    return task_logger, log_filename

def normalize_filename(filename):
    """Normaliza o nome de arquivos removendo caracteres especiais e emojis"""
    filename = re.sub(r'\s+', ' ', filename.strip())

    def remove_special_chars(value):
        value = unicodedata.normalize('NFKD', value)
        value = value.encode('ascii', 'ignore').decode('ascii')
        return str(value)

    sanitized_name = remove_special_chars(filename)
    sanitized_filename = sanitize_filename(sanitized_name)

    name, ext = os.path.splitext(sanitized_filename)
    MAX_FILENAME_LENGTH = 255
    if len(name) > MAX_FILENAME_LENGTH - len(ext):
        name = name[:MAX_FILENAME_LENGTH - len(ext)]

    ext = ext.lower()

    return f"{name}{ext}"

def detect_and_rename_file(file_path, logger):
    """Detecta o formato do vídeo usando ffprobe e renomeia o arquivo se necessário"""
    try:
        ffprobe_command = [
            ffprobe_path,
            '-v', 'error',
            '-select_streams', 'v:0',
            '-show_entries', 'format=format_name',
            '-of', 'default=noprint_wrappers=1:nokey=1',
            file_path
        ]
        result = subprocess.run(ffprobe_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        format_detected = result.stdout.strip().decode('utf-8')

        format_extension_map = {
            'mov,mp4,m4a,3gp,3g2,mj2': '.mp4',
            'matroska,webm': '.mkv',
            'flv': '.flv',
            'avi': '.avi',
            'mpeg': '.mpg',
        }

        file_extension = next((format_extension_map[fmt] for fmt in format_detected.split(',') if fmt in format_extension_map), '.mp4')
        new_file_path = file_path + file_extension
        os.rename(file_path, new_file_path)
        logger.info(f"Arquivo renomeado para incluir extensão: {file_extension}")
        return new_file_path

    except Exception as e:
        logger.error(f"Erro ao detectar formato: {str(e)}. Usando '.mp4' como padrão.")
        file_extension = '.mp4'
        new_file_path = file_path + file_extension
        os.rename(file_path, new_file_path)
        return new_file_path

def get_video_info(video_path, logger):
    """Obtém informações do vídeo utilizando ffprobe"""
    try:
        command = [
            ffprobe_path,
            "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=width,height,bit_rate,r_frame_rate,codec_name",
            "-show_entries", "format=duration,format_name",
            "-of", "json",
            video_path
        ]
        result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
        video_data = json.loads(result.stdout)
        video_info = video_data.get("streams", [{}])[0]
        format_info = video_data.get("format", {})

        width = video_info.get("width", 0)
        height = video_info.get("height", 0)
        bit_rate = int(video_info.get("bit_rate", 0))
        duration = float(format_info.get("duration", 0))
        r_frame_rate = video_info.get("r_frame_rate", "30/1")
        codec_name = video_info.get("codec_name", "unknown")
        format_name = format_info.get("format_name", "unknown")

        file_size = os.path.getsize(video_path)
        if bit_rate == 0 and duration > 0:
            bit_rate = int((file_size * 8) / duration)
            logger.warning(f"Bitrate do vídeo não encontrado. Bitrate estimado: {bit_rate} bps")

        command_audio = [
            ffprobe_path,
            "-v", "error",
            "-select_streams", "a:0",
            "-show_entries", "stream=bit_rate,codec_name",
            "-of", "json",
            video_path
        ]
        result_audio = subprocess.run(command_audio, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
        audio_info = json.loads(result_audio.stdout).get("streams", [{}])[0]
        audio_bit_rate = int(audio_info.get("bit_rate", 0))
        audio_codec_name = audio_info.get("codec_name", "unknown")

        if audio_bit_rate == 0:
            audio_bit_rate = 128000  # Bitrate padrão de áudio estimado

        unsupported_video_formats = ['matroska,webm', 'flv', 'avi', 'mpeg', '3gp', '3g2', 'ogg']
        unsupported_video_codecs = ['vp8', 'vp9', 'hevc', 'h265', 'av1']
        unsupported_audio_codecs = ['opus', 'vorbis']

        needs_transcoding = (
            format_name in unsupported_video_formats or 
            codec_name in unsupported_video_codecs or 
            audio_info["codec_name"] in unsupported_audio_codecs
        )

        return {
            "width": width,
            "height": height,
            "bit_rate": bit_rate,
            "duration": duration,
            "r_frame_rate": r_frame_rate,
            "codec_name": codec_name,
            "format_name": format_name,
            "needs_transcoding": needs_transcoding
        }, {
            "bit_rate": audio_bit_rate,
            "codec_name": audio_codec_name
        }

    except Exception as e:
        logger.error(f"Erro ao obter informações do vídeo: {str(e)}")
        raise

# Resto do código permanece o mesmo...

def transcode_video(video_path, output_dir, video_info, audio_info, logger, codec="h264_nvenc", target_resolution=720, use_nvenc=True, audio_codec="aac", hw_accel="cuda"):
    """Transcodifica o vídeo utilizando NVENC ou outro codec conforme necessário"""
    try:
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

        width = video_info["width"]
        height = video_info["height"]
        video_bit_rate = int(video_info["bit_rate"])
        audio_bit_rate = int(audio_info["bit_rate"]) // 1000
        frame_rate = eval(video_info["r_frame_rate"])

        # Resolução de saída parametrizada
        target_height = target_resolution if height > target_resolution else height
        target_width = int((width / height) * target_height)
        scale_filter = f"scale={target_width}:{target_height}"

        output_file = os.path.join(output_dir, os.path.splitext(os.path.basename(video_path))[0] + "_resized_transcoded.mp4")

        # Usando NVENC ou outro codec de vídeo conforme o parâmetro
        video_codec = codec if use_nvenc else "libx264"

        transcode_command = [
            ffmpeg_path,
            "-y",
            "-hwaccel", hw_accel,  # Aceleração por hardware parametrizada
            "-i", video_path,
            "-c:v", video_codec,  # Codec de vídeo parametrizado
            "-b:v", f"{video_bit_rate}",
            "-vf", scale_filter,
            "-r", str(frame_rate),
            "-c:a", audio_codec,  # Codec de áudio parametrizado
            "-b:a", f"{audio_bit_rate}k",
            "-ar", "44100",
            output_file
        ]

        subprocess.run(transcode_command, check=True)
        logger.info(f"Transcoding completed successfully using {video_codec}. Output file: {output_file}")
        return output_file

    except subprocess.CalledProcessError as e:
        logger.error(f"Error during transcoding: {e.stderr}")
        raise


def split_video(video_path, segment_duration, output_dir, logger, codec="h264_nvenc", use_nvenc=True, audio_codec="aac", hw_accel="cuda"):
    """Divide o vídeo em segmentos menores utilizando NVENC ou outro codec conforme necessário"""
    try:
        video_info = get_video_info(video_path, logger)[0]
        duration = float(video_info['duration'])
        frame_rate = eval(video_info["r_frame_rate"])
        video_bit_rate = int(video_info["bit_rate"])

        num_segments = int(duration // segment_duration)
        segment_files = []

        for i in range(num_segments):
            start_time = i * segment_duration
            output_segment = os.path.join(output_dir, f"segment_{i+1}.mp4")

            # Usando NVENC ou outro codec de vídeo conforme o parâmetro
            video_codec = codec if use_nvenc else "libx264"

            split_command = [
                ffmpeg_path,
                "-y",
                "-hwaccel", hw_accel,  # Aceleração por hardware parametrizada
                "-i", video_path,
                "-ss", str(start_time),
                "-t", str(segment_duration),
                "-c:v", video_codec,  # Codec de vídeo parametrizado
                "-b:v", f"{video_bit_rate}",
                "-r", str(frame_rate),
                "-c:a", audio_codec,  # Codec de áudio parametrizado
                "-b:a", "128k",
                output_segment
            ]
            subprocess.run(split_command, check=True)
            segment_files.append(output_segment)

        logger.info(f"Splitting completed using {video_codec}. Segments: {segment_files}")
        return segment_files

    except subprocess.CalledProcessError as e:
        logger.error(f"Error during splitting: {e.stderr}")
        raise

def worker_task(url, id_request, id_user):
    """Função principal que gerencia o download e processamento de vídeo"""
    base_dir = os.path.join('downloads', id_user, id_request)
    os.makedirs(base_dir, exist_ok=True)

    log_filename = f"{id_user}_{id_request}.log"
    task_logger, log_filename = configure_individual_logging(id_request, id_user)
    task_logger.info(f"Task started for URL: {url}")

    video_file_path = os.path.join(base_dir, 'video')

    try:
        parsed_url = urllib.parse.urlparse(url)
        if not parsed_url.scheme:
            url = 'https://' + url
            task_logger.warning(f"URL missing scheme, adjusted to: {url}")

        url = urllib.parse.unquote(url)
        task_logger.info(f"Final adjusted URL: {url}")

    except Exception as e:
        error_message = f"Failed to adjust URL: {url} with error: {str(e)}"
        task_logger.error(error_message)
        update_task_status(id_request, id_user, 'FAILED', error_message)
        return {"message": "Failed to process video.", "error": error_message}

    yt_dlp_command = [
        'yt-dlp',
        '-f', 'bestvideo[height<=720]+bestaudio/best',
        '-o', video_file_path,
        url
    ]

    try:
        update_task_status(id_request, id_user, 'STARTED')
        result = subprocess.run(yt_dlp_command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        task_logger.info(f"Video download completed for request {id_request} by user {id_user}")
    except subprocess.CalledProcessError as e:
        error_message = f"Failed to download video from URL: {url} with error: {e.stderr}"
        task_logger.error(error_message)
        update_task_status(id_request, id_user, 'FAILED', error_message)
        return {"message": "Failed to process video.", "error": str(e)}

    download_extension = None
    for ext in ['.mp4', '.webm', '.mkv', '.flv', '.avi']:
        possible_file_path = video_file_path + ext
        if os.path.exists(possible_file_path):
            download_extension = ext
            video_file_path = possible_file_path
            break

    if not download_extension:
        task_logger.warning(f"File extension not detected for downloaded video, attempting to rename.")
        video_file_path = detect_and_rename_file(video_file_path, task_logger)

    normalized_video_path = os.path.join(os.path.dirname(video_file_path), normalize_filename(os.path.basename(video_file_path)))
    os.rename(video_file_path, normalized_video_path)

    video_info, audio_info = get_video_info(normalized_video_path, task_logger)
    final_video_path = transcode_video(normalized_video_path, base_dir, video_info, audio_info, task_logger)

    if os.path.getsize(final_video_path) > 31 * 1024 * 1024:
        segment_duration = int(video_info["duration"] // (os.path.getsize(final_video_path) / (31 * 1024 * 1024)))
        final_videos = split_video(final_video_path, segment_duration, base_dir, task_logger)
    else:
        final_videos = [final_video_path]

    response_data = {
        "message": "Download, transcode, resize and split successful",
        "number_of_videos": len(final_videos),
        "video_paths": final_videos,
        "log_file": log_filename
    }
    update_task_status(id_request, id_user, 'COMPLETED')
    return response_data


@app.route('/download', methods=['POST'])
def download_video():
    try:
        data = request.get_json()
        url = data.get('url')
        id_request = data.get('id_request')
        id_user = data.get('id_user')
        result = worker_task(url, id_request, id_user)
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": f"An error occurred: {str(e)}"}), 500

# Rota para visualizar logs individuais
@app.route('/logs/<log_filename>', methods=['GET'])
def view_log(log_filename):
    log_directory = os.path.join(app.root_path, 'logs')
    try:
        return send_from_directory(log_directory, log_filename, as_attachment=False)
    except Exception as e:
        return jsonify({"error": f"Could not find log file: {log_filename}. Error: {str(e)}"}), 404

# Rota para visualizar status dos workers (threads ativas)
@app.route('/workers_status', methods=['GET'])
def workers_status():
    active_threads = threading.active_count()
    return jsonify({"active_threads": active_threads, "max_workers": MAX_WORKERS})

# Rota para visualizar as tarefas no banco de dados
@app.route('/tasks', methods=['GET'])
def view_tasks():
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute('SELECT id, id_request, id_user, status, error_message FROM tasks ORDER BY id DESC')
    tasks = cursor.fetchall()
    conn.close()
    return render_template('tasks.html', tasks=tasks)

# Rota para servir os arquivos e diretórios da pasta downloads
@app.route('/downloads/', defaults={'subpath': ''})
@app.route('/downloads/<path:subpath>')
def serve_downloads(subpath):
    """Serve arquivos da pasta downloads ou lista o conteúdo de diretórios."""
    directory = os.path.join('downloads', subpath)

    if os.path.isdir(directory):
        # Se for um diretório, listar o conteúdo
        files = os.listdir(directory)
        html_content = f"<h2>Navegando: /downloads/{subpath}</h2><ul>"
        for file_name in files:
            file_path = os.path.join(subpath, file_name)
            if os.path.isdir(os.path.join(directory, file_name)):
                html_content += f'<li><a href="/downloads/{file_path}/">{file_name}/</a></li>'
            else:
                html_content += f'<li><a href="/downloads/{file_path}">{file_name}</a></li>'
        html_content += "</ul>"
        return render_template_string(html_content)
    elif os.path.isfile(directory):
        # Se for um arquivo, retornar o arquivo
        return send_from_directory('downloads', subpath)
    else:
        return jsonify({"error": "Caminho não encontrado"}), 404

# Inicializa o servidor
if __name__ == '__main__':
    init_db()
    # Expondo o serviço na rede local e no host 0.0.0.0 para permitir o acesso externo
    app.run(debug=True, host='0.0.0.0', port=5008)