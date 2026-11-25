import unittest

from core.cache import filtrar_sugestoes, gerar_chave, normalizar
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

    def test_desconfia_quando_ia_quer_apagar_quase_tudo(self):
        pergunta = normalizar("capital japao tokyo mesmo")
        self.assertEqual(filtrar_sugestoes(["capital", "japao", "tokyo", "mesmo"], pergunta), set())


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
