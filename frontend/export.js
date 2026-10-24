/* On-demand print view. No conversation upload or server-side PDF generation. */
(async () => {
  const params = new URLSearchParams(location.search);
  const pt = params.get("lang") !== "en";
  document.documentElement.lang = pt ? "pt-BR" : "en";
  const status = document.getElementById("export-status");
  const print = document.getElementById("print-pdf");
  print.textContent = pt ? "Salvar como PDF" : "Save as PDF";
  document.getElementById("export-help").textContent = pt
    ? "Na janela de impressão, escolha ‘Salvar como PDF’. O arquivo inclui textos e imagens e pode ser compartilhado."
    : "Choose ‘Save as PDF’ in the print dialog. Text and images are included for sharing.";
  print.onclick = () => {
    try { window.print(); }
    catch { status.textContent = pt ? "Abra esta prévia no Firefox ou Chrome para usar a impressão e salvar em PDF."
      : "Open this preview in Firefox or Chrome to print and save as PDF."; }
  };
  const pendingImages = [];
  function pictures(images) {
    const gallery = document.createElement("div"); gallery.className = "export-images";
    const used = new Set();
    for (const image of images || []) {
      if (!/^img_[a-f0-9]{16}$/.test(image.id) || used.has(image.id)) continue;
      used.add(image.id);
      const figure = document.createElement("figure");
      const img = document.createElement("img"); img.alt = pt ? "Imagem da etapa" : "Step image";
      pendingImages.push({img, figure, id: image.id}); figure.appendChild(img); gallery.appendChild(figure);
    }
    return gallery;
  }
  function message(row) {
    const article = document.createElement("article"); article.className = "export-message";
    const author = document.createElement("h2"); author.textContent = row.role === "user" ? (pt ? "Você" : "You") : "Krono";
    article.appendChild(author);
    const options = row.options || {};
    const text = document.createElement("div");
    text.innerHTML = renderMarkdown(options.blocks?.length ? options.introduction || "" : row.text || "");
    article.appendChild(text);
    for (const block of options.blocks || []) {
      const section = document.createElement("section");
      if (block.title) { const h = document.createElement("h3"); h.textContent = block.title; section.appendChild(h); }
      const body = document.createElement("div"); body.innerHTML = renderMarkdown(block.body);
      section.append(body, pictures(block.images)); article.appendChild(section);
    }
    if (!options.blocks?.length) article.appendChild(pictures(options.images));
    return article;
  }
  let store;
  try {
    store = await HistoryStore.open();
    const record = await store.get(params.get("conversation"));
    if (!record) throw new Error(pt ? "Conversa não encontrada neste navegador." : "Conversation not found in this browser.");
    document.getElementById("export-title").textContent = record.title;
    document.title = `${record.title} - Krono`;
    let before = record.count + 1;
    let count = 0;
    const root = document.getElementById("export-messages");
    // Read newest-to-oldest pages, then render chronologically before collecting images.
    const pages = [];
    while (before > 1) {
      const rows = await store.page(record.id, before, 30);
      if (!rows.length) break;
      pages.unshift(rows); before = rows[0].seq;
    }
    for (const rows of pages) {
      const fragment = document.createDocumentFragment();
      for (const row of rows) { fragment.appendChild(message(row)); count++; }
      root.appendChild(fragment);
    }
    if (count !== record.count) throw new Error(pt ? "A conversa mudou. Reabra a exportação." : "Conversation changed. Reopen the export.");
    pages.length = 0; store.db.close(); store = null;
    let missing = 0;
    let next = 0;
    async function loadImages() {
      while (next < pendingImages.length) {
        const {img, figure, id} = pendingImages[next++];
        await new Promise(resolve => {
          let settled = false;
          const finish = ok => {
            if (settled) return; settled = true; clearTimeout(timer);
            if (!ok) { missing++; img.remove(); figure.className = "missing-image";
              figure.textContent = pt ? "Imagem indisponível nesta exportação." : "Image unavailable in this export."; }
            resolve();
          };
          const timer = setTimeout(() => finish(false), 15000);
          img.onload = () => finish(true); img.onerror = () => finish(false);
          img.src = `/media/${encodeURIComponent(id)}?variant=thumb`;
        });
      }
    }
    await Promise.all(Array.from({length: 4}, loadImages));
    status.textContent = missing
      ? (pt ? `${missing} imagem(ns) indisponível(is). Você pode salvar o texto e as imagens restantes.` : `${missing} image(s) unavailable. Text and remaining images can be saved.`)
      : (pt ? "Pronto para salvar em PDF." : "Ready to save as PDF.");
    print.disabled = false;
  } catch (error) {
    store?.db.close(); status.textContent = error.message;
  }
})();
