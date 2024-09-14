import os
import time

LOCK_FILE = os.path.join(os.getcwd(), "gpu_lock.lock")  # Caminho relativo

def acquire_lock():
    """Função para adquirir o lock criando um arquivo."""
    while os.path.exists(LOCK_FILE):
        print("GPU está em uso. Aguardando...")
        time.sleep(1)  # Espera 1 segundo antes de tentar novamente
    
    # Cria o arquivo de lock
    open(LOCK_FILE, 'w').close()
    print("Lock adquirido, usando GPU...")

def release_lock():
    """Função para liberar o lock removendo o arquivo."""
    if os.path.exists(LOCK_FILE):
        os.remove(LOCK_FILE)
        print("Lock liberado, GPU disponível.")
