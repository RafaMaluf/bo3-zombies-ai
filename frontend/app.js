const API_BASE = window.location.origin;
const chatEl = document.getElementById("chat");
const formEl = document.getElementById("chat-form");
const inputEl = document.getElementById("message-input");
const sendBtn = document.getElementById("send-btn");
const statusEl = document.getElementById("status");

const conversationHistory = [];

function addMessage(role, text, options = {}) {
  const wrapper = document.createElement("div");
  wrapper.className = `message ${role}${options.clarification ? " clarification" : ""}${options.error ? " error" : ""}`;

  const meta = document.createElement("div");
  meta.className = "message-meta";
  meta.textContent = role === "user" ? "You" : options.clarification ? "Clarification needed" : "Assistant";
  wrapper.appendChild(meta);

  const body = document.createElement("div");
  body.textContent = text;
  wrapper.appendChild(body);

  if (options.images && options.images.length > 0) {
    const imagesWrap = document.createElement("div");
    imagesWrap.className = "message-images";

    for (const imgPath of options.images) {
      const img = document.createElement("img");
      img.src = buildImageUrl(options.selectedFiles, imgPath);
      img.alt = imgPath;
      img.title = imgPath;
      imagesWrap.appendChild(img);
    }

    wrapper.appendChild(imagesWrap);
  }

//   if (options.selectedFiles && options.selectedFiles.length > 0) {
//     const fileList = document.createElement("div");
//     fileList.className = "file-list";
//     const labels = options.selectedFiles.map(f => `${f.map_id}/${f.path}`);
//     fileList.textContent = `Selected files: ${labels.join(", ")}`;
//     wrapper.appendChild(fileList);
//   }

  chatEl.appendChild(wrapper);
  chatEl.scrollTop = chatEl.scrollHeight;
}

function buildImageUrl(selectedFiles, relativeImagePath) {
  if (!selectedFiles || selectedFiles.length === 0) {
    return "";
  }

  // Assume first selected file's map is the correct map for image resolution.
  const mapId = selectedFiles[0].map_id;
  return `${API_BASE}/static/${mapId}/${relativeImagePath}`;
}

async function checkHealth() {
  try {
    const res = await fetch(`${API_BASE}/health`);
    if (!res.ok) throw new Error("Health check failed");
    statusEl.textContent = "Backend: online";
  } catch (err) {
    statusEl.textContent = "Backend: offline";
  }
}

async function sendMessage(message) {
  const payload = {
    message,
    conversation_history: conversationHistory
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

  inputEl.value = "";
  sendBtn.disabled = true;
  sendBtn.textContent = "Sending...";

  try {
    const data = await sendMessage(message);

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

checkHealth();