class ConversationHistory {
  constructor(deps) {
    this.deps = deps; this.meta = null; this.store = null; this.queue = Promise.resolve();
    this.window = []; this.pageBefore = null; this.listBefore = null;
    this.dialog = document.getElementById("history-dialog");
    this.pt = deps.locale.startsWith("pt");
    this.copy = this.pt ? {
      title: "Conversas", new: "Nova conversa", close: "Fechar", more: "Mais conversas",
      empty: "Nenhuma conversa salva.", rename: "Renomear", remove: "Excluir", pdf: "Exportar PDF",
      older: "Mensagens anteriores", latest: "Voltar às recentes", recovered: "Partida recuperada",
      deleteQuestion: "Excluir esta conversa e seu acompanhamento deste navegador? Esta ação não pode ser desfeita.",
      storage: "Não foi possível salvar o histórico neste navegador. O conteúdo recente permanece nesta aba; não feche sem copiar o que deseja guardar.",
      changed: "A conversa mudou em outra aba. O registro mais recente foi carregado.",
    } : {
      title: "Conversations", new: "New conversation", close: "Close", more: "More conversations",
      empty: "No saved conversations.", rename: "Rename", remove: "Delete", pdf: "Export PDF",
      older: "Older messages", latest: "Back to recent", recovered: "Recovered match",
      deleteQuestion: "Delete this conversation and its companion from this browser? This cannot be undone.",
      storage: "Could not save history in this browser. Recent content remains in this tab; copy what you need before closing.",
      changed: "The conversation changed in another tab. The latest record was loaded.",
    };
    document.getElementById("history-open").setAttribute("aria-label", this.copy.title);
    this.dialog.setAttribute("aria-label", this.copy.title);
    document.getElementById("history-title").textContent = this.copy.title;
    document.getElementById("history-local-copy").textContent = this.pt
      ? "Salvo neste navegador, sem exclusão automática. Limpar os dados do site pode apagar o histórico. Sem sincronização entre dispositivos."
      : "Saved in this browser, without automatic deletion. Clearing site data can erase history. No device synchronization.";
    document.getElementById("history-close").setAttribute("aria-label", this.copy.close);
    document.getElementById("history-info-label").textContent = this.pt ? "Sobre o histórico" : "About history";
    document.getElementById("history-more").textContent = this.copy.more;
    document.getElementById("clear-chat-label").textContent = this.copy.new;
    document.getElementById("export-chat").textContent = this.copy.pdf;
    document.getElementById("history-open").onclick = () => this.show();
    document.getElementById("history-close").onclick = () => this.dialog.close();
    this.dialog.addEventListener("close", () => document.getElementById("history-open").setAttribute("aria-expanded", "false"));
    this.dialog.addEventListener("click", event => {
      if (event.target !== this.dialog) return;
      const rect = this.dialog.getBoundingClientRect();
      if (event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom) this.dialog.close();
    });
    document.getElementById("history-more").onclick = () => this.list(true);
    document.getElementById("export-chat").onclick = () => { this.closeMenu(); this.export(); };
    for (const [id, action, label] of [["rename-chat", "rename", this.copy.rename], ["delete-chat", "remove", this.copy.remove]]) {
      const button = document.getElementById(id); button.textContent = label;
      button.onclick = async () => { this.closeMenu(); await this.show(true);
        const item = [...document.querySelectorAll(".history-item")].find(item => item.dataset.id === this.meta?.id);
        if (item) { item.querySelector("details").open = true;
          item.querySelector(`[data-history-action="${action}"]`)?.click(); }
      };
    }
    if (typeof BroadcastChannel !== "undefined") {
      this.channel = new BroadcastChannel("krono.history.v1");
      this.channel.onmessage = async ({data}) => {
        if (data.id !== this.meta?.id) return;
        this.deps.cancel();
        await this.flush();
        const record = await this.store?.get(data.id);
        if (record) { await this.open(record.id); this.warn(this.copy.changed); }
        else await this.newConversation();
      };
    }
  }
  closeMenu() { document.getElementById("conversation-menu").open = false; }
  updateChrome() {
    document.getElementById("conversation-title").textContent = this.meta?.title || this.copy.new;
  }
  async show(includeCurrent = false) {
    await this.flush(); this.listBefore = null; await this.list(false, includeCurrent);
    if (!this.dialog.open) this.dialog.showModal();
    document.getElementById("history-open").setAttribute("aria-expanded", "true");
  }
  warn(message) {
    const warning = document.getElementById("history-warning");
    warning.textContent = message; warning.hidden = !message;
  }
  async init() {
    try {
      this.store = await HistoryStore.open();
      let legacy = null;
      try { legacy = localStorage.getItem("krono.match.v1"); } catch {}
      const migrated = await this.store.migrateLegacy(legacy, this.copy.recovered);
      if (migrated) {
        try { if (localStorage.getItem("krono.match.v1") === legacy) localStorage.removeItem("krono.match.v1"); } catch {}
      }
      const lastId = await this.store.setting("current");
      const last = lastId ? await this.store.get(lastId) : null;
      if (!await this.open(last?.id || migrated?.id || (await this.store.list())[0]?.id || null)) throw new Error(this.copy.storage);
    } catch {
      this.store = null;
      this.meta = {id: crypto.randomUUID(), title: this.copy.new, revision: 0, count: 0};
      this.warn(this.copy.storage);
      this.deps.setMatch(null, []);
    }
  }
  flush() { return this.queue; }
  write(patch = {}, rows = []) {
    const id = this.meta?.id;
    const operation = this.queue.then(async () => {
      if (!this.store || id !== this.meta?.id) {
        if (!this.store) { Object.assign(this.meta, patch); return; }
        throw new Error(this.copy.changed);
      }
      this.meta = await this.store.update(id, patch, rows, this.meta.revision);
      this.updateChrome();
      this.channel?.postMessage({id});
    });
    this.queue = operation.catch(error => { this.warn(`${this.copy.storage} ${error.message || ""}`); });
    return operation;
  }
  append(row) {
    this.write({}, [row]).then(() => {
      if (this.meta?.count > 30 && !document.querySelector(".history-pagination button")) {
        const button = document.createElement("button"); button.type = "button";
        button.className = "ghost-button"; button.textContent = this.copy.older;
        button.onclick = async () => { this.pageBefore = this.meta.count - 29; await this.renderPage(); };
        const nav = document.createElement("div"); nav.className = "history-pagination"; nav.appendChild(button);
        document.getElementById("chat").prepend(nav);
      }
    }).catch(() => {});
  }
  async open(id) {
    this.switching = true;
    try {
      this.deps.cancel(); await this.flush();
      let record = id && this.store ? await this.store.get(id) : null;
      if (!record) record = this.store ? await this.store.create(this.copy.new)
        : {id: crypto.randomUUID(), title: this.copy.new, count: 0, revision: 0};
      this.meta = record;
      this.updateChrome();
      if (this.store) {
        try { await this.store.setting("current", this.meta.id); }
        catch { this.warn(this.copy.storage); }
      }
      this.deps.reset();
      this.deps.setMatch(this.meta.match || null, this.meta.offered || []);
      this.deps.selectMap(this.meta.mapId || null);
      await this.latest();
      this.dialog.close();
      return true;
    } catch (error) { this.warn(`${this.copy.storage} ${error.message || ""}`); return false; }
    finally { this.switching = false; }
  }
  async newConversation() { return this.open(null); }
  async latest() {
    this.pageBefore = null;
    await this.renderPage();
  }
  async renderPage() {
    if (!this.store) return;
    const id = this.meta.id;
    const rows = await this.store.page(id, this.pageBefore ?? Infinity);
    const recent = this.pageBefore === null ? rows : await this.store.page(id);
    if (id !== this.meta.id) return;
    this.window = rows;
    this.deps.renderRows(rows, {
      older: rows[0]?.seq > 1 ? async () => { this.pageBefore = rows[0].seq; await this.renderPage(); } : null,
      latest: this.pageBefore !== null ? () => this.latest() : null,
      copy: this.copy,
    });
    this.deps.setContext(recent.filter(row => row.context !== false).slice(-10).map(row => ({
      role: row.role, content: transcriptText(row).slice(0, 12000) || "…",
      source_paths: [...new Set((row.options?.sources || []).map(s => s.path))],
    })));
  }
  async cachedAnswer(state) {
    if (!this.store) return null;
    const rows = await this.store.page(this.meta.id);
    const row = rows.reverse().find(r => r.companion?.sessionId === state.session_id
      && r.companion.focus === state.focus && r.companion.revision === state.revision);
    return row ? {answer: transcriptText(row), introduction: row.options.introduction,
      blocks: row.options.blocks, relevant_images: row.options.images, sources: row.options.sources} : null;
  }
  async list(append = false, includeCurrent = false) {
    const list = document.getElementById("history-list");
    if (!append) list.replaceChildren();
    const rows = this.store ? await this.store.list(append ? this.listBefore : null) : [];
    if (includeCurrent && this.meta && !rows.some(row => row.id === this.meta.id)) rows.unshift(this.meta);
    if (!rows.length && !append) list.textContent = this.copy.empty;
    for (const row of rows) {
      const item = document.createElement("div"); item.className = "history-item"; item.dataset.id = row.id;
      const open = document.createElement("button"); open.type = "button";
      open.textContent = row.title; open.className = "history-select";
      open.setAttribute("aria-current", String(row.id === this.meta?.id));
      open.onclick = () => this.open(row.id).catch(error => this.warn(error.message));
      const rename = document.createElement("button"); rename.type = "button";
      rename.dataset.historyAction = "rename";
      rename.textContent = this.copy.rename; rename.onclick = () => {
        const form = document.createElement("form"); form.className = "history-edit";
        const input = document.createElement("input"); input.value = row.title; input.maxLength = 120;
        input.setAttribute("aria-label", this.copy.rename);
        const save = document.createElement("button"); save.type = "submit"; save.textContent = this.pt ? "Salvar" : "Save";
        const cancel = document.createElement("button"); cancel.type = "button"; cancel.textContent = this.pt ? "Cancelar" : "Cancel";
        cancel.onclick = () => this.list();
        form.append(input, save, cancel); actions.replaceChildren(form); input.focus();
        form.onsubmit = async event => {
          event.preventDefault(); const title = input.value.trim(); if (!title) return;
          try {
            await this.flush();
            const updated = await this.store.update(row.id, {title, automaticTitle: false});
            if (row.id === this.meta?.id) { this.meta = updated; this.updateChrome(); }
            this.channel?.postMessage({id: row.id}); await this.list();
          } catch (error) { this.warn(`${this.copy.storage} ${error.message}`); }
        };
      };
      const remove = document.createElement("button"); remove.type = "button";
      remove.dataset.historyAction = "remove";
      remove.textContent = this.copy.remove; remove.onclick = () => {
        const question = document.createElement("p"); question.textContent = this.copy.deleteQuestion;
        const confirm = document.createElement("button"); confirm.type = "button";
        confirm.textContent = this.pt ? "Confirmar exclusão" : "Confirm deletion";
        const cancel = document.createElement("button"); cancel.type = "button";
        cancel.textContent = this.pt ? "Cancelar" : "Cancel"; cancel.onclick = () => this.list();
        actions.replaceChildren(question, confirm, cancel);
        confirm.onclick = async () => {
          try {
            if (row.id === this.meta?.id) this.deps.cancel();
            await this.flush(); await this.store.remove(row.id);
            this.channel?.postMessage({id: row.id});
            if (row.id === this.meta?.id) await this.newConversation();
            else await this.list();
          } catch (error) { this.warn(`${this.copy.storage} ${error.message}`); }
        };
      };
      const actions = document.createElement("div"); actions.className = "history-item-actions";
      actions.append(rename, remove);
      const menu = document.createElement("details"); menu.className = "history-item-menu";
      const summary = document.createElement("summary"); summary.textContent = "···";
      summary.setAttribute("aria-label", `${this.pt ? "Opções de" : "Options for"} ${row.title}`);
      menu.append(summary, actions);
      menu.addEventListener("toggle", () => { if (menu.open) {
        for (const other of list.querySelectorAll(".history-item-menu[open]")) if (other !== menu) other.open = false;
      }});
      item.append(open, menu); list.appendChild(item);
    }
    this.listBefore = rows.at(-1) || this.listBefore;
    document.getElementById("history-more").hidden = rows.length < 20;
  }
  async export() {
    if (!this.store) { this.warn(this.copy.storage); return; }
    const conversationId = this.meta.id;
    // Open synchronously so browsers do not treat the awaited flush as a popup.
    const tab = window.open("about:blank", "_blank");
    if (!tab) { this.warn(this.pt ? "Permita abrir a prévia de PDF neste site." : "Allow this site's PDF preview to open."); return; }
    tab.opener = null;
    await this.flush();
    tab.location.href = `./export.html?conversation=${encodeURIComponent(conversationId)}&lang=${this.pt ? "pt" : "en"}`;
  }
}
