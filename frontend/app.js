(function () {
  "use strict";

  const API_BASE = window.RAG_CONFIG.API_BASE;

  const el = {
    apiStatusDot: document.getElementById("apiStatusDot"),
    apiStatusLabel: document.getElementById("apiStatusLabel"),
    viewTitle: document.getElementById("viewTitle"),
    viewSubtitle: document.getElementById("viewSubtitle"),

    // dashboard
    statTotal: document.getElementById("statTotal"),
    statCompleted: document.getElementById("statCompleted"),
    statProcessing: document.getElementById("statProcessing"),
    statFailed: document.getElementById("statFailed"),
    statChunks: document.getElementById("statChunks"),
    healthDb: document.getElementById("healthDb"),
    healthVector: document.getElementById("healthVector"),
    healthConfig: document.getElementById("healthConfig"),
    recentDocsList: document.getElementById("recentDocsList"),

    // documents
    dropZone: document.getElementById("dropZone"),
    fileInput: document.getElementById("fileInput"),
    rawTextForm: document.getElementById("rawTextForm"),
    rawTextFilename: document.getElementById("rawTextFilename"),
    rawTextContent: document.getElementById("rawTextContent"),
    documentTableBody: document.getElementById("documentTableBody"),

    // chat
    scopeSelect: document.getElementById("scopeSelect"),
    transcript: document.getElementById("transcript"),
    queryForm: document.getElementById("queryForm"),
    queryInput: document.getElementById("queryInput"),
    askButton: document.getElementById("askButton"),
    clearChatBtn: document.getElementById("clearChatBtn"),

    // search
    searchForm: document.getElementById("searchForm"),
    searchQueryInput: document.getElementById("searchQueryInput"),
    searchTopK: document.getElementById("searchTopK"),
    searchResults: document.getElementById("searchResults"),

    // settings
    settingsModels: document.getElementById("settingsModels"),
    settingsChunking: document.getElementById("settingsChunking"),
    settingsRetrieval: document.getElementById("settingsRetrieval"),
    settingsUploads: document.getElementById("settingsUploads"),

    // drawer
    drawerOverlay: document.getElementById("drawerOverlay"),
    drawerTitle: document.getElementById("drawerTitle"),
    drawerBody: document.getElementById("drawerBody"),
    drawerClose: document.getElementById("drawerClose"),

    toastStack: document.getElementById("toastStack"),
  };

  const answerTemplate = document.getElementById("answerTemplate");
  const questionTemplate = document.getElementById("questionTemplate");

  const VIEW_META = {
    dashboard: { title: "Dashboard", subtitle: "An overview of what's in the catalog." },
    documents: { title: "Documents", subtitle: "File, review, reindex, and remove documents." },
    chat: { title: "RAG Chat", subtitle: "Ask questions answered only from your documents." },
    search: { title: "Search", subtitle: "Inspect raw retrieval results before asking a question." },
    settings: { title: "Settings", subtitle: "Currently active configuration (read-only)." },
  };

  let documents = [];
  let pollHandle = null;
  let settingsLoaded = false;
  let dashboardLoaded = false;

  // ---------------------------------------------------------------------
  // Toasts
  // ---------------------------------------------------------------------
  function toast(message, kind) {
    const node = document.createElement("div");
    node.className = `toast${kind ? ` toast-${kind}` : ""}`;
    node.textContent = message;
    el.toastStack.appendChild(node);
    setTimeout(() => {
      node.classList.add("toast-hide");
      setTimeout(() => node.remove(), 200);
    }, 4000);
  }

  // ---------------------------------------------------------------------
  // View routing
  // ---------------------------------------------------------------------
  function showView(name) {
    document.querySelectorAll(".view").forEach((v) => v.classList.toggle("active", v.id === `view-${name}`));
    document.querySelectorAll(".nav-item").forEach((btn) => btn.classList.toggle("active", btn.dataset.view === name));
    const meta = VIEW_META[name] || { title: name, subtitle: "" };
    el.viewTitle.textContent = meta.title;
    el.viewSubtitle.textContent = meta.subtitle;

    if (name === "settings" && !settingsLoaded) loadSettings();
  }

  document.querySelectorAll(".nav-item").forEach((btn) => {
    btn.addEventListener("click", () => showView(btn.dataset.view));
  });
  document.querySelectorAll("[data-view-link]").forEach((btn) => {
    btn.addEventListener("click", () => showView(btn.dataset.viewLink));
  });

  // ---------------------------------------------------------------------
  // API helpers
  // ---------------------------------------------------------------------
  async function apiFetch(path, options) {
    const response = await fetch(`${API_BASE}${path}`, options);
    let body = null;
    try {
      body = await response.json();
    } catch (_) {
      /* no body */
    }
    if (!response.ok) {
      const message = (body && body.error && body.error.message) || `Request failed (${response.status})`;
      throw new Error(message);
    }
    return body;
  }

  async function checkHealth() {
    try {
      const rootBase = API_BASE.replace(/\/api\/v1\/?$/, "");
      const response = await fetch(`${rootBase}/health`);
      setApiStatus(response.ok);
    } catch (_) {
      setApiStatus(false);
    }
  }

  function setApiStatus(ok) {
    el.apiStatusDot.classList.toggle("ok", ok);
    el.apiStatusDot.classList.toggle("bad", !ok);
    el.apiStatusLabel.textContent = ok ? "All systems online" : "Backend unreachable";
  }

  async function refreshReadiness() {
    try {
      const data = await apiFetch("/health/ready");
      setPill(el.healthDb, data.checks.database === "ok");
      setPill(el.healthVector, data.checks.vector_extension === "ok");
      setPill(el.healthConfig, data.checks.configuration === "ok");
    } catch (_) {
      [el.healthDb, el.healthVector, el.healthConfig].forEach((p) => setPill(p, false, "unknown"));
    }
  }

  function setPill(node, ok, label) {
    node.textContent = label || (ok ? "ok" : "issue");
    node.classList.toggle("pill-ok", ok);
    node.classList.toggle("pill-bad", !ok);
  }

  // ---------------------------------------------------------------------
  // Documents: fetch + render (table, dashboard stats, chat scope)
  // ---------------------------------------------------------------------
  async function refreshDocuments() {
    try {
      const data = await apiFetch("/documents");
      documents = data.documents || [];
      renderDashboardStats();
      renderRecentDocs();
      renderDocumentTable();
      renderScopeOptions();
      setApiStatus(true);
    } catch (err) {
      setApiStatus(false);
    }
  }

  function renderDashboardStats() {
    const completed = documents.filter((d) => d.status === "completed");
    const processing = documents.filter((d) => d.status === "processing" || d.status === "uploaded");
    const failed = documents.filter((d) => d.status === "failed");
    const totalChunks = documents.reduce((sum, d) => sum + (d.chunk_count || 0), 0);

    setStat(el.statTotal, documents.length);
    setStat(el.statCompleted, completed.length);
    setStat(el.statProcessing, processing.length);
    setStat(el.statFailed, failed.length);
    setStat(el.statChunks, totalChunks);
    dashboardLoaded = true;
  }

  function setStat(node, value) {
    node.textContent = value;
    node.classList.remove("is-loading");
  }

  function renderRecentDocs() {
    const recent = [...documents].slice(0, 5);
    if (recent.length === 0) {
      el.recentDocsList.innerHTML = '<li class="empty-row">No documents yet.</li>';
      return;
    }
    el.recentDocsList.innerHTML = "";
    for (const doc of recent) {
      const li = document.createElement("li");
      li.innerHTML = `<span class="doc-name"></span><span class="status-badge status-${doc.status}"></span>`;
      li.querySelector(".doc-name").textContent = doc.original_filename;
      li.querySelector(".status-badge").textContent = doc.status;
      el.recentDocsList.appendChild(li);
    }
  }

  function renderDocumentTable() {
    if (documents.length === 0) {
      el.documentTableBody.innerHTML = `<tr><td colspan="7"><div class="empty-state">
        <span class="empty-icon">＋</span>
        <span class="empty-title">The shelf is empty</span>
        <p>File a document above to begin — PDF, DOC, DOCX, TXT, or pasted raw text.</p>
      </div></td></tr>`;
      return;
    }
    el.documentTableBody.innerHTML = "";
    for (const doc of documents) {
      const tr = document.createElement("tr");
      tr.className = "row-clickable";
      tr.dataset.id = doc.id;

      const uploaded = new Date(doc.created_at);
      const uploadedLabel = isNaN(uploaded) ? "–" : uploaded.toLocaleDateString();
      const sizeLabel = formatBytes(doc.file_size);

      tr.innerHTML = `
        <td class="filename-cell"></td>
        <td class="mono-cell"></td>
        <td class="mono-cell"></td>
        <td class="mono-cell"></td>
        <td><span class="status-badge"></span></td>
        <td class="mono-cell"></td>
        <td class="row-actions">
          <button class="reindex">↻ Reindex</button>
          <button class="delete">✕ Delete</button>
        </td>
      `;
      tr.querySelector(".filename-cell").textContent = doc.original_filename;
      const cells = tr.querySelectorAll(".mono-cell");
      cells[0].textContent = `.${doc.file_type}`;
      cells[1].textContent = sizeLabel;
      cells[2].textContent = uploadedLabel;
      cells[3].textContent = doc.status === "completed" ? doc.chunk_count : "–";

      const badge = tr.querySelector(".status-badge");
      badge.textContent = doc.status;
      badge.classList.add(`status-${doc.status}`);

      const reindexBtn = tr.querySelector(".reindex");
      const deleteBtn = tr.querySelector(".delete");
      if (doc.status === "processing") reindexBtn.disabled = true;

      reindexBtn.addEventListener("click", (e) => { e.stopPropagation(); reindexDocument(doc.id); });
      deleteBtn.addEventListener("click", (e) => { e.stopPropagation(); deleteDocument(doc.id, doc.original_filename); });
      tr.addEventListener("click", () => openDrawer(doc));

      el.documentTableBody.appendChild(tr);
    }
  }

  function renderScopeOptions() {
    const current = el.scopeSelect.value;
    el.scopeSelect.innerHTML = '<option value="">All documents</option>';
    for (const doc of documents) {
      if (doc.status !== "completed") continue;
      const opt = document.createElement("option");
      opt.value = doc.id;
      opt.textContent = doc.original_filename;
      el.scopeSelect.appendChild(opt);
    }
    if ([...el.scopeSelect.options].some((o) => o.value === current)) {
      el.scopeSelect.value = current;
    }
  }

  function formatBytes(bytes) {
    if (!bytes && bytes !== 0) return "–";
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  }

  function startPollingIfNeeded() {
    const hasInFlight = documents.some((d) => d.status === "uploaded" || d.status === "processing");
    if (hasInFlight && !pollHandle) {
      pollHandle = setInterval(async () => {
        await refreshDocuments();
        const stillInFlight = documents.some((d) => d.status === "uploaded" || d.status === "processing");
        if (!stillInFlight) {
          clearInterval(pollHandle);
          pollHandle = null;
        }
      }, 2500);
    }
  }

  // ---------------------------------------------------------------------
  // Document actions
  // ---------------------------------------------------------------------
  async function uploadFile(file) {
    const allowed = ["pdf", "doc", "docx", "txt"];
    const ext = (file.name.split(".").pop() || "").toLowerCase();
    if (!allowed.includes(ext)) {
      toast(`Unsupported file type ".${ext}". Allowed: ${allowed.join(", ")}`, "error");
      return;
    }
    const formData = new FormData();
    formData.append("file", file);
    try {
      await apiFetch("/documents/upload", { method: "POST", body: formData });
      toast(`Uploaded "${file.name}" — processing started.`, "success");
      await refreshDocuments();
      startPollingIfNeeded();
    } catch (err) {
      toast(`Upload failed: ${err.message}`, "error");
    }
  }

  async function reindexDocument(id) {
    try {
      await apiFetch(`/documents/${id}/reindex`, { method: "POST" });
      toast("Reindexing started.", "success");
      await refreshDocuments();
      startPollingIfNeeded();
      closeDrawer();
    } catch (err) {
      toast(`Reindex failed: ${err.message}`, "error");
    }
  }

  async function deleteDocument(id, name) {
    if (!confirm(`Remove "${name}" from the catalog? This also deletes its chunks.`)) return;
    try {
      await apiFetch(`/documents/${id}`, { method: "DELETE" });
      toast(`Deleted "${name}".`, "success");
      await refreshDocuments();
      closeDrawer();
    } catch (err) {
      toast(`Delete failed: ${err.message}`, "error");
    }
  }

  // ---------------------------------------------------------------------
  // Document drawer
  // ---------------------------------------------------------------------
  function openDrawer(doc) {
    el.drawerTitle.textContent = doc.original_filename;
    const uploaded = new Date(doc.created_at);
    const uploadedLabel = isNaN(uploaded) ? "–" : uploaded.toLocaleString();

    let html = "";
    if (doc.status === "failed" && doc.error_message) {
      html += `<div class="error-box">${escapeHtml(doc.error_message)}</div>`;
    }
    html += `
      <dl class="kv-list">
        <div><dt>Status</dt><dd>${doc.status}</dd></div>
        <div><dt>Type</dt><dd>.${doc.file_type}</dd></div>
        <div><dt>Size</dt><dd>${formatBytes(doc.file_size)}</dd></div>
        <div><dt>Chunks</dt><dd>${doc.chunk_count}</dd></div>
        <div><dt>Uploaded</dt><dd>${uploadedLabel}</dd></div>
        <div><dt>Content hash</dt><dd style="font-size:10.5px;">${doc.content_hash.slice(0, 16)}…</dd></div>
      </dl>
      <div class="entry-label" style="margin-bottom:6px;">Metadata</div>
      <pre>${escapeHtml(JSON.stringify(doc.metadata || {}, null, 2))}</pre>
      <div class="drawer-actions">
        <button class="primary reindex-action" ${doc.status === "processing" ? "disabled" : ""}>↻ Reindex</button>
        <button class="danger delete-action">✕ Delete</button>
      </div>
    `;
    el.drawerBody.innerHTML = html;
    el.drawerBody.querySelector(".reindex-action").addEventListener("click", () => reindexDocument(doc.id));
    el.drawerBody.querySelector(".delete-action").addEventListener("click", () => deleteDocument(doc.id, doc.original_filename));

    el.drawerOverlay.classList.add("open");
  }

  function closeDrawer() {
    el.drawerOverlay.classList.remove("open");
  }

  el.drawerClose.addEventListener("click", closeDrawer);
  el.drawerOverlay.addEventListener("click", (e) => { if (e.target === el.drawerOverlay) closeDrawer(); });
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") closeDrawer(); });

  // ---------------------------------------------------------------------
  // Chat
  // ---------------------------------------------------------------------
  function clearTranscriptEmptyState() {
    const empty = el.transcript.querySelector(".transcript-empty");
    if (empty) empty.remove();
  }

  function appendQuestion(text) {
    clearTranscriptEmptyState();
    const node = questionTemplate.content.cloneNode(true);
    node.querySelector(".entry-text").textContent = text;
    el.transcript.appendChild(node);
    el.transcript.scrollTop = el.transcript.scrollHeight;
  }

  function appendLoadingAnswer() {
    clearTranscriptEmptyState();
    const wrap = document.createElement("div");
    wrap.className = "entry entry-answer entry-loading-wrap";
    wrap.innerHTML = '<div class="entry-label">Answer</div><p class="entry-loading">Consulting the catalog…</p>';
    el.transcript.appendChild(wrap);
    el.transcript.scrollTop = el.transcript.scrollHeight;
    return wrap;
  }

  function escapeHtml(str) {
    const div = document.createElement("div");
    div.textContent = str;
    return div.innerHTML;
  }

  async function askQuestion(query) {
    appendQuestion(query);
    const placeholder = appendLoadingAnswer();

    el.askButton.disabled = true;
    try {
      const payload = { query };
      if (el.scopeSelect.value) payload.document_id = el.scopeSelect.value;

      const data = await apiFetch("/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      const answerNode = answerTemplate.content.cloneNode(true);
      const entryEl = answerNode.querySelector(".entry-answer");
      answerNode.querySelector(".entry-text").textContent = data.data.answer;

      const actions = document.createElement("div");
      actions.className = "entry-actions";
      const copyBtn = document.createElement("button");
      copyBtn.textContent = "Copy answer";
      copyBtn.addEventListener("click", () => {
        navigator.clipboard.writeText(data.data.answer).then(() => toast("Answer copied.", "success"));
      });
      actions.appendChild(copyBtn);
      answerNode.querySelector(".entry-text").after(actions);

      const rail = answerNode.querySelector(".citation-rail");
      const sources = data.data.sources || [];
      if (sources.length > 0) {
        sources.forEach((s, i) => {
          const row = document.createElement("div");
          row.className = "citation";
          const pageLabel = s.page ? `, p. ${s.page}` : "";
          row.innerHTML = `<span class="cite-index">[${i + 1}]</span><span class="cite-file"></span><span class="cite-score">${(s.score * 100).toFixed(0)}%</span>`;
          row.querySelector(".cite-file").textContent = `${s.filename}${pageLabel}`;
          rail.appendChild(row);
        });
      } else {
        const row = document.createElement("div");
        row.className = "citation";
        row.textContent = "No matching source passages found.";
        rail.appendChild(row);
      }

      placeholder.replaceWith(entryEl);
      el.transcript.scrollTop = el.transcript.scrollHeight;
    } catch (err) {
      placeholder.classList.add("entry-error");
      placeholder.innerHTML = `<div class="entry-label">Error</div><p class="entry-loading">${escapeHtml(err.message)}</p>`;
    } finally {
      el.askButton.disabled = false;
    }
  }

  el.clearChatBtn.addEventListener("click", () => {
    el.transcript.innerHTML = '<div class="transcript-empty"><p>Ask a question below. Answers are drawn only from documents in the catalog, with citations back to the exact source and page.</p></div>';
  });

  // ---------------------------------------------------------------------
  // Search (retrieval only)
  // ---------------------------------------------------------------------
  el.searchForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const query = el.searchQueryInput.value.trim();
    if (!query) return;
    const topK = Math.max(1, Math.min(50, parseInt(el.searchTopK.value, 10) || 5));

    el.searchResults.innerHTML = '<li class="empty-row">Searching…</li>';
    try {
      const data = await apiFetch("/search", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query, top_k: topK }),
      });
      renderSearchResults(data.results || []);
    } catch (err) {
      el.searchResults.innerHTML = "";
      toast(`Search failed: ${err.message}`, "error");
    }
  });

  function renderSearchResults(results) {
    if (results.length === 0) {
      el.searchResults.innerHTML = `<li><div class="empty-state">
        <span class="empty-icon">⌕</span>
        <span class="empty-title">No matching chunks</span>
        <p>Try rephrasing the query, or lower SIMILARITY_THRESHOLD in .env if you expect a match here.</p>
      </div></li>`;
      return;
    }
    el.searchResults.innerHTML = "";
    results.forEach((r) => {
      const li = document.createElement("li");
      li.className = "result-item";
      const pageLabel = r.page ? `, p. ${r.page}` : "";
      li.innerHTML = `
        <div class="result-head">
          <span></span>
          <span class="result-score"></span>
        </div>
        <p class="result-text"></p>
      `;
      li.querySelector(".result-head span").textContent = `${r.filename}${pageLabel}`;
      li.querySelector(".result-score").textContent = `${(r.score * 100).toFixed(1)}% match`;
      li.querySelector(".result-text").textContent = r.content;
      el.searchResults.appendChild(li);
    });
  }

  // ---------------------------------------------------------------------
  // Settings (read-only)
  // ---------------------------------------------------------------------
  async function loadSettings() {
    try {
      const data = await apiFetch("/settings");
      settingsLoaded = true;

      fillKv(el.settingsModels, {
        "Embedding provider": data.embedding.provider,
        "Embedding model": data.embedding.model,
        "Embedding dimension": data.embedding.dimension,
        "LLM provider": data.llm.provider,
        "LLM model": data.llm.model,
        "Temperature": data.llm.temperature,
      });
      fillKv(el.settingsChunking, {
        "Chunk size": data.chunking.chunk_size,
        "Chunk overlap": data.chunking.chunk_overlap,
        "Min chunk size": data.chunking.min_chunk_size,
        "Max chunk size": data.chunking.max_chunk_size,
      });
      fillKv(el.settingsRetrieval, {
        "Top-K": data.retrieval.top_k,
        "Similarity threshold": data.retrieval.similarity_threshold,
        "Max context chars": data.retrieval.max_context_chars,
        "Reranking enabled": data.retrieval.reranking_enabled ? "yes" : "no",
      });
      fillKv(el.settingsUploads, {
        "Allowed extensions": data.uploads.allowed_extensions.join(", "),
        "Max upload size": `${data.uploads.max_upload_size_mb} MB`,
      });
    } catch (err) {
      toast(`Could not load settings: ${err.message}`, "error");
    }
  }

  function fillKv(node, obj) {
    node.innerHTML = "";
    for (const [k, v] of Object.entries(obj)) {
      const row = document.createElement("div");
      row.innerHTML = `<dt></dt><dd></dd>`;
      row.querySelector("dt").textContent = k;
      row.querySelector("dd").textContent = v;
      node.appendChild(row);
    }
  }

  // ---------------------------------------------------------------------
  // Event wiring: intake
  // ---------------------------------------------------------------------
  el.fileInput.addEventListener("change", (e) => {
    if (e.target.files && e.target.files[0]) uploadFile(e.target.files[0]);
    e.target.value = "";
  });

  ["dragover", "dragenter"].forEach((evt) =>
    el.dropZone.addEventListener(evt, (e) => { e.preventDefault(); el.dropZone.classList.add("dragover"); })
  );
  ["dragleave", "drop"].forEach((evt) =>
    el.dropZone.addEventListener(evt, (e) => { e.preventDefault(); el.dropZone.classList.remove("dragover"); })
  );
  el.dropZone.addEventListener("drop", (e) => {
    const file = e.dataTransfer.files && e.dataTransfer.files[0];
    if (file) uploadFile(file);
  });

  el.rawTextForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const filename = el.rawTextFilename.value.trim();
    const text = el.rawTextContent.value.trim();
    if (!filename || !text) return;
    try {
      await apiFetch("/documents/text", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text, filename }),
      });
      toast(`Added "${filename}" to the catalog.`, "success");
      el.rawTextFilename.value = "";
      el.rawTextContent.value = "";
      await refreshDocuments();
    } catch (err) {
      toast(`Ingestion failed: ${err.message}`, "error");
    }
  });

  el.queryForm.addEventListener("submit", (e) => {
    e.preventDefault();
    const query = el.queryInput.value.trim();
    if (!query) return;
    el.queryInput.value = "";
    askQuestion(query);
  });

  // ---------------------------------------------------------------------
  // Init
  // ---------------------------------------------------------------------
  [el.statTotal, el.statCompleted, el.statProcessing, el.statFailed, el.statChunks].forEach((n) =>
    n.classList.add("is-loading")
  );
  checkHealth();
  refreshDocuments();
  refreshReadiness();
  setInterval(checkHealth, 15000);
  setInterval(refreshDocuments, 15000);
  setInterval(refreshReadiness, 20000);
})();