const API_BASE = window.location.origin;

const UI_COPY = {
  "pt-BR": {
    pageTitle: "Kronochat — Black Ops III Zombies",
    availableMaps: "Mapas disponíveis",
    library: "Base de conhecimento",
    checkingBase: "Verificando base",
    clearChat: "Limpar conversa",
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
    welcomeEyebrow: "Krono está online",
    welcomeTitle: "Entre no round<br />sabendo o próximo passo.",
    welcomeCopy: "Escolha um mapa ou pergunte diretamente. A resposta usa apenas os guias locais e traz as imagens certas para cada etapa.",
    quickPap: "Liberar Pack-a-Punch",
    quickPapPrompt: "Como eu libero o Pack-a-Punch?",
    quickEe: "Easter Egg principal",
    quickEePrompt: "Como faço o Easter Egg principal?",
    quickShield: "Montar o escudo",
    quickShieldPrompt: "Como monto o escudo?",
    placeholder: "Pergunte sobre o mapa…",
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
    staying: "Certo — continuamos em {current}."
  },
  en: {
    pageTitle: "Kronochat — Black Ops III Zombies",
    availableMaps: "Available maps",
    library: "Knowledge base",
    checkingBase: "Checking knowledge base",
    clearChat: "Clear conversation",
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
    welcomeEyebrow: "Krono is online",
    welcomeTitle: "Enter the round<br />knowing your next step.",
    welcomeCopy: "Choose a map or ask directly. Answers use the local guides and bring the right images for each step.",
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
    staying: "Got it — we will stay in {current}."
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
  sidebar: document.getElementById("sidebar"),
  sidebarBackdrop: document.getElementById("sidebar-backdrop"),
  menuToggle: document.getElementById("menu-toggle"),
  mapList: document.getElementById("map-list"),
  mapCount: document.getElementById("map-count"),
  activeMapLabel: document.getElementById("active-map-label"),
  knowledgeStats: document.getElementById("knowledge-stats"),
  systemStatus: document.getElementById("system-status"),
  clearChat: document.getElementById("clear-chat"),
  welcome: document.getElementById("welcome"),
  quickPrompts: document.getElementById("quick-prompts"),
  chat: document.getElementById("chat"),
  form: document.getElementById("chat-form"),
  input: document.getElementById("message-input"),
  sendButton: document.getElementById("send-btn"),
  composerContext: document.getElementById("composer-context"),
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
  pendingMapSwitch: null
};

function applyUiLocale() {
  document.documentElement.lang = UI_LOCALE;
  document.title = t("pageTitle");
  elements.sidebar.setAttribute("aria-label", t("availableMaps"));
  elements.sidebarBackdrop.setAttribute("aria-label", t("closeMaps"));
  elements.menuToggle.setAttribute("aria-label", t("openMaps"));
  elements.modalClose.setAttribute("aria-label", t("close"));
  elements.chat.setAttribute("aria-label", t("conversation"));
  document.getElementById("library-title").textContent = t("library");
  document.getElementById("system-status-label").textContent = t("checkingBase");
  document.getElementById("clear-chat-label").textContent = t("clearChat");
  document.getElementById("active-context-title").textContent = t("activeContext");
  document.getElementById("welcome-eyebrow").textContent = t("welcomeEyebrow");
  document.getElementById("welcome-title").innerHTML = t("welcomeTitle");
  document.getElementById("welcome-copy").textContent = t("welcomeCopy");
  elements.input.placeholder = t("placeholder");
  elements.sendButton.setAttribute("aria-label", t("send"));
  document.getElementById("composer-hint-label").textContent = t("composerHint");
  elements.mapSwitchEyebrow.textContent = t("switchEyebrow");
  elements.activeMapLabel.textContent = t("allMaps");
  document.getElementById("composer-context-label").textContent = t("searchingAll");

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

function escapeHtml(value) {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function renderInlineMarkdown(value) {
  return escapeHtml(value)
    .replace(/`([^`]+)`/g, "<code>$1</code>")
    .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
}

function renderMarkdown(value) {
  const lines = value.replace(/\r\n/g, "\n").split("\n");
  const output = [];
  let listType = null;

  const closeList = () => {
    if (listType) output.push(`</${listType}>`);
    listType = null;
  };

  for (const rawLine of lines) {
    const line = rawLine.trim();
    if (!line) {
      closeList();
      continue;
    }

    const numbered = line.match(/^(\d+)\.\s+(.+)$/);
    const bullet = line.match(/^[-*]\s+(.+)$/);
    if (numbered) {
      if (listType !== "ol") {
        closeList();
        output.push("<ol>");
        listType = "ol";
      }
      output.push(`<li>${renderInlineMarkdown(numbered[2])}</li>`);
      continue;
    }
    if (bullet) {
      if (listType !== "ul") {
        closeList();
        output.push("<ul>");
        listType = "ul";
      }
      output.push(`<li>${renderInlineMarkdown(bullet[1])}</li>`);
      continue;
    }

    closeList();
    if (line.startsWith("### ")) {
      output.push(`<h4>${renderInlineMarkdown(line.slice(4))}</h4>`);
    } else if (line.startsWith("## ")) {
      output.push(`<h3>${renderInlineMarkdown(line.slice(3))}</h3>`);
    } else if (line.startsWith("# ")) {
      output.push(`<h3>${renderInlineMarkdown(line.slice(2))}</h3>`);
    } else {
      output.push(`<p>${renderInlineMarkdown(line)}</p>`);
    }
  }

  closeList();
  return output.join("");
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
  document.body.classList.toggle("sidebar-open", open);
  elements.menuToggle.setAttribute("aria-expanded", String(open));
}

function selectMap(mapId, { focus = true } = {}) {
  state.activeMapId = mapId || null;
  const selectedMap = getMap(state.activeMapId);
  elements.activeMapLabel.textContent = selectedMap?.display_name || t("allMaps");
  elements.composerContext.querySelector("span:last-child").textContent = selectedMap
    ? t("searchingMap", { map: selectedMap.display_name })
    : t("searchingAll");

  for (const button of elements.mapList.querySelectorAll(".map-button")) {
    button.classList.toggle("active", button.dataset.mapId === (mapId || ""));
  }

  setSidebarOpen(false);
  if (focus) elements.input.focus();
}

function renderMaps() {
  elements.mapList.replaceChildren();

  const allButton = document.createElement("button");
  allButton.className = "map-button active";
  allButton.type = "button";
  allButton.dataset.mapId = "";
  allButton.innerHTML = `
    <span class="map-cover map-cover-all"></span>
    <span class="map-copy">
      <strong>${t("allMaps")}</strong>
      <small>${t("allMapsHint")}</small>
    </span>
  `;
  allButton.addEventListener("click", () => selectMap(null));
  elements.mapList.appendChild(allButton);

  for (const map of state.maps) {
    const button = document.createElement("button");
    button.className = "map-button";
    button.type = "button";
    button.dataset.mapId = map.map_id;

    const cover = document.createElement("span");
    cover.className = "map-cover";
    if (map.cover_image_id) {
      const coverUrl = map.cover_image_url || mediaUrl(map.cover_image_id);
      cover.style.backgroundImage = `linear-gradient(90deg, rgba(9,9,11,.08), rgba(9,9,11,.7)), url("${coverUrl}")`;
    }

    const copy = document.createElement("span");
    copy.className = "map-copy";
    const title = document.createElement("strong");
    title.textContent = map.display_name;
    const meta = document.createElement("small");
    meta.textContent = t("mapMeta", {
      documents: map.document_count,
      images: map.image_count
    });
    copy.append(title, meta);
    button.append(cover, copy);
    button.addEventListener("click", () => selectMap(map.map_id));
    elements.mapList.appendChild(button);
  }

  elements.mapCount.textContent = String(state.maps.length);
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

function createImageGallery(images) {
  if (!images?.length) return null;

  const gallery = document.createElement("div");
  gallery.className = "message-images";
  for (const image of images) {
    const figure = document.createElement("figure");
    const img = document.createElement("img");
    img.src = imageVariantUrl(image, "thumb");
    img.alt = "";
    img.loading = "lazy";
    img.decoding = "async";

    const caption = document.createElement("figcaption");
    caption.textContent = image.caption;

    figure.append(img, caption);
    figure.addEventListener("click", () => openImage(image));
    gallery.appendChild(figure);
  }
  return gallery;
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
    : '<span class="assistant-mark">K</span><span>Krono</span>';

  const body = document.createElement("div");
  body.className = "message-body";
  if (role === "assistant") {
    body.innerHTML = renderMarkdown(text);
  } else {
    body.textContent = text;
  }

  article.append(header, body);

  const gallery = createImageGallery(options.images);
  if (gallery) article.appendChild(gallery);

  const sources = createSourceDetails(options.sources);
  if (sources) article.appendChild(sources);

  if (options.suggestedMapIds?.length) {
    const suggestions = document.createElement("div");
    suggestions.className = "map-suggestions";
    for (const mapId of options.suggestedMapIds) {
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
    <header><span class="assistant-mark">K</span><span>Krono</span></header>
    <div class="typing"><span></span><span></span><span></span></div>
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

function openImage(image) {
  elements.modalImage.src = imageVariantUrl(image, "full");
  elements.modalImage.alt = image.caption;
  elements.modalCaption.textContent = `${getMap(image.map_id)?.display_name || image.map_id} · ${image.caption}`;
  elements.imageModal.showModal();
}

function closeImage() {
  elements.imageModal.close();
  elements.modalImage.removeAttribute("src");
}

function setPending(pending) {
  state.pending = pending;
  elements.input.disabled = pending;
  elements.sendButton.disabled = pending;
  elements.sendButton.classList.toggle("pending", pending);
}

function resetComposer() {
  elements.input.value = "";
  elements.input.style.height = "auto";
  elements.characterCount.textContent = "0 / 2000";
}

async function sendMessage(message) {
  const response = await fetch(`${API_BASE}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      message,
      conversation_history: state.history.slice(-10),
      active_map_id: state.activeMapId,
      preferred_language: navigator.languages?.[0] || navigator.language || "pt-BR"
    })
  });

  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(payload.detail || t("requestError"));
  }
  return payload;
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
  elements.input.focus();
}

function confirmMapSwitch() {
  const pending = state.pendingMapSwitch;
  if (!pending) return;
  elements.mapSwitchModal.close();
  state.pendingMapSwitch = null;
  clearConversation();
  selectMap(pending.action.requested_map_id, { focus: false });
  submitMessage(pending.message);
}

async function submitMessage(message, { echoUser = true } = {}) {
  const cleanMessage = message.trim();
  if (!cleanMessage || state.pending) return;

  if (echoUser) {
    addMessage("user", cleanMessage);
    state.history.push({ role: "user", content: cleanMessage });
  }
  resetComposer();
  setPending(true);
  const typing = addTypingIndicator();

  try {
    const response = await sendMessage(cleanMessage);
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
      addMessage("assistant", response.answer, {
        images: response.relevant_images,
        sources: response.sources
      });
      state.history.push({
        role: "assistant",
        content: response.answer,
        source_paths: [...new Set(response.sources.map(source => source.path))]
      });
    }
  } catch (error) {
    typing.remove();
    addMessage("assistant", error.message, { error: true });
  } finally {
    setPending(false);
    if (!elements.mapSwitchModal.open) elements.input.focus();
  }
}

function clearConversation() {
  state.history = [];
  elements.chat.replaceChildren();
  elements.welcome.hidden = false;
  selectMap(null, { focus: false });
}

function autoResizeComposer() {
  elements.input.style.height = "auto";
  elements.input.style.height = `${Math.min(elements.input.scrollHeight, 160)}px`;
  elements.characterCount.textContent = `${elements.input.value.length} / 2000`;
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
    renderMaps();

    const stats = t("stats", { chunks: health.chunks, images: health.images });
    const [chunkCopy, imageCopy] = stats.split(" · ");
    elements.knowledgeStats.innerHTML = `<strong>${chunkCopy.split(" ")[0]}</strong> ${chunkCopy.split(" ").slice(1).join(" ")}<span></span><strong>${imageCopy.split(" ")[0]}</strong> ${imageCopy.split(" ").slice(1).join(" ")}`;

    const healthy = health.status === "ok";
    elements.systemStatus.classList.toggle("error", !healthy);
    elements.systemStatus.querySelector("span:last-child").textContent = healthy
      ? health.llm_configured ? t("healthy") : t("baseOnly")
      : t("inconsistent");
  } catch {
    elements.mapList.innerHTML = `<p class="load-error">${t("mapsLoadError")}</p>`;
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
elements.menuToggle.addEventListener("click", () => {
  setSidebarOpen(!document.body.classList.contains("sidebar-open"));
});
elements.sidebarBackdrop.addEventListener("click", () => setSidebarOpen(false));
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

applyUiLocale();
loadApplication();
elements.input.focus();

if ("serviceWorker" in navigator && window.isSecureContext) {
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("./service-worker.js").catch(() => {});
  });
}
