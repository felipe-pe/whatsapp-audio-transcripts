import subprocess
import sys

# Função para rodar comandos no shell
def run_command(command):
    result = subprocess.run(command, shell=True)
    if result.returncode != 0:
        sys.exit(f"Erro ao executar {command}")

# Função para verificar e instalar as dependências necessárias
def install_dependencies():
    print("Instalando dependências para Windows Intel x64...")

    # Instalar PyTorch para CPU (versão sem suporte CUDA)
    run_command("pip install torch==2.0.1+cpu torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu")
    
    # Instalar outras bibliotecas necessárias (Flask, pysrt, logging)
    run_command("pip install flask pysrt logging")

    print("Instalação das dependências concluída.")

if __name__ == "__main__":
    install_dependencies()
