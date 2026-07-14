"""API HTTP para o agente AcmePass. Expoe o `executar_agente` de agente.py via FastAPI."""

import logging
import uuid
from typing import Dict, List

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from langchain_core.messages import AnyMessage, SystemMessage
from pydantic import BaseModel, Field

from agente import SYSTEM_PROMPT, executar_agente

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("agente_api")

app = FastAPI(title="Agente AcmePass API")

# memoria por sessao. processo unico, em memoria: reinicia o servidor, perde tudo (ok pra treinamento).
SESSOES: Dict[str, List[AnyMessage]] = {}

MENSAGEM_MAX_CHARS = 2000


class ChatRequest(BaseModel):
    mensagem: str = Field(min_length=1, max_length=MENSAGEM_MAX_CHARS)
    session_id: str | None = None


class ChatResponse(BaseModel):
    resposta: str
    session_id: str


@app.post("/chat", response_model=ChatResponse)
def chat(payload: ChatRequest) -> ChatResponse:
    session_id = payload.session_id or str(uuid.uuid4())
    historico = SESSOES.get(session_id, [SystemMessage(content=SYSTEM_PROMPT)])

    try:
        texto_resposta, historico_atualizado = executar_agente(historico, payload.mensagem)
    except Exception:
        logger.exception("Falha ao executar o agente (session_id=%s)", session_id)
        raise HTTPException(status_code=502, detail="Agente indisponivel agora. Tente novamente.")

    SESSOES[session_id] = historico_atualizado
    return ChatResponse(resposta=texto_resposta, session_id=session_id)


@app.delete("/chat/{session_id}")
def limpar_sessao(session_id: str) -> dict[str, bool]:
    existia = SESSOES.pop(session_id, None) is not None
    return {"ok": existia}


app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
def index() -> FileResponse:
    return FileResponse("static/index.html")
