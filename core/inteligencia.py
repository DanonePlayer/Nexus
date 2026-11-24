import json
import logging
import os
import time
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from google.genai import types

RAIZ = Path(__file__).resolve().parent.parent
load_dotenv(RAIZ / ".env")

API_KEY = os.getenv("GEMINI_API_KEY")

if not API_KEY:
    raise RuntimeError("Chave da API Gemini não encontrada.")

MODELOS = [
    m.strip()
    for m in os.getenv(
        "NEXO_MODELOS",
        "gemini-3.5-flash-lite,gemini-3.1-flash-lite,gemini-3.5-flash,gemini-3.8-flash",
    ).split(",")
    if m.strip()
]
TEMPO_LIMITE_SEGUNDOS = int(os.getenv("NEXO_TEMPO_LIMITE", "25"))
SALVAR_PENSAMENTO = os.getenv("NEXO_SALVAR_PENSAMENTO", "0") == "1"
RODADAS = 2
PAUSA_ENTRE_RODADAS = 2

PERSONALIDADE = (RAIZ / "config" / "personalidade.md").read_text(encoding="utf-8")

log = logging.getLogger("nexo.inteligencia")

cliente = genai.Client(
    api_key=API_KEY,
    http_options=types.HttpOptions(
        timeout=TEMPO_LIMITE_SEGUNDOS * 1000,
        retry_options=types.HttpRetryOptions(attempts=1),
    ),
)

ESQUEMA_RESPOSTA = types.Schema(
    type="OBJECT",
    properties={
        "resposta": types.Schema(type="STRING"),
        "lembrar": types.Schema(type="ARRAY", items=types.Schema(type="STRING")),
        "reutilizavel": types.Schema(type="BOOLEAN"),
    },
    required=["resposta", "lembrar", "reutilizavel"],
)


class IaIndisponivel(Exception):
    pass


def _separar_texto(resposta):
    texto, pensamento = [], []
    candidatos = resposta.candidates or []
    partes = candidatos[0].content.parts if candidatos and candidatos[0].content else []
    for parte in partes or []:
        if not parte.text:
            continue
        (pensamento if parte.thought else texto).append(parte.text)
    return "".join(texto), "\n".join(pensamento) or None


def _gerar(contents, config=None):
    erros = []
    for rodada in range(RODADAS):
        if rodada:
            time.sleep(PAUSA_ENTRE_RODADAS)
        for modelo in MODELOS:
            resultado = _tentar(modelo, contents, config, erros)
            if resultado:
                return resultado
    raise IaIndisponivel(" | ".join(erros))


def _tentar(modelo, contents, config, erros):
    try:
        resposta = cliente.models.generate_content(
            model=modelo, contents=contents, config=config
        )
        texto, pensamento = _separar_texto(resposta)
        if texto:
            log.info("Resposta gerada pelo modelo %s", modelo)
            return modelo, texto, pensamento, resposta.usage_metadata
        erros.append(f"{modelo}: resposta vazia")
    except Exception as erro:
        log.warning("Falha no modelo %s: %s", modelo, erro)
        erros.append(f"{modelo}: {str(erro)[:100]}")
    return None


def perguntar(mensagem):
    _, texto, _, _ = _gerar(mensagem)
    return texto


def responder(mensagem, historico, memorias):
    lembrancas = "\n".join(f"- [{categoria}] {informacao}" for categoria, informacao in memorias)
    instrucao = (
        f"{PERSONALIDADE}\n\n"
        f"# Agora\n{datetime.now():%d/%m/%Y %H:%M}\n\n"
        f"# O que você lembra\n{lembrancas or '(nada ainda)'}"
    )

    contents = [
        types.Content(
            role="user" if papel == "usuario" else "model",
            parts=[types.Part(text=texto)],
        )
        for papel, texto in historico
    ]
    contents.append(types.Content(role="user", parts=[types.Part(text=mensagem)]))

    config = types.GenerateContentConfig(
        system_instruction=instrucao,
        response_mime_type="application/json",
        response_schema=ESQUEMA_RESPOSTA,
        temperature=0.8,
        thinking_config=types.ThinkingConfig(include_thoughts=True) if SALVAR_PENSAMENTO else None,
    )

    modelo, texto, pensamento, uso = _gerar(contents, config)

    resultado = {
        "modelo": modelo,
        "resposta": texto.strip(),
        "lembrar": [],
        "reutilizavel": False,
        "pensamento": pensamento,
        "tokens_entrada": getattr(uso, "prompt_token_count", None),
        "tokens_saida": getattr(uso, "candidates_token_count", None),
    }

    try:
        dados = json.loads(texto)
    except json.JSONDecodeError:
        return resultado

    resultado["resposta"] = (dados.get("resposta") or "").strip()
    resultado["lembrar"] = [item.strip() for item in dados.get("lembrar", []) if item and item.strip()]
    resultado["reutilizavel"] = bool(dados.get("reutilizavel"))
    return resultado
