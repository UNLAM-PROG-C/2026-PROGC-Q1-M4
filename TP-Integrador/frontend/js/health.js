const aiIndicator = document.getElementById("aiIndicator");
const aiLabel = document.getElementById("aiLabel");
const HEALTH_URL = `${BACKEND_URL}/health`;
const POLL_INTERVAL = 10000; // cada 10 segundos
const HEALTH_TIMEOUT_MS = 4000;

const STATUS_CHECKING = "checking";
const STATUS_ONLINE = "online";
const STATUS_OFFLINE = "offline";
const HEALTH_OK = "ok";

const AI_LABELS = {
  checking: "Verificando motor...",
  online: "Motor de IA activo",
  offline: "Motor de IA apagado",
};

function setAiStatus(status) {
  aiIndicator.classList.remove(STATUS_CHECKING, STATUS_OFFLINE);
  if (status === STATUS_CHECKING) aiIndicator.classList.add(STATUS_CHECKING);
  if (status === STATUS_OFFLINE) aiIndicator.classList.add(STATUS_OFFLINE);
  aiLabel.textContent = AI_LABELS[status] || AI_LABELS.offline;
}

async function checkHealth() {
  try {
    const res = await fetch(HEALTH_URL, {
      signal: AbortSignal.timeout(HEALTH_TIMEOUT_MS),
    });
    const data = await res.json();
    setAiStatus(data.status === HEALTH_OK ? STATUS_ONLINE : STATUS_OFFLINE);
  } catch {
    setAiStatus(STATUS_OFFLINE);
  }
}

// Primera verificación al cargar
checkHealth();
// Polling periódico
setInterval(checkHealth, POLL_INTERVAL);
