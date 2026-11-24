import re
import unicodedata
from datetime import datetime

from memory.memoria import buscar_por_chave

PALAVRAS_VAZIAS = {
    "o", "a", "os", "as", "um", "uma", "uns", "umas",
    "de", "do", "da", "dos", "das", "no", "na", "nos", "nas", "em",
    "pra", "para", "pro", "ao", "aos", "e", "eh",
    "me", "te", "ai", "ae", "ei", "oi", "ola", "nexo",
    "voce", "vc", "sabe", "diz", "diga", "fala", "falar", "explica", "explique",
    "favor", "porfavor", "ne", "entao", "agora",
}

DIAS = ["segunda-feira", "terça-feira", "quarta-feira", "quinta-feira", "sexta-feira", "sábado", "domingo"]
MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho",
         "agosto", "setembro", "outubro", "novembro", "dezembro"]

PERGUNTA_HORA = re.compile(
    r"(nexo )?(que horas sao|que horas e|que hora e|qual (e )?a hora|(me )?(diz|fala) (as|a) horas?)( agora)?"
)
PERGUNTA_DATA = re.compile(
    r"(nexo )?(que dia e hoje|qual (e )?a data( de hoje)?|que data e hoje|hoje e que dia|(me )?(diz|fala) a data)( de hoje)?"
)


def normalizar(texto):
    sem_acento = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    sem_pontuacao = re.sub(r"[^a-z0-9 ]", " ", sem_acento.lower())
    return " ".join(sem_pontuacao.split()).replace("por que", "porque")


def gerar_chave(normalizado):
    return " ".join(sorted({p for p in normalizado.split() if p not in PALAVRAS_VAZIAS}))


def resposta_local(normalizado):
    agora = datetime.now()
    if PERGUNTA_HORA.fullmatch(normalizado):
        return f"Agora são {agora:%H:%M}."
    if PERGUNTA_DATA.fullmatch(normalizado):
        return f"Hoje é {DIAS[agora.weekday()]}, {agora.day} de {MESES[agora.month - 1]} de {agora.year}."
    return None


def buscar_no_cache(chave):
    if not chave:
        return None
    return buscar_por_chave(chave)
