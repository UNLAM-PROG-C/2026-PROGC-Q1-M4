const HIGH_CONFIDENCE = 70;
const MEDIUM_CONFIDENCE = 40;
const LOW_CONFIDENCE = 20;

const HIGH_BAR = "linear-gradient(90deg, #34d399, #059669)";
const MEDIUM_BAR = "linear-gradient(90deg, #60a5fa, #3b82f6)";
const LOW_BAR = "linear-gradient(90deg, #a78bfa, #7c3aed)";
const MIN_BAR = "linear-gradient(90deg, #f472b6, #db2777)";

const HIGH_TEXT = "#34d399";
const MEDIUM_TEXT = "#60a5fa";
const LOW_TEXT = "#a78bfa";
const MIN_TEXT = "#f472b6";

const MAX_PERCENT = 100;
const PCT_DECIMALS = 1;
const ITEM_ANIM_STEP = 0.07;
const BAR_FILL_BASE_DELAY_MS = 100;
const BAR_FILL_STEP_MS = 70;

function getBarColor(pct) {
  if (pct >= HIGH_CONFIDENCE) return HIGH_BAR;
  if (pct >= MEDIUM_CONFIDENCE) return MEDIUM_BAR;
  if (pct >= LOW_CONFIDENCE) return LOW_BAR;
  return MIN_BAR;
}

function getPctColor(pct) {
  if (pct >= HIGH_CONFIDENCE) return HIGH_TEXT;
  if (pct >= MEDIUM_CONFIDENCE) return MEDIUM_TEXT;
  if (pct >= LOW_CONFIDENCE) return LOW_TEXT;
  return MIN_TEXT;
}

function buildResultItem(item, index, pct) {
  const div = document.createElement("div");
  div.className = "result-item";
  div.style.animationDelay = index * ITEM_ANIM_STEP + "s";
  div.innerHTML = `
      <span class="result-name">${item.name}</span>
      <div class="result-bar-wrap">
        <div class="result-bar" id="bar${index}" style="background: ${getBarColor(pct)}"></div>
      </div>
      <span class="result-pct" style="color:${getPctColor(pct)}">${pct.toFixed(PCT_DECIMALS)}%</span>
    `;
  return div;
}

function animateBarFill(index, pct) {
  setTimeout(() => {
    const bar = document.getElementById("bar" + index);
    if (bar) bar.style.width = Math.min(pct, MAX_PERCENT) + "%";
  }, BAR_FILL_BASE_DELAY_MS + index * BAR_FILL_STEP_MS);
}

function renderResults(data) {
  const list = document.getElementById("resultsList");
  list.innerHTML = "";
  document.getElementById("resultsCount").textContent =
    data.length + " resultado" + (data.length !== 1 ? "s" : "");

  const sorted = [...data].sort((a, b) => b.probability - a.probability);
  sorted.forEach((item, i) => {
    const pct = parseFloat(item.probability);
    list.appendChild(buildResultItem(item, i, pct));
    animateBarFill(i, pct);
  });
}
