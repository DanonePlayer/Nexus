import os
from datetime import datetime

NOME = "NEXO"

def iniciar():
    os.system("clear")

    print("=" * 35)
    print(f"       {NOME} - SISTEMA ONLINE")
    print("=" * 35)

    print(f"Inicialização: {datetime.now()}")
    print("Status: Funcionando")
    print("Memória: Em preparação")
    print("Inteligência artificial: Em preparação")
    print("Sensores: Em preparação")

    print("=" * 35)
    print("Olá! Eu sou o NEXO.")
    print("Meu desenvolvimento começou!")

if __name__ == "__main__":
    iniciar()
