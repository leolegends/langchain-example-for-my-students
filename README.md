# agente-langchain

Material didatico: agente de suporte do **AcmePass** (produto ficticio, so pra treinamento) feito com **LangChain** + **OpenAI**. O agente responde apenas com base numa FAQ fixa e numa tool de consulta de CEP; fora disso, ele recusa e encaminha pra um humano. Este README explica **cada linha** de `agente.py`, pra quem esta aprendendo LangChain do zero.

## Estrutura do projeto

```
agente-langchain/
├── .venv/              # ambiente virtual Python (nao versionar)
├── .env                # guarda OPENAI_API_KEY (nao versionar)
├── .gitignore           # diz ao git o que ignorar
├── requirements.txt    # dependencias travadas (saida de pip freeze)
├── agente.py           # codigo do agente (explicado linha a linha abaixo)
└── README.md           # este arquivo
```

## Conceitos antes de ler o codigo

- **LLM (Large Language Model)**: o modelo de linguagem (aqui, `gpt-4o-mini` da OpenAI) que gera texto a partir de um prompt.
- **System prompt**: instrucao fixa, invisivel pro usuario final, que define o comportamento/persona/regras do modelo.
- **Tool (ferramenta)**: uma funcao Python comum que o modelo pode "pedir" pra executar (tool calling / function calling). O modelo NAO executa a funcao — ele so decide qual chamar e com quais argumentos; quem executa e o seu codigo.
- **Tool calling / function calling**: mecanismo onde o modelo devolve uma resposta estruturada dizendo "quero chamar a funcao X com esses argumentos", em vez de so texto livre.
- **Agente**: um LLM + tools + um loop que decide quando chamar tool e quando responder direto.

## Setup

```bash
cd agente-langchain
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

pip install langchain langchain-openai \
            requests fastapi uvicorn python-dotenv
```

O que cada pacote faz:

| Pacote | Para que serve aqui |
|---|---|
| `langchain` | framework base de orquestracao de LLM (mensagens, tools, etc.) |
| `langchain-openai` | integracao especifica da LangChain com os modelos da OpenAI (`ChatOpenAI`) |
| `requests` | cliente HTTP usado pela tool `consultar_cep` pra chamar a API ViaCEP |
| `fastapi` / `uvicorn` | instalados para uma extensao futura (expor o agente como API web); nao usados no `agente.py` atual |
| `python-dotenv` | le variaveis de um arquivo `.env` e injeta no ambiente do processo (`load_dotenv`) |

## Configuracao da chave

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

## `agente.py` explicado linha a linha

### Imports (linhas 1-10)

```python
"""Agente de suporte AcmePass (ficticio) com LangChain + OpenAI."""
```
Docstring do modulo — descreve o que o arquivo faz. Nao afeta a execucao.

```python
import os
import re
from typing import List
```
- `os`: usado pra ler variavel de ambiente (`os.getenv`).
- `re`: usado pra limpar o CEP com regex (remover tudo que nao for digito).
- `List`: type hint pra listas (usado no tipo do historico de mensagens).

```python
import requests
```
Biblioteca HTTP. Usada dentro de `consultar_cep` pra chamar a API ViaCEP.

```python
from dotenv import load_dotenv
```
Funcao que le o arquivo `.env` da pasta atual e injeta as variaveis no ambiente do processo (equivalente a fazer `export VAR=valor` no shell, mas via codigo).

```python
from langchain_openai import ChatOpenAI
```
Classe da LangChain que encapsula a chamada ao modelo de chat da OpenAI (`gpt-4o-mini`, `gpt-4o`, etc.).

```python
from langchain_core.messages import AnyMessage, HumanMessage, SystemMessage
```
Tipos de mensagem do "protocolo de chat" da LangChain:
- `SystemMessage`: instrucao de sistema (regras/persona do agente).
- `HumanMessage`: mensagem do usuario.
- `AnyMessage`: tipo "uniao" que representa qualquer tipo de mensagem (system, human, tool, resposta do modelo etc.) — usado so como type hint pra tipar a lista `historico`.

```python
from langchain_core.tools import tool
```
Decorator `@tool`, que transforma uma funcao Python comum numa "tool" que o LLM consegue enxergar e pedir pra chamar.

### Carregamento e validacao da chave (linhas 12-17)

```python
# carrega variaveis do .env (OPENAI_API_KEY) para o ambiente do processo
load_dotenv()
```
Executa a leitura do `.env`. A partir daqui, `os.getenv("OPENAI_API_KEY")` enxerga o valor.

```python
if not os.getenv("OPENAI_API_KEY"):
    # falha rapido se a chave nao estiver configurada
    raise RuntimeError("OPENAI_API_KEY nao encontrada. Configure o arquivo .env.")
```
Validacao de boundary: se a chave nao existir, o programa para imediatamente com erro claro, em vez de falhar depois, no meio de uma chamada a API, com um erro confuso.

### System prompt (linhas 19-41)

```python
SYSTEM_PROMPT = """
Você é o assistente de suporte do AcmePass
...
"""
```
String multi-linha com as instrucoes fixas do agente: escopo (FAQ + tool de CEP), regra de esclarecimento (se o usuario quer consultar CEP mas nao deu o numero, perguntar o numero em vez de recusar), regra anti-alucinacao (se nao souber, recusa e encaminha pra humano) e regra de protecao de dados sensiveis (nunca pedir CPF, cartao, senha, dados de saude). Essa string vira o conteudo de um `SystemMessage`, enviado em toda chamada ao modelo — e o que da o "carater" e os limites do agente.

**Licao pratica:** na primeira versao, a regra 3 (recusar o que fugir da FAQ/tool) nao existia separada da regra de "perguntar o CEP" — resultado: perguntar "voce consegue consultar meu CEP?" (sem informar o numero) fazia o modelo cair direto na regra de recusa, porque nao havia CEP pra passar pra tool. O ajuste foi explicitar no prompt: "se a intencao e consultar CEP mas falta o numero, pergunte o numero, nao recuse". Isso mostra que o `SYSTEM_PROMPT` precisa cobrir nao so "o que responder" mas tambem "o que fazer quando falta informacao pra usar a tool".

### Constante de timeout (linha 43)

```python
CEP_TIMEOUT_SEGUNDOS = 5
```
Numero magico nomeado: tempo maximo (em segundos) que a chamada HTTP pra ViaCEP pode esperar antes de desistir. Evita que o agente trave para sempre se a API externa nao responder.

### Tool `consultar_cep` (linhas 46-71)

```python
@tool
def consultar_cep(cep: str) -> str:
    """Consulta endereco a partir de um CEP brasileiro (formato 00000000 ou 00000-000)."""
```
O decorator `@tool` registra essa funcao como tool. A **docstring** aqui nao e so documentacao: e o texto que o LLM le para decidir se/quando chamar essa funcao. Escreva a docstring pensando em "isso vai ser lido pelo modelo, nao so por humanos".

```python
    cep_limpo = re.sub(r"\D", "", cep)
```
Remove qualquer caractere que nao seja digito (`\D` = "nao-digito"). Assim `"01310-100"` e `"01310100"` viram a mesma coisa.

```python
    # valida na borda: CEP brasileiro tem exatamente 8 digitos
    if len(cep_limpo) != 8:
        return "CEP invalido. Informe um CEP com 8 digitos."
```
Validacao de entrada (boundary check). CEP brasileiro sempre tem 8 digitos; se nao tiver, retorna erro amigavel sem nem chamar a API.

```python
    try:
        resposta = requests.get(
            f"https://viacep.com.br/ws/{cep_limpo}/json/",
            timeout=CEP_TIMEOUT_SEGUNDOS,
        )
        resposta.raise_for_status()
    except requests.RequestException:
        return "Nao foi possivel consultar o CEP agora. Tente novamente mais tarde."
```
Chama a API publica **ViaCEP** (`viacep.com.br`), que devolve um JSON com o endereco daquele CEP.
- `timeout=CEP_TIMEOUT_SEGUNDOS`: nao deixa a chamada pendurar indefinidamente.
- `raise_for_status()`: lanca excecao se o HTTP retornar codigo de erro (4xx/5xx).
- `except requests.RequestException`: captura qualquer erro de rede/timeout/HTTP e devolve mensagem amigavel, em vez de estourar stacktrace pro usuario final.

```python
    dados = resposta.json()
    if dados.get("erro"):
        return "CEP nao encontrado."
```
Converte o corpo da resposta em dict Python. A API ViaCEP retorna `{"erro": true}` quando o CEP e valido no formato mas nao existe — tratamos esse caso separado do erro de rede.

```python
    return (
        f"{dados.get('logradouro', '')}, {dados.get('bairro', '')}, "
        f"{dados.get('localidade', '')}/{dados.get('uf', '')}"
    )
```
Monta a string final do endereco (rua, bairro, cidade/UF). `dados.get(chave, '')` evita erro se algum campo vier ausente no JSON.

### Instancia do modelo e das tools (linhas 74-80)

```python
# modelo da OpenAI usado pelo agente. troque o nome do modelo conforme sua conta/plano
llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
```
Cria o cliente do modelo de chat.
- `model="gpt-4o-mini"`: modelo escolhido (mais barato/rapido; pode trocar por `gpt-4o`, etc., conforme acesso da sua conta).
- `temperature=0`: reduz aleatoriedade da resposta — bom pra um agente de suporte, que deve ser consistente, nao criativo.

```python
# vincula as tools ao modelo para permitir tool-calling
llm_com_tools = llm.bind_tools([consultar_cep])
```
`bind_tools` cria uma nova versao do LLM que "conhece" a tool `consultar_cep` — o modelo passa a poder responder pedindo a chamada dessa funcao.

```python
TOOLS_POR_NOME = {"consultar_cep": consultar_cep}
```
Dicionario que mapeia o nome da tool (string que o modelo devolve) pra funcao Python real. Usado depois para executar a chamada.

### Funcao `executar_agente` — com memoria de conversa

```python
def executar_agente(
    historico: List[AnyMessage], pergunta: str
) -> tuple[str, List[AnyMessage]]:
    """Pergunta -> modelo decide se usa tool -> aplica tool -> resposta final.

    Recebe o historico da conversa (memoria) e devolve um NOVO historico
    com o turno atual anexado, sem mutar a lista recebida.
    """
```
A funcao recebe o `historico` (lista de mensagens dos turnos anteriores — a "memoria" do agente) e a `pergunta` nova. Ela devolve uma tupla: `(texto_da_resposta, historico_atualizado)`. Note que ela **nao muta** a lista recebida — sempre cria uma lista nova com `+`. Isso segue o principio de imutabilidade: evita efeitos colaterais escondidos (se outro pedaço de codigo ainda tiver referencia ao `historico` antigo, ele continua intacto).

```python
    mensagens = historico + [HumanMessage(content=pergunta)]
```
Cria uma nova lista: tudo que ja aconteceu na conversa (`historico`) + a pergunta nova. Isso e a "memoria" na pratica — o modelo recebe as trocas anteriores junto da pergunta atual.

```python
    resposta = llm_com_tools.invoke(mensagens)
    mensagens = mensagens + [resposta]
```
Manda tudo pro modelo. A resposta e anexada (numa lista nova, nao com `.append`) pro caso de precisar de uma segunda chamada (quando o modelo pediu tool).

```python
    # se o modelo pediu para chamar alguma tool, executa e devolve o resultado pra ele
    for chamada in resposta.tool_calls or []:
```
`resposta.tool_calls` e uma lista (pode vir vazia/`None`) com as tools que o modelo pediu pra chamar, cada uma com nome e argumentos. O `or []` evita erro se vier `None`.

```python
        tool_fn = TOOLS_POR_NOME[chamada["name"]]
        resultado = tool_fn.invoke(chamada["args"])
```
Busca a funcao real pelo nome que o modelo pediu, e executa com os argumentos que o modelo gerou (ex: `{"cep": "01310-100"}`).

```python
        mensagens = mensagens + [
            {
                "role": "tool",
                "content": str(resultado),
                "tool_call_id": chamada["id"],
            }
        ]
```
Anexa o resultado da tool ao historico (lista nova de novo), como mensagem de "role: tool" — assim o modelo, na proxima chamada, ve o resultado e pode usa-lo pra montar a resposta final. `tool_call_id` amarra essa resposta a chamada especifica que o modelo pediu.

```python
    if resposta.tool_calls:
        # pede resposta final ao modelo, agora com o resultado da tool no contexto
        resposta_final = llm_com_tools.invoke(mensagens)
        mensagens = mensagens + [resposta_final]
        return resposta_final.content, mensagens
```
Se alguma tool foi chamada, faz uma segunda chamada ao modelo — agora com o resultado da tool no historico — pra ele gerar a resposta final. O historico final (com a resposta da tool E a resposta final) e devolvido, pra alimentar o proximo turno.

```python
    return resposta.content, mensagens
```
Se o modelo NAO pediu nenhuma tool, a resposta original ja e a resposta final (ex: perguntas de FAQ). O `mensagens` devolvido aqui ja inclui essa resposta — mantendo a memoria consistente mesmo quando nenhuma tool foi usada.

**Por que isso e "memoria"?** Sem isso, cada `executar_agente` comecava do zero (so `SystemMessage` + a pergunta atual) — o modelo nao via nada do que foi dito antes. Um sintoma real desse bug: perguntar "voce consegue consultar meu CEP?" (sem o numero) fazia o agente pedir o CEP, mas se o usuario respondesse so o numero no proximo turno, o agente nao lembrava que aquilo era resposta a propria pergunta dele — cada turno era uma conversa nova. Com o historico passado adiante, o modelo agora ve a conversa inteira a cada chamada.

**Limitacao consciente:** o historico cresce sem limite. Numa conversa muito longa, isso aumenta o custo (tokens) e pode eventualmente estourar o limite de contexto do modelo. Para este material didatico isso nao foi tratado (YAGNI) — numa aplicacao real, valeria truncar ou resumir o historico mais antigo periodicamente.

### Loop principal — mantendo a memoria entre turnos

```python
if __name__ == "__main__":
```
So executa o bloco abaixo quando o arquivo roda diretamente (`python agente.py`), nao quando e importado por outro modulo.

```python
    print("Agente AcmePass pronto. Digite sua pergunta (CTRL+C para sair).")

    # memoria da conversa: comeca so com o system prompt e cresce a cada turno
    historico: List[AnyMessage] = [SystemMessage(content=SYSTEM_PROMPT)]

    while True:
```
Mensagem inicial e criacao do `historico` — a variavel que guarda a memoria da conversa. Comeca so com o `SystemMessage` (as regras fixas); a cada turno, `executar_agente` devolve um `historico` maior, que e reatribuido aqui fora do loop (por isso a variavel `historico` precisa existir antes do `while True`, nao dentro dele).

```python
        try:
            pergunta = input("> ")
```
`input("> ")` mostra o prompt `> ` e bloqueia esperando o usuario digitar e apertar Enter.

```python
        except KeyboardInterrupt:
            # CTRL+C: encerra sem stacktrace
            print("\nEncerrado.")
            break
```
`CTRL+C` gera `KeyboardInterrupt` em Python. Sem esse `try/except`, o programa terminaria mostrando um stacktrace feio; aqui ele encerra com mensagem limpa.

```python
        except EOFError:
            # stdin fechado (ex: pipe acabou): encerra sem stacktrace
            print("\nEncerrado (EOF).")
            break
```
`EOFError` acontece quando o `stdin` fecha (ex: rodando via pipe `echo "pergunta" | python agente.py`, ou `CTRL+D` no terminal). Tratado do mesmo jeito, pra nao quebrar feio.

```python
        if not pergunta.strip():
            continue
```
Se o usuario so apertou Enter (linha vazia/so espacos), pula pra proxima iteracao sem chamar o modelo — evita gastar uma chamada de API a toa.

```python
        texto_resposta, historico = executar_agente(historico, pergunta)
        print(f"Resposta: {texto_resposta}")
```
Chama o agente passando o `historico` atual e a pergunta digitada. `executar_agente` devolve o texto da resposta e o `historico` **atualizado**, que sobrescreve a variavel `historico` — e assim que a memoria persiste de um turno pro outro. Volta pro topo do `while True` e espera a proxima pergunta, agora com mais contexto disponivel.

## Extensoes possiveis

- Trocar o modelo (`model=`) por outro disponivel na sua conta OpenAI.
- Adicionar novas tools com o decorator `@tool` (ex: consulta de status do cartao).
- Expor o agente via FastAPI (`uvicorn` ja instalado) criando um endpoint que chama `executar_agente(pergunta)`.
- Usar `langchain-anthropic` no lugar de `langchain-openai` caso troque de provedor (Claude/Anthropic).

## Seguranca

- `.env` fica fora do controle de versao (`.gitignore`).
- Nunca commitar chaves de API.
- Validar `OPENAI_API_KEY` no startup (ja feito em `agente.py`) evita falha silenciosa.
- O `SYSTEM_PROMPT` proibe explicitamente pedir dados sensiveis (CPF, cartao, senha, saude) — mas isso e uma instrucao pro modelo, nao uma garantia tecnica. Nao trate como controle de seguranca suficiente sozinho; se este agente evoluir pra lidar com dados reais de usuarios, validacao e sanitizacao devem acontecer no codigo, nao so no prompt.
