import unittest

from core.cache import (
    encontrar_colisao, filtrar_sugestoes, gerar_chave, mesmo_sentido, normalizar, pode_ir_para_cache,
)
from core.lembrancas import selecionar_memorias
from core.respostas_locais import resolver_conta, resposta_local


def local(texto):
    return resposta_local(texto, normalizar(texto))


class TestCache(unittest.TestCase):
    def test_normalizar(self):
        self.assertEqual(normalizar("Por quê o céu é AZUL?"), "porque o ceu e azul")

    def test_chave_ignora_ordem_e_palavras_vazias(self):
        self.assertEqual(
            gerar_chave(normalizar("Qual a capital da França?"), aprendidas=set()),
            gerar_chave(normalizar("nexo, a capital da frança é qual?"), aprendidas=set()),
        )

    def test_chave_diferencia_paises_parecidos(self):
        self.assertNotEqual(
            gerar_chave(normalizar("capital da Áustria"), aprendidas=set()),
            gerar_chave(normalizar("capital da Austrália"), aprendidas=set()),
        )


class TestAbreviacoes(unittest.TestCase):
    def test_abreviacoes_viram_palavra_inteira(self):
        self.assertEqual(normalizar("pq o céu é azul?"), normalizar("por que o céu é azul?"))
        self.assertEqual(normalizar("vc tbm acha q n?"), "voce tambem acha que nao")
        self.assertEqual(normalizar("qntos ossos"), "quantos ossos")

    def test_mesma_chave_com_abreviacao(self):
        self.assertEqual(
            gerar_chave(normalizar("quantos gramas tem um kg"), aprendidas=set()),
            gerar_chave(normalizar("quantos gramas tem um quilo"), aprendidas=set()),
        )

    def test_hora_abreviada_e_local(self):
        self.assertTrue(local("q horas sao").startswith("Agora são"))


class TestLembrancas(unittest.TestCase):
    TODAS = [
        (1, "identidade", "Meu nome é NEXO."),
        (2, "essencial", "O criador quer ser chamado de senhor."),
        (3, "dono", "O criador gosta de motocicletas."),
        (4, "dono", "O criador gosta de café."),
        (5, "dono", "O criador tem uma impressora 3D."),
        (6, "dono", "O criador mexe com Arduino."),
    ]

    def test_poucas_lembrancas_vao_todas(self):
        self.assertEqual(len(selecionar_memorias(["oi"], limite=25, todas=self.TODAS)), 6)

    def test_escolhe_essenciais_e_relevantes(self):
        escolhidas = selecionar_memorias(["qual moto eu devo comprar?"], limite=3, todas=self.TODAS)
        textos = [informacao for _, informacao in escolhidas]
        self.assertIn("Meu nome é NEXO.", textos)
        self.assertIn("O criador quer ser chamado de senhor.", textos)
        self.assertIn("O criador gosta de motocicletas.", textos)

    def test_completa_com_as_mais_recentes(self):
        escolhidas = selecionar_memorias(["tudo bem?"], limite=3, todas=self.TODAS)
        self.assertIn("O criador mexe com Arduino.", [i for _, i in escolhidas])


class TestPalavrasAprendidas(unittest.TestCase):
    def test_chave_com_palavra_aprendida(self):
        pergunta = normalizar("nexo, qual é mesmo a capital do japão?")
        self.assertEqual(gerar_chave(pergunta, aprendidas=set()), "capital japao mesmo qual")
        self.assertEqual(gerar_chave(pergunta, aprendidas={"mesmo"}), "capital japao qual")

    def test_aceita_enfeite(self):
        pergunta = normalizar("qual é mesmo a capital do japão")
        self.assertEqual(filtrar_sugestoes(["mesmo"], pergunta), {"mesmo"})

    def test_recusa_protegidas_e_inventadas(self):
        pergunta = normalizar("quem não é o presidente do brasil mesmo")
        self.assertEqual(filtrar_sugestoes(["não", "quem", "tipo", "123"], pergunta), set())
        self.assertEqual(filtrar_sugestoes(["eu"], normalizar("do que eu gosto mesmo")), set())

    def test_desconfia_quando_ia_quer_apagar_quase_tudo(self):
        pergunta = normalizar("capital japao tokyo mesmo")
        self.assertEqual(filtrar_sugestoes(["capital", "japao", "tokyo", "mesmo"], pergunta), set())


class TestColisao(unittest.TestCase):
    def test_palavra_que_muda_sentido_e_barrada(self):
        respostas = [
            ("ainda chove em São Paulo?", "Sim, ainda está chovendo forte agora."),
            ("chove em São Paulo?", "Em São Paulo chove bastante no verão."),
        ]
        self.assertIsNotNone(encontrar_colisao("ainda", respostas, aprendidas=set()))

    def test_enfeite_de_verdade_passa(self):
        respostas = [
            ("qual a capital do Japão?", "A capital do Japão é Tóquio."),
            ("qual é mesmo a capital do Japão?", "A capital do Japão é Tóquio, senhor."),
        ]
        self.assertIsNone(encontrar_colisao("mesmo", respostas, aprendidas=set()))

    def test_sem_dados_parecidos_passa(self):
        respostas = [("o que é python", "Python é uma linguagem de programação.")]
        self.assertIsNone(encontrar_colisao("tipo", respostas, aprendidas=set()))

    def test_mesmo_sentido(self):
        self.assertTrue(mesmo_sentido("A capital é Tóquio.", "A capital é Tóquio, senhor."))
        self.assertFalse(mesmo_sentido("Sim, está chovendo.", "Não, faz sol hoje."))


class TestContas(unittest.TestCase):
    def test_contas(self):
        casos = {
            "quanto é 2 + 2": "Dá 4.",
            "Quanto é 15 vezes 3?": "Dá 45.",
            "calcula 10 dividido por 4": "Dá 2,5.",
            "quanto da 2 elevado a 10": "Dá 1.024.",
            "quanto é 7x8": "Dá 56.",
            "quanto é (2+3)*4": "Dá 20.",
            "quanto é 1,5 + 1,5": "Dá 3.",
            "quanto é 1 / 0": "Não dá para dividir por zero.",
        }
        for pergunta, esperado in casos.items():
            with self.subTest(pergunta=pergunta):
                self.assertEqual(resolver_conta(pergunta), esperado)

    def test_conta_solta(self):
        casos = {"1+2 ?": "Dá 3.", "20+14?": "Dá 34.", "3 x 4 =": "Dá 12.", "(2+3)*4": "Dá 20.",
                 "10/4": "Dá 2,5.", "nexo, 7-10?": "Dá -3."}
        for pergunta, esperado in casos.items():
            with self.subTest(pergunta=pergunta):
                self.assertEqual(local(pergunta), esperado)

    def test_numero_sozinho_nao_e_conta(self):
        for pergunta in ["2024", "42?", "1,5"]:
            with self.subTest(pergunta=pergunta):
                self.assertIsNone(resolver_conta(pergunta))

    def test_travas_do_cache(self):
        def pode(texto):
            n = normalizar(texto)
            return pode_ir_para_cache(n, gerar_chave(n, aprendidas=set()))
        self.assertFalse(pode("memoria"))
        self.assertFalse(pode("quanto é 10 - 2 elevado a raiz"))
        self.assertTrue(pode("qual a capital do Japão?"))
        self.assertTrue(pode("como calcular o determinante de uma matriz 2x2"))

    def test_operadores_mudam_a_chave(self):
        chaves = {gerar_chave(normalizar(c), aprendidas=set()) for c in ["1+2", "1-2", "1*2", "1/2"]}
        self.assertEqual(len(chaves), 4)

    def test_nao_e_conta(self):
        for pergunta in ["quanto é o dólar hoje", "quanto custa um raspberry",
                         "quanto é 2 ** 999999", "calcula __import__('os')"]:
            with self.subTest(pergunta=pergunta):
                self.assertIsNone(resolver_conta(pergunta))


class TestRespostasLocais(unittest.TestCase):
    def test_hora_e_data(self):
        self.assertTrue(local("Que horas são?").startswith("Agora são"))
        self.assertTrue(local("que dia é hoje").startswith("Hoje é"))
        self.assertRegex(local("que dia da semana é hoje"), r"^Hoje é \S+\.$")

    def test_dias_relativos(self):
        casos = {
            "que dia é amanhã?": "Amanhã vai ser",
            "Amanhã é que dia?": "Amanhã vai ser",
            "qual a data de ontem": "Ontem foi",
            "que dia foi anteontem": "Anteontem foi",
            "que dia vai ser depois de amanhã": "Depois de amanhã vai ser",
            "qual dia da semana vai cair amanhã": "Amanhã vai ser",
        }
        for pergunta, inicio in casos.items():
            with self.subTest(pergunta=pergunta):
                self.assertTrue((local(pergunta) or "").startswith(inicio), local(pergunta))
        self.assertIsNone(local("o que vamos fazer amanhã?"))

    def test_conversa_simples(self):
        self.assertIsNotNone(local("Bom dia, NEXO!"))
        self.assertIsNotNone(local("valeu"))
        self.assertIn("NEXO", local("quem é você?"))
        self.assertIn("aprenda", local("ajuda"))

    def test_vai_para_ia(self):
        for pergunta in ["oi, me conta uma piada", "qual a capital da frança", "bom dia, como foi seu dia?"]:
            with self.subTest(pergunta=pergunta):
                self.assertIsNone(local(pergunta))


if __name__ == "__main__":
    unittest.main()
