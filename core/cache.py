import logging
import re
import unicodedata

from memory.memoria import (
    atualizar_chave,
    buscar_por_chave,
    interacoes_com_palavra,
    palavras_vazias_aprendidas,
    perguntas_do_cache,
    votar_palavras,
)

log = logging.getLogger("nexo.cache")

# Palavras que nunca mudam o sentido da pergunta (lista fixa, escrita à mão).
PALAVRAS_VAZIAS = {
    "o", "a", "os", "as", "um", "uma", "uns", "umas",
    "de", "do", "da", "dos", "das", "no", "na", "nos", "nas", "em",
    "pra", "para", "pro", "ao", "aos", "e", "eh",
    "me", "te", "ai", "ae", "ei", "oi", "ola", "nexo",
    "voce", "vc", "sabe", "diz", "diga", "fala", "falar", "explica", "explique",
    "favor", "porfavor", "ne", "entao", "agora",
}

# Palavras que mudam o sentido: a IA pode sugerir, mas nunca viram palavra vazia.
# Ex.: "é verdade" e "não é verdade" não podem ter a mesma chave.
PALAVRAS_PROTEGIDAS = {
    "nao", "nunca", "nem", "sem", "com", "sim", "jamais", "nenhum", "nenhuma",
    "mais", "menos", "maior", "menor", "melhor", "pior", "muito", "pouco",
    "maximo", "minimo", "primeiro", "primeira", "ultimo", "ultima", "so", "apenas", "todo", "todos",
    "antes", "depois", "ontem", "hoje", "amanha", "anteontem", "cedo", "tarde", "noite",
    "quem", "onde", "quando", "como", "porque", "quanto", "quantos", "quanta", "quantas",
    "qual", "quais", "que", "certo", "errado", "verdade", "mentira",
    "entre", "contra", "sobre", "sob", "dentro", "fora", "acima", "abaixo",
    "eu", "meu", "minha", "meus", "minhas", "ele", "ela", "eles", "elas", "seu", "sua",
}

# Abreviações de digitação viram a palavra inteira antes de montar a chave.
# "pq o ceu e azul" e "por que o céu é azul" passam a ser a mesma pergunta.
ABREVIACOES = {
    "pq": "porque", "pqe": "porque", "q": "que", "oq": "o que", "n": "nao",
    "vc": "voce", "vcs": "voces", "tb": "tambem", "tbm": "tambem", "hj": "hoje",
    "td": "tudo", "tds": "todos", "msm": "mesmo", "mt": "muito", "mto": "muito",
    "qnd": "quando", "qdo": "quando", "qto": "quanto", "qnto": "quanto", "qnta": "quanta",
    "qtos": "quantos", "qts": "quantos", "qntos": "quantos", "qnts": "quantos", "qntas": "quantas",
    "cmg": "comigo", "ctz": "certeza", "blz": "beleza", "obg": "obrigado", "vlw": "valeu",
    "kg": "quilo", "kgs": "quilos", "km": "quilometro", "kms": "quilometros",
    "cm": "centimetro", "mm": "milimetro", "ml": "mililitro", "seg": "segundo",
}

VOTOS_PARA_ATIVAR = 3
TAMANHO_MAXIMO_PALAVRA = 20

_aprendidas = None


def _palavras_aprendidas():
    global _aprendidas
    if _aprendidas is None:
        _aprendidas = palavras_vazias_aprendidas()
    return _aprendidas


def normalizar(texto):
    sem_acento = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    sem_pontuacao = re.sub(r"[^a-z0-9 ]", " ", sem_acento.lower())
    palavras = [ABREVIACOES.get(palavra, palavra) for palavra in sem_pontuacao.split()]
    return " ".join(palavras).replace("por que", "porque")


def refazer_todas_as_chaves():
    """Recalcula a chave de todas as respostas do cache a partir da pergunta original.
    Usar quando a normalização mudar (ex.: abreviações novas)."""
    refeitas = 0
    for id_interacao, pergunta in perguntas_do_cache():
        normalizado = normalizar(pergunta)
        atualizar_chave(id_interacao, gerar_chave(normalizado), normalizado)
        refeitas += 1
    return refeitas


def gerar_chave(normalizado, aprendidas=None):
    ignorar = PALAVRAS_VAZIAS | (_palavras_aprendidas() if aprendidas is None else aprendidas)
    return " ".join(sorted({p for p in normalizado.split() if p not in ignorar}))


def buscar_no_cache(chave):
    if not chave:
        return None
    return buscar_por_chave(chave)


def filtrar_sugestoes(sugestoes, normalizado):
    """Só aceita palavras que estão de fato na pergunta, são palavras simples
    e não estão protegidas nem já ignoradas."""
    da_pergunta = set(normalizado.split())
    aceitas = set()
    for sugestao in sugestoes:
        palavra = normalizar(sugestao)
        if (
            palavra in da_pergunta
            and palavra.isalpha()
            and 2 <= len(palavra) <= TAMANHO_MAXIMO_PALAVRA
            and palavra not in PALAVRAS_PROTEGIDAS
            and palavra not in PALAVRAS_VAZIAS
        ):
            aceitas.add(palavra)
    # Se a IA mandar ignorar quase tudo, desconfia e não vota em nada.
    if len(aceitas) > len(da_pergunta) // 2:
        return set()
    return aceitas


def aprender_palavras(sugestoes, normalizado):
    """Registra os votos da IA. Quando uma palavra atinge os votos necessários,
    passa a ser ignorada e as chaves antigas que a continham são refeitas."""
    global _aprendidas
    aceitas = filtrar_sugestoes(sugestoes, normalizado) - _palavras_aprendidas()
    if not aceitas:
        return []

    ativadas = votar_palavras(aceitas, VOTOS_PARA_ATIVAR)
    if not ativadas:
        return []

    _aprendidas = palavras_vazias_aprendidas()
    for palavra in ativadas:
        refeitas = 0
        for id_interacao, pergunta_normalizada in interacoes_com_palavra(palavra):
            atualizar_chave(id_interacao, gerar_chave(pergunta_normalizada))
            refeitas += 1
        log.info("Palavra vazia aprendida: %s (%d chaves refeitas)", palavra, refeitas)
    return ativadas
