(function () {
  "use strict";

  const apiBaseInput = document.getElementById("api-base");

  function apiBase() {
    return apiBaseInput.value.replace(/\/+$/, "");
  }

  function el(id) {
    return document.getElementById(id);
  }

  function show(elem) {
    elem.classList.remove("hidden");
  }

  function hide(elem) {
    elem.classList.add("hidden");
  }

  function escapeHtml(text) {
    const div = document.createElement("div");
    div.textContent = text == null ? "" : String(text);
    return div.innerHTML;
  }

  // ---------- Tabs ----------

  document.querySelectorAll(".tab-button").forEach((button) => {
    button.addEventListener("click", () => {
      document.querySelectorAll(".tab-button").forEach((b) => b.classList.remove("active"));
      document.querySelectorAll(".tab-panel").forEach((p) => p.classList.remove("active"));
      button.classList.add("active");
      el("tab-" + button.dataset.tab).classList.add("active");
    });
  });

  // ---------- Ask ----------

  const askForm = el("ask-form");
  const askSubmit = el("ask-submit");

  askForm.addEventListener("submit", async (event) => {
    event.preventDefault();

    const question = el("question-input").value.trim();
    if (!question) return;

    const webFallback = el("web-fallback-checkbox").checked;
    const debug = el("debug-checkbox").checked;

    hide(el("ask-error"));
    hide(el("answer-block"));
    hide(el("debug-panel"));
    show(el("ask-loading"));
    askSubmit.disabled = true;

    try {
      const response = await fetch(apiBase() + "/ask", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question, web_fallback: webFallback, debug }),
      });

      if (!response.ok) {
        const body = await response.text();
        throw new Error(`Request failed (${response.status}): ${body}`);
      }

      const data = await response.json();
      renderAnswer(data);
    } catch (err) {
      el("ask-error").textContent =
        "Could not reach the backend at " + apiBase() + ". Is it running? Details: " + err.message;
      show(el("ask-error"));
    } finally {
      hide(el("ask-loading"));
      askSubmit.disabled = false;
    }
  });

  function statusBadgeClass(status) {
    return "status-" + String(status || "").toLowerCase();
  }

  function renderAnswer(data) {
    el("answer-text").textContent = data.answer;

    const retrievalBadge = el("retrieval-status-badge");
    retrievalBadge.textContent = "Retrieval: " + data.retrieval_status;
    retrievalBadge.className = "badge " + statusBadgeClass(data.retrieval_status);

    const groundingBadge = el("grounding-status-badge");
    groundingBadge.textContent = "Grounding: " + data.grounding_status;
    groundingBadge.className = "badge " + statusBadgeClass(data.grounding_status);

    const sourcesList = el("sources-list");
    sourcesList.innerHTML = "";
    if (!data.sources || data.sources.length === 0) {
      const li = document.createElement("li");
      li.textContent = "No sources.";
      sourcesList.appendChild(li);
    } else {
      data.sources.forEach((source) => {
        const li = document.createElement("li");
        const isWeb = source.source_type === "WEB_SOURCE";
        const tagClass = isWeb ? "web" : "local";
        const tagText = isWeb ? "web" : "local";
        const pageText = source.page ? `, page ${source.page}` : "";
        li.innerHTML =
          `<span class="source-tag ${tagClass}">${tagText}</span>` +
          `<span>[${escapeHtml(source.id)}] ${escapeHtml(source.source)}${escapeHtml(pageText)}</span>`;
        sourcesList.appendChild(li);
      });
    }

    show(el("answer-block"));

    if (data.debug) {
      renderDebug(data.debug);
      show(el("debug-panel"));
    }
  }

  function renderDebug(debug) {
    el("debug-rounds").innerHTML = (debug.rounds || [])
      .map(
        (r) =>
          `<pre>Round ${r.round} — query: ${escapeHtml(r.query)}\n` +
          `decision: ${r.quality.decision} (score=${r.quality.quality_score.toFixed(2)}, ` +
          `mean=${r.quality.mean_score.toFixed(2)}, best=${r.quality.best_score.toFixed(2)}, ` +
          `relevant_ratio=${r.quality.relevant_ratio.toFixed(2)})</pre>`
      )
      .join("") || "<p>No rounds recorded.</p>";

    el("debug-rewrites").innerHTML = (debug.rewrites || [])
      .map(
        (r) =>
          `<pre>${escapeHtml(r.original_query)}\n-> ${escapeHtml(r.rewritten_query)}\n(${escapeHtml(r.reason)})</pre>`
      )
      .join("") || "<p>No query rewrites were needed.</p>";

    if (debug.web_search_triggered) {
      const results = (debug.web_results || [])
        .map((w) => `<pre>${escapeHtml(w.title)}\n${escapeHtml(w.url)}\n${escapeHtml(w.snippet)}</pre>`)
        .join("");
      el("debug-web").innerHTML =
        `<p>Triggered: yes · Used in answer: ${debug.web_used ? "yes" : "no"}</p>` + results;
    } else {
      el("debug-web").innerHTML = "<p>Web fallback was not triggered.</p>";
    }

    el("debug-evidence").innerHTML = (debug.evidence || [])
      .map(
        (e) =>
          `<pre>[${escapeHtml(e.id)}] (${escapeHtml(e.type)}) ${escapeHtml(e.source)}${
            e.location ? " — " + escapeHtml(e.location) : ""
          }\n${escapeHtml(e.text)}</pre>`
      )
      .join("") || "<p>No evidence.</p>";

    const verification = debug.verification;
    if (verification) {
      const claims = (verification.claims || [])
        .map(
          (c) =>
            `<pre>${c.supported ? "SUPPORTED" : "UNSUPPORTED"} (confidence=${c.confidence.toFixed(2)})\n"${escapeHtml(
              c.claim
            )}"\nevidence: ${escapeHtml((c.evidence_ids || []).join(", ") || "none")}</pre>`
        )
        .join("");
      el("debug-verification").innerHTML =
        `<p>Grounding score: ${verification.grounding_score.toFixed(2)} — status: ${verification.status}. ` +
        `Draft answer corrected: ${debug.answer_corrected ? "yes" : "no"} ` +
        `(attempts: ${debug.correction_attempts}, gave up: ${debug.gave_up_on_correction ? "yes" : "no"})</p>` +
        claims;
    } else {
      el("debug-verification").innerHTML = "<p>No verification data.</p>";
    }
  }

  // ---------- Documents ----------

  const uploadForm = el("upload-form");

  uploadForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const fileInput = el("file-input");
    const file = fileInput.files[0];
    if (!file) return;

    const statusEl = el("upload-status");
    statusEl.textContent = "Uploading " + file.name + " ...";

    try {
      const formData = new FormData();
      formData.append("file", file);

      const uploadResponse = await fetch(apiBase() + "/documents/upload", {
        method: "POST",
        body: formData,
      });
      if (!uploadResponse.ok) {
        throw new Error(`Upload failed (${uploadResponse.status}): ${await uploadResponse.text()}`);
      }
      const uploadData = await uploadResponse.json();

      statusEl.textContent = "Indexing " + uploadData.filename + " ...";
      const indexResponse = await fetch(
        apiBase() + "/documents/index?filename=" + encodeURIComponent(uploadData.filename),
        { method: "POST" }
      );
      if (!indexResponse.ok) {
        throw new Error(`Indexing failed (${indexResponse.status}): ${await indexResponse.text()}`);
      }
      const indexData = await indexResponse.json();

      statusEl.textContent = `Indexed "${indexData.source}" — ${indexData.chunks_indexed} chunk(s).`;
      fileInput.value = "";
      loadDocuments();
    } catch (err) {
      statusEl.textContent = "Error: " + err.message;
    }
  });

  async function loadDocuments() {
    const tbody = el("documents-body");
    tbody.innerHTML = '<tr><td colspan="5">Loading...</td></tr>';
    try {
      const response = await fetch(apiBase() + "/documents");
      if (!response.ok) throw new Error(`Request failed (${response.status})`);
      const documents = await response.json();

      if (documents.length === 0) {
        tbody.innerHTML = '<tr><td colspan="5">No documents indexed yet.</td></tr>';
        return;
      }

      tbody.innerHTML = "";
      documents.forEach((doc) => {
        const tr = document.createElement("tr");
        tr.innerHTML =
          `<td>${escapeHtml(doc.title)}</td>` +
          `<td>${escapeHtml(doc.source)}</td>` +
          `<td>${doc.chunk_count}</td>` +
          `<td>${escapeHtml(doc.indexed_at)}</td>` +
          `<td><button data-doc-id="${escapeHtml(doc.document_id)}" class="delete-doc-btn">Delete</button></td>`;
        tbody.appendChild(tr);
      });

      tbody.querySelectorAll(".delete-doc-btn").forEach((btn) => {
        btn.addEventListener("click", async () => {
          btn.disabled = true;
          try {
            const resp = await fetch(apiBase() + "/documents/" + encodeURIComponent(btn.dataset.docId), {
              method: "DELETE",
            });
            if (!resp.ok) throw new Error(`Delete failed (${resp.status})`);
            loadDocuments();
          } catch (err) {
            alert("Could not delete document: " + err.message);
            btn.disabled = false;
          }
        });
      });
    } catch (err) {
      tbody.innerHTML = `<tr><td colspan="5">Could not load documents: ${escapeHtml(err.message)}</td></tr>`;
    }
  }

  el("refresh-documents").addEventListener("click", loadDocuments);

  // ---------- Evaluation ----------

  const evalForm = el("eval-form");

  evalForm.addEventListener("submit", async (event) => {
    event.preventDefault();

    const limit = parseInt(el("eval-limit").value, 10) || 2;
    const webFallback = el("eval-web-fallback").checked;
    const includeRagas = el("eval-include-ragas").checked;

    hide(el("eval-error"));
    hide(el("eval-report"));
    show(el("eval-loading"));

    try {
      const params = new URLSearchParams({
        limit: String(limit),
        web_fallback: String(webFallback),
        include_ragas: String(includeRagas),
      });
      const response = await fetch(apiBase() + "/evaluate?" + params.toString(), { method: "POST" });
      if (!response.ok) {
        throw new Error(`Request failed (${response.status}): ${await response.text()}`);
      }
      const report = await response.json();
      renderEvalReport(report);
    } catch (err) {
      el("eval-error").textContent = "Evaluation failed: " + err.message;
      show(el("eval-error"));
    } finally {
      hide(el("eval-loading"));
    }
  });

  function renderEvalReport(report) {
    const metricNames = Array.from(
      new Set([...Object.keys(report.baseline_metrics || {}), ...Object.keys(report.crag_metrics || {})])
    );

    let metricsRows = metricNames
      .map((name) => {
        const b = report.baseline_metrics[name];
        const c = report.crag_metrics[name];
        const imp = report.improvement_pct[name];
        return (
          `<tr><td>${escapeHtml(name)}</td><td>${b != null ? b.toFixed(3) : "n/a"}</td>` +
          `<td>${c != null ? c.toFixed(3) : "n/a"}</td>` +
          `<td>${imp != null ? imp.toFixed(1) + "%" : "n/a"}</td></tr>`
        );
      })
      .join("");
    if (!metricsRows) {
      metricsRows = '<tr><td colspan="4">No RAGAS metrics computed.</td></tr>';
    }

    const examples = (report.failure_examples || [])
      .map(
        (ex) =>
          `<div class="eval-example"><strong>${escapeHtml(ex.question_id)}</strong> (${escapeHtml(ex.category)})<br/>` +
          `Q: ${escapeHtml(ex.question)}<br/>A: ${escapeHtml(ex.answer)}<br/>` +
          `retrieval_status=${escapeHtml(ex.retrieval_status)}, grounding_status=${escapeHtml(ex.grounding_status)}, ` +
          `rewrite_used=${ex.rewrite_used}, web_used=${ex.web_used}, answer_corrected=${ex.answer_corrected}</div>`
      )
      .join("");

    el("eval-report").innerHTML = `
      <p>Dataset size: <strong>${report.dataset_size}</strong></p>

      <h3>RAGAS metrics: baseline vs CRAG</h3>
      <table>
        <thead><tr><th>Metric</th><th>Baseline</th><th>CRAG</th><th>Improvement</th></tr></thead>
        <tbody>${metricsRows}</tbody>
      </table>

      <h3>Latency</h3>
      <table>
        <thead><tr><th></th><th>Baseline</th><th>CRAG</th></tr></thead>
        <tbody>
          <tr><td>Average</td><td>${report.latency.baseline_avg.toFixed(2)}s</td><td>${report.latency.crag_avg.toFixed(2)}s</td></tr>
          <tr><td>p50</td><td>${report.latency.baseline_p50.toFixed(2)}s</td><td>${report.latency.crag_p50.toFixed(2)}s</td></tr>
          <tr><td>p95</td><td>${report.latency.baseline_p95.toFixed(2)}s</td><td>${report.latency.crag_p95.toFixed(2)}s</td></tr>
        </tbody>
      </table>

      <h3>CRAG behavior</h3>
      <ul>
        <li>Average retrieval rounds: ${report.average_retrieval_rounds.toFixed(2)}</li>
        <li>Query rewrite rate: ${(report.rewrite_rate * 100).toFixed(0)}%</li>
        <li>Web fallback rate: ${(report.web_fallback_rate * 100).toFixed(0)}%</li>
        <li>Answer correction rate: ${(report.answer_correction_rate * 100).toFixed(0)}%</li>
        <li>Insufficient-evidence rate: ${(report.insufficient_evidence_rate * 100).toFixed(0)}%</li>
      </ul>

      <h3>Failure / correction examples</h3>
      ${examples || "<p>No examples.</p>"}
    `;
    show(el("eval-report"));
  }

  // ---------- Init ----------

  loadDocuments();
})();
