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

function addMessage(role, text, options = {}) {
  const wrapper = document.createElement("div");
  wrapper.className = `message ${role}${options.clarification ? " clarification" : ""}${options.error ? " error" : ""}`;

  const meta = document.createElement("div");
  meta.className = "message-meta";
  meta.textContent = role === "user" ? "You" : options.clarification ? "Clarification needed" : "KronoChat";
  wrapper.appendChild(meta);

  const body = document.createElement("div");
  body.textContent = text;
  wrapper.appendChild(body);

  if (options.images && options.images.length > 0) {
    const imagesWrap = document.createElement("div");
    imagesWrap.className = "message-images";

    for (const imgObj of options.images) {
      const img = document.createElement("img");
      img.src = buildImageUrl(imgObj);
      img.alt = imgObj.path;
      img.title = `${imgObj.map_id}/${imgObj.path}`;
      img.addEventListener("click", () => openImageModal(img.src, img.alt));
      imagesWrap.appendChild(img);
    }

    wrapper.appendChild(imagesWrap);
  }

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