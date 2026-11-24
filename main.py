import os
from datetime import datetime

from core.conversa import conversar
from core.inteligencia import MODELOS
from memory.memoria import consultar, iniciar_memoria

NOME = "NEXO"


def iniciar():
    os.system("clear")
    iniciar_memoria()
    print("=" * 35)
    print(f"       {NOME} - SISTEMA ONLINE")
    print("=" * 35)
    print(f"Inicialização: {datetime.now():%d/%m/%Y %H:%M:%S}")
    print("Status: Funcionando")
    print(f"Memória: {len(consultar())} lembranças")
    print(f"Inteligência artificial: {MODELOS[0]} (+{len(MODELOS) - 1} reservas)")
    print("Sensores: Em preparação")
    print("=" * 35)
    conversar()


if __name__ == "__main__":
    iniciar()
