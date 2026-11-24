import unittest

from core.cache import gerar_chave, normalizar
from core.respostas_locais import resolver_conta, resposta_local


def local(texto):
    return resposta_local(texto, normalizar(texto))


class TestCache(unittest.TestCase):
    def test_normalizar(self):
        self.assertEqual(normalizar("Por quê o céu é AZUL?"), "porque o ceu e azul")

    def test_chave_ignora_ordem_e_palavras_vazias(self):
        self.assertEqual(
            gerar_chave(normalizar("Qual a capital da França?")),
            gerar_chave(normalizar("nexo, a capital da frança é qual?")),
        )

    def test_chave_diferencia_paises_parecidos(self):
        self.assertNotEqual(
            gerar_chave(normalizar("capital da Áustria")),
            gerar_chave(normalizar("capital da Austrália")),
        )


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
