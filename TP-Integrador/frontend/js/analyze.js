function showOnlyState(visibleKey, visibleDisplay) {
  for (const [key, id] of Object.entries(STATE_IDS)) {
    document.getElementById(id).style.display =
      key === visibleKey ? visibleDisplay : DISPLAY_NONE;
  }
}

function showIdle() {
  showOnlyState(STATE_KEY_IDLE, DISPLAY_FLEX);
  setMode(MODE_IDLE);
}

function showLoading() {
  showOnlyState(STATE_KEY_LOADING, DISPLAY_BLOCK);
  setupNeuralGrid();
  animateLoadingText();
  setMode(MODE_LOADING);
}

function showResults(data) {
  showOnlyState(STATE_KEY_RESULTS, DISPLAY_BLOCK);
  renderResults(data);
  setMode(MODE_DONE);
}

function showError(msg) {
  showOnlyState(STATE_KEY_ERROR, DISPLAY_FLEX);
  document.getElementById(ID_ERROR_MSG).textContent =
    msg || DEFAULT_ERROR_MESSAGE;
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
    dot.className = CLASS_NEURAL_DOT;
    dot.style.animationDelay = Math.random() * NEURAL_MAX_DELAY + "s";
    grid.appendChild(dot);
  }
}

function highlightNeuralRun(dots) {
  const idx = Math.floor(Math.random() * dots.length);
  dots.forEach((d) => d.classList.remove(CLASS_ACTIVE));
  for (let k = 0; k < NEURAL_ACTIVE_RUN; k++)
    dots[(idx + k) % dots.length].classList.add(CLASS_ACTIVE);
}

function setupNeuralGrid() {
  const grid = document.getElementById(ID_NEURAL_GRID);
  buildNeuralDots(grid);
  let count = 0;
  const intervalId = setInterval(() => {
    if (mode !== MODE_LOADING || count > NEURAL_MAX_TICKS) {
      clearInterval(intervalId);
      return;
    }
    highlightNeuralRun(grid.querySelectorAll(`.${CLASS_NEURAL_DOT}`));
    count++;
  }, NEURAL_TICK_MS);
}

const LOADING_TEXT_INTERVAL_MS = 900;
let msgIdx = 0,
  msgIv;
function animateLoadingText() {
  clearInterval(msgIv);
  msgIdx = 0;
  const el = document.getElementById(ID_LOADING_TEXT);
  msgIv = setInterval(() => {
    if (mode !== MODE_LOADING) {
      clearInterval(msgIv);
      return;
    }
    el.textContent = LOADING_MESSAGES[msgIdx % LOADING_MESSAGES.length];
    msgIdx++;
  }, LOADING_TEXT_INTERVAL_MS);
}

async function requestAnalysis(file) {
  const form = new FormData();
  form.append(IMAGE_FIELD, file);
  const res = await fetch(ANALYZE_ENDPOINT, { method: HTTP_POST, body: form });
  if (!res.ok) throw new Error(HTTP_STATUS_PREFIX + res.status);
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

analyzeBtn.addEventListener(EVENT_CLICK, analyze);

showOnlyState(STATE_KEY_IDLE, DISPLAY_FLEX);
