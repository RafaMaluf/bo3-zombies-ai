/* Durable records are separate from metadata: listing chats never loads their bodies. */
class HistoryStore {
  static async open(name = "krono.history.v1") {
    const db = await new Promise((resolve, reject) => {
      const request = indexedDB.open(name, 1);
      request.onupgradeneeded = () => {
        const database = request.result;
        database.createObjectStore("conversations", {keyPath: "id"}).createIndex("updated", "updated");
        database.createObjectStore("messages", {keyPath: ["conversationId", "seq"]});
        database.createObjectStore("settings");
      };
      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(request.error);
      request.onblocked = () => reject(new Error("Feche as outras abas do Krono e tente novamente."));
    });
    db.onversionchange = () => db.close();
    return new HistoryStore(db);
  }

  constructor(db) { this.db = db; }
  transaction(stores, mode, work) {
    return new Promise((resolve, reject) => {
      const tx = this.db.transaction(stores, mode);
      let value;
      tx.oncomplete = () => resolve(value);
      tx.onabort = () => reject(tx.error || new Error("A conversa mudou em outra aba. Reabra-a antes de continuar."));
      tx.onerror = () => {}; // onabort reports the failed transaction once
      try { work(tx, result => { value = result; }); } catch (error) { tx.abort(); reject(error); }
    });
  }
  get(id) {
    return this.transaction(["conversations"], "readonly", (tx, done) => {
      tx.objectStore("conversations").get(id).onsuccess = event => done(event.target.result);
    });
  }
  create(title, match = null) {
    const now = Date.now();
    const record = {id: crypto.randomUUID(), title, created: now, updated: now, count: 0,
      revision: 0, mapId: match?.map_id || null, match, offered: [], automaticTitle: true};
    return this.transaction(["conversations"], "readwrite", (tx, done) => {
      tx.objectStore("conversations").add(record); done(record);
    });
  }
  list(before = null, limit = 20) {
    return this.transaction(["conversations"], "readonly", (tx, done) => {
      const rows = [];
      const range = before ? IDBKeyRange.upperBound(before.updated) : null;
      tx.objectStore("conversations").index("updated").openCursor(range, "prev").onsuccess = event => {
        const cursor = event.target.result;
        if (!cursor || rows.length === limit) { done(rows); return; }
        if (!before || cursor.value.updated < before.updated
          || (cursor.value.updated === before.updated && cursor.value.id < before.id)) {
          const {id, title, updated, count} = cursor.value;
          rows.push({id, title, updated, count});
        }
        cursor.continue();
      };
    });
  }
  page(id, before = Infinity, limit = 30) {
    return this.transaction(["messages"], "readonly", (tx, done) => {
      const rows = [];
      const range = IDBKeyRange.bound([id, 0], [id, Number.isFinite(before) ? before : Number.MAX_SAFE_INTEGER], false, true);
      tx.objectStore("messages").openCursor(range, "prev").onsuccess = event => {
        const cursor = event.target.result;
        if (!cursor || rows.length === limit) { done(rows.reverse()); return; }
        rows.push(cursor.value); cursor.continue();
      };
    });
  }
  update(id, patch = {}, rows = [], expected = null) {
    return this.transaction(["conversations", "messages"], "readwrite", (tx, done) => {
      const conversations = tx.objectStore("conversations");
      conversations.get(id).onsuccess = event => {
        const record = event.target.result;
        if (!record || (expected !== null && record.revision !== expected)) { tx.abort(); return; }
        Object.assign(record, patch);
        for (const row of rows) {
          tx.objectStore("messages").add({...row, conversationId: id, seq: ++record.count, time: Date.now()});
          if (record.automaticTitle && row.role === "user" && row.text?.trim()) {
            record.title = row.text.trim().slice(0, 80); record.automaticTitle = false;
          }
        }
        record.updated = Date.now(); record.revision += 1;
        conversations.put(record); done(record);
      };
    });
  }
  remove(id) {
    return this.transaction(["conversations", "messages"], "readwrite", tx => {
      tx.objectStore("conversations").delete(id);
      tx.objectStore("messages").delete(IDBKeyRange.bound([id, 0], [id, Number.MAX_SAFE_INTEGER]));
    });
  }
  setting(key, value) {
    return this.transaction(["settings"], value === undefined ? "readonly" : "readwrite", (tx, done) => {
      const store = tx.objectStore("settings");
      if (value === undefined) store.get(key).onsuccess = e => done(e.target.result);
      else { store.put(value, key); done(value); }
    });
  }
  async migrateLegacy(raw, title) {
    if (!raw) return null;
    let match;
    try { match = JSON.parse(raw); } catch { return null; }
    if (match.version !== 1 || !match.map_id || !match.catalog_version) return null;
    // Claim and create in one transaction, so two startup tabs cannot import twice.
    return this.transaction(["settings", "conversations"], "readwrite", (tx, done) => {
      const settings = tx.objectStore("settings");
      settings.get("legacy-match-imported").onsuccess = e => {
        if (e.target.result) { done(null); return; }
        const now = Date.now();
        const record = {id: crypto.randomUUID(), title, created: now, updated: now, revision: 0,
          count: 0, mapId: match.map_id, match, offered: [], automaticTitle: false};
        tx.objectStore("conversations").add(record);
        settings.put(record.id, "legacy-match-imported"); done(record);
      };
    });
  }
}

function transcriptRow(role, text, options = {}, context = true) {
  // Bodies are stored once; images stay as references, never binary/base64 copies.
  const blocks = options.blocks || [];
  return {role, text: blocks.length ? "" : text, context, companion: options.companion || null,
    options: {blocks, introduction: blocks.length ? options.introduction || "" : "", images: blocks.length ? [] : options.images || [],
      sources: options.sources || [], clarification: !!options.clarification, error: !!options.error,
      suggestedMapIds: options.suggestedMapIds || [], suggestedQueries: options.suggestedQueries || [],
      retryMessage: options.retryMessage || ""}};
}
function transcriptText(row) {
  return [row.text, row.options?.introduction, ...(row.options?.blocks || []).map(b => `${b.title}\n${b.body}`)]
    .filter(Boolean).join("\n\n");
}
if (typeof module !== "undefined") module.exports = {HistoryStore, transcriptRow, transcriptText};
