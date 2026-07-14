"""Agente de suporte AcmePass (ficticio) com LangChain + OpenAI."""

import os
import re
from typing import List

import requests
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.messages import AnyMessage, HumanMessage, SystemMessage
from langchain_core.tools import tool

# carrega variaveis do .env (OPENAI_API_KEY) para o ambiente do processo
load_dotenv()

if not os.getenv("OPENAI_API_KEY"):
    # falha rapido se a chave nao estiver configurada
    raise RuntimeError("OPENAI_API_KEY nao encontrada. Configure o arquivo .env.")

SYSTEM_PROMPT = """
Você é o assistente de suporte do AcmePass
(produto fictício para treinamento).

Regras:
1. Responda SOMENTE com base na FAQ e na
   ferramenta de CEP.
2. Se pedirem endereço por CEP, use
   consultar_cep.
3. Se o usuário disser que quer consultar um
   CEP mas não informou o número, PERGUNTE
   qual é o CEP. Não recuse essa intenção.
4. Se fugir da FAQ/ferramenta, ou não tiver
   certeza, NÃO invente. Responda:
   "Não tenho essa informação. Vou te
   encaminhar para um atendente humano."
5. Nunca peça dados sensíveis (CPF, cartão,
   senha, dados de saúde).

FAQ:
- Ativar: app AcmePass > "Meu cartão" > "Ativar".
- Limite mensal: R$ 500, renova dia 1º.
- Onde usar: farmácias e mercados credenciados.
- Perdido: app > "Segurança" > "Bloquear".
- Reembolso: até 5 dias úteis.
"""

CEP_TIMEOUT_SEGUNDOS = 5


@tool
def consultar_cep(cep: str) -> str:
    """Consulta endereco a partir de um CEP brasileiro (formato 00000000 ou 00000-000)."""
    cep_limpo = re.sub(r"\D", "", cep)

    # valida na borda: CEP brasileiro tem exatamente 8 digitos
    if len(cep_limpo) != 8:
        return "CEP invalido. Informe um CEP com 8 digitos."

    try:
        resposta = requests.get(
            f"https://viacep.com.br/ws/{cep_limpo}/json/",
            timeout=CEP_TIMEOUT_SEGUNDOS,
        )
        resposta.raise_for_status()
    except requests.RequestException:
        return "Nao foi possivel consultar o CEP agora. Tente novamente mais tarde."

    dados = resposta.json()
    if dados.get("erro"):
        return "CEP nao encontrado."

    return (
        f"{dados.get('logradouro', '')}, {dados.get('bairro', '')}, "
        f"{dados.get('localidade', '')}/{dados.get('uf', '')}"
    )


# modelo da OpenAI usado pelo agente. troque o nome do modelo conforme sua conta/plano
llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)

# vincula as tools ao modelo para permitir tool-calling
llm_com_tools = llm.bind_tools([consultar_cep])

TOOLS_POR_NOME = {"consultar_cep": consultar_cep}


def executar_agente(
    historico: List[AnyMessage], pergunta: str
) -> tuple[str, List[AnyMessage]]:
    """Pergunta -> modelo decide se usa tool -> aplica tool -> resposta final.

    Recebe o historico da conversa (memoria) e devolve um NOVO historico
    com o turno atual anexado, sem mutar a lista recebida.
    """
    mensagens = historico + [HumanMessage(content=pergunta)]

    resposta = llm_com_tools.invoke(mensagens)
    mensagens = mensagens + [resposta]

    # se o modelo pediu para chamar alguma tool, executa e devolve o resultado pra ele
    for chamada in resposta.tool_calls or []:
        tool_fn = TOOLS_POR_NOME[chamada["name"]]
        resultado = tool_fn.invoke(chamada["args"])
        mensagens = mensagens + [
            {
                "role": "tool",
                "content": str(resultado),
                "tool_call_id": chamada["id"],
            }
        ]

    if resposta.tool_calls:
        # pede resposta final ao modelo, agora com o resultado da tool no contexto
        resposta_final = llm_com_tools.invoke(mensagens)
        mensagens = mensagens + [resposta_final]
        return resposta_final.content, mensagens

    return resposta.content, mensagens


if __name__ == "__main__":
    print("Agente AcmePass pronto. Digite sua pergunta (CTRL+C para sair).")

    # memoria da conversa: comeca so com o system prompt e cresce a cada turno
    historico: List[AnyMessage] = [SystemMessage(content=SYSTEM_PROMPT)]

    while True:
        try:
            pergunta = input("> ")
        except KeyboardInterrupt:
            # CTRL+C: encerra sem stacktrace
            print("\nEncerrado.")
            break
        except EOFError:
            # stdin fechado (ex: pipe acabou): encerra sem stacktrace
            print("\nEncerrado (EOF).")
            break

        if not pergunta.strip():
            continue

        texto_resposta, historico = executar_agente(historico, pergunta)
        print(f"Resposta: {texto_resposta}")
