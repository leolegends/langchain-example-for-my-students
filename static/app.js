const SESSION_STORAGE_KEY = "acmepass_session_id";

const listaMensagens = document.getElementById("lista-mensagens");
const formChat = document.getElementById("form-chat");
const inputMensagem = document.getElementById("input-mensagem");
const btnEnviar = document.getElementById("btn-enviar");
const btnLimpar = document.getElementById("btn-limpar");
const elErro = document.getElementById("erro");

function obterSessionId() {
  return localStorage.getItem(SESSION_STORAGE_KEY);
}

function salvarSessionId(sessionId) {
  localStorage.setItem(SESSION_STORAGE_KEY, sessionId);
}

function adicionarMensagem(texto, autor, { pendente = false } = {}) {
  const bolha = document.createElement("div");
  bolha.className = `msg msg-${autor}${pendente ? " msg-pendente" : ""}`;

  if (pendente) {
    bolha.innerHTML =
      '<span class="typing-dots"><span></span><span></span><span></span></span>';
  } else {
    const paragrafo = document.createElement("p");
    paragrafo.textContent = texto;
    bolha.appendChild(paragrafo);
  }

  listaMensagens.appendChild(bolha);
  listaMensagens.scrollTo({ top: listaMensagens.scrollHeight, behavior: "smooth" });
  return bolha;
}

function mostrarErro(mensagem) {
  elErro.textContent = mensagem;
  elErro.hidden = false;
  // reinicia a animacao de shake mesmo se o erro anterior ainda estiver visivel
  elErro.style.animation = "none";
  void elErro.offsetWidth;
  elErro.style.animation = "";
}

function limparErro() {
  elErro.hidden = true;
  elErro.textContent = "";
}

async function enviarMensagem(mensagem) {
  const resposta = await fetch("/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ mensagem, session_id: obterSessionId() }),
  });

  if (!resposta.ok) {
    throw new Error("Nao foi possivel falar com o agente agora.");
  }

  return resposta.json();
}

formChat.addEventListener("submit", async (evento) => {
  evento.preventDefault();
  limparErro();

  const mensagem = inputMensagem.value.trim();
  if (!mensagem) return;

  adicionarMensagem(mensagem, "usuario");
  inputMensagem.value = "";
  inputMensagem.disabled = true;
  btnEnviar.disabled = true;

  const bolhaPendente = adicionarMensagem("", "agente", { pendente: true });

  try {
    const { resposta, session_id } = await enviarMensagem(mensagem);
    salvarSessionId(session_id);
    bolhaPendente.remove();
    adicionarMensagem(resposta, "agente");
  } catch (erro) {
    bolhaPendente.remove();
    mostrarErro(erro.message);
  } finally {
    inputMensagem.disabled = false;
    btnEnviar.disabled = false;
    inputMensagem.focus();
  }
});

btnLimpar.addEventListener("click", async () => {
  const sessionId = obterSessionId();
  if (sessionId) {
    await fetch(`/chat/${sessionId}`, { method: "DELETE" }).catch(() => {});
  }
  localStorage.removeItem(SESSION_STORAGE_KEY);
  listaMensagens.querySelectorAll(".msg").forEach((el, i) => {
    if (i > 0) el.remove();
  });
  limparErro();
  inputMensagem.focus();
});
