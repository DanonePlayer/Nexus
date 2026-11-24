import sqlite3
from pathlib import Path

BANCO = Path(__file__).parent / "nexo.db"

def conectar():
    return sqlite3.connect(BANCO)

def iniciar_memoria():
    with conectar() as conexao:
        conexao.execute("""
            CREATE TABLE IF NOT EXISTS memorias (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                categoria TEXT NOT NULL,
                informacao TEXT NOT NULL,
                data_criacao DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

def guardar(categoria, informacao):
    with conectar() as conexao:
        conexao.execute(
            "INSERT INTO memorias (categoria, informacao) VALUES (?, ?)",
            (categoria, informacao)
        )

def consultar():
    with conectar() as conexao:
        return conexao.execute(
            "SELECT categoria, informacao FROM memorias ORDER BY id"
        ).fetchall()

if __name__ == "__main__":
    iniciar_memoria()
    guardar("identidade", "Meu nome é NEXO.")
    guardar("projeto", "Estou sendo desenvolvido no Raspberry Pi.")

    print("Lembranças armazenadas:")
    for categoria, informacao in consultar():
        print(f"- [{categoria}] {informacao}")
def pesquisar(palavra):
    with conectar() as conexao:
        return conexao.execute(
            """
            SELECT categoria, informacao
            FROM memorias
            WHERE informacao LIKE ?
            ORDER BY id
            """,
            (f"%{palavra}%",)
        ).fetchall()
