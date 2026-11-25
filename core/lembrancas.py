"""Escolhe quais lembranças vão junto para a IA.

Com poucas lembranças, vão todas. Quando passarem do limite, vão:
1. as essenciais (categoria 'identidade' ou 'essencial'), sempre;
2. as que têm palavras em comum com a conversa, das mais parecidas para as menos;
3. as mais recentes, até completar o limite.
"""
from core.cache import PALAVRAS_VAZIAS, normalizar
from memory.memoria import consultar_com_id

LIMITE_MEMORIAS = 25
CATEGORIAS_ESSENCIAIS = {"identidade", "essencial"}
TAMANHO_MINIMO_RADICAL = 4


def _palavras(texto):
    return {p for p in normalizar(texto).split() if p not in PALAVRAS_VAZIAS and len(p) >= 3}


def _parecidas(a, b):
    """'moto' e 'motocicletas' contam como a mesma palavra."""
    if a == b:
        return True
    curta, longa = sorted((a, b), key=len)
    return len(curta) >= TAMANHO_MINIMO_RADICAL and longa.startswith(curta)


def _pontuacao(palavras_memoria, palavras_conversa):
    return sum(
        1 for palavra in palavras_memoria
        if any(_parecidas(palavra, outra) for outra in palavras_conversa)
    )


def selecionar_memorias(textos_da_conversa, limite=LIMITE_MEMORIAS, todas=None):
    """Recebe a mensagem atual e as últimas falas; devolve [(categoria, informacao)]."""
    todas = consultar_com_id() if todas is None else todas
    if len(todas) <= limite:
        return [(categoria, informacao) for _, categoria, informacao in todas]

    palavras_conversa = set().union(*(_palavras(texto) for texto in textos_da_conversa))
    escolhidas = {id_ for id_, categoria, _ in todas if categoria in CATEGORIAS_ESSENCIAIS}

    relevantes = sorted(
        ((pontos, id_) for id_, _, informacao in todas
         if id_ not in escolhidas
         and (pontos := _pontuacao(_palavras(informacao), palavras_conversa)) > 0),
        reverse=True,
    )
    for _, id_ in relevantes:
        if len(escolhidas) >= limite:
            break
        escolhidas.add(id_)

    for id_, _, _ in reversed(todas):
        if len(escolhidas) >= limite:
            break
        escolhidas.add(id_)

    return [(categoria, informacao) for id_, categoria, informacao in todas if id_ in escolhidas]
