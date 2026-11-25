import ast
import operator
import random
import re
from datetime import datetime, timedelta

DIAS = ["segunda-feira", "terça-feira", "quarta-feira", "quinta-feira", "sexta-feira", "sábado", "domingo"]
MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho",
         "agosto", "setembro", "outubro", "novembro", "dezembro"]

PERGUNTA_HORA = re.compile(
    r"(nexo )?(que horas sao|que horas e|que hora e|qual (e )?a hora|(me )?(diz|fala) (as|a) horas?)( agora)?"
)
PERGUNTA_DATA = re.compile(
    r"(nexo )?(que dia e hoje|qual (e )?a data( de hoje)?|que data e hoje|hoje e que dia|(me )?(diz|fala) a data)( de hoje)?"
)
PERGUNTA_DIA_SEMANA = re.compile(
    r"(nexo )?(que|qual) (e o )?dia da semana (e )?hoje|hoje e que dia da semana"
)
DIAS_RELATIVOS = {"anteontem": -2, "ontem": -1, "amanha": 1, "depois de amanha": 2}
_RELATIVO = r"(?P<{}>depois de amanha|amanha|anteontem|ontem)"
_VERBO = r"(?:e|foi|era|sera|vai ser|vai cair|cai)"
PERGUNTA_DIA_RELATIVO = re.compile(
    r"(?:nexo )?(?:"
    rf"(?:que|qual) (?:e (?:o |a )?)?(?:dia|dia da semana|data) {_VERBO} {_RELATIVO.format('a')}"
    rf"|{_RELATIVO.format('b')} {_VERBO} (?:que|qual) (?:dia|dia da semana|data)"
    rf"|qual (?:e |sera |foi )?a data de {_RELATIVO.format('c')}"
    r")"
)
CUMPRIMENTO = re.compile(r"(oi|ola|ei|eai|e ai|opa|salve|bom dia|boa tarde|boa noite)( nexo)?( tudo bem)?")
AGRADECIMENTO = re.compile(r"(muito )?(obrigado|obrigada|valeu|vlw|brigado|brigada)( nexo)?( mesmo)?")
IDENTIDADE = re.compile(r"(nexo )?(quem e voce|qual (e )?(o )?seu nome|como voce se chama)( nexo)?")
AJUDA = re.compile(r"(ajuda|comandos|o que voce faz|me ajuda)")

PEDIDO_CONTA = re.compile(r"^\s*(?:nexo,?\s*)?(?:quanto (?:e|é|da|dá)|calcul[ae])\s+(.+?)\s*\??\s*$")
PALAVRAS_OPERADORES = [
    (r"\bdividido por\b", "/"), (r"\belevado a\b", "**"), (r"\bmultiplicado por\b", "*"),
    (r"\bvezes\b", "*"), (r"\bmais\b", "+"), (r"\bmenos\b", "-"),
    (r"(?<=\d)\s*x\s*(?=\d)", "*"), ("×", "*"), ("÷", "/"), (r"\^", "**"),
]
OPERADORES = {
    ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
    ast.Div: operator.truediv, ast.Pow: operator.pow, ast.Mod: operator.mod,
    ast.USub: operator.neg, ast.UAdd: operator.pos,
}

AJUDA_TEXTO = (
    "Eu converso com você e lembro das coisas importantes. Comandos: "
    "'aprenda: algo' para eu guardar, 'esqueça: algo' para eu apagar uma lembrança, "
    "'o que você sabe', 'estatísticas', 'palavras', 'desaprende: palavra', 'esquece essa resposta' e 'sair'. "
    "Hora, data e contas eu respondo na hora, sem usar a IA."
)


def _periodo(hora):
    if 5 <= hora < 12:
        return "Bom dia"
    if 12 <= hora < 18:
        return "Boa tarde"
    return "Boa noite"


def _calcular(no):
    if isinstance(no, ast.Expression):
        return _calcular(no.body)
    if isinstance(no, ast.Constant) and isinstance(no.value, (int, float)):
        return no.value
    if isinstance(no, ast.UnaryOp) and type(no.op) in OPERADORES:
        return OPERADORES[type(no.op)](_calcular(no.operand))
    if isinstance(no, ast.BinOp) and type(no.op) in OPERADORES:
        esquerda, direita = _calcular(no.left), _calcular(no.right)
        if isinstance(no.op, ast.Pow) and abs(direita) > 100:
            raise ValueError("expoente grande demais")
        return OPERADORES[type(no.op)](esquerda, direita)
    raise ValueError("expressão não permitida")


def _formatar_numero(valor):
    if isinstance(valor, float) and valor.is_integer():
        valor = int(valor)
    if isinstance(valor, int):
        return f"{valor:,}".replace(",", ".")
    return f"{valor:.4f}".rstrip("0").replace(".", ",")


def resolver_conta(mensagem):
    pedido = PEDIDO_CONTA.match(mensagem.lower())
    if not pedido:
        return None
    expressao = pedido.group(1)
    for padrao, simbolo in PALAVRAS_OPERADORES:
        expressao = re.sub(padrao, simbolo, expressao)
    expressao = re.sub(r"(?<=\d),(?=\d)", ".", expressao)
    if not re.fullmatch(r"[\d.+\-*/%() ]+", expressao) or not re.search(r"\d", expressao):
        return None
    try:
        resultado = _calcular(ast.parse(expressao, mode="eval"))
    except ZeroDivisionError:
        return "Não dá para dividir por zero."
    except (SyntaxError, ValueError, TypeError, OverflowError):
        return None
    return f"Dá {_formatar_numero(resultado)}."


def _data_por_extenso(data):
    return f"{DIAS[data.weekday()]}, {data.day} de {MESES[data.month - 1]} de {data.year}"


def _dia_relativo(normalizado, agora):
    pedido = PERGUNTA_DIA_RELATIVO.fullmatch(normalizado)
    if not pedido:
        return None
    palavra = pedido.group("a") or pedido.group("b") or pedido.group("c")
    deslocamento = DIAS_RELATIVOS[palavra]
    data = agora + timedelta(days=deslocamento)
    nome = {"amanha": "Amanhã", "depois de amanha": "Depois de amanhã"}.get(palavra, palavra.capitalize())
    verbo = "vai ser" if deslocamento > 0 else "foi"
    return f"{nome} {verbo} {_data_por_extenso(data)}."


def resposta_local(mensagem, normalizado):
    agora = datetime.now()
    if PERGUNTA_HORA.fullmatch(normalizado):
        return f"Agora são {agora:%H:%M}."
    if PERGUNTA_DIA_SEMANA.fullmatch(normalizado):
        return f"Hoje é {DIAS[agora.weekday()]}."
    if PERGUNTA_DATA.fullmatch(normalizado):
        return f"Hoje é {_data_por_extenso(agora)}."
    relativo = _dia_relativo(normalizado, agora)
    if relativo:
        return relativo
    if CUMPRIMENTO.fullmatch(normalizado):
        return random.choice([
            f"{_periodo(agora.hour)}! Tô aqui, pode falar.",
            f"{_periodo(agora.hour)}! Em que posso ajudar?",
            "Oi! Que bom te ver por aqui.",
        ])
    if AGRADECIMENTO.fullmatch(normalizado):
        return random.choice(["De nada!", "Por nada, tô sempre aqui.", "Disponha!"])
    if IDENTIDADE.fullmatch(normalizado):
        return "Eu sou o NEXO, um robô companheiro que fica no seu ombro."
    if AJUDA.fullmatch(normalizado):
        return AJUDA_TEXTO
    return resolver_conta(mensagem)
