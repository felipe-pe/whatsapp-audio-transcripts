import os
import subprocess
import sys

# Função para rodar comandos de instalação
def run_command(command):
    result = subprocess.run(command, shell=True)
    if result.returncode != 0:
        sys.exit(f"Erro ao executar {command}")

def main():
    # Instalar CUDA Toolkit e cuDNN no ambiente virtual
    print("Instalando CUDA Toolkit e cuDNN...")
    run_command("conda install -c conda-forge cudatoolkit=11.8 cudnn=9.2.1.18 -y")

    # Instalar PyTorch com suporte a CUDA 11.8
    print("Instalando PyTorch com suporte a CUDA 11.8...")
    run_command("pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118")

    # Instalar Flask e pysrt via pip
    print("Instalando dependências Flask e pysrt...")
    run_command("pip install flask pysrt")

    # Verificar se o executável faster-whisper-xxl.exe está presente
    exe_path = os.path.join(os.getcwd(), 'faster-whisper-xxl.exe')
    if not os.path.exists(exe_path):
        print("Atenção: O arquivo 'faster-whisper-xxl.exe' não foi encontrado na pasta do projeto.")
        print("Por favor, coloque o 'faster-whisper-xxl.exe' na pasta raiz do projeto para garantir a funcionalidade.")

    print("Instalação concluída! Ambiente configurado corretamente.")

if __name__ == "__main__":
    main()
