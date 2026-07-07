const BACKEND_URL = "http://localhost:3001";

const STATE_IDS = {
  idle: "idleState",
  loading: "loadingState",
  results: "resultsState",
  error: "errorState",
};
const DEFAULT_ERROR_MESSAGE = "Error al conectar con el servidor";

function showOnlyState(visibleKey, visibleDisplay) {
  for (const [key, id] of Object.entries(STATE_IDS)) {
    document.getElementById(id).style.display =
      key === visibleKey ? visibleDisplay : DISPLAY_NONE;
  }
}

function showIdle() {
  showOnlyState("idle", DISPLAY_FLEX);
  setMode(MODE_IDLE);
}

function showLoading() {
  showOnlyState("loading", DISPLAY_BLOCK);
  setupNeuralGrid();
  animateLoadingText();
  setMode(MODE_LOADING);
}

function showResults(data) {
  showOnlyState("results", DISPLAY_BLOCK);
  renderResults(data);
  setMode(MODE_DONE);
}

function showError(msg) {
  showOnlyState("error", DISPLAY_FLEX);
  document.getElementById("errorMsg").textContent = msg || DEFAULT_ERROR_MESSAGE;
  setMode(MODE_IDLE);
}

const NEURAL_DOT_COUNT = 25;
const NEURAL_MAX_DELAY = 1.5;
const NEURAL_ACTIVE_RUN = 5;
const NEURAL_MAX_TICKS = 60;
const NEURAL_TICK_MS = 120;

function buildNeuralDots(grid) {
  grid.innerHTML = "";
  for (let i = 0; i < NEURAL_DOT_COUNT; i++) {
    const dot = document.createElement("div");
    dot.className = "neural-dot";
    dot.style.animationDelay = Math.random() * NEURAL_MAX_DELAY + "s";
    grid.appendChild(dot);
  }
}

function highlightNeuralRun(dots) {
  const idx = Math.floor(Math.random() * dots.length);
  dots.forEach((d) => d.classList.remove("active"));
  for (let k = 0; k < NEURAL_ACTIVE_RUN; k++)
    dots[(idx + k) % dots.length].classList.add("active");
}

function setupNeuralGrid() {
  const grid = document.getElementById("neuralGrid");
  buildNeuralDots(grid);
  let count = 0;
  const intervalId = setInterval(() => {
    if (mode !== MODE_LOADING || count > NEURAL_MAX_TICKS) {
      clearInterval(intervalId);
      return;
    }
    highlightNeuralRun(grid.querySelectorAll(".neural-dot"));
    count++;
  }, NEURAL_TICK_MS);
}

const loadingMsgs = [
  "Procesando imagen...",
  "Extrayendo características...",
  "Consultando red neuronal...",
  "Clasificando objetos...",
  "Calculando probabilidades...",
  "Casi listo...",
];
const LOADING_TEXT_INTERVAL_MS = 900;
let msgIdx = 0,
  msgIv;
function animateLoadingText() {
  clearInterval(msgIv);
  msgIdx = 0;
  const el = document.getElementById("loadingText");
  msgIv = setInterval(() => {
    if (mode !== MODE_LOADING) {
      clearInterval(msgIv);
      return;
    }
    el.textContent = loadingMsgs[msgIdx % loadingMsgs.length];
    msgIdx++;
  }, LOADING_TEXT_INTERVAL_MS);
}

const ANALYZE_ENDPOINT = `${BACKEND_URL}/analyze`;
const IMAGE_FIELD = "image";
const HTTP_POST = "POST";
const CONNECTION_ERROR_PREFIX = "No se pudo conectar: ";

async function requestAnalysis(file) {
  const form = new FormData();
  form.append(IMAGE_FIELD, file);
  const res = await fetch(ANALYZE_ENDPOINT, { method: HTTP_POST, body: form });
  if (!res.ok) throw new Error("HTTP " + res.status);
  return res.json();
}

async function analyze() {
  if (!currentFile) return;
  analyzeBtn.disabled = true;
  showLoading();
  try {
    showResults(await requestAnalysis(currentFile));
  } catch (err) {
    showError(CONNECTION_ERROR_PREFIX + err.message);
  } finally {
    clearInterval(msgIv);
    analyzeBtn.disabled = false;
  }
}

analyzeBtn.addEventListener("click", analyze);

showOnlyState("idle", DISPLAY_FLEX);
