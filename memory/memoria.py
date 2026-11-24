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
        conexao.execute("""
            CREATE TABLE IF NOT EXISTS mensagens (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                papel TEXT NOT NULL,
                texto TEXT NOT NULL,
                data_criacao DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conexao.execute("""
            CREATE TABLE IF NOT EXISTS interacoes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pergunta TEXT NOT NULL,
                pergunta_normalizada TEXT NOT NULL,
                chave TEXT NOT NULL,
                resposta TEXT NOT NULL,
                origem TEXT NOT NULL,
                modelo TEXT,
                reutilizavel INTEGER NOT NULL DEFAULT 0,
                ativo INTEGER NOT NULL DEFAULT 1,
                cache_de_id INTEGER,
                pensamento TEXT,
                memorias_novas TEXT,
                tokens_entrada INTEGER,
                tokens_saida INTEGER,
                tempo_ms INTEGER,
                data_criacao DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conexao.execute(
            "CREATE INDEX IF NOT EXISTS idx_interacoes_chave ON interacoes (chave)"
        )


CAMPOS_INTERACAO = (
    "pergunta", "pergunta_normalizada", "chave", "resposta", "origem", "modelo",
    "reutilizavel", "cache_de_id", "pensamento", "memorias_novas",
    "tokens_entrada", "tokens_saida", "tempo_ms",
)


def registrar_interacao(**dados):
    campos = [campo for campo in CAMPOS_INTERACAO if campo in dados]
    with conectar() as conexao:
        cursor = conexao.execute(
            f"INSERT INTO interacoes ({', '.join(campos)}) "
            f"VALUES ({', '.join('?' * len(campos))})",
            [dados[campo] for campo in campos]
        )
        return cursor.lastrowid


def buscar_por_chave(chave):
    with conectar() as conexao:
        return conexao.execute(
            """
            SELECT id, resposta
            FROM interacoes
            WHERE chave = ? AND origem = 'ia' AND reutilizavel = 1 AND ativo = 1
            ORDER BY id DESC
            LIMIT 1
            """,
            (chave,)
        ).fetchone()


def desativar_interacao(id_interacao):
    with conectar() as conexao:
        cursor = conexao.execute(
            "UPDATE interacoes SET ativo = 0 WHERE id = ?", (id_interacao,)
        )
        return cursor.rowcount > 0


def estatisticas():
    with conectar() as conexao:
        return conexao.execute(
            """
            SELECT origem, COUNT(*), AVG(tempo_ms),
                   COALESCE(SUM(tokens_entrada), 0), COALESCE(SUM(tokens_saida), 0)
            FROM interacoes
            GROUP BY origem
            ORDER BY origem
            """
        ).fetchall()


def guardar(categoria, informacao):
    with conectar() as conexao:
        existe = conexao.execute(
            "SELECT 1 FROM memorias WHERE lower(informacao) = lower(?)",
            (informacao,)
        ).fetchone()
        if existe:
            return False
        conexao.execute(
            "INSERT INTO memorias (categoria, informacao) VALUES (?, ?)",
            (categoria, informacao)
        )
        return True


def consultar():
    with conectar() as conexao:
        return conexao.execute(
            "SELECT categoria, informacao FROM memorias ORDER BY id"
        ).fetchall()


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


def guardar_mensagem(papel, texto):
    with conectar() as conexao:
        conexao.execute(
            "INSERT INTO mensagens (papel, texto) VALUES (?, ?)",
            (papel, texto)
        )


def ultimas_mensagens(quantidade):
    with conectar() as conexao:
        linhas = conexao.execute(
            "SELECT papel, texto FROM mensagens ORDER BY id DESC LIMIT ?",
            (quantidade,)
        ).fetchall()
    linhas.reverse()
    while linhas and linhas[0][0] != "usuario":
        linhas.pop(0)
    return linhas


if __name__ == "__main__":
    iniciar_memoria()
    guardar("identidade", "Meu nome é NEXO.")
    guardar("projeto", "Estou sendo desenvolvido no Raspberry Pi.")
    print("Lembranças armazenadas:")
    for categoria, informacao in consultar():
        print(f"- [{categoria}] {informacao}")
