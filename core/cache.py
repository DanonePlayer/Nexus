import logging
import re
import unicodedata

from memory.memoria import (
    ativar_palavra,
    atualizar_chave,
    bloquear_palavra,
    buscar_por_chave,
    interacoes_com_palavra,
    palavras_bloqueadas,
    palavras_vazias_aprendidas,
    perguntas_do_cache,
    respostas_do_cache,
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
SIMILARIDADE_MINIMA = 0.5
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


def _palavras_da_resposta(texto):
    return {p for p in normalizar(texto).split() if p not in PALAVRAS_VAZIAS} - {"senhor"}


def mesmo_sentido(resposta_a, resposta_b):
    """Compara duas respostas pelas palavras importantes em comum."""
    a, b = _palavras_da_resposta(resposta_a), _palavras_da_resposta(resposta_b)
    if not a or not b:
        return a == b
    return len(a & b) / len(a | b) >= SIMILARIDADE_MINIMA


def encontrar_colisao(palavra, respostas=None, aprendidas=None):
    """Simula ignorar a palavra no cache real. Se duas perguntas que hoje são
    diferentes passariam a ter a mesma chave com respostas de sentido diferente,
    a palavra muda o sentido: devolve o par de perguntas que provou isso."""
    respostas = respostas_do_cache() if respostas is None else respostas
    atuais = _palavras_aprendidas() if aprendidas is None else aprendidas
    com_palavra = atuais | {palavra}

    grupos = {}
    for pergunta, resposta in respostas:
        normalizado = normalizar(pergunta)
        grupos.setdefault(gerar_chave(normalizado, com_palavra), []).append(
            (gerar_chave(normalizado, atuais), pergunta, resposta, palavra in normalizado.split())
        )

    for itens in grupos.values():
        for chave_a, pergunta_a, resposta_a, tem_palavra in itens:
            if not tem_palavra:
                continue
            for chave_b, pergunta_b, resposta_b, _ in itens:
                if chave_a != chave_b and not mesmo_sentido(resposta_a, resposta_b):
                    return pergunta_a, pergunta_b
    return None


def desaprender(palavra):
    """Para de ignorar a palavra, bloqueia para sempre e refaz todas as chaves."""
    global _aprendidas
    palavra = normalizar(palavra)
    estava_ativa = bloquear_palavra(palavra, "bloqueada pelo dono")
    _aprendidas = palavras_vazias_aprendidas()
    if estava_ativa:
        refazer_todas_as_chaves()
    log.info("Palavra desaprendida e bloqueada: %s", palavra)
    return estava_ativa


def aprender_palavras(sugestoes, normalizado):
    """Registra os votos da IA (um por pergunta diferente). Quando uma palavra atinge
    os votos, passa pelo teste de colisão: se passar, é ativada e as chaves antigas
    são refeitas; se falhar, é bloqueada para sempre."""
    global _aprendidas
    aceitas = (
        filtrar_sugestoes(sugestoes, normalizado) - _palavras_aprendidas() - palavras_bloqueadas()
    )
    if not aceitas:
        return []

    candidatas = votar_palavras(aceitas, gerar_chave(normalizado), VOTOS_PARA_ATIVAR)
    ativadas = []
    for palavra in candidatas:
        colisao = encontrar_colisao(palavra)
        if colisao:
            motivo = f"colisão: '{colisao[0]}' x '{colisao[1]}'"
            bloquear_palavra(palavra, motivo)
            log.warning("Palavra '%s' bloqueada no teste de %s", palavra, motivo)
            continue
        ativar_palavra(palavra)
        ativadas.append(palavra)
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
