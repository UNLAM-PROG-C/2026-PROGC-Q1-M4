const dropZone = document.getElementById("dropZone");
const fileInput = document.getElementById("fileInput");
const browseBtn = document.getElementById("browseBtn");
const clearBtn = document.getElementById("clearBtn");
const loadAnotherBtn = document.getElementById("loadAnotherBtn");
const preview = document.getElementById("preview");
const previewName = document.getElementById("previewName");
const previewContainer = document.getElementById("preview-container");
const previewActions = document.getElementById(
  "preview-actions-container",
);
const dropPlaceholder = document.getElementById("drop-placeholder");
const analyzeBtn = document.getElementById("analyzeBtn");

let currentFile = null;

const IMAGE_MIME_PREFIX = "image/";
const BYTES_PER_KB = 1024;
const KB_DECIMALS = 1;

const DISPLAY_NONE = "none";
const DISPLAY_BLOCK = "block";
const DISPLAY_FLEX = "flex";

function loadImage(file) {
  if (!file || !file.type.startsWith(IMAGE_MIME_PREFIX)) return;
  currentFile = file;
  preview.src = URL.createObjectURL(file);
  previewName.textContent =
    file.name + " (" + (file.size / BYTES_PER_KB).toFixed(KB_DECIMALS) + " KB)";
  dropPlaceholder.style.display = DISPLAY_NONE;
  previewContainer.style.display = DISPLAY_BLOCK;
  previewActions.style.display = DISPLAY_FLEX;
  dropZone.classList.add("has-image");
  analyzeBtn.disabled = false;
  showIdle();
}

dropZone.addEventListener("click", (e) => {
  if (currentFile) return;
  if (
    e.target === browseBtn ||
    e.target === dropZone ||
    e.target.closest("#drop-placeholder")
  )
    fileInput.click();
});
browseBtn.addEventListener("click", (e) => {
  e.stopPropagation();
  fileInput.click();
});
fileInput.addEventListener("change", () => {
  if (fileInput.files[0]) loadImage(fileInput.files[0]);
});

dropZone.addEventListener("dragover", (e) => {
  e.preventDefault();
  dropZone.classList.add("dragover");
});
dropZone.addEventListener("dragleave", () =>
  dropZone.classList.remove("dragover"),
);
dropZone.addEventListener("drop", (e) => {
  e.preventDefault();
  dropZone.classList.remove("dragover");
  const file = e.dataTransfer.files[0];
  if (file) loadImage(file);
});

clearBtn.addEventListener("click", () => {
  currentFile = null;
  preview.src = "";
  fileInput.value = "";
  dropPlaceholder.style.display = DISPLAY_BLOCK;
  previewContainer.style.display = DISPLAY_NONE;
  previewActions.style.display = DISPLAY_NONE;
  dropZone.classList.remove("has-image");
  analyzeBtn.disabled = true;
  showIdle();
});

loadAnotherBtn.addEventListener("click", () => fileInput.click());

document.addEventListener("paste", (e) => {
  const items = (e.clipboardData || e.originalEvent.clipboardData).items;
  for (const item of items) {
    if (item.type.startsWith(IMAGE_MIME_PREFIX)) {
      const file = item.getAsFile();
      if (file) loadImage(file);
      break;
    }
  }
});
