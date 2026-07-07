// ── Element IDs ────────────────────────────────────────────────────────────
const ID_PARTICLES = "particles";
const ID_DROP_ZONE = "dropZone";
const ID_FILE_INPUT = "fileInput";
const ID_BROWSE_BTN = "browseBtn";
const ID_CLEAR_BTN = "clearBtn";
const ID_LOAD_ANOTHER_BTN = "loadAnotherBtn";
const ID_PREVIEW = "preview";
const ID_PREVIEW_NAME = "previewName";
const ID_PREVIEW_CONTAINER = "preview-container";
const ID_PREVIEW_ACTIONS_CONTAINER = "preview-actions-container";
const ID_DROP_PLACEHOLDER = "drop-placeholder";
const ID_ANALYZE_BTN = "analyzeBtn";
const ID_AI_INDICATOR = "aiIndicator";
const ID_AI_LABEL = "aiLabel";
const ID_NEURAL_GRID = "neuralGrid";
const ID_LOADING_TEXT = "loadingText";
const ID_RESULTS_LIST = "resultsList";
const ID_RESULTS_COUNT = "resultsCount";
const ID_ERROR_MSG = "errorMsg";
const ID_IDLE_STATE = "idleState";
const ID_LOADING_STATE = "loadingState";
const ID_RESULTS_STATE = "resultsState";
const ID_ERROR_STATE = "errorState";
const RESULT_BAR_ID_PREFIX = "bar";

// ── CSS class names ────────────────────────────────────────────────────────
const CLASS_HAS_IMAGE = "has-image";
const CLASS_DRAGOVER = "dragover";
const CLASS_NEURAL_DOT = "neural-dot";
const CLASS_ACTIVE = "active";
const CLASS_RESULT_ITEM = "result-item";

// ── DOM event names ────────────────────────────────────────────────────────
const EVENT_CLICK = "click";
const EVENT_CHANGE = "change";
const EVENT_DRAGOVER = "dragover";
const EVENT_DRAGLEAVE = "dragleave";
const EVENT_DROP = "drop";
const EVENT_PASTE = "paste";
const EVENT_RESIZE = "resize";

// ── CSS display values ─────────────────────────────────────────────────────
const DISPLAY_NONE = "none";
const DISPLAY_BLOCK = "block";
const DISPLAY_FLEX = "flex";

// ── App state modes (particle animation + result panel) ───────────────────
const MODE_IDLE = "idle";
const MODE_LOADING = "loading";
const MODE_DONE = "done";

const STATE_KEY_IDLE = "idle";
const STATE_KEY_LOADING = "loading";
const STATE_KEY_RESULTS = "results";
const STATE_KEY_ERROR = "error";

const STATE_IDS = {
  [STATE_KEY_IDLE]: ID_IDLE_STATE,
  [STATE_KEY_LOADING]: ID_LOADING_STATE,
  [STATE_KEY_RESULTS]: ID_RESULTS_STATE,
  [STATE_KEY_ERROR]: ID_ERROR_STATE,
};

// ── Backend endpoints ───────────────────────────────────────────────────────
const BACKEND_URL = "http://localhost:3001";
const ANALYZE_ENDPOINT = `${BACKEND_URL}/analyze`;
const HEALTH_URL = `${BACKEND_URL}/health`;
const IMAGE_FIELD = "image";
const HTTP_POST = "POST";
const HTTP_STATUS_PREFIX = "HTTP ";

// ── Health indicator status ────────────────────────────────────────────────
const STATUS_CHECKING = "checking";
const STATUS_ONLINE = "online";
const STATUS_OFFLINE = "offline";
const HEALTH_OK = "ok";

const AI_LABELS = {
  checking: "Verificando motor...",
  online: "Motor de IA activo",
  offline: "Motor de IA apagado",
};

// ── Messages ────────────────────────────────────────────────────────────────
const DEFAULT_ERROR_MESSAGE = "Error al conectar con el servidor";
const CONNECTION_ERROR_PREFIX = "No se pudo conectar: ";
const RESULT_LABEL_SINGULAR = " resultado";
const RESULT_LABEL_PLURAL_SUFFIX = "s";

const LOADING_MESSAGES = [
  "Procesando imagen...",
  "Extrayendo características...",
  "Consultando red neuronal...",
  "Clasificando objetos...",
  "Calculando probabilidades...",
  "Casi listo...",
];

// ── Misc formatting ─────────────────────────────────────────────────────────
const IMAGE_MIME_PREFIX = "image/";
const BYTES_PER_KB = 1024;
const KB_DECIMALS = 1;
const FILE_SIZE_UNIT = " KB";
