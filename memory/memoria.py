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
        conexao.execute("""
            CREATE TABLE IF NOT EXISTS resumos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ate_mensagem_id INTEGER NOT NULL,
                texto TEXT NOT NULL,
                data_criacao DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        colunas = {linha[1] for linha in conexao.execute("PRAGMA table_info(interacoes)")}
        if "emocao" not in colunas:
            conexao.execute("ALTER TABLE interacoes ADD COLUMN emocao TEXT")
        # canal: 'conversa' (falando com o NEXO) ou 'carga' (pré-carga do cache)
        if "canal" not in colunas:
            conexao.execute(
                "ALTER TABLE interacoes ADD COLUMN canal TEXT NOT NULL DEFAULT 'conversa'"
            )
        # Índice parcial: só as respostas que podem sair do cache. A busca vai direto
        # na chave, não importa quantas interações o banco tenha.
        conexao.execute("""
            CREATE INDEX IF NOT EXISTS idx_interacoes_cache
            ON interacoes (chave, id)
            WHERE origem = 'ia' AND reutilizavel = 1 AND ativo = 1
        """)
        conexao.execute("""
            CREATE TABLE IF NOT EXISTS palavras_vazias (
                palavra TEXT PRIMARY KEY,
                votos INTEGER NOT NULL DEFAULT 0,
                ativa INTEGER NOT NULL DEFAULT 0,
                data_criacao DATETIME DEFAULT CURRENT_TIMESTAMP,
                data_ativacao DATETIME
            )
        """)
        conexao.execute("PRAGMA journal_mode=WAL")


CAMPOS_INTERACAO = (
    "pergunta", "pergunta_normalizada", "chave", "resposta", "origem", "modelo",
    "reutilizavel", "emocao", "canal", "cache_de_id", "pensamento", "memorias_novas",
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
            SELECT id, resposta, emocao
            FROM interacoes
            WHERE chave = ? AND origem = 'ia' AND reutilizavel = 1 AND ativo = 1
            ORDER BY id DESC
            LIMIT 1
            """,
            (chave,)
        ).fetchone()


def palavras_vazias_aprendidas():
    with conectar() as conexao:
        return {linha[0] for linha in conexao.execute(
            "SELECT palavra FROM palavras_vazias WHERE ativa = 1"
        )}


def votar_palavras(palavras, votos_para_ativar):
    """Soma um voto em cada palavra e devolve as que acabaram de ser ativadas."""
    with conectar() as conexao:
        conexao.executemany(
            """
            INSERT INTO palavras_vazias (palavra, votos) VALUES (?, 1)
            ON CONFLICT(palavra) DO UPDATE SET votos = votos + 1
            """,
            [(palavra,) for palavra in palavras]
        )
        marcador = ", ".join("?" * len(palavras))
        ativadas = [linha[0] for linha in conexao.execute(
            f"SELECT palavra FROM palavras_vazias "
            f"WHERE ativa = 0 AND votos >= ? AND palavra IN ({marcador})",
            [votos_para_ativar, *palavras]
        )]
        conexao.executemany(
            "UPDATE palavras_vazias SET ativa = 1, data_ativacao = CURRENT_TIMESTAMP WHERE palavra = ?",
            [(palavra,) for palavra in ativadas]
        )
    return ativadas


def palavras_vazias_resumo():
    with conectar() as conexao:
        return conexao.execute(
            "SELECT palavra, votos, ativa FROM palavras_vazias ORDER BY ativa DESC, votos DESC"
        ).fetchall()


def interacoes_com_palavra(palavra):
    """Respostas do cache cuja chave contém a palavra (para refazer a chave)."""
    with conectar() as conexao:
        return conexao.execute(
            """
            SELECT id, pergunta_normalizada
            FROM interacoes
            WHERE origem = 'ia' AND reutilizavel = 1 AND ativo = 1
              AND ' ' || chave || ' ' LIKE ?
            """,
            (f"% {palavra} %",)
        ).fetchall()


def atualizar_chave(id_interacao, chave, pergunta_normalizada=None):
    with conectar() as conexao:
        conexao.execute(
            "UPDATE interacoes SET chave = ?, "
            "pergunta_normalizada = COALESCE(?, pergunta_normalizada) WHERE id = ?",
            (chave, pergunta_normalizada, id_interacao)
        )


def perguntas_do_cache():
    with conectar() as conexao:
        return conexao.execute(
            "SELECT id, pergunta FROM interacoes "
            "WHERE origem = 'ia' AND reutilizavel = 1 AND ativo = 1"
        ).fetchall()


def consultar_com_id():
    with conectar() as conexao:
        return conexao.execute(
            "SELECT id, categoria, informacao FROM memorias ORDER BY id"
        ).fetchall()


def resumo_economia():
    with conectar() as conexao:
        total, sem_ia = conexao.execute(
            "SELECT COUNT(*), COALESCE(SUM(origem != 'ia'), 0) FROM interacoes "
            "WHERE canal = 'conversa'"
        ).fetchone()
    return total, sem_ia


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
            WHERE canal = 'conversa'
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


def apagar_memorias(trecho):
    """Apaga as lembranças que contêm o trecho, só se for exatamente uma.
    Devolve a lista do que foi encontrado, para quem chamou decidir o que dizer."""
    encontradas = pesquisar(trecho)
    if len(encontradas) == 1:
        with conectar() as conexao:
            conexao.execute(
                "DELETE FROM memorias WHERE informacao LIKE ?", (f"%{trecho}%",)
            )
    return encontradas


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


def ultimo_resumo():
    with conectar() as conexao:
        linha = conexao.execute(
            "SELECT ate_mensagem_id, texto FROM resumos ORDER BY id DESC LIMIT 1"
        ).fetchone()
    return linha or (0, None)


def mensagens_fora_do_historico(depois_do_id, tamanho_historico):
    """Mensagens depois do último resumo que já saíram do histórico recente."""
    with conectar() as conexao:
        return conexao.execute(
            """
            SELECT id, papel, texto
            FROM mensagens
            WHERE id > ?
              AND id <= (SELECT COALESCE(MAX(id), 0) FROM mensagens) - ?
            ORDER BY id
            """,
            (depois_do_id, tamanho_historico)
        ).fetchall()


def guardar_resumo(ate_mensagem_id, texto):
    with conectar() as conexao:
        conexao.execute(
            "INSERT INTO resumos (ate_mensagem_id, texto) VALUES (?, ?)",
            (ate_mensagem_id, texto)
        )


if __name__ == "__main__":
    iniciar_memoria()
    guardar("identidade", "Meu nome é NEXO.")
    guardar("projeto", "Estou sendo desenvolvido no Raspberry Pi.")
    print("Lembranças armazenadas:")
    for categoria, informacao in consultar():
        print(f"- [{categoria}] {informacao}")
