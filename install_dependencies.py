import os
import subprocess
import sys
import urllib.request
import shutil

# URL para baixar o instalador do 7-Zip caso ele não esteja disponível
SEVEN_ZIP_URL = "https://www.7-zip.org/a/7z2301-x64.exe"  # Atualize conforme a versão mais recente

# Função para rodar comandos de instalação
def run_command(command):
    result = subprocess.run(command, shell=True)
    if result.returncode != 0:
        sys.exit(f"Erro ao executar {command}")

# Função para verificar e instalar o 7-Zip
def ensure_7zip_installed():
    seven_zip_path = os.path.join("C:\\Program Files\\7-Zip", "7z.exe")
    
    if not os.path.exists(seven_zip_path):
        print("7-Zip não encontrado. Baixando e instalando 7-Zip...")
        installer_path = os.path.join(os.getcwd(), '7z_installer.exe')
        
        try:
            urllib.request.urlretrieve(SEVEN_ZIP_URL, installer_path)
            print(f"Baixando 7-Zip de {SEVEN_ZIP_URL}...")
            
            # Executando o instalador do 7-Zip
            run_command(f'{installer_path} /S')  # /S faz uma instalação silenciosa
            
            print("7-Zip instalado com sucesso.")
        except Exception as e:
            sys.exit(f"Erro ao baixar ou instalar o 7-Zip: {e}")
        finally:
            if os.path.exists(installer_path):
                os.remove(installer_path)  # Remover o instalador após a instalação
    else:
        print("7-Zip já está instalado.")

# Função para garantir que o pip está atualizado
def ensure_pip_up_to_date():
    print("Verificando e atualizando o pip, se necessário...")
    run_command("python -m pip install --upgrade pip")

# Função para verificar se o CUDA Toolkit e o cuDNN já estão instalados
def check_cuda_and_cudnn():
    try:
        import torch
        if torch.cuda.is_available():
            print(f"CUDA disponível: {torch.version.cuda}")
            return True
        else:
            print("CUDA não está disponível.")
            return False
    except ImportError:
        print("PyTorch não está instalado.")
        return False

# Função para baixar o arquivo .7z
def download_faster_whisper():
    exe_url = "https://github.com/Purfview/whisper-standalone-win/releases/download/Faster-Whisper-XXL/Faster-Whisper-XXL_r192.3.4_windows.7z"
    exe_path = os.path.join(os.getcwd(), 'Faster-Whisper-XXL_r192.3.4_windows.7z')
    
    if not os.path.exists(exe_path):
        print(f"Baixando 'Faster-Whisper-XXL_r192.3.4_windows.7z' de {exe_url}...")
        try:
            urllib.request.urlretrieve(exe_url, exe_path)
            print(f"'Faster-Whisper-XXL_r192.3.4_windows.7z' baixado com sucesso.")
        except Exception as e:
            sys.exit(f"Erro ao baixar 'Faster-Whisper-XXL_r192.3.4_windows.7z': {e}")
    else:
        print("'Faster-Whisper-XXL_r192.3.4_windows.7z' já está presente no diretório.")

# Função para descompactar o arquivo .7z usando 7z.exe
def extract_faster_whisper_with_7z():
    ensure_7zip_installed()
    
    seven_z_path = os.path.join("C:\\Program Files\\7-Zip", "7z.exe")
    seven_z_file = os.path.join(os.getcwd(), 'Faster-Whisper-XXL_r192.3.4_windows.7z')
    extract_dir = os.path.join(os.getcwd(), 'Faster-Whisper-XXL_r192.3.4_windows')

    if not os.path.exists(extract_dir):
        print(f"Descompactando '{seven_z_file}' usando 7z.exe...")
        try:
            run_command(f'"{seven_z_path}" x "{seven_z_file}" -o"{extract_dir}"')
            print(f"Arquivo descompactado com sucesso em {extract_dir}")
        except Exception as e:
            sys.exit(f"Erro ao descompactar com 7z: {e}")
    else:
        print(f"Arquivos já descompactados em {extract_dir}.")

# Função para mover o conteúdo da pasta _xxl_data e os arquivos necessários
def move_faster_whisper_files():
    base_dir = os.path.join(os.getcwd(), 'Faster-Whisper-XXL_r192.3.4_windows', 'Faster-Whisper-XXL')
    exe_source = os.path.join(base_dir, 'faster-whisper-xxl.exe')
    xxl_data_source = os.path.join(base_dir, '_xxl_data')

    # Caminhos de destino no projeto
    exe_dest = os.path.join(os.getcwd(), 'faster-whisper-xxl.exe')
    xxl_data_dest = os.path.join(os.getcwd(), '_xxl_data')

    # Verifica se o executável faster-whisper-xxl.exe existe e o move
    if os.path.exists(exe_source):
        print(f"Movendo {exe_source} para {exe_dest}...")
        shutil.move(exe_source, exe_dest)
    else:
        print(f"'{exe_dest}' já está no local correto.")

    # Verifica se a pasta _xxl_data existe e, se não existir, a move
    if os.path.exists(xxl_data_source):
        if not os.path.exists(xxl_data_dest):
            print(f"Movendo {xxl_data_source} para {xxl_data_dest}...")
            shutil.move(xxl_data_source, xxl_data_dest)
        else:
            print(f"A pasta '_xxl_data' já existe na raiz do projeto.")
    else:
        print(f"Erro: A pasta '_xxl_data' não foi encontrada.")

    # Criar ou atualizar o arquivo .gitignore para excluir a pasta _xxl_data
    gitignore_path = os.path.join(os.getcwd(), '.gitignore')
    with open(gitignore_path, 'a') as gitignore:
        gitignore.write('\n/_xxl_data\n')
    print(f"Pasta '_xxl_data' adicionada ao .gitignore.")

# Função para limpar os arquivos temporários e pastas descompactadas
def clean_up():
    seven_z_path = os.path.join(os.getcwd(), 'Faster-Whisper-XXL_r192.3.4_windows.7z')
    extract_dir = os.path.join(os.getcwd(), 'Faster-Whisper-XXL_r192.3.4_windows')

    # Remover o arquivo .7z
    if os.path.exists(seven_z_path):
        print(f"Removendo o arquivo {seven_z_path}...")
        os.remove(seven_z_path)

    # Remover a pasta descompactada
    if os.path.exists(extract_dir):
        print(f"Removendo a pasta {extract_dir}...")
        shutil.rmtree(extract_dir)

def main():
    # Verificar e atualizar o pip
    ensure_pip_up_to_date()

    # Verificar se CUDA Toolkit e cuDNN já estão instalados
    if not check_cuda_and_cudnn():
        print("Instalando CUDA Toolkit e cuDNN...")
        run_command("conda install -c conda-forge cudatoolkit=11.8 cudnn=9.2.1.18 -y")
    else:
        print("CUDA Toolkit e cuDNN já estão instalados.")

    # Instalar PyTorch com suporte a CUDA 11.8
    print("Instalando PyTorch com suporte a CUDA 11.8...")
    run_command("pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118")

    # Instalar Flask e pysrt via pip
    print("Instalando dependências Flask e pysrt...")
    run_command("pip install flask pysrt")

    # Conferir se os arquivos e pastas já estão presentes antes de baixar e descompactar
    if not os.path.exists('faster-whisper-xxl.exe') or not os.path.exists('_xxl_data'):
        download_faster_whisper()
        extract_faster_whisper_with_7z()
        move_faster_whisper_files()
        clean_up()
    else:
        print("O arquivo 'faster-whisper-xxl.exe' e a pasta '_xxl_data' já estão no local correto.")

    print("Instalação concluída! Ambiente configurado corretamente.")

if __name__ == "__main__":
    main()
