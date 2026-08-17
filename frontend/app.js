const API_BASE = window.location.origin;

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
  modalClose: document.getElementById("modal-close")
};

const state = {
  maps: [],
  activeMapId: null,
  history: [],
  pending: false
};

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

function setSidebarOpen(open) {
  document.body.classList.toggle("sidebar-open", open);
  elements.menuToggle.setAttribute("aria-expanded", String(open));
}

function selectMap(mapId, { focus = true } = {}) {
  state.activeMapId = mapId || null;
  const selectedMap = getMap(state.activeMapId);
  elements.activeMapLabel.textContent = selectedMap?.display_name || "Todos os mapas";
  elements.composerContext.querySelector("span:last-child").textContent = selectedMap
    ? `Buscando apenas em ${selectedMap.display_name}`
    : "Busca em todos os mapas";

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
      <strong>Todos os mapas</strong>
      <small>Deixe o assunto identificar o mapa</small>
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
      cover.style.backgroundImage = `linear-gradient(90deg, rgba(9,9,11,.08), rgba(9,9,11,.7)), url("${mediaUrl(map.cover_image_id)}")`;
    }

    const copy = document.createElement("span");
    copy.className = "map-copy";
    const title = document.createElement("strong");
    title.textContent = map.display_name;
    const meta = document.createElement("small");
    meta.textContent = `${map.document_count} guias · ${map.image_count} imagens`;
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
  summary.textContent = `${uniqueFiles.size} fonte${uniqueFiles.size > 1 ? "s" : ""} da base`;
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
    img.src = mediaUrl(image.id, "thumb");
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
    ? "<span>Você</span>"
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
  elements.modalImage.src = mediaUrl(image.id, "full");
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
    throw new Error(payload.detail || "Não foi possível responder agora.");
  }
  return payload;
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
    elements.input.focus();
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

    elements.knowledgeStats.innerHTML = `
      <strong>${health.chunks}</strong> trechos
      <span></span>
      <strong>${health.images}</strong> imagens
    `;

    const healthy = health.status === "ok";
    elements.systemStatus.classList.toggle("error", !healthy);
    elements.systemStatus.querySelector("span:last-child").textContent = healthy
      ? health.llm_configured ? "Base e IA prontas" : "Base pronta · configure a IA"
      : "Base com inconsistências";
  } catch {
    elements.mapList.innerHTML = '<p class="load-error">Não foi possível carregar os mapas.</p>';
    elements.systemStatus.classList.add("error");
    elements.systemStatus.querySelector("span:last-child").textContent = "API offline";
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

loadApplication();
elements.input.focus();
