"""Pré-carrega o cache do NEXO com perguntas de uma lista.

Cada pergunta passa pelo mesmo caminho da conversa (local -> banco -> IA),
mas sem histórico, sem gravar na conversa e sem criar lembranças.

Uso:  python scripts/carregar_base.py [arquivo]   (padrão: data/perguntas_base.txt)
"""
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from core.cache import aprender_palavras, buscar_no_cache, gerar_chave, normalizar  # noqa: E402
from core.conversa import EMOCOES_NAO_REUTILIZAVEIS  # noqa: E402
from core.inteligencia import IaIndisponivel, responder  # noqa: E402
from core.respostas_locais import resposta_local  # noqa: E402
from memory.memoria import consultar, iniciar_memoria, registrar_interacao  # noqa: E402

PAUSA_ENTRE_CHAMADAS = 5
FALHAS_SEGUIDAS_PARA_PARAR = 5


def ler_perguntas(arquivo):
    linhas = Path(arquivo).read_text(encoding="utf-8").splitlines()
    return [linha.strip() for linha in linhas if linha.strip() and not linha.startswith("#")]


def carregar(arquivo):
    iniciar_memoria()
    perguntas = ler_perguntas(arquivo)
    contagem = {"local": 0, "banco": 0, "guardada": 0, "nao_reutilizavel": 0, "falha": 0}
    falhas_seguidas = 0

    for numero, pergunta in enumerate(perguntas, 1):
        prefixo = f"[{numero}/{len(perguntas)}] {pergunta}"
        normalizado = normalizar(pergunta)
        chave = gerar_chave(normalizado)

        if resposta_local(pergunta, normalizado):
            contagem["local"] += 1
            print(f"{prefixo} -> resposta local, pulando", flush=True)
            continue
        if buscar_no_cache(chave):
            contagem["banco"] += 1
            print(f"{prefixo} -> já está no banco", flush=True)
            continue

        inicio = time.monotonic()
        try:
            resultado = responder(pergunta, [], consultar())
        except IaIndisponivel as erro:
            contagem["falha"] += 1
            falhas_seguidas += 1
            print(f"{prefixo} -> FALHOU ({str(erro)[:80]})", flush=True)
            if falhas_seguidas >= FALHAS_SEGUIDAS_PARA_PARAR:
                print("Muitas falhas seguidas (cota ou Google fora). Parando; rode de novo depois.")
                break
            time.sleep(PAUSA_ENTRE_CHAMADAS * 2)
            continue
        falhas_seguidas = 0

        reutilizavel = (
            resultado["reutilizavel"] and resultado["emocao"] not in EMOCOES_NAO_REUTILIZAVEIS
        )
        registrar_interacao(
            pergunta=pergunta, pergunta_normalizada=normalizado, chave=chave,
            resposta=resultado["resposta"], origem="ia", modelo=resultado["modelo"],
            reutilizavel=int(reutilizavel), emocao=resultado["emocao"],
            pensamento=resultado["pensamento"],
            tokens_entrada=resultado["tokens_entrada"], tokens_saida=resultado["tokens_saida"],
            tempo_ms=int((time.monotonic() - inicio) * 1000),
        )
        aprender_palavras(resultado["palavras_irrelevantes"], normalizado)

        contagem["guardada" if reutilizavel else "nao_reutilizavel"] += 1
        marca = "guardada" if reutilizavel else "não reutilizável"
        print(f"{prefixo} -> {marca}: {resultado['resposta'][:70]}", flush=True)
        time.sleep(PAUSA_ENTRE_CHAMADAS)

    print(
        f"\nFim. Guardadas no cache: {contagem['guardada']} | não reutilizáveis: "
        f"{contagem['nao_reutilizavel']} | já no banco: {contagem['banco']} | "
        f"locais: {contagem['local']} | falhas: {contagem['falha']}"
    )


if __name__ == "__main__":
    carregar(sys.argv[1] if len(sys.argv) > 1 else RAIZ / "data" / "perguntas_base.txt")
