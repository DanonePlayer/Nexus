import json
import logging
import re
import time
from pathlib import Path

from core.cache import aprender_palavras, buscar_no_cache, desaprender, gerar_chave, normalizar
from core.inteligencia import IaIndisponivel, responder, resumir
from core.lembrancas import selecionar_memorias
from core.respostas_locais import resposta_local
from memory.memoria import (
    apagar_memorias,
    consultar,
    desativar_interacao,
    estatisticas,
    palavras_vazias_resumo,
    resumo_economia,
    guardar,
    guardar_mensagem,
    guardar_resumo,
    iniciar_memoria,
    mensagens_fora_do_historico,
    registrar_interacao,
    ultimas_mensagens,
    ultimo_resumo,
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
LOTE_RESUMO = 20
# Piada repetida perde a graça e tristeza depende do momento: nunca vão para o cache.
EMOCOES_NAO_REUTILIZAVEIS = {"brincalhao", "triste"}
COMANDO_DESAPRENDER = re.compile(r"^desaprend[ae]\s*:\s*(.*)$", re.IGNORECASE)
COMANDO_APAGAR = re.compile(r"^esque[cç][ae]\s*:\s*(.*)$", re.IGNORECASE)
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

    total, sem_ia = resumo_economia()
    if total:
        print(f"- Economia: {sem_ia} de {total} respostas ({sem_ia * 100 // total}%) saíram sem usar a IA")

    aprendidas = [palavra for palavra, _, ativa, _, _ in palavras_vazias_resumo() if ativa]
    if aprendidas:
        print(f"- Palavras de enfeite que aprendi a ignorar: {', '.join(aprendidas)}")
    print("  (digite 'palavras' para ver os detalhes)")


def _mostrar_palavras():
    linhas = palavras_vazias_resumo()
    aprendidas = [palavra for palavra, _, ativa, _, _ in linhas if ativa]
    em_teste = [f"{palavra} ({votos}/3)" for palavra, votos, ativa, bloqueada, _ in linhas
                if not ativa and not bloqueada]
    bloqueadas = [(palavra, motivo) for palavra, _, _, bloqueada, motivo in linhas if bloqueada]
    print(f"NEXO: Ignoro estas palavras: {', '.join(aprendidas) or 'nenhuma ainda'}.")
    print(f"      Em teste (votos de perguntas diferentes): {', '.join(em_teste) or 'nenhuma'}.")
    if bloqueadas:
        print("      Bloqueadas (nunca vou ignorar):")
        for palavra, motivo in bloqueadas:
            print(f"      - {palavra}: {motivo}")
    print("      Para eu parar de ignorar uma palavra: 'desaprende: palavra'.")


def _responder_e_registrar(mensagem, normalizado, chave, inicio):
    local = resposta_local(mensagem, normalizado)
    if local:
        registrar_interacao(
            pergunta=mensagem, pergunta_normalizada=normalizado, chave=chave,
            resposta=local, origem="local", tempo_ms=_milissegundos(inicio),
        )
        return local, None, "resposta local", None

    encontrado = buscar_no_cache(chave)
    if encontrado:
        id_origem, resposta, emocao = encontrado
        registrar_interacao(
            pergunta=mensagem, pergunta_normalizada=normalizado, chave=chave,
            resposta=resposta, origem="cache", cache_de_id=id_origem, emocao=emocao,
            tempo_ms=_milissegundos(inicio),
        )
        return resposta, id_origem, "do banco", emocao

    print("NEXO: (pensando...)")
    historico = ultimas_mensagens(TAMANHO_HISTORICO)
    memorias = selecionar_memorias([mensagem] + [texto for _, texto in historico[-4:]])
    resultado = responder(mensagem, historico, memorias, ultimo_resumo()[1])
    novas = [item for item in resultado["lembrar"] if guardar("conversa", item)]

    reutilizavel = (
        resultado["reutilizavel"] and not novas
        and resultado["emocao"] not in EMOCOES_NAO_REUTILIZAVEIS
    )
    id_interacao = registrar_interacao(
        pergunta=mensagem, pergunta_normalizada=normalizado, chave=chave,
        resposta=resultado["resposta"], origem="ia", modelo=resultado["modelo"],
        reutilizavel=int(reutilizavel), emocao=resultado["emocao"],
        pensamento=resultado["pensamento"],
        memorias_novas=json.dumps(novas, ensure_ascii=False) if novas else None,
        tokens_entrada=resultado["tokens_entrada"], tokens_saida=resultado["tokens_saida"],
        tempo_ms=_milissegundos(inicio),
    )

    if novas:
        print(f"      (guardei na memória: {' | '.join(novas)})")

    for palavra in aprender_palavras(resultado["palavras_irrelevantes"], normalizado):
        print(f"      (aprendi que '{palavra}' não muda o sentido das perguntas)")
    log.info("modelo=%s reutilizavel=%s emocao=%s memorias_novas=%d",
             resultado["modelo"], resultado["reutilizavel"], resultado["emocao"], len(novas))
    return (resultado["resposta"], id_interacao if reutilizavel else None,
            resultado["modelo"], resultado["emocao"])


def _atualizar_resumo():
    ate_id, resumo_anterior = ultimo_resumo()
    pendentes = mensagens_fora_do_historico(ate_id, TAMANHO_HISTORICO)
    if len(pendentes) < LOTE_RESUMO:
        return
    try:
        novo = resumir(resumo_anterior, [(papel, texto) for _, papel, texto in pendentes])
    except IaIndisponivel as erro:
        log.warning("Resumo adiado, IA indisponível: %s", erro)
        return
    if novo:
        guardar_resumo(pendentes[-1][0], novo)
        log.info("Resumo atualizado até a mensagem %d", pendentes[-1][0])


def _apagar_lembranca(trecho):
    if not trecho:
        print("NEXO: O que você quer que eu esqueça? Ex.: 'esqueça: motocicletas'")
        return
    encontradas = apagar_memorias(trecho)
    if not encontradas:
        print("NEXO: Não achei nenhuma lembrança com isso.")
    elif len(encontradas) == 1:
        print(f"NEXO: Pronto, esqueci: {encontradas[0][1]}")
    else:
        print("NEXO: Achei mais de uma, seja mais específico:")
        for _, informacao in encontradas:
            print(f"- {informacao}")


def conversar():
    iniciar_memoria()

    print("\nNEXO: Olá! Pode falar comigo.")
    print("NEXO: Digite 'ajuda' para ver o que eu sei fazer.")

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

        if normalizado == "palavras":
            _mostrar_palavras()
            continue

        desaprender_pedido = COMANDO_DESAPRENDER.match(mensagem)
        if desaprender_pedido:
            palavra = desaprender_pedido.group(1).strip()
            if not palavra or " " in palavra:
                print("NEXO: Me diga uma palavra só. Ex.: 'desaprende: mesmo'")
            elif desaprender(palavra):
                print(f"NEXO: Pronto, voltei a considerar '{palavra}' e consertei as respostas guardadas.")
            else:
                print(f"NEXO: Eu não ignorava '{palavra}', mas agora ela está bloqueada para sempre.")
            continue

        apagar = COMANDO_APAGAR.match(mensagem)
        if apagar:
            _apagar_lembranca(apagar.group(1).strip())
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
            resposta, ultima_resposta_id, fonte, emocao = _responder_e_registrar(
                mensagem, normalizado, gerar_chave(normalizado), inicio
            )
        except IaIndisponivel as erro:
            log.error("IA indisponível: %s", erro)
            print("NEXO: Não consegui pensar agora, minha conexão com a IA falhou. Tenta de novo daqui a pouco.")
            continue

        guardar_mensagem("usuario", mensagem)
        guardar_mensagem("nexo", resposta)

        print(f"NEXO: {resposta}")
        detalhes = [fonte, f"{_milissegundos(inicio) / 1000:.1f}s"] + ([emocao] if emocao else [])
        print(f"      [{' · '.join(detalhes)}]")

        _atualizar_resumo()


if __name__ == "__main__":
    conversar()
