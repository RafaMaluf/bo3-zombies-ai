/* Focused companion view; durable progress and events belong to its conversation. */
class CompanionUI {
  constructor(deps) {
    this.deps = deps;
    this.saved = null;
    this.view = null;
    this.active = false;
    this.busy = false;
    this.epoch = 0;
    this.offered = new Set();
    this.storageKey = "krono.match.v1";
    this.words = deps.locale.startsWith("pt") ? {
      title: "Acompanhamento", chat: "Voltar ao chat", resume: "Retomar partida",
      offer: "Vai fazer esse Easter Egg?", offerCopy: "Posso acompanhar sua partida e explicar cada etapa conforme você avança.",
      try: "Experimentar", no: "Agora não", players: "Quantos jogadores?",
      unknown: "Ainda não sei", solo: "1 — Solo", start: "Iniciar acompanhamento",
      replace: "Iniciar substitui a partida salva nesta conversa.", roadmap: "Roteiro",
      position: "Vão começar do início ou já fizeram alguma parte?",
      placeholder: "Pergunte ou conte o que aconteceu…", send: "Enviar",
      explain: "Explicar melhor", done: "Terminei", cancel: "Cancelar resposta",
      confirm: "Confirmar correção", decline: "Manter como estava",
      completed: "objetivos concluídos", finish: "Easter Egg concluído!",
      finishedCopy: "Vocês concluíram os objetivos registrados. Pode consultar o roteiro ou voltar ao chat.",
      starting: "Preparando o acompanhamento…", understanding: "Entendendo sua mensagem…",
      planning: "Organizando a etapa e os pré-requisitos…", generating: "Preparando a explicação…",
      finalizing: "Organizando o texto e as imagens…", retry: "Tentar novamente",
      saved: "Seu progresso foi preservado.", storage: "Não foi possível salvar neste dispositivo. Mantenha esta aba aberta para preservar a partida.",
      corrupt: "A partida salva não pôde ser lida. Ela foi preservada; você pode iniciar uma nova pelo convite de um Easter Egg.",
      conditional: "Caminho condicional: confirme na conversa o que se aplica à sua partida.",
      missing: "Pré-requisitos pendentes ou ainda não confirmados: ",
      anotherTab: "A partida foi atualizada em outra aba. Retome para carregar a versão mais recente.",
      newMatch: "Iniciar nova partida",
      elapsed: "Tempo decorrido", optional: "Ajuda com equipamentos", you: "Você",
    } : {
      title: "Companion", chat: "Back to chat", resume: "Resume match",
      offer: "Planning to do this Easter Egg?", offerCopy: "I can follow your match and explain each objective as you progress.",
      try: "Try it", no: "Not now", players: "How many players?", unknown: "Not sure yet",
      solo: "1 — Solo", start: "Start companion", replace: "Starting replaces the match saved in this conversation.",
      roadmap: "Roadmap", position: "Starting from the beginning, or have you already completed some objectives?",
      placeholder: "Ask a question or tell me what happened…", send: "Send",
      explain: "Explain further", done: "Done", cancel: "Cancel answer", confirm: "Confirm correction",
      decline: "Keep previous progress", completed: "objectives completed", finish: "Easter Egg complete!",
      finishedCopy: "You completed the recorded objectives. You can consult the roadmap or return to chat.",
      starting: "Preparing the companion…", understanding: "Understanding your message…",
      planning: "Organizing this objective and its prerequisites…", generating: "Preparing the explanation…",
      finalizing: "Arranging text and images…", retry: "Try again", saved: "Your progress was preserved.",
      storage: "Could not save on this device. Keep this tab open to preserve the match.",
      corrupt: "The saved match could not be read. It was preserved; you can start a new one from an Easter Egg invitation.",
      conditional: "Conditional route: tell me which path applies to your match.",
      missing: "Pending or unconfirmed prerequisites: ",
      anotherTab: "The match changed in another tab. Resume to load the latest version.",
      newMatch: "Start a new match",
      elapsed: "Elapsed time", optional: "Equipment help", you: "You",
    };
    this.root = document.createElement("section");
    this.root.id = "companion";
    this.root.hidden = true;
    this.root.setAttribute("aria-label", this.tr("title"));
    this.root.innerHTML = `
      <header class="companion-header">
        <div><span class="eyebrow">${this.tr("title")}</span><h2 class="companion-title"></h2>
        <p class="companion-progress"></p></div>
        <div class="companion-navigation"><button type="button" class="ghost-button companion-chat">${this.tr("chat")}</button>
        <details class="companion-menu"><summary>${this.tr("roadmap")}</summary><nav></nav></details></div>
      </header>
      <div class="companion-scroll" tabindex="-1">
        <div class="companion-setup" hidden></div>
        <p class="companion-notice" role="status"></p>
        <div class="companion-confirm" hidden>
          <button type="button" data-action="confirm">${this.tr("confirm")}</button>
          <button type="button" data-action="decline">${this.tr("decline")}</button>
        </div>
        <div class="companion-answer message-body"></div>
        <p class="companion-error" role="alert"></p>
        <button type="button" class="ghost-button companion-retry" hidden>${this.tr("retry")}</button>
        <button type="button" class="ghost-button companion-new" hidden>${this.tr("newMatch")}</button>
      </div>
      <footer class="companion-footer">
        <div class="companion-actions">
          <button type="button" data-action="explain">${this.tr("explain")}</button>
          <button type="button" data-action="complete">${this.tr("done")}</button>
        </div>
        <p class="companion-status" role="status" aria-live="polite"></p>
        <form class="companion-form"><textarea rows="1" maxlength="2000" required aria-label="${this.tr("placeholder")}" placeholder="${this.tr("placeholder")}"></textarea>
          <button type="submit">${this.tr("send")}</button>
          <button type="button" class="companion-cancel" hidden>${this.tr("cancel")}</button></form>
      </footer>`;
    document.querySelector(".chat-stage").after(this.root);
    this.find(".companion-chat").addEventListener("click", () => this.leave());
    this.find(".companion-cancel").addEventListener("click", () => this.aborter?.abort());
    for (const button of this.root.querySelectorAll("[data-action]")) {
      button.addEventListener("click", () => this.act(button.dataset.action));
    }
    this.find(".companion-retry").addEventListener("click", () => this.run(signal => this.explain(signal, this.lastExplanation)));
    this.find(".companion-new").addEventListener("click", () => this.setup(this.saved.map_id));
    this.find("form").addEventListener("submit", event => {
      event.preventDefault();
      const text = this.find("textarea").value.trim();
      if (text) this.act("message", text);
    });
    this.find("textarea").addEventListener("keydown", event => {
      if (event.key === "Enter" && !event.shiftKey) {
        event.preventDefault();
        this.find("form").requestSubmit();
      }
    });
    this.find("textarea").addEventListener("input", event => {
      event.target.style.height = "auto";
      event.target.style.height = `${Math.min(event.target.scrollHeight, 120)}px`;
    });
    this.banner = document.createElement("button");
    this.banner.type = "button";
    this.banner.className = "ghost-button companion-resume";
    this.banner.textContent = this.tr("resume");
    this.banner.hidden = true;
    this.banner.addEventListener("click", () => this.resume());
    document.querySelector(".topbar").appendChild(this.banner);
    if (!deps.saveMatch) try {
      const raw = localStorage.getItem(this.storageKey);
      if (raw) {
        const stored = JSON.parse(raw);
        if (stored.version !== 1 || !stored.map_id || !stored.catalog_version) throw new Error();
        this.saved = stored;
        this.banner.hidden = false;
      }
    } catch {
      this.banner.hidden = false;
      this.banner.textContent = this.tr("resume");
      this.storageWarning = this.tr("corrupt");
    }
    window.addEventListener("storage", event => {
      if (deps.saveMatch || event.key !== this.storageKey) return;
      this.leave();
      try { this.saved = event.newValue ? JSON.parse(event.newValue) : null; } catch { this.saved = null; }
      this.banner.hidden = !this.saved;
      this.banner.title = this.tr("anotherTab");
      this.deps.notice(this.tr("anotherTab"));
    });
  }

  tr(key) { return this.words[key] || key; }
  find(selector) { return this.root.querySelector(selector); }
  get matchState() { return this.saved; }
  get busyActive() { return this.active && this.busy; }

  offer(mapId, language) {
    if (!mapId || this.offered.has(mapId)) return;
    this.offered.add(mapId);
    this.deps.onOffered?.([...this.offered]);
    this.offerLanguage = language || this.deps.language;
    const dialog = document.createElement("dialog");
    dialog.className = "companion-invite";
    const title = document.createElement("h2"); title.textContent = this.tr("offer");
    const text = document.createElement("p"); text.textContent = this.tr("offerCopy");
    const yes = document.createElement("button"); yes.textContent = this.tr("try");
    const no = document.createElement("button"); no.textContent = this.tr("no");
    yes.addEventListener("click", () => { dialog.close(); dialog.remove(); this.setup(mapId); });
    no.addEventListener("click", () => { dialog.close(); dialog.remove(); });
    dialog.addEventListener("cancel", () => dialog.remove());
    dialog.append(title, text, yes, no);
    document.body.appendChild(dialog); dialog.showModal(); yes.focus();
  }

  enter(mapId) {
    this.deps.cancelChat();
    this.deps.selectMap(mapId);
    this.active = true;
    this.banner.hidden = true;
    document.querySelector(".chat-stage").hidden = true;
    document.querySelector(".composer-shell").hidden = true;
    this.root.hidden = false;
    document.body.classList.add("companion-active");
  }

  leave({notify = true} = {}) {
    this.aborter?.abort();
    this.epoch += 1;
    this.busy = false;
    this.active = false;
    this.root.hidden = true;
    document.querySelector(".chat-stage").hidden = false;
    document.querySelector(".composer-shell").hidden = false;
    document.body.classList.remove("companion-active");
    this.banner.hidden = !this.saved || this.saved.stage === "finished";
    if (notify) this.deps.onLeave?.();
  }

  setMatch(match, offered = []) {
    this.leave({notify: false});
    this.find(".companion-answer").replaceChildren();
    this.saved = match; this.view = null; this.offered = new Set(offered);
    this.offerLanguage = match?.language || this.deps.language;
    this.lastExplanation = {};
    this.find("textarea").value = "";
    this.find("textarea").style.height = "auto";
    this.find(".companion-error").textContent = "";
    this.find(".companion-retry").hidden = true;
    this.find(".companion-new").hidden = true;
    this.storageWarning = "";
    this.banner.hidden = !match || match.stage === "finished";
  }

  setup(mapId) {
    this.enter(mapId);
    this.view = null;
    this.find(".companion-answer").replaceChildren();
    this.find(".companion-error").textContent = "";
    this.find(".companion-new").hidden = true;
    this.render();
    const panel = this.find(".companion-setup");
    panel.hidden = false;
    panel.replaceChildren();
    const label = document.createElement("label"); label.textContent = this.tr("players");
    const select = document.createElement("select");
    select.setAttribute("aria-label", this.tr("players"));
    select.add(new Option(this.tr("unknown"), ""));
    for (let i = 1; i <= 4; i++) select.add(new Option(i === 1 ? this.tr("solo") : String(i), String(i)));
    label.appendChild(select); panel.appendChild(label);
    if (this.saved || this.storageWarning) {
      const warning = document.createElement("p"); warning.textContent = this.tr("replace"); panel.appendChild(warning);
    }
    const start = document.createElement("button"); start.textContent = this.tr("start");
    start.type = "button";
    start.addEventListener("click", () => this.run(async signal => {
      const data = await this.deps.requestJson("/companion/start", {
        method: "POST", timeoutMs: 65000, headers: {"Content-Type": "application/json"},
        body: JSON.stringify({map_id: mapId, player_count: select.value ? Number(select.value) : null,
                              language: this.offerLanguage || this.saved?.language || this.deps.language}),
      }, signal);
      if (signal.aborted) return;
      await this.accept(data, {overview: true});
    }));
    panel.appendChild(start);
  }

  async accept(data, event = {}) {
    const previousView = this.view;
    const previousSaved = this.saved;
    if (this.view?.catalog.version === data.catalog.version
      && this.view.state.language === data.state.language) {
      const titles = new Map(this.view.catalog.objectives.map(o => [o.id, o.title]));
      for (const objective of data.catalog.objectives) objective.title = titles.get(objective.id) || objective.title;
    }
    const preserve = this.view?.state.focus === data.state.focus
      && data.state.stage === "active" && !data.can_explain;
    this.view = data;
    this.saved = data.state;
    const rows = [];
    if (event.text) rows.push(transcriptRow("user", event.text, {}, !!event.question));
    if (event.overview) {
      const overview = data.catalog.objectives.filter(o => o.main).map((o, i) => `${i + 1}. ${o.title}`).join("\n");
      rows.push(transcriptRow("assistant", `## ${data.catalog.map_name}\n\n${this.tr("players")}: ${data.state.player_count || this.tr("unknown")}\n\n${overview}\n\n${this.tr("position")}`));
    }
    if (data.message && (event.text || event.overview)) rows.push(transcriptRow("assistant", data.message));
    if (data.state.stage === "finished" && event.text) {
      const completed = data.catalog.objectives.filter(o => o.main && data.state.statuses[o.id] === "complete");
      rows.push(transcriptRow("assistant", `## ${this.tr("finish")}\n\n${data.completed_count} / ${data.total_count} ${this.tr("completed")}\n\n${completed.map(o => `- ${o.title}`).join("\n")}`));
    }
    if (this.deps.saveMatch) {
      try { await this.deps.saveMatch(this.saved, rows); }
      catch (error) { this.view = previousView; this.saved = previousSaved; throw error; }
      this.storageWarning = "";
    } else try {
      localStorage.setItem(this.storageKey, JSON.stringify(this.saved));
      this.storageWarning = "";
    } catch { this.storageWarning = this.tr("storage"); }
    this.banner.hidden = this.active;
    this.find(".companion-error").textContent = this.storageWarning;
    if (!preserve) this.find(".companion-answer").replaceChildren();
    this.find(".companion-retry").hidden = true;
    this.find(".companion-new").hidden = true;
    this.lastExplanation = {};
    this.render();
    if (data.state.stage === "finished") this.leave();
  }

  render() {
    const data = this.view;
    this.find(".companion-setup").hidden = true;
    this.find(".companion-confirm").hidden = !data?.needs_confirmation;
    this.find(".companion-menu").hidden = !data;
    this.find(".companion-actions").hidden = !data?.state.focus || data.needs_confirmation;
    this.find(".companion-form").hidden = !data || data.needs_confirmation;
    this.find(".companion-notice").textContent = data?.message || "";
    this.find(".companion-title").textContent = data?.catalog.map_name || this.tr("title");
    this.find(".companion-progress").textContent = data
      ? `${data.completed_count} / ${data.total_count} ${this.tr("completed")}` : "";
    if (!data) return;
    const nav = this.find(".companion-menu nav"); nav.replaceChildren();
    for (const objective of data.catalog.objectives) {
      const button = document.createElement("button"); button.type = "button";
      button.textContent = `${data.state.statuses[objective.id] === "complete" ? "✓ " : ""}${objective.number ? objective.number + ". " : ""}${objective.title}${objective.optional ? " · " + this.tr("optional") : ""}`;
      button.addEventListener("click", () => {
        this.find(".companion-menu").open = false;
        this.act("consult", "", objective.id);
      });
      nav.appendChild(button);
    }
    const answer = this.find(".companion-answer");
    if (data.state.stage === "position") {
      const list = document.createElement("ol");
      for (const objective of data.catalog.objectives.filter(o => o.main)) {
        const item = document.createElement("li"); item.textContent = objective.title; list.appendChild(item);
      }
      answer.replaceChildren(list);
      const question = document.createElement("p"); question.className = "companion-position";
      question.textContent = this.tr("position"); answer.appendChild(question);
    } else if (data.state.stage === "finished") {
      const title = document.createElement("h3"); title.textContent = this.tr("finish");
      const text = document.createElement("p"); text.textContent = this.tr("finishedCopy");
      answer.replaceChildren(title, text);
    } else {
      const objective = data.catalog.objectives.find(o => o.id === data.state.focus);
      this.find(".companion-title").textContent = objective?.title || data.catalog.map_name;
      const notes = [];
      if (objective?.condition && data.state.applicability[objective.id] === undefined) notes.push(this.tr("conditional"));
      const missing = objective?.requires.filter(id => data.state.statuses[id] !== "complete"
        && data.state.applicability[id] !== false) || [];
      if (missing.length) notes.push(this.tr("missing") + missing.map(id => data.catalog.objectives.find(o => o.id === id)?.title).join(", "));
      if (!data.message) this.find(".companion-notice").textContent = notes.join(" ");
    }
  }

  async resume() {
    if (!this.saved) { this.deps.notice(this.storageWarning || this.tr("corrupt")); return; }
    this.enter(this.saved.map_id);
    await this.run(async signal => {
      const data = await this.actionRequest("resume", "", null, signal);
      if (signal.aborted) return;
      await this.accept(data);
      if (data.can_explain) {
        const cached = await this.deps.cachedAnswer?.(data.state);
        if (signal.aborted) return;
        if (cached) this.deps.renderAnswer(this.find(".companion-answer"), cached);
        else await this.explain(signal, {});
      }
    });
  }

  async actionRequest(action, message, objectiveId, signal) {
    return this.deps.requestJson("/companion/action", {
      method: "POST", timeoutMs: 65000, headers: {"Content-Type": "application/json"},
      body: JSON.stringify({state: this.saved, action, message, objective_id: objectiveId}),
    }, signal);
  }

  async act(action, message = "", objectiveId = null) {
    if (!this.view || this.busy) return;
    await this.run(async signal => {
      const title = this.view.catalog.objectives.find(o => o.id === this.saved.focus)?.title || "";
      if (action === "explain") {
        await this.deps.record?.("user", `${this.tr("explain")}: ${title}`, {}, false);
        await this.explain(signal, {deeper: true}); return;
      }
      const data = await this.actionRequest(action, message,
        objectiveId || (action === "complete" ? this.saved.focus : null), signal);
      if (signal.aborted) return;
      const target = this.view.catalog.objectives.find(o => o.id === objectiveId)?.title || title;
      const labels = {complete: `${this.tr("done")}: ${title}`, consult: `${this.deps.locale.startsWith("pt") ? "Consultar etapa" : "Consult step"}: ${target}`,
        confirm: this.tr("confirm"), decline: this.tr("decline")};
      await this.accept(data, {text: message || labels[action] || action, question: data.question_mode});
      // The state and action record commit together BEFORE requesting generated text.
      this.find("textarea").value = "";
      if (data.can_explain) await this.explain(signal, {message, question: data.question_mode});
    });
  }

  async explain(signal, options = {}) {
    this.explanationStarted = true;
    this.lastExplanation = options;
    const job = await this.deps.requestJson("/companion/explain/jobs", {
      method: "POST", headers: {"Content-Type": "application/json"},
      body: JSON.stringify({state: this.saved, ...options}),
    }, signal);
    const response = await this.deps.pollJob(job, signal, progress => this.progress(progress));
    if (signal.aborted) return;
    await this.deps.record?.("assistant", response.answer, {
      blocks: response.blocks, introduction: response.introduction, images: response.relevant_images,
      sources: response.sources,
      companion: {sessionId: this.saved.session_id, focus: this.saved.focus, revision: this.saved.revision},
    });
    if (signal.aborted) return;
    this.deps.renderAnswer(this.find(".companion-answer"), response);
    this.find(".companion-scroll").scrollTop = 0;
  }

  progress(job) {
    const phase = this.words[job.phase] ? this.tr(job.phase) : this.tr("generating");
    this.find(".companion-status").textContent = phase + (job.elapsed_seconds >= 10
      ? ` · ${this.tr("elapsed")}: ${job.elapsed_seconds}s` : "");
  }

  setBusy(busy) {
    this.busy = busy;
    for (const element of this.root.querySelectorAll("button, textarea, select")) {
      element.disabled = busy && !element.classList.contains("companion-cancel")
        && !element.classList.contains("companion-chat");
    }
    this.find(".companion-cancel").hidden = !busy;
    this.find(".companion-form button[type=submit]").hidden = busy;
    if (!busy) this.find(".companion-status").textContent = "";
  }

  async run(work) {
    if (this.busy) return;
    const epoch = ++this.epoch;
    const aborter = new AbortController(); this.aborter = aborter;
    this.setBusy(true);
    this.explanationStarted = false;
    this.find(".companion-error").textContent = this.storageWarning || "";
    this.find(".companion-retry").hidden = true;
    this.find(".companion-status").textContent = this.tr("starting");
    try { await work(aborter.signal); }
    catch (error) {
      if (epoch === this.epoch) {
        this.find(".companion-error").textContent = (aborter.signal.aborted ? "" : error.message + " ") + this.tr("saved");
        this.find(".companion-retry").hidden = !this.explanationStarted
          || !this.view?.state.focus || !!this.view?.needs_confirmation;
        this.find(".companion-new").hidden = error.httpStatus !== 422 || !this.saved;
      }
    } finally {
      if (epoch === this.epoch) {
        this.setBusy(false);
        if (this.active && !this.find("form").hidden && !window.matchMedia("(pointer: coarse)").matches) this.find("textarea").focus();
      }
    }
  }
}
