# agente-langchain

Agente de suporte do AcmePass (produto ficticio, uso didatico) com LangChain + OpenAI. Responde apenas com base numa FAQ fixa no system prompt e numa tool de consulta de CEP (ViaCEP); fora disso, recusa e encaminha para atendimento humano.

## Estrutura

```
agente-langchain/
├── .venv/              # ambiente virtual Python (nao versionar)
├── .env                # OPENAI_API_KEY (nao versionar)
├── .gitignore
├── requirements.txt    # dependencias travadas (pip freeze)
└── agente.py           # codigo do agente
```

## Setup

```bash
cd agente-langchain
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

pip install langchain langchain-openai \
            requests fastapi uvicorn python-dotenv
```

## Configuracao da chave

Crie o `.env` na raiz do projeto (ja gitignorado):

```bash
echo "OPENAI_API_KEY=sua_chave" > .env
echo ".env" >> .gitignore
```

**Importante:** nunca cole a chave direto no chat, terminal compartilhado, commit ou log. Se uma chave for exposta em qualquer canal fora do `.env` local, revogue no painel da OpenAI (platform.openai.com/api-keys) e gere outra.

## Rodando

```bash
python agente.py
```

O agente fica em loop interativo, lendo perguntas do terminal ate voce apertar `CTRL+C`:

```
Agente AcmePass pronto. Digite sua pergunta (CTRL+C para sair).
> Qual o limite mensal do cartao?
Resposta: O limite mensal do cartão AcmePass é de R$ 500, e ele se renova no dia 1º de cada mês.
> Qual endereco do CEP 01310-100?
Resposta: O endereço do CEP 01310-100 é: Avenida Paulista, Bela Vista, São Paulo/SP.
> Qual a capital da Franca?
Resposta: Não tenho essa informação. Vou te encaminhar para um atendente humano.
> ^C
Encerrado.
```

## Como funciona

1. `load_dotenv()` le o `.env` e injeta `OPENAI_API_KEY` no ambiente do processo.
2. `SYSTEM_PROMPT` fixa o escopo do agente: responder so com base na FAQ e na tool `consultar_cep`, recusar o resto, nunca pedir dado sensivel.
3. `ChatOpenAI(model="gpt-4o-mini")` instancia o modelo da OpenAI usado pelo agente.
4. `llm.bind_tools([consultar_cep])` informa ao modelo que ele pode pedir a consulta de CEP.
5. `consultar_cep` valida o CEP (8 digitos) e chama a API publica ViaCEP (`https://viacep.com.br`), com timeout e tratamento de erro de rede/CEP invalido.
6. `executar_agente()` implementa o loop: envia a pergunta, verifica se o modelo pediu a tool call, executa `consultar_cep`, devolve o resultado ao modelo e retorna a resposta final.

## Extensoes possiveis

- Trocar o modelo (`model=`) por outro disponivel na sua conta OpenAI.
- Adicionar novas tools com o decorator `@tool` (ex: consulta de status do cartao).
- Expor o agente via FastAPI (`uvicorn` ja instalado) criando um endpoint que chama `executar_agente(pergunta)`.
- Usar `langchain-anthropic` no lugar de `langchain-openai` caso troque de provedor (Claude/Anthropic).

## Seguranca

- `.env` fica fora do controle de versao (`.gitignore`).
- Nunca commitar chaves de API.
- Validar `OPENAI_API_KEY` no startup (ja feito em `agente.py`) evita falha silenciosa.
