const API_BASE = window.location.origin;

const UI_COPY = {
  "pt-BR": {
    responseMode: "Modo de resposta", modeQuick: "Rápido", modeComplete: "Completo",
    modeQuickHint: "Um guia · prioriza velocidade",
    modeCompleteHint: "Guias relacionados · pode demorar mais",
    expandMode: "Quer incluir os pré-requisitos e guias relacionados?",
    useComplete: "Usar Completo",
    requestCancel: "Cancelar resposta",
    requestCancelled: "Resposta cancelada.",
    pageTitle: "Kronochat — Black Ops III Zombies",
    availableMaps: "Mapas disponíveis",
    library: "Base de conhecimento",
    checkingBase: "Verificando base",
    clearChat: "Nova conversa",
    openMaps: "Abrir mapas",
    closeMaps: "Fechar menu",
    close: "Fechar",
    activeContext: "Contexto ativo",
    allMaps: "Todos os mapas",
    allMapsHint: "Deixe o assunto identificar o mapa",
    searchingAll: "Busca em todos os mapas",
    searchingMap: "Buscando apenas em {map}",
    stats: "{chunks} trechos · {images} imagens",
    mapMeta: "{documents} guias · {images} imagens",
    healthy: "Base e IA prontas",
    baseOnly: "Base pronta · configure a IA",
    inconsistent: "Base com inconsistências",
    apiOffline: "API offline",
    mapsLoadError: "Não foi possível carregar os mapas.",
    requestError: "Não foi possível responder agora.",
    requestProcessing: "Preparando a resposta… {seconds}s",
    requestStarting: "Recebendo sua pergunta…",
    requestUnderstanding: "Entendendo sua pergunta…",
    requestSearching: "Consultando os guias…",
    requestPlanning: "Organizando as etapas e os pré-requisitos…",
    requestGenerating: "Gerando a resposta…",
    requestReviewing: "Conferindo a resposta…",
    requestFinalizing: "Organizando o texto e as imagens…",
    requestElapsed: "Tempo decorrido: {seconds}s",
    requestConnectionError: "A conexão falhou. Tente novamente.",
    requestExpired: "A resposta não terminou no prazo de espera. Tente novamente.",
    welcomeEyebrow: "Krono está online",
    welcomeTitle: "Seu próximo passo começa aqui.",
    welcomeCopy: "Pergunte sobre o mapa, uma peça ou um Easter Egg.",
    quickPap: "Liberar Pack-a-Punch",
    quickPapPrompt: "Como eu libero o Pack-a-Punch?",
    quickEe: "Easter Egg principal",
    quickEePrompt: "Como faço o Easter Egg principal?",
    quickShield: "Montar o escudo",
    quickShieldPrompt: "Como monto o escudo?",
    placeholder: "Escreva sua pergunta…",
    send: "Enviar",
    composerHint: "Enter envia · Shift + Enter quebra a linha",
    conversation: "Conversa",
    you: "Você",
    source: "fonte da base",
    sources: "fontes da base",
    switchEyebrow: "Outro mapa detectado",
    switchTitle: "Esta pergunta parece ser sobre {requested}.",
    switchCopy: "A conversa atual está no contexto de {current}. Deseja iniciar uma nova conversa em {requested}?",
    switchConfirm: "Ir para {requested}",
    switchContinue: "Continuar em {current}",
    staying: "Certo — continuamos em {current}.",
    guideRoadmap: "Roteiro do Easter Egg", guideFullTitle: "Guia completo",
    guideStart: "Começar do início", guideComplete: "Concluí esta fase",
    guideOverview: "Ver roteiro", guideFull: "Ver guia completo", guideStop: "Encerrar acompanhamento",
    guidePhase: "Fase {current} de {total}", guideFinished: "Última fase concluída",
    guideJump: "Ir para uma fase", guidePlayers: "Jogadores", guideUnknown: "Não informado",
    guideSolo: "Solo", guideHelp: "Estou com dificuldade nesta fase.",
    guideHelpButton: "Estou com dificuldade", imageLimit: "Há mais imagens nesta etapa. Consulte a fase separadamente.",
    imageUnavailable: "Imagem indisponível", imageOpen: "Ampliar imagem: {caption}"
  },
  en: {
    responseMode: "Response mode", modeQuick: "Quick", modeComplete: "Complete",
    modeQuickHint: "One guide · prioritizes speed",
    modeCompleteHint: "Related guides · may take longer",
    expandMode: "Want to include prerequisites and related guides?",
    useComplete: "Use Complete",
    requestCancel: "Cancel answer",
    requestCancelled: "Answer cancelled.",
    pageTitle: "Kronochat — Black Ops III Zombies",
    availableMaps: "Available maps",
    library: "Knowledge base",
    checkingBase: "Checking knowledge base",
    clearChat: "New conversation",
    openMaps: "Open maps",
    closeMaps: "Close menu",
    close: "Close",
    activeContext: "Active context",
    allMaps: "All maps",
    allMapsHint: "Let the question identify the map",
    searchingAll: "Searching all maps",
    searchingMap: "Searching only {map}",
    stats: "{chunks} passages · {images} images",
    mapMeta: "{documents} guides · {images} images",
    healthy: "Knowledge base and AI ready",
    baseOnly: "Knowledge base ready · configure AI",
    inconsistent: "Knowledge base has inconsistencies",
    apiOffline: "API offline",
    mapsLoadError: "The maps could not be loaded.",
    requestError: "Krono could not answer right now.",
    requestProcessing: "Preparing the answer… {seconds}s",
    requestStarting: "Receiving your question…",
    requestUnderstanding: "Understanding your question…",
    requestSearching: "Consulting the guides…",
    requestPlanning: "Organizing the steps and prerequisites…",
    requestGenerating: "Generating the answer…",
    requestReviewing: "Reviewing the answer…",
    requestFinalizing: "Arranging the text and images…",
    requestElapsed: "Elapsed time: {seconds}s",
    requestConnectionError: "The connection failed. Please try again.",
    requestExpired: "The answer did not finish within the time limit. Please try again.",
    welcomeEyebrow: "Krono is online",
    welcomeTitle: "Your next step starts here.",
    welcomeCopy: "Ask about a map, a part, or an Easter Egg.",
    quickPap: "Unlock Pack-a-Punch",
    quickPapPrompt: "How do I unlock Pack-a-Punch?",
    quickEe: "Main Easter Egg",
    quickEePrompt: "How do I complete the main Easter Egg?",
    quickShield: "Build the shield",
    quickShieldPrompt: "How do I build the shield?",
    placeholder: "Ask about the map…",
    send: "Send",
    composerHint: "Enter sends · Shift + Enter adds a line",
    conversation: "Conversation",
    you: "You",
    source: "knowledge-base source",
    sources: "knowledge-base sources",
    switchEyebrow: "Another map detected",
    switchTitle: "This question appears to be about {requested}.",
    switchCopy: "Your current conversation is scoped to {current}. Start a new conversation in {requested}?",
    switchConfirm: "Go to {requested}",
    switchContinue: "Stay in {current}",
    staying: "Got it — we will stay in {current}.",
    guideRoadmap: "Easter Egg roadmap", guideFullTitle: "Full guide",
    guideStart: "Start from the beginning", guideComplete: "I completed this phase",
    guideOverview: "View roadmap", guideFull: "View full guide", guideStop: "Stop tracking",
    guidePhase: "Phase {current} of {total}", guideFinished: "Final phase completed",
    guideJump: "Go to a phase", guidePlayers: "Players", guideUnknown: "Not specified",
    guideSolo: "Solo", guideHelp: "I need help with this phase.",
    guideHelpButton: "I need help", imageLimit: "More images belong to this step. Open the phase separately.",
    imageUnavailable: "Image unavailable", imageOpen: "Enlarge image: {caption}"
  }
};

function resolveUiLocale() {
  const requestedLocale = new URLSearchParams(window.location.search).get("lang");
  if (requestedLocale) {
    const requestedBase = requestedLocale.toLowerCase().split("-")[0];
    if (requestedBase === "pt") return "pt-BR";
    if (requestedBase === "en") return "en";
  }

  const languages = navigator.languages?.length
    ? navigator.languages
    : [navigator.language || "en"];
  for (const language of languages) {
    const base = language.toLowerCase().split("-")[0];
    if (base === "pt") return "pt-BR";
    if (base === "en") return "en";
  }
  return "en";
}

const UI_LOCALE = resolveUiLocale();

function t(key, values = {}) {
  let text = UI_COPY[UI_LOCALE][key] || UI_COPY.en[key] || key;
  for (const [name, value] of Object.entries(values)) {
    text = text.replaceAll(`{${name}}`, String(value));
  }
  return text;
}

const elements = {
  sidebar: document.getElementById("history-dialog"),
  menuToggle: document.getElementById("history-open"),
  activeMapLabel: document.getElementById("active-map-label"),
  systemStatus: document.getElementById("system-status"),
  clearChat: document.getElementById("clear-chat"),
  welcome: document.getElementById("welcome"),
  quickPrompts: document.getElementById("quick-prompts"),
  chat: document.getElementById("chat"),
  form: document.getElementById("chat-form"),
  input: document.getElementById("message-input"),
  responseMode: document.getElementById("response-mode"),
  sendButton: document.getElementById("send-btn"),
  cancelButton: document.getElementById("cancel-btn"),
  characterCount: document.getElementById("character-count"),
  imageModal: document.getElementById("image-modal"),
  modalImage: document.getElementById("modal-image"),
  modalCaption: document.getElementById("modal-caption"),
  modalClose: document.getElementById("modal-close"),
  mapSwitchModal: document.getElementById("map-switch-modal"),
  mapSwitchEyebrow: document.getElementById("map-switch-eyebrow"),
  mapSwitchTitle: document.getElementById("map-switch-title"),
  mapSwitchCopy: document.getElementById("map-switch-copy"),
  mapSwitchContinue: document.getElementById("map-switch-continue"),
  mapSwitchConfirm: document.getElementById("map-switch-confirm")
};

const state = {
  maps: [],
  activeMapId: null,
  history: [],
  pending: false,
  pendingMapSwitch: null,
  requestAbort: null,
  guide: null,
  responseMode: "quick"
};

function applyUiLocale() {
  document.documentElement.lang = UI_LOCALE;
  document.title = t("pageTitle");
  elements.modalClose.setAttribute("aria-label", t("close"));
  elements.chat.setAttribute("aria-label", t("conversation"));
  document.getElementById("system-status-label").textContent = t("checkingBase");
  document.getElementById("clear-chat-label").textContent = t("clearChat");
  document.getElementById("welcome-title").innerHTML = t("welcomeTitle");
  document.getElementById("welcome-copy").textContent = t("welcomeCopy");
  elements.input.placeholder = t("placeholder");
  elements.responseMode.options[0].textContent = t("modeQuick");
  elements.responseMode.options[1].textContent = t("modeComplete");
  updateResponseMode();
  elements.sendButton.setAttribute("aria-label", t("send"));
  elements.cancelButton.textContent = t("requestCancel");
  elements.mapSwitchEyebrow.textContent = t("switchEyebrow");
  elements.activeMapLabel.textContent = "";
  elements.input.setAttribute("aria-label", UI_LOCALE === "pt-BR" ? "Mensagem" : "Message");
  document.querySelector(".conversation-menu summary").setAttribute("aria-label", UI_LOCALE === "pt-BR" ? "Opções da conversa" : "Conversation options");
  document.getElementById("image-previous").setAttribute("aria-label", UI_LOCALE === "pt-BR" ? "Imagem anterior" : "Previous image");
  document.getElementById("image-next").setAttribute("aria-label", UI_LOCALE === "pt-BR" ? "Próxima imagem" : "Next image");
  document.querySelector(".response-mode-menu summary").setAttribute("aria-label", t("responseMode"));
  document.getElementById("mode-quick-hint").textContent = t("modeQuickHint");
  document.getElementById("mode-complete-hint").textContent = t("modeCompleteHint");
  document.querySelectorAll("[data-response-mode] strong").forEach((label, i) => label.textContent = t(i ? "modeComplete" : "modeQuick"));

  const prompts = [
    ["quickPap", "quickPapPrompt"],
    ["quickEe", "quickEePrompt"],
    ["quickShield", "quickShieldPrompt"]
  ];
  [...elements.quickPrompts.querySelectorAll("button")].forEach((button, index) => {
    const [labelKey, promptKey] = prompts[index];
    button.textContent = t(labelKey);
    button.dataset.prompt = t(promptKey);
  });
}

function updateResponseMode(value = state.responseMode) {
  state.responseMode = value === "complete" ? "complete" : "quick";
  elements.responseMode.value = state.responseMode;
  document.getElementById("response-mode-label").textContent = t(state.responseMode === "complete" ? "modeComplete" : "modeQuick");
  for (const button of document.querySelectorAll("[data-response-mode]")) button.setAttribute("aria-pressed", String(button.dataset.responseMode === state.responseMode));
  document.getElementById("response-mode-description").textContent =
    t(state.responseMode === "complete" ? "modeCompleteHint" : "modeQuickHint");
}

function chooseResponseMode(value) {
  updateResponseMode(value);
  try { localStorage.setItem("krono.responseMode.v1", state.responseMode); } catch {}
}

function getMap(mapId) {
  return state.maps.find(map => map.map_id === mapId) || null;
}

function mediaUrl(imageId, variant = "thumb") {
  return `${API_BASE}/media/${encodeURIComponent(imageId)}?variant=${variant}`;
}

function imageVariantUrl(image, variant = "thumb") {
  if (variant === "full" && image?.full_url) return image.full_url;
  if (variant === "thumb" && image?.thumbnail_url) return image.thumbnail_url;
  return mediaUrl(image.id, variant);
}

function setSidebarOpen(open) {
  if (open) return historyUI.show();
  elements.sidebar.close();
  elements.menuToggle.setAttribute("aria-expanded", "false");
}

function selectMap(mapId, { focus = true, persist = true } = {}) {
  if (companionUI.active && mapId !== companionUI.matchState?.map_id) companionUI.leave();
  state.activeMapId = mapId || null;
  if (state.guide && state.guide.state.map_id !== state.activeMapId) {
    state.guide = null;
    renderGuideControls();
  }
  const selectedMap = getMap(state.activeMapId);
  elements.activeMapLabel.textContent = selectedMap?.display_name || "";
  elements.activeMapLabel.hidden = !selectedMap;

  if (persist && historyUI?.meta && historyUI.meta.mapId !== state.activeMapId) {
    historyUI.write({mapId: state.activeMapId}).catch(() => {});
  }
  setSidebarOpen(false);
  if (focus) KronoViewport.focusInput(elements.input);
}

function createSourceDetails(sources) {
  if (!sources?.length) return null;

  const details = document.createElement("details");
  details.className = "message-sources";
  const summary = document.createElement("summary");
  const uniqueFiles = new Set(sources.map(source => `${source.map_id}/${source.path}`));
  summary.textContent = `${uniqueFiles.size} ${t(uniqueFiles.size === 1 ? "source" : "sources")}`;
  details.appendChild(summary);

  const list = document.createElement("div");
  list.className = "source-list";
  for (const source of sources) {
    const item = document.createElement("span");
    item.textContent = `${source.map_name} · ${source.path} · ${source.section}`;
    list.appendChild(item);
  }
  details.appendChild(list);
  return details;
}

function createImageGallery(images, { inline = false } = {}) {
  if (!images?.length) return null;

  const gallery = document.createElement("div");
  gallery.className = inline ? "message-images step-images" : "message-images";
  for (const [index, image] of images.entries()) {
    const figure = document.createElement("figure");
    const img = document.createElement("img");
    img.src = imageVariantUrl(image, "thumb");
    img.alt = image.caption;
    img.loading = "lazy";
    img.decoding = "async";

    const caption = document.createElement("figcaption");
    caption.textContent = String(index + 1);

    figure.append(img, caption);
    figure.tabIndex = 0;
    figure.setAttribute("role", "button");
    figure.setAttribute("aria-label", t("imageOpen", { caption: image.caption }));
    figure.addEventListener("click", () => openImage(image, images, index));
    figure.addEventListener("keydown", event => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        openImage(image, images, index);
      }
    });
    img.addEventListener("error", () => {
      figure.classList.add("image-unavailable");
      caption.textContent = t("imageUnavailable");
    }, { once: true });
    gallery.appendChild(figure);
  }
  gallery.classList.toggle("many-images", images.length > 3);
  return gallery;
}

function createAnswerStep(block) {
  const section = document.createElement("section");
  section.className = "answer-step";
  if (block.title) {
    const title = document.createElement("h3");
    title.textContent = block.title;
    section.appendChild(title);
  }
  const copy = document.createElement("div");
  copy.className = "step-copy";
  copy.innerHTML = renderMarkdown(block.body);
  section.appendChild(copy);
  const images = createImageGallery(block.images, { inline: true });
  if (images) section.appendChild(images);
  if (block.available_image_count > block.images.length) {
    const notice = document.createElement("p");
    notice.className = "image-limit-note";
    notice.textContent = t("imageLimit");
    section.appendChild(notice);
  }
  return section;
}

function addMessage(role, text, options = {}) {
  elements.welcome.hidden = true;

  const article = document.createElement("article");
  article.className = `message ${role}`;
  if (options.error) article.classList.add("error");
  if (options.clarification) article.classList.add("clarification");

  const header = document.createElement("header");
  header.innerHTML = role === "user"
    ? `<span>${t("you")}</span>`
    : `<span>Krono</span><span class="field-notes">/ ${UI_LOCALE === "pt-BR" ? "Notas de campo" : "Field notes"}</span>`;

  const body = document.createElement("div");
  body.className = "message-body";
  if (role === "assistant") {
    body.innerHTML = renderMarkdown(options.blocks?.length ? options.introduction || "" : text);
    for (const block of options.blocks || []) {
      body.appendChild(createAnswerStep(block));
    }
  } else {
    body.textContent = text;
  }

  article.append(header, body);

  const gallery = options.blocks?.length ? null : createImageGallery(options.images);
  if (gallery) article.appendChild(gallery);

  const sources = createSourceDetails(options.sources);
  if (sources) article.appendChild(sources);

  if (options.suggestedMapIds?.length) {
    const suggestions = document.createElement("div");
    suggestions.className = "map-suggestions";
    const order = state.maps.map(map => map.map_id);
    for (const mapId of [...options.suggestedMapIds].sort((a, b) => order.indexOf(a) - order.indexOf(b))) {
      const map = getMap(mapId);
      if (!map) continue;
      const button = document.createElement("button");
      button.type = "button";
      button.textContent = map.display_name;
      button.addEventListener("click", () => {
        selectMap(mapId);
        if (options.retryMessage) {
          submitMessage(options.retryMessage, { echoUser: false });
        }
      });
      suggestions.appendChild(button);
    }
    article.appendChild(suggestions);
  }

  if (options.suggestedQueries?.length) {
    const suggestions = document.createElement("div");
    suggestions.className = "map-suggestions";
    for (const query of options.suggestedQueries) {
      const button = document.createElement("button");
      button.type = "button";
      button.textContent = query;
      button.addEventListener("click", () => submitMessage(query));
      suggestions.appendChild(button);
    }
    article.appendChild(suggestions);
  }

  elements.chat.appendChild(article);
  while (elements.chat.querySelectorAll(".message:not(.typing-message)").length > 30) {
    elements.chat.querySelector(".message:not(.typing-message)").remove();
  }
  if (options.persist !== false && historyUI?.meta) {
    historyUI.append(transcriptRow(role, text, options, !options.error));
  }
  if (role === "assistant") {
    scrollMessageToStart(article);
  } else {
    scrollToBottom();
  }
  return article;
}

function addTypingIndicator() {
  const article = document.createElement("article");
  article.className = "message assistant typing-message";
  article.innerHTML = `
    <header><span>Krono</span></header>
    <p class="request-status" role="status" aria-live="polite">${t("requestStarting")}</p>
    <p class="request-elapsed"></p>
  `;
  elements.chat.appendChild(article);
  scrollToBottom();
  return article;
}

function scrollToBottom() {
  requestAnimationFrame(() => {
    elements.chat.scrollTop = elements.chat.scrollHeight;
  });
}

function scrollMessageToStart(article) {
  requestAnimationFrame(() => {
    const chatRect = elements.chat.getBoundingClientRect();
    const messageRect = article.getBoundingClientRect();
    elements.chat.scrollTo({
      top: elements.chat.scrollTop + messageRect.top - chatRect.top - 8,
      behavior: "smooth"
    });
  });
}

let imageGroup = [], imagePosition = 0;
function openImage(image, group = [image], position = 0) {
  imageGroup = group; imagePosition = position;
  showImage();
  if (!elements.imageModal.open) elements.imageModal.showModal();
}
function showImage() {
  const image = imageGroup[imagePosition];
  elements.modalImage.src = imageVariantUrl(image, "full");
  elements.modalImage.alt = image.caption || "";
  elements.modalCaption.textContent = `${getMap(image.map_id)?.display_name || image.map_id} · ${imagePosition + 1} / ${imageGroup.length}`;
  document.getElementById("image-previous").disabled = imagePosition === 0;
  document.getElementById("image-next").disabled = imagePosition === imageGroup.length - 1;
  document.querySelector(".image-navigation").hidden = imageGroup.length < 2;
}
function moveImage(direction) {
  const next = imagePosition + direction;
  if (next < 0 || next >= imageGroup.length) return;
  imagePosition = next; showImage();
}
function closeImage() { elements.imageModal.close(); }
elements.imageModal.addEventListener("close", () => { elements.modalImage.removeAttribute("src"); imageGroup = []; });
document.getElementById("image-previous").onclick = () => moveImage(-1);
document.getElementById("image-next").onclick = () => moveImage(1);
elements.imageModal.addEventListener("keydown", event => {
  if (event.key === "ArrowLeft" || event.key === "ArrowRight") { event.preventDefault(); moveImage(event.key === "ArrowLeft" ? -1 : 1); }
});

function setPending(pending) {
  state.pending = pending;
  elements.input.disabled = pending;
  elements.responseMode.disabled = pending;
  for (const button of document.querySelectorAll("[data-response-mode]")) button.disabled = pending;
  if (pending) document.getElementById("response-mode-menu").open = false;
  elements.sendButton.disabled = pending;
  elements.sendButton.hidden = pending;
  elements.cancelButton.hidden = !pending;
  elements.sendButton.classList.toggle("pending", pending);
  for (const control of document.querySelectorAll("#guide-controls button, #guide-controls select")) {
    control.disabled = pending;
  }
}

function resetComposer() {
  elements.input.value = "";
  elements.input.style.height = "auto";
  elements.characterCount.textContent = "0 / 2000";
  elements.characterCount.classList.remove("near-limit");
}

async function requestJson(path, options = {}, signal = null) {
  const { timeoutMs = 20000, ...fetchOptions } = options;
  if (signal?.aborted) throw new DOMException("Cancelled", "AbortError");
  const controller = new AbortController();
  const abort = () => controller.abort();
  signal?.addEventListener("abort", abort, { once: true });
  const timeout = setTimeout(abort, timeoutMs);
  try {
    const response = await fetch(`${API_BASE}${path}`, { ...fetchOptions, signal: controller.signal });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) {
      const error = new Error(payload.detail || t("requestError"));
      error.httpStatus = response.status;
      throw error;
    }
    return payload;
  } catch (error) {
    if (signal?.aborted) throw new DOMException("Cancelled", "AbortError");
    if (error.httpStatus) throw error;
    const connectionError = new Error(t("requestConnectionError"));
    connectionError.transient = true;
    throw connectionError;
  } finally {
    clearTimeout(timeout);
    signal?.removeEventListener("abort", abort);
  }
}

async function sendMessage(message, {
  guideAction = null, guidePhase = null, signal = null, onProgress = () => {}
} = {}) {
  let job = await requestJson("/chat/jobs", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      message,
      response_mode: state.responseMode,
      guide_state: null,
      match_state: !state.activeMapId || companionUI.matchState?.map_id === state.activeMapId
        ? companionUI.matchState : null,
      guide_action: guideAction,
      guide_phase: guidePhase,
      conversation_history: state.history.slice(-10),
      active_map_id: state.activeMapId,
      preferred_language: navigator.languages?.[0] || navigator.language || "pt-BR"
    })
  }, signal);
  return pollJob(job, signal, onProgress);
}

async function pollJob(job, signal, onProgress = () => {}) {
  if (!job.job_id) throw new Error(t("requestError"));
  const jobId = job.job_id;
  const started = Date.now();
  let failures = 0;
  let completed = false;
  try {
    while (Date.now() - started < 660000) {
      if (signal?.aborted) throw new DOMException("Cancelled", "AbortError");
      onProgress(job);
      if (job.state === "completed" && job.response) {
        completed = true;
        return job.response;
      }
      if (job.state === "failed") throw new Error(job.error || t("requestError"));
      if (job.state !== "pending") throw new Error(t("requestError"));
      await new Promise(resolve => setTimeout(resolve, 1500));
      try {
        job = await requestJson(`/chat/jobs/${encodeURIComponent(jobId)}`, {}, signal);
        failures = 0;
      } catch (error) {
        if (!error.transient || ++failures >= 3) throw error;
      }
    }
    throw new Error(t("requestExpired"));
  } finally {
    if (!completed) {
      fetch(`${API_BASE}/chat/jobs/${encodeURIComponent(jobId)}`, {
        method: "DELETE", keepalive: true
      }).catch(() => {});
    }
  }
}

function removePendingMessageFromHistory(message) {
  const lastMessage = state.history.at(-1);
  if (lastMessage?.role === "user" && lastMessage.content === message) {
    state.history.pop();
  }
}

function openMapSwitchModal(action, message) {
  const currentMap = getMap(action.current_map_id);
  const requestedMap = getMap(action.requested_map_id);
  if (!currentMap || !requestedMap) return false;

  state.pendingMapSwitch = { action, message };
  const names = {
    current: currentMap.display_name,
    requested: requestedMap.display_name
  };
  elements.mapSwitchTitle.textContent = t("switchTitle", names);
  elements.mapSwitchCopy.textContent = t("switchCopy", names);
  elements.mapSwitchContinue.textContent = t("switchContinue", names);
  elements.mapSwitchConfirm.textContent = t("switchConfirm", names);
  elements.mapSwitchModal.showModal();
  elements.mapSwitchConfirm.focus();
  return true;
}

function continueCurrentMap() {
  const pending = state.pendingMapSwitch;
  if (!pending) return;
  const currentMap = getMap(pending.action.current_map_id);
  removePendingMessageFromHistory(pending.message);
  elements.mapSwitchModal.close();
  state.pendingMapSwitch = null;
  if (currentMap) {
    const notice = t("staying", { current: currentMap.display_name });
    addMessage("assistant", notice, { clarification: true });
    state.history.push({ role: "assistant", content: notice });
  }
  KronoViewport.focusInput(elements.input);
}

async function confirmMapSwitch() {
  const pending = state.pendingMapSwitch;
  if (!pending) return;
  elements.mapSwitchModal.close();
  state.pendingMapSwitch = null;
  if (!await clearConversation()) return;
  selectMap(pending.action.requested_map_id, { focus: false });
  submitMessage(pending.message);
}

async function submitMessage(message, { echoUser = true, guideAction = null, guidePhase = null } = {}) {
  const cleanMessage = message.trim();
  if (!cleanMessage || state.pending || !historyUI.meta || historyUI.switching) return;
  if (historyUI.pageBefore !== null) await historyUI.latest();
  state.history = state.history.slice(-10);

  if (echoUser) {
    addMessage("user", cleanMessage);
    state.history.push({ role: "user", content: cleanMessage });
  }
  resetComposer();
  setPending(true);
  const typing = addTypingIndicator();
  const requestAbort = new AbortController();
  state.requestAbort = requestAbort;

  try {
    const response = await sendMessage(cleanMessage, {
      guideAction, guidePhase, signal: requestAbort.signal,
      onProgress: job => {
        if (state.requestAbort !== requestAbort || requestAbort.signal.aborted) return;
        const keys = {
          starting: "requestStarting", understanding: "requestUnderstanding",
          searching: "requestSearching", planning: "requestPlanning",
          generating: "requestGenerating", reviewing: "requestReviewing",
          finalizing: "requestFinalizing"
        };
        const status = typing.querySelector(".request-status");
        const label = keys[job.phase] ? t(keys[job.phase]) : t("requestProcessing", {
          seconds: job.elapsed_seconds
        });
        if (status.textContent !== label) status.textContent = label;
        typing.querySelector(".request-elapsed").textContent = job.elapsed_seconds >= 10
          ? t("requestElapsed", { seconds: job.elapsed_seconds }) : "";
      }
    });
    if (requestAbort.signal.aborted) return;
    typing.remove();

    if (response.map_switch && openMapSwitchModal(response.map_switch, cleanMessage)) {
      return;
    }

    if (response.active_map_id) {
      selectMap(response.active_map_id, { focus: false });
    }

    if (response.need_clarification) {
      addMessage("assistant", response.clarification_question, {
        clarification: true,
        suggestedMapIds: response.suggested_map_ids,
        suggestedQueries: response.suggested_queries,
        retryMessage: cleanMessage
      });
      state.history.push({
        role: "assistant",
        content: response.clarification_question
      });
    } else {
      const article = addMessage("assistant", response.answer, {
        images: response.relevant_images,
        blocks: response.blocks,
        introduction: response.introduction,
        sources: response.sources
      });
      if (response.offer_complete) {
        const offer = document.createElement("div");
        offer.className = "response-mode-offer";
        const copy = document.createElement("p"); copy.textContent = t("expandMode");
        const button = document.createElement("button"); button.type = "button";
        button.className = "ghost-button"; button.textContent = t("useComplete");
        button.addEventListener("click", () => {
          if (state.pending) return;
          chooseResponseMode("complete");
          submitMessage(cleanMessage, { echoUser: false });
        });
        offer.append(copy, button); article.appendChild(offer);
      }
      state.history.push({
        role: "assistant",
        content: response.answer.slice(0, 12000),
        source_paths: [...new Set(response.sources.map(source => source.path))]
      });
    }
    companionUI.offer(response.companion_offer_map_id,
      response.guide?.state.language || response.response_language);
  } catch (error) {
    typing.remove();
    if (state.requestAbort !== requestAbort) return;
    removePendingMessageFromHistory(cleanMessage);
    const cancelled = requestAbort.signal.aborted;
    const detail = cancelled ? t("requestCancelled") : error.message;
    if (!cancelled || requestAbort.signal.reason === "user-cancel") {
      addMessage("assistant", detail, { error: !cancelled });
    }
  } finally {
    if (state.requestAbort === requestAbort) {
      state.requestAbort = null;
      setPending(false);
      if (!elements.mapSwitchModal.open) KronoViewport.focusInput(elements.input);
    }
  }
}

function renderGuideControls() {
  document.getElementById("guide-controls")?.remove();
}

async function clearConversation() {
  return historyUI.newConversation();
}

function resetConversationView() {
  resetComposer();
  companionUI.offered.clear();
  if (companionUI.active) companionUI.leave({notify: false});
  state.requestAbort?.abort();
  state.requestAbort = null;
  setPending(false);
  state.history = [];
  state.guide = null;
  renderGuideControls();
  elements.chat.replaceChildren();
  elements.welcome.hidden = false;
  closeImage();
  selectMap(null, { focus: false, persist: false });
}

function autoResizeComposer() {
  elements.input.style.height = "auto";
  elements.input.style.height = `${Math.min(elements.input.scrollHeight, 160)}px`;
  elements.characterCount.textContent = `${elements.input.value.length} / 2000`;
  elements.characterCount.classList.toggle("near-limit", elements.input.value.length >= 1800);
}

async function loadApplication() {
  try {
    const [healthResponse, mapsResponse] = await Promise.all([
      fetch(`${API_BASE}/health`),
      fetch(`${API_BASE}/maps`)
    ]);
    if (!healthResponse.ok || !mapsResponse.ok) throw new Error("API unavailable");

    const health = await healthResponse.json();
    state.maps = await mapsResponse.json();

    const healthy = health.status === "ok";
    elements.systemStatus.hidden = healthy && health.llm_configured;
    elements.systemStatus.classList.toggle("error", !healthy);
    elements.systemStatus.querySelector("span:last-child").textContent = healthy
      ? health.llm_configured ? t("healthy") : t("baseOnly")
      : t("inconsistent");
  } catch {
    elements.systemStatus.hidden = false;
    elements.systemStatus.classList.add("error");
    elements.systemStatus.querySelector("span:last-child").textContent = t("apiOffline");
  }
}

elements.form.addEventListener("submit", event => {
  event.preventDefault();
  submitMessage(elements.input.value);
});

elements.input.addEventListener("keydown", event => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    elements.form.requestSubmit();
  }
});

elements.input.addEventListener("input", autoResizeComposer);
elements.quickPrompts.addEventListener("click", event => {
  const button = event.target.closest("[data-prompt]");
  if (button) submitMessage(button.dataset.prompt);
});
elements.clearChat.addEventListener("click", clearConversation);
elements.cancelButton.addEventListener("click", () => state.requestAbort?.abort("user-cancel"));
elements.modalClose.addEventListener("click", closeImage);
elements.imageModal.addEventListener("click", event => {
  if (event.target === elements.imageModal) closeImage();
});
elements.mapSwitchContinue.addEventListener("click", continueCurrentMap);
elements.mapSwitchConfirm.addEventListener("click", confirmMapSwitch);
elements.mapSwitchModal.addEventListener("cancel", event => {
  event.preventDefault();
  continueCurrentMap();
});
elements.mapSwitchModal.addEventListener("click", event => {
  if (event.target === elements.mapSwitchModal) continueCurrentMap();
});

const companionUI = new CompanionUI({
  locale: UI_LOCALE,
  language: navigator.languages?.[0] || navigator.language || "pt-BR",
  requestJson, pollJob,
  cachedAnswer: match => historyUI.cachedAnswer(match),
  saveMatch: async (match, rows) => { await historyUI.write({match}, rows); },
  onOffered: offered => historyUI.write({offered}).catch(() => {}),
  onLeave: async () => { await historyUI.flush(); await historyUI.latest(); },
  record: (role, text, options = {}, context = true) => historyUI.write({}, [transcriptRow(role, text, options, context)]),
  selectMap: mapId => selectMap(mapId, {focus: false}),
  cancelChat: () => {
    if (state.pending && state.history.at(-1)?.role === "user") state.history.pop();
    state.requestAbort?.abort(); state.requestAbort = null; setPending(false);
  },
  notice: text => addMessage("assistant", text, {error: true}),
  renderAnswer: (container, response) => {
    container.replaceChildren();
    const intro = document.createElement("div");
    intro.innerHTML = renderMarkdown(response.need_clarification
      ? response.clarification_question : response.blocks?.length ? response.introduction || "" : response.answer);
    container.appendChild(intro);
    for (const block of response.blocks || []) container.appendChild(createAnswerStep(block));
    const sources = createSourceDetails(response.sources);
    if (sources) container.appendChild(sources);
  }
});

const historyUI = new ConversationHistory({
  locale: UI_LOCALE,
  cancel: () => {
    state.requestAbort?.abort(); state.requestAbort = null; setPending(false);
    companionUI.leave({notify: false});
  },
  reset: resetConversationView,
  setMatch: (match, offered) => companionUI.setMatch(match, offered),
  selectMap: mapId => selectMap(mapId, {focus: false, persist: false}),
  setContext: messages => { state.history = messages; },
  renderRows: (rows, pager) => {
    elements.chat.replaceChildren(); elements.welcome.hidden = !!rows.length;
    const navigation = document.createElement("div"); navigation.className = "history-pagination";
    for (const [action, label] of [[pager.older, pager.copy.older], [pager.latest, pager.copy.latest]]) {
      if (!action) continue;
      const button = document.createElement("button"); button.type = "button";
      button.className = "ghost-button"; button.textContent = label; button.onclick = action;
      navigation.appendChild(button);
    }
    elements.chat.appendChild(navigation);
    for (const row of rows) addMessage(row.role, row.text, {...row.options, persist: false});
    if (rows.length) scrollMessageToStart(pager.latest ? elements.chat.querySelector(".message") : elements.chat.querySelector(".message:last-child"));
  },
});

try { updateResponseMode(localStorage.getItem("krono.responseMode.v1")); } catch {}
elements.responseMode.addEventListener("change", () => chooseResponseMode(elements.responseMode.value));
for (const button of document.querySelectorAll("[data-response-mode]")) button.addEventListener("click", () => {
  if (state.pending) return;
  chooseResponseMode(button.dataset.responseMode);
  document.getElementById("response-mode-menu").open = false;
});
for (const menu of document.querySelectorAll(".conversation-menu, .response-mode-menu")) {
  document.addEventListener("click", event => { if (!menu.contains(event.target)) menu.open = false; });
  menu.addEventListener("keydown", event => { if (event.key === "Escape") { menu.open = false; menu.querySelector("summary").focus(); } });
}
applyUiLocale();
elements.input.disabled = true; elements.sendButton.disabled = true;
elements.menuToggle.disabled = true; elements.clearChat.disabled = true;
loadApplication().then(() => historyUI.init()).finally(() => {
  elements.input.disabled = false; elements.sendButton.disabled = false;
  elements.menuToggle.disabled = false; elements.clearChat.disabled = false;
  selectMap(state.activeMapId, {focus: false, persist: false});
});

KronoViewport.install(window, document);

if ("serviceWorker" in navigator && window.isSecureContext) {
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("./service-worker.js").catch(() => {});
  });
}
