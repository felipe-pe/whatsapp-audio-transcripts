import os
import subprocess
import sys
import urllib.request
import shutil
import platform

# URL para baixar o instalador do 7-Zip
SEVEN_ZIP_URL = "https://www.7-zip.org/a/7z2301-x64.exe"  # Atualize conforme a versão mais recente

# Função para rodar comandos no shell
def run_command(command):
    result = subprocess.run(command, shell=True)
    if result.returncode != 0:
        sys.exit(f"Erro ao executar {command}")

# Função para verificar e instalar o 7-Zip no Windows
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

# Função para verificar se o CUDA Toolkit e cuDNN já estão instalados
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

# Função para baixar o Whisper para Windows
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

# Função para descompactar o arquivo .7z usando 7z.exe no Windows
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

# Função para mover os arquivos do Whisper para o local correto
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

    # Verifica se a pasta _xxl_data existe e a move
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

# Função para limpar arquivos temporários
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

# Função para instalar dependências adicionais (Flask, pysrt, etc.)
def install_additional_dependencies():
    print("Instalando dependências Flask, pysrt e logging...")
    run_command("pip install flask pysrt logging")

# Função para detectar sistema operacional e arquitetura
def detect_system():
    system = platform.system()
    architecture = platform.machine()

    if system == "Windows":
        os_type = "windows"
    elif system == "Linux":
        os_type = "linux"
    elif system == "Darwin":
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

# Função para instalar dependências para GPUs Nvidia no Windows
def install_gpu_dependencies():
    print("Instalando dependências para Windows com GPU Nvidia...")

    # Verificar e instalar CUDA Toolkit e cuDNN
    if not check_cuda_and_cudnn():
        print("Instalando CUDA Toolkit e cuDNN...")
        run_command("conda install -c conda-forge cudatoolkit=11.8 cudnn=9.2.1.18 -y")

    # Instalar PyTorch com suporte a CUDA 11.8
    print("Instalando PyTorch com suporte a CUDA 11.8...")
    run_command("pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118")

    # Instalar dependências adicionais
    install_additional_dependencies()

# Função para instalar dependências para CPUs
def install_cpu_dependencies(os_type, arch_type):
    print(f"Instalando dependências para {os_type} com arquitetura {arch_type}...")

    # Instalar PyTorch para CPU
    run_command(f"pip install torch==2.0.1+cpu torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu")

    # Instalar dependências adicionais
    install_additional_dependencies()

# Função principal para configurar o ambiente
def main():
    os_type, arch_type = detect_system()

    # Se for Windows com GPU Nvidia, seguir com instalação de GPU
    if os_type == "windows" and check_cuda_and_cudnn():
        install_gpu_dependencies()
    else:
        # Se não houver GPU ou for outro sistema, seguir com instalação de CPU
        install_cpu_dependencies(os_type, arch_type)

    # Baixar e configurar o Whisper se necessário
    if os_type == "windows":
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
