const dropZone = document.getElementById(ID_DROP_ZONE);
const fileInput = document.getElementById(ID_FILE_INPUT);
const browseBtn = document.getElementById(ID_BROWSE_BTN);
const clearBtn = document.getElementById(ID_CLEAR_BTN);
const loadAnotherBtn = document.getElementById(ID_LOAD_ANOTHER_BTN);
const preview = document.getElementById(ID_PREVIEW);
const previewName = document.getElementById(ID_PREVIEW_NAME);
const previewContainer = document.getElementById(ID_PREVIEW_CONTAINER);
const previewActions = document.getElementById(ID_PREVIEW_ACTIONS_CONTAINER);
const dropPlaceholder = document.getElementById(ID_DROP_PLACEHOLDER);
const analyzeBtn = document.getElementById(ID_ANALYZE_BTN);

let currentFile = null;

function loadImage(file) {
  if (!file || !file.type.startsWith(IMAGE_MIME_PREFIX)) return;
  currentFile = file;
  preview.src = URL.createObjectURL(file);
  previewName.textContent =
    file.name +
    " (" +
    (file.size / BYTES_PER_KB).toFixed(KB_DECIMALS) +
    FILE_SIZE_UNIT +
    ")";
  dropPlaceholder.style.display = DISPLAY_NONE;
  previewContainer.style.display = DISPLAY_BLOCK;
  previewActions.style.display = DISPLAY_FLEX;
  dropZone.classList.add(CLASS_HAS_IMAGE);
  analyzeBtn.disabled = false;
  showIdle();
}

dropZone.addEventListener(EVENT_CLICK, (e) => {
  if (currentFile) return;
  if (
    e.target === browseBtn ||
    e.target === dropZone ||
    e.target.closest(`#${ID_DROP_PLACEHOLDER}`)
  )
    fileInput.click();
});
browseBtn.addEventListener(EVENT_CLICK, (e) => {
  e.stopPropagation();
  fileInput.click();
});
fileInput.addEventListener(EVENT_CHANGE, () => {
  if (fileInput.files[0]) loadImage(fileInput.files[0]);
});

dropZone.addEventListener(EVENT_DRAGOVER, (e) => {
  e.preventDefault();
  dropZone.classList.add(CLASS_DRAGOVER);
});
dropZone.addEventListener(EVENT_DRAGLEAVE, () =>
  dropZone.classList.remove(CLASS_DRAGOVER),
);
dropZone.addEventListener(EVENT_DROP, (e) => {
  e.preventDefault();
  dropZone.classList.remove(CLASS_DRAGOVER);
  const file = e.dataTransfer.files[0];
  if (file) loadImage(file);
});

clearBtn.addEventListener(EVENT_CLICK, () => {
  currentFile = null;
  preview.src = "";
  fileInput.value = "";
  dropPlaceholder.style.display = DISPLAY_BLOCK;
  previewContainer.style.display = DISPLAY_NONE;
  previewActions.style.display = DISPLAY_NONE;
  dropZone.classList.remove(CLASS_HAS_IMAGE);
  analyzeBtn.disabled = true;
  showIdle();
});

loadAnotherBtn.addEventListener(EVENT_CLICK, () => fileInput.click());

document.addEventListener(EVENT_PASTE, (e) => {
  const items = (e.clipboardData || e.originalEvent.clipboardData).items;
  for (const item of items) {
    if (item.type.startsWith(IMAGE_MIME_PREFIX)) {
      const file = item.getAsFile();
      if (file) loadImage(file);
      break;
    }
  }
});
