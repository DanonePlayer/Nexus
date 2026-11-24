from memory.memoria import iniciar_memoria, guardar, consultar, pesquisar

def conversar():
    iniciar_memoria()

    print("\nNEXO: Olá! Estou aprendendo a conversar.")
    print("NEXO: Digite 'sair' para encerrar.")

    while True:
        mensagem = input("\nVocê: ").strip()

        if mensagem.lower() == "sair":
            print("NEXO: Até logo!")
            break

        elif mensagem.lower().startswith("aprenda:"):
            informacao = mensagem.split(":", 1)[1].strip()

            if informacao:
                guardar("aprendizado", informacao)
                print("NEXO: Aprendi e guardei essa informação!")
            else:
                print("NEXO: O que você quer me ensinar?")

        elif "o que você sabe" in mensagem.lower():
            print("NEXO: Estas são minhas lembranças:")

            for categoria, informacao in consultar():
                print(f"- {informacao}")

        else:
            resultados = pesquisar(mensagem)

            if resultados:
                print("NEXO: Encontrei algo na minha memória:")

                for categoria, informacao in resultados:
                    print(f"- {informacao}")
            else:
                print("NEXO: Ainda não encontrei essa informação.")

if __name__ == "__main__":
    conversar()
