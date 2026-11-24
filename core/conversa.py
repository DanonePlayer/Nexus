import json
import logging
import time
from pathlib import Path

from core.cache import buscar_no_cache, gerar_chave, normalizar, resposta_local
from core.inteligencia import IaIndisponivel, responder
from memory.memoria import (
    consultar,
    desativar_interacao,
    estatisticas,
    guardar,
    guardar_mensagem,
    iniciar_memoria,
    registrar_interacao,
    ultimas_mensagens,
)

PASTA_LOGS = Path(__file__).resolve().parent.parent / "logs"
PASTA_LOGS.mkdir(exist_ok=True)

logging.basicConfig(
    filename=PASTA_LOGS / "nexo.log",
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger("nexo.conversa")

TAMANHO_HISTORICO = 20
COMANDOS_ESQUECER = {"esquece essa resposta", "esqueca essa resposta", "esquece isso", "esqueca isso"}


def _milissegundos(inicio):
    return int((time.monotonic() - inicio) * 1000)


def _mostrar_estatisticas():
    linhas = estatisticas()
    if not linhas:
        print("NEXO: Ainda não tenho nenhuma interação registrada.")
        return
    nomes = {"ia": "Inteligência artificial", "cache": "Banco (reaproveitado)", "local": "Resposta local"}
    print("NEXO: Minhas estatísticas:")
    for origem, total, tempo_medio, entrada, saida in linhas:
        tempo = f"{(tempo_medio or 0) / 1000:.1f}s"
        tokens = f", {entrada + saida} tokens" if origem == "ia" else ""
        print(f"- {nomes.get(origem, origem)}: {total} respostas, média {tempo}{tokens}")


def _responder_e_registrar(mensagem, normalizado, chave, inicio):
    local = resposta_local(normalizado)
    if local:
        registrar_interacao(
            pergunta=mensagem, pergunta_normalizada=normalizado, chave=chave,
            resposta=local, origem="local", tempo_ms=_milissegundos(inicio),
        )
        return local, None, "resposta local"

    encontrado = buscar_no_cache(chave)
    if encontrado:
        id_origem, resposta = encontrado
        registrar_interacao(
            pergunta=mensagem, pergunta_normalizada=normalizado, chave=chave,
            resposta=resposta, origem="cache", cache_de_id=id_origem,
            tempo_ms=_milissegundos(inicio),
        )
        return resposta, id_origem, "do banco"

    print("NEXO: (pensando...)")
    resultado = responder(mensagem, ultimas_mensagens(TAMANHO_HISTORICO), consultar())
    novas = [item for item in resultado["lembrar"] if guardar("conversa", item)]

    reutilizavel = resultado["reutilizavel"] and not novas
    id_interacao = registrar_interacao(
        pergunta=mensagem, pergunta_normalizada=normalizado, chave=chave,
        resposta=resultado["resposta"], origem="ia", modelo=resultado["modelo"],
        reutilizavel=int(reutilizavel),
        pensamento=resultado["pensamento"],
        memorias_novas=json.dumps(novas, ensure_ascii=False) if novas else None,
        tokens_entrada=resultado["tokens_entrada"], tokens_saida=resultado["tokens_saida"],
        tempo_ms=_milissegundos(inicio),
    )

    if novas:
        print(f"      (guardei na memória: {' | '.join(novas)})")
    log.info("modelo=%s reutilizavel=%s memorias_novas=%d",
             resultado["modelo"], resultado["reutilizavel"], len(novas))
    return resultado["resposta"], id_interacao if reutilizavel else None, resultado["modelo"]


def conversar():
    iniciar_memoria()

    print("\nNEXO: Olá! Pode falar comigo.")
    print("NEXO: Comandos: 'aprenda: <algo>', 'o que você sabe', 'estatisticas', 'esquece essa resposta', 'sair'.")

    ultima_resposta_id = None

    while True:
        try:
            mensagem = input("\nVocê: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nNEXO: Até logo!")
            break

        if not mensagem:
            continue

        normalizado = normalizar(mensagem)

        if normalizado == "sair":
            print("NEXO: Até logo!")
            break

        if mensagem.lower().startswith("aprenda:"):
            informacao = mensagem.split(":", 1)[1].strip()
            if not informacao:
                print("NEXO: O que você quer me ensinar?")
            elif guardar("aprendizado", informacao):
                print("NEXO: Aprendi e guardei essa informação!")
            else:
                print("NEXO: Isso eu já sabia!")
            continue

        if "o que voce sabe" in normalizado:
            print("NEXO: Estas são minhas lembranças:")
            for _, informacao in consultar():
                print(f"- {informacao}")
            continue

        if normalizado in ("estatisticas", "estatistica"):
            _mostrar_estatisticas()
            continue

        if normalizado in COMANDOS_ESQUECER:
            if ultima_resposta_id and desativar_interacao(ultima_resposta_id):
                print("NEXO: Pronto, não vou mais reaproveitar essa resposta.")
            else:
                print("NEXO: Não tenho nenhuma resposta recente para esquecer.")
            ultima_resposta_id = None
            continue

        inicio = time.monotonic()
        try:
            resposta, ultima_resposta_id, fonte = _responder_e_registrar(
                mensagem, normalizado, gerar_chave(normalizado), inicio
            )
        except IaIndisponivel as erro:
            log.error("IA indisponível: %s", erro)
            print("NEXO: Não consegui pensar agora, minha conexão com a IA falhou. Tenta de novo daqui a pouco.")
            continue

        guardar_mensagem("usuario", mensagem)
        guardar_mensagem("nexo", resposta)

        print(f"NEXO: {resposta}")
        print(f"      [{fonte} · {_milissegundos(inicio) / 1000:.1f}s]")


if __name__ == "__main__":
    conversar()
