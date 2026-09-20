// ============================================================
// LegalScope frontend — chat-based UI over the existing /analyze API.
//
// Connection contract is UNCHANGED from the previous frontend:
//   POST {API_BASE_URL}/analyze, multipart/form-data, fields:
//     files  -> one or more PDFs
//     prompt -> the user's question
//   Response: a ComplianceReport JSON object
//     { status, summary, findings: [ {finding_id, severity, status,
//       requirement, document, page, section, evidence, analysis,
//       recommendation} ] }
//
// The backend's pipeline keeps its own conversation memory across
// calls, but /analyze still requires files on every request. To make
// this feel like a real chat without touching the backend, every
// turn re-sends all currently uploaded files alongside the new
// prompt — the files never need to be re-picked by the user.
// ============================================================

const CONFIG = {
  API_BASE_URL: "http://127.0.0.1:8000",
  MAX_FILES: 4,
  MAX_FILE_SIZE: 10 * 1024 * 1024, // 10MB
  ALLOWED_TYPES: ["application/pdf"],
};

/* ---------------- elements ---------------- */
const fileInput = document.getElementById("fileInput");
const dropZone = document.getElementById("dropZone");
const fileList = document.getElementById("fileList");
const fileCount = document.getElementById("fileCount");
const clearBtn = document.getElementById("clearBtn");

const thread = document.getElementById("thread");
const emptyState = document.getElementById("emptyState");
const statusLine = document.getElementById("status-line");
const promptInput = document.getElementById("promptInput");
const sendBtn = document.getElementById("sendBtn");

const healthPill = document.getElementById("healthPill");
const healthText = document.getElementById("healthText");
const themeToggle = document.getElementById("themeToggle");
const themeIcon = document.getElementById("themeIcon");

/* ---------------- state ---------------- */
let uploadedFiles = []; // File[]
let indexed = false; // becomes true after the first successful analyze
let isProcessing = false;

/* ---------------- theme ---------------- */
const SUN_PATH =
  '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M4.93 19.07l1.41-1.41M17.66 6.34l1.41-1.41"/>';
const MOON_PATH = '<path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z"/>';

function applyTheme(theme) {
  document.documentElement.dataset.theme = theme;
  themeIcon.innerHTML = theme === "dark" ? SUN_PATH : MOON_PATH;
  try {
    localStorage.setItem("legalscope-theme", theme);
  } catch (_) {}
}

function initTheme() {
  let saved = null;
  try {
    saved = localStorage.getItem("legalscope-theme");
  } catch (_) {}
  const prefersLight =
    window.matchMedia && window.matchMedia("(prefers-color-scheme: light)").matches;
  applyTheme(saved || (prefersLight ? "light" : "dark"));
}

themeToggle.addEventListener("click", () => {
  const next = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
  applyTheme(next);
});

/* ---------------- helpers ---------------- */
function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str ?? "";
  return div.innerHTML;
}

function formatSize(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function setStatus(message, type = "info") {
  statusLine.textContent = message || "";
  statusLine.className = type;
}

function scrollThreadToBottom() {
  thread.scrollTop = thread.scrollHeight;
}

/* ---------------- sidebar: file handling ---------------- */
function renderFileList() {
  fileList.innerHTML = "";
  fileCount.textContent = `${uploadedFiles.length} file${uploadedFiles.length === 1 ? "" : "s"}`;

  if (uploadedFiles.length === 0) {
    const p = document.createElement("p");
    p.className = "file-placeholder";
    p.textContent = "No documents uploaded yet.";
    fileList.appendChild(p);
    updateButtonStates();
    return;
  }

  uploadedFiles.forEach((file, i) => {
    const card = document.createElement("div");
    card.className = "file-card";

    const row1 = document.createElement("div");
    row1.className = "row1";
    const fname = document.createElement("span");
    fname.className = "fname";
    fname.textContent = file.name;
    const removeBtn = document.createElement("button");
    removeBtn.type = "button";
    removeBtn.textContent = "Remove";
    removeBtn.addEventListener("click", () => removeFile(i));
    row1.appendChild(fname);
    row1.appendChild(removeBtn);

    const metaRow = document.createElement("div");
    metaRow.className = "meta-row";
    const fsize = document.createElement("span");
    fsize.className = "fsize";
    fsize.textContent = formatSize(file.size);
    const badge = document.createElement("span");
    badge.className = `badge ${indexed ? "badge-indexed" : "badge-ready"}`;
    badge.textContent = indexed ? "Indexed" : "Ready";
    metaRow.appendChild(fsize);
    metaRow.appendChild(badge);

    card.appendChild(row1);
    card.appendChild(metaRow);
    fileList.appendChild(card);
  });

  updateButtonStates();
}

function removeFile(index) {
  uploadedFiles.splice(index, 1);
  indexed = false;
  renderFileList();
}

function clearAllFiles() {
  uploadedFiles = [];
  indexed = false;
  renderFileList();
}

function addFiles(fileArray) {
  const errors = [];

  for (const file of fileArray) {
    if (uploadedFiles.length >= CONFIG.MAX_FILES) {
      errors.push(`Only ${CONFIG.MAX_FILES} files can be reviewed at once.`);
      break;
    }
    if (!CONFIG.ALLOWED_TYPES.includes(file.type) && !file.name.toLowerCase().endsWith(".pdf")) {
      errors.push(`"${file.name}" was skipped — PDF files only.`);
      continue;
    }
    if (file.size > CONFIG.MAX_FILE_SIZE) {
      errors.push(`"${file.name}" was skipped — over 10MB.`);
      continue;
    }
    const alreadyAdded = uploadedFiles.some((f) => f.name === file.name && f.size === file.size);
    if (alreadyAdded) continue;

    uploadedFiles.push(file);
  }

  if (errors.length) setStatus(errors[0], "error");
  indexed = false;
  renderFileList();
}

function updateButtonStates() {
  clearBtn.disabled = uploadedFiles.length === 0;
  sendBtn.disabled = uploadedFiles.length === 0 || isProcessing || !promptInput.value.trim();
}

/* ---------------- upload / drag & drop ---------------- */
dropZone.addEventListener("click", () => {
  if (uploadedFiles.length < CONFIG.MAX_FILES) fileInput.click();
  else setStatus(`Maximum ${CONFIG.MAX_FILES} files already uploaded`, "error");
});

fileInput.addEventListener("change", (e) => {
  addFiles(Array.from(e.target.files));
  fileInput.value = "";
});

["dragenter", "dragover"].forEach((evt) => {
  dropZone.addEventListener(evt, (e) => {
    e.preventDefault();
    e.stopPropagation();
    dropZone.classList.add("drag-over");
  });
});
["dragleave", "drop"].forEach((evt) => {
  dropZone.addEventListener(evt, (e) => {
    e.preventDefault();
    e.stopPropagation();
    dropZone.classList.remove("drag-over");
  });
});
dropZone.addEventListener("drop", (e) => {
  const dropped = e.dataTransfer?.files ? Array.from(e.dataTransfer.files) : [];
  if (dropped.length) addFiles(dropped);
});

clearBtn.addEventListener("click", clearAllFiles);

/* ---------------- composer ---------------- */
promptInput.addEventListener("input", () => {
  promptInput.style.height = "auto";
  promptInput.style.height = Math.min(promptInput.scrollHeight, 140) + "px";
  updateButtonStates();
});

promptInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    sendMessage();
  }
});

sendBtn.addEventListener("click", sendMessage);

/* ---------------- chat rendering ---------------- */
function appendUserTurn(promptText) {
  if (emptyState) emptyState.remove();

  const turn = document.createElement("div");
  turn.className = "turn";

  const block = document.createElement("div");
  block.className = "query-block";
  const who = document.createElement("div");
  who.className = "who";
  who.innerHTML = `<span>YOU</span><span>${new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</span>`;
  const p = document.createElement("p");
  p.textContent = promptText;
  block.appendChild(who);
  block.appendChild(p);
  turn.appendChild(block);

  thread.appendChild(turn);
  scrollThreadToBottom();
  return turn;
}

function appendThinking(turn) {
  const thinking = document.createElement("div");
  thinking.className = "thinking";
  thinking.innerHTML = `<span class="spinner"></span><span>Analyzing documents…</span>`;
  turn.appendChild(thinking);
  scrollThreadToBottom();
  return thinking;
}

function statusToPillClass(status) {
  const s = (status || "").toUpperCase();
  if (s === "COMPLIANT") return "pill-compliant";
  if (s === "PARTIALLY_COMPLIANT") return "pill-partial";
  if (s === "NON_COMPLIANT") return "pill-noncompliant";
  return "pill-insufficient"; // INSUFFICIENT_EVIDENCE or unknown
}

function severityToPillClass(sev) {
  const s = (sev || "").toUpperCase();
  if (s === "HIGH") return "pill-high";
  if (s === "MEDIUM") return "pill-medium";
  return "pill-low";
}

function renderFinding(finding) {
  const el = document.createElement("div");
  el.className = "finding";

  const tags = document.createElement("div");
  tags.className = "finding-tags";
  tags.innerHTML = `
    <span class="pill mono">${escapeHtml(finding.finding_id ?? "—")}</span>
    <span class="pill mono ${severityToPillClass(finding.severity)}">${escapeHtml(finding.severity ?? "—")}</span>
    <span class="pill mono ${statusToPillClass(finding.status)}">${escapeHtml(String(finding.status ?? "—").replace(/_/g, " "))}</span>
  `;
  el.appendChild(tags);

  const req = document.createElement("div");
  req.className = "finding-req";
  req.textContent = finding.requirement ?? "—";
  el.appendChild(req);

  const meta = document.createElement("div");
  meta.className = "finding-meta";
  meta.textContent = `${finding.document ?? "N/A"} · page ${finding.page ?? 0} · ${finding.section ?? "N/A"}`;
  el.appendChild(meta);

  if (finding.evidence) {
    const quote = document.createElement("div");
    quote.className = "finding-quote";
    quote.textContent = `"${finding.evidence}"`;
    el.appendChild(quote);
  }

  if (finding.analysis) {
    const analysis = document.createElement("div");
    analysis.className = "finding-line";
    analysis.innerHTML = `<b>Analysis — </b>${escapeHtml(finding.analysis)}`;
    el.appendChild(analysis);
  }

  if (finding.recommendation) {
    const rec = document.createElement("div");
    rec.className = "finding-line";
    rec.innerHTML = `<b>Recommendation — </b>${escapeHtml(finding.recommendation)}`;
    el.appendChild(rec);
  }

  return el;
}

function renderReportCard(report) {
  const card = document.createElement("div");
  card.className = "report-card";

  const head = document.createElement("div");
  head.className = "report-head";
  const findingsCount = Array.isArray(report.findings) ? report.findings.length : 0;
  head.innerHTML = `
    <h3>Compliance Report</h3>
    <span class="pill ${statusToPillClass(report.status)}">${escapeHtml(String(report.status ?? "—").replace(/_/g, " "))}</span>
  `;
  card.appendChild(head);

  const summary = document.createElement("div");
  summary.className = "summary-box";
  summary.textContent = report.summary ?? "";
  card.appendChild(summary);

  const heading = document.createElement("div");
  heading.className = "findings-heading";
  heading.textContent = `FINDINGS (${findingsCount})`;
  card.appendChild(heading);

  (report.findings || []).forEach((f) => card.appendChild(renderFinding(f)));

  return card;
}

function appendErrorCard(turn, message) {
  const card = document.createElement("div");
  card.className = "error-card";
  card.innerHTML = `<b>Analysis failed.</b> ${escapeHtml(message)}`;
  turn.appendChild(card);
  scrollThreadToBottom();
}

/* ---------------- sending ---------------- */
async function sendMessage() {
  const promptText = promptInput.value.trim();
  if (!promptText || uploadedFiles.length === 0 || isProcessing) return;

  isProcessing = true;
  updateButtonStates();
  setStatus("", "info");

  const turn = appendUserTurn(promptText);
  promptInput.value = "";
  promptInput.style.height = "auto";
  const thinking = appendThinking(turn);

  try {
    const formData = new FormData();
    uploadedFiles.forEach((file) => formData.append("files", file));
    formData.append("prompt", promptText);
    // No API key is ever sent from the frontend — the backend holds its own.

    const response = await fetch(`${CONFIG.API_BASE_URL}/analyze`, {
      method: "POST",
      body: formData,
    });

    thinking.remove();

    if (!response.ok) {
      let errorMessage = `Server error: ${response.status}`;
      try {
        const errorData = await response.json();
        if (errorData.detail) errorMessage = errorData.detail;
      } catch (_) {}
      throw new Error(errorMessage);
    }

    const report = await response.json();
    turn.appendChild(renderReportCard(report));
    indexed = true;
    renderFileList();
  } catch (error) {
    thinking.remove();
    console.error("Analysis error:", error);
    appendErrorCard(turn, error.message || "Could not reach the backend.");
    setStatus(error.message || "Could not reach the backend.", "error");
  } finally {
    isProcessing = false;
    updateButtonStates();
    scrollThreadToBottom();
  }
}

/* ---------------- health check ---------------- */
async function checkHealth() {
  try {
    const response = await fetch(`${CONFIG.API_BASE_URL}/`);
    if (response.ok) {
      healthPill.className = "status-pill online";
      healthText.textContent = "Backend online";
      return;
    }
    healthPill.className = "status-pill offline";
    healthText.textContent = `Backend error (${response.status})`;
  } catch (error) {
    healthPill.className = "status-pill offline";
    healthText.textContent = "Backend unreachable";
    console.error("Health check error:", error);
  }
}

/* ---------------- init ---------------- */
function init() {
  initTheme();
  renderFileList();
  updateButtonStates();
  checkHealth();
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", init);
} else {
  init();
}
