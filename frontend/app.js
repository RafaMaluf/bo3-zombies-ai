const API_BASE = window.location.origin;
const chatEl = document.getElementById("chat");
const formEl = document.getElementById("chat-form");
const inputEl = document.getElementById("message-input");
const sendBtn = document.getElementById("send-btn");
const imageModalEl = document.getElementById("image-modal");
const modalImageEl = document.getElementById("modal-image");
const modalCloseEl = document.getElementById("modal-close");

const conversationHistory = [];
const SHOW_DEBUG_FILES = false;
let activeMapId = null;
let typingBubble = null;
let hasSentFirstMessage = false;

function renderMessageBody(text, allImages, container) {
  // Parse [IMAGE: map_id|images/path.jpg] markers embedded inline by the LLM
  const markerRe = /\[IMAGE:\s*([^\|\]]+)\|([^\]]+)\]/g;
  const renderedPaths = new Set();
  const segments = [];
  let lastIndex = 0;
  let match;

  while ((match = markerRe.exec(text)) !== null) {
    if (match.index > lastIndex) {
      segments.push({ type: "text", content: text.slice(lastIndex, match.index) });
    }
    segments.push({ type: "image", map_id: match[1].trim(), path: match[2].trim() });
    lastIndex = markerRe.lastIndex;
  }
  if (lastIndex < text.length) {
    segments.push({ type: "text", content: text.slice(lastIndex) });
  }

  // Collapse consecutive image segments into groups for a grid layout
  const collapsed = [];
  for (const seg of segments) {
    const last = collapsed[collapsed.length - 1];
    if (seg.type === "image" && last && last.type === "image-group") {
      last.images.push(seg);
    } else if (seg.type === "image") {
      collapsed.push({ type: "image-group", images: [seg] });
    } else {
      collapsed.push(seg);
    }
  }

  for (const seg of collapsed) {
    if (seg.type === "text") {
      const trimmed = seg.content.trim();
      if (!trimmed) continue;
      const div = document.createElement("div");
      div.className = "message-text-block";
      div.textContent = trimmed;
      container.appendChild(div);
    } else if (seg.type === "image-group") {
      const groupEl = document.createElement("div");
      if (seg.images.length > 1) groupEl.className = "inline-image-group";

      for (const imgSeg of seg.images) {
        const imgEl = document.createElement("img");
        imgEl.src = buildImageUrl(imgSeg);
        imgEl.alt = imgSeg.path;
        imgEl.className = "inline-image";
        imgEl.title = `${imgSeg.map_id}/${imgSeg.path}`;
        imgEl.addEventListener("click", () => openImageModal(imgEl.src, imgEl.alt));
        groupEl.appendChild(imgEl);
        renderedPaths.add(`${imgSeg.map_id}/${imgSeg.path}`);
      }

      container.appendChild(groupEl);
    }
  }

  // Fallback: show any images from relevant_images not already embedded inline
  if (allImages && allImages.length > 0) {
    const remaining = allImages.filter(
      img => !renderedPaths.has(`${img.map_id}/${img.path}`)
    );
    if (remaining.length > 0) {
      const grid = document.createElement("div");
      grid.className = "message-images";
      for (const imgObj of remaining) {
        const imgEl = document.createElement("img");
        imgEl.src = buildImageUrl(imgObj);
        imgEl.alt = imgObj.path;
        imgEl.title = `${imgObj.map_id}/${imgObj.path}`;
        imgEl.addEventListener("click", () => openImageModal(imgEl.src, imgEl.alt));
        grid.appendChild(imgEl);
      }
      container.appendChild(grid);
    }
  }
}

function addMessage(role, text, options = {}) {
  const wrapper = document.createElement("div");
  wrapper.className = `message ${role}${options.clarification ? " clarification" : ""}${options.error ? " error" : ""}`;

  const meta = document.createElement("div");
  meta.className = "message-meta";
  meta.textContent = role === "user" ? "You" : options.clarification ? "Clarification needed" : "KronoChat";
  wrapper.appendChild(meta);

  const body = document.createElement("div");
  body.className = "message-body";
  renderMessageBody(text, options.images || [], body);
  wrapper.appendChild(body);

  if (SHOW_DEBUG_FILES && options.selectedFiles && options.selectedFiles.length > 0) {
    const fileList = document.createElement("div");
    fileList.className = "file-list";
    const labels = options.selectedFiles.map(f => `${f.map_id}/${f.path}`);
    fileList.textContent = `Selected files: ${labels.join(", ")}`;
    wrapper.appendChild(fileList);
  }

  chatEl.appendChild(wrapper);
  chatEl.scrollTop = chatEl.scrollHeight;
}

function addTypingMessage() {
  const wrapper = document.createElement("div");
  wrapper.className = "message assistant";
  wrapper.id = "typing-message";

  const meta = document.createElement("div");
  meta.className = "message-meta";
  meta.textContent = "KronoChat";
  wrapper.appendChild(meta);

  const typing = document.createElement("div");
  typing.className = "typing";
  typing.innerHTML = "<span></span><span></span><span></span>";
  wrapper.appendChild(typing);

  chatEl.appendChild(wrapper);
  chatEl.scrollTop = chatEl.scrollHeight;
  typingBubble = wrapper;
}

function removeTypingMessage() {
  if (typingBubble) {
    typingBubble.remove();
    typingBubble = null;
  }
}

function buildImageUrl(imageObj) {
  return `${API_BASE}/static/${imageObj.map_id}/${imageObj.path}`;
}

function openImageModal(src, alt = "") {
  modalImageEl.src = src;
  modalImageEl.alt = alt;
  imageModalEl.classList.remove("hidden");
  imageModalEl.setAttribute("aria-hidden", "false");
}

function closeImageModal() {
  imageModalEl.classList.add("hidden");
  imageModalEl.setAttribute("aria-hidden", "true");
  modalImageEl.src = "";
}

function updateInputPlaceholder() {
  if (hasSentFirstMessage) {
    inputEl.placeholder = "Digite aqui...";
  } else {
    inputEl.placeholder = "Ask something like: how do i unlock pack a punch on shadows of evil?";
  }
}

async function checkHealth() {
  try {
    const res = await fetch(`${API_BASE}/health`);
    if (!res.ok) throw new Error("Health check failed");
  } catch (err) {
    // Intentionally silent in UI now
  }
}

async function sendMessage(message) {
  const payload = {
    message,
    conversation_history: conversationHistory,
    active_map_id: activeMapId
  };

  const res = await fetch(`${API_BASE}/chat`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify(payload)
  });

  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || "Request failed");
  }

  return res.json();
}

formEl.addEventListener("submit", async (e) => {
  e.preventDefault();

  const message = inputEl.value.trim();
  if (!message) return;

  addMessage("user", message);
  conversationHistory.push({ role: "user", content: message });

  hasSentFirstMessage = true;
  updateInputPlaceholder();

  inputEl.value = "";
  sendBtn.disabled = true;
  sendBtn.textContent = "Sending...";
  addTypingMessage();

  try {
    const data = await sendMessage(message);

    if (data.active_map_id) {
      activeMapId = data.active_map_id;
    }

    removeTypingMessage();

    if (data.need_clarification) {
      addMessage("assistant", data.clarification_question, {
        clarification: true,
        selectedFiles: data.selected_files || []
      });

      conversationHistory.push({
        role: "assistant",
        content: data.clarification_question
      });
    } else {
      addMessage("assistant", data.answer, {
        images: data.relevant_images || [],
        selectedFiles: data.selected_files || []
      });

      conversationHistory.push({
        role: "assistant",
        content: data.answer
      });
    }
  } catch (err) {
    removeTypingMessage();
    addMessage("assistant", `Error: ${err.message}`, { error: true });
  } finally {
    sendBtn.disabled = false;
    sendBtn.textContent = "Send";
    inputEl.focus();
  }
});

inputEl.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    formEl.requestSubmit();
  }
});

modalCloseEl.addEventListener("click", closeImageModal);

imageModalEl.addEventListener("click", (e) => {
  if (e.target === imageModalEl) {
    closeImageModal();
  }
});

document.addEventListener("keydown", (e) => {
  if (e.key === "Escape" && !imageModalEl.classList.contains("hidden")) {
    closeImageModal();
  }
});

updateInputPlaceholder();
checkHealth();