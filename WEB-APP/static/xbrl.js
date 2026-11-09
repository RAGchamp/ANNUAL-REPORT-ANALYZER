// XBRL page: download a filing from SEC EDGAR into XBRL-docs\<TICKER>\, list the downloaded
// filings, ingest one. All text goes in with textContent (no innerHTML).

const $ = (id) => document.getElementById(id);
let busy = false;

async function api(url, body) {
  const opts = body === undefined
    ? {}
    : { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) };
  const res = await fetch(url, opts);
  let data = {};
  try { data = await res.json(); } catch (_) { /* non-JSON error page */ }
  if (!res.ok) throw new Error(data.error || `Request failed (${res.status})`);
  return data;
}

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function showError(message) {
  $("error-box").textContent = message;
  $("error-box").classList.toggle("hidden", !message);
}

function setBusy(value) {
  busy = value;
  document.querySelectorAll("button[data-job]").forEach((b) => { b.disabled = value; });
}

async function runJob(url, body, status, label) {
  setBusy(true);
  status.textContent = label;
  const started = Date.now();
  try {
    const { job_id } = await api(url, body);
    for (;;) {
      await new Promise((r) => setTimeout(r, 1000));
      const job = await api(`/api/jobs/${job_id}`);
      if (job.status === "done") { status.textContent = ""; return job.result; }
      if (job.status === "error") throw new Error(job.error);
      const s = Math.round((Date.now() - started) / 1000);
      status.textContent = `${job.progress || label} (${s}s)`;
    }
  } finally {
    status.textContent = "";
    setBusy(false);
  }
}

function renderFolder(f) {
  const box = el("div", "ingest-report");
  const head = el("div", "ingest-head");
  head.append(el("b", "", f.ticker), el("span", "muted", ` (${f.size_mb} MB)`));
  const status = f.readable ? (f.status || "not ingested") : "not readable";
  head.append(el("span", `status-badge status-${status.replace(/ /g, "-")}`, status));
  const facts = [f.company, f.form, f.period && `period ${f.period}`, f.downloaded_at && `downloaded ${f.downloaded_at}`]
    .filter(Boolean).join(" · ");
  if (facts) head.append(el("span", "muted small-text", facts));
  box.appendChild(head);

  const files = el("div", "muted small-text", "Files: " + f.files.map((x) => `${x.name} (${x.kb.toLocaleString()} KB)`).join(" · "));
  box.appendChild(files);
  if (f.quality && f.quality.length) {
    const list = el("ul", "quality-panel");
    for (const line of f.quality.slice(1)) list.appendChild(el("li", line.startsWith("Warning:") ? "warning" : "", line));
    box.appendChild(list);
  }

  const actions = el("div", "row");
  if (f.readable) {
    const ingest = el("button", "", f.status === "up to date" ? "Re-ingest" : "Ingest");
    ingest.type = "button";
    ingest.dataset.job = "1";
    const jobStatus = el("span", "muted small-text job-status");
    ingest.addEventListener("click", async () => {
      showError("");
      try {
        const row = await runJob("/api/xbrl/ingest", { ticker: f.ticker }, jobStatus, "Ingesting…");
        box.replaceWith(renderFolder(row));
      } catch (err) {
        showError(`${f.ticker}: ${err.message}`);
      }
    });
    actions.append(ingest, jobStatus);
    if (f.status === "up to date") {
      const view = el("a", "", "View statements ↗");
      view.href = `/statements?report=${encodeURIComponent(f.ticker)}`;
      view.target = "_blank";
      view.rel = "noopener";
      actions.appendChild(view);
    }
  }
  if (f.index) {
    const sec = el("a", "", "Filing on SEC ↗");
    sec.href = f.index;
    sec.target = "_blank";
    sec.rel = "noopener noreferrer";
    actions.appendChild(sec);
  }
  box.appendChild(actions);
  return box;
}

async function loadFolders() {
  const list = $("folder-list");
  try {
    const { folders } = await api("/api/xbrl/folders");
    list.replaceChildren();
    if (!folders.length) list.appendChild(el("div", "muted", "No filings downloaded yet."));
    for (const f of folders) list.appendChild(renderFolder(f));
  } catch (err) {
    showError(`Could not list the downloaded filings: ${err.message}`);
  }
}

$("ticker").addEventListener("input", (e) => { e.target.value = e.target.value.toUpperCase(); });

$("download-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  if (busy) return;
  showError("");
  try {
    await runJob("/api/xbrl/download", {
      ticker: $("ticker").value.trim(), link: $("link").value.trim(), overwrite: $("overwrite").checked,
    }, $("download-status"), "Downloading from SEC…");
    $("overwrite").checked = false;
    await loadFolders();
  } catch (err) {
    showError(err.message);
  }
});

$("refresh").addEventListener("click", () => { if (!busy) loadFolders(); });

loadFolders();
