import re
import unicodedata

from memory.memoria import buscar_por_chave

PALAVRAS_VAZIAS = {
    "o", "a", "os", "as", "um", "uma", "uns", "umas",
    "de", "do", "da", "dos", "das", "no", "na", "nos", "nas", "em",
    "pra", "para", "pro", "ao", "aos", "e", "eh",
    "me", "te", "ai", "ae", "ei", "oi", "ola", "nexo",
    "voce", "vc", "sabe", "diz", "diga", "fala", "falar", "explica", "explique",
    "favor", "porfavor", "ne", "entao", "agora",
}


def normalizar(texto):
    sem_acento = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    sem_pontuacao = re.sub(r"[^a-z0-9 ]", " ", sem_acento.lower())
    return " ".join(sem_pontuacao.split()).replace("por que", "porque")


def gerar_chave(normalizado):
    return " ".join(sorted({p for p in normalizado.split() if p not in PALAVRAS_VAZIAS}))


def buscar_no_cache(chave):
    if not chave:
        return None
    return buscar_por_chave(chave)
