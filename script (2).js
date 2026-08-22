const fileInput = document.getElementById('fileInput');
const uploadBtn = document.getElementById('uploadBtn');
const analyzeBtn = document.getElementById('analyzeBtn');
const clearBtn = document.getElementById('clearBtn');
const fileList = document.getElementById('fileList');
const resultsDiv = document.getElementById('results');
const statusDiv = document.getElementById('status');
const promptInput = document.getElementById('promptInput');
const askBtn = document.getElementById('askBtn');

const dropZone = document.getElementById('dropZone');

const MAX_FILES = 4;
const MAX_SIZE = 10 * 1024 * 1024; // 10 MB

let uploadedFiles = [];   // File[]
let analysisDone = false;

const DEFAULT_STATUS = 'Ready. Upload PDF documents to analyze. (Max 4 files, 10MB each)';

/* ---------------- helpers ---------------- */
function formatSize(bytes) {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function setStatus(message, type) {
    statusDiv.textContent = '';
    statusDiv.className = type || 'info';

    if (type === 'info') {
        const spinner = document.createElement('span');
        spinner.className = 'spinner';
        statusDiv.appendChild(spinner);
    }

    const text = document.createElement('span');
    text.textContent = message;
    statusDiv.appendChild(text);
}

function updateButtonStates() {
    analyzeBtn.disabled = uploadedFiles.length === 0;
    clearBtn.style.display = uploadedFiles.length > 0 ? 'inline-flex' : 'none';
    // promptInput and askBtn stay interactive at all times; handleAsk()
    // gives a gentle nudge if the user asks before analysis has run.
}

function renderFileList() {
    fileList.innerHTML = '';

    if (uploadedFiles.length === 0) {
        const p = document.createElement('p');
        p.className = 'file-placeholder';
        p.textContent = 'No files uploaded yet.';
        fileList.appendChild(p);
        updateButtonStates();
        return;
    }

    const ul = document.createElement('ul');

    uploadedFiles.forEach((file, i) => {
        const li = document.createElement('li');

        const idx = document.createElement('span');
        idx.className = 'idx';
        idx.textContent = String(i + 1).padStart(2, '0');

        const meta = document.createElement('span');
        meta.className = 'meta';
        meta.innerHTML = `<span class="fname">${escapeHtml(file.name)}</span><span class="fsize">${formatSize(file.size)}</span>`;

        const removeBtn = document.createElement('button');
        removeBtn.textContent = 'Remove';
        removeBtn.addEventListener('click', () => removeFile(i));

        li.appendChild(idx);
        li.appendChild(meta);
        li.appendChild(removeBtn);
        ul.appendChild(li);
    });

    fileList.appendChild(ul);
    updateButtonStates();
}

function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

function removeFile(index) {
    uploadedFiles.splice(index, 1);
    analysisDone = false;
    resultsDiv.innerHTML = '';
    setStatus(DEFAULT_STATUS, 'info');
    renderFileList();
}

function addFiles(fileArray) {
    const errors = [];

    for (const file of fileArray) {
        if (uploadedFiles.length >= MAX_FILES) {
            errors.push(`Only ${MAX_FILES} files can be reviewed at once.`);
            break;
        }
        if (file.type !== 'application/pdf' && !file.name.toLowerCase().endsWith('.pdf')) {
            errors.push(`"${file.name}" was skipped — PDF files only.`);
            continue;
        }
        if (file.size > MAX_SIZE) {
            errors.push(`"${file.name}" was skipped — over 10 MB.`);
            continue;
        }
        const alreadyAdded = uploadedFiles.some(f => f.name === file.name && f.size === file.size);
        if (alreadyAdded) continue;

        uploadedFiles.push(file);
    }

    if (errors.length) {
        setStatus(errors[0], 'error');
    } else {
        setStatus(DEFAULT_STATUS, 'info');
    }

    analysisDone = false;
    resultsDiv.innerHTML = '';
    renderFileList();
}

/* ---------------- upload / drag & drop ---------------- */
uploadBtn.addEventListener('click', () => fileInput.click());

dropZone.addEventListener('click', () => fileInput.click());

fileInput.addEventListener('change', (e) => {
    addFiles(Array.from(e.target.files));
    fileInput.value = '';
});

['dragenter', 'dragover'].forEach(evt => {
    dropZone.addEventListener(evt, (e) => {
        e.preventDefault();
        e.stopPropagation();
        dropZone.classList.add('drag-over');
    });
});

['dragleave', 'drop'].forEach(evt => {
    dropZone.addEventListener(evt, (e) => {
        e.preventDefault();
        e.stopPropagation();
        dropZone.classList.remove('drag-over');
    });
});

dropZone.addEventListener('drop', (e) => {
    const dropped = e.dataTransfer && e.dataTransfer.files ? Array.from(e.dataTransfer.files) : [];
    if (dropped.length) addFiles(dropped);
});

/* ---------------- clear all ---------------- */
clearBtn.addEventListener('click', () => {
    uploadedFiles = [];
    analysisDone = false;
    resultsDiv.innerHTML = '';
    promptInput.value = '';
    setStatus(DEFAULT_STATUS, 'info');
    renderFileList();
});

/* ---------------- mock analysis engine ---------------- */
// Deterministic pseudo-hash so the same file name always yields the same findings.
function hashString(str) {
    let h = 0;
    for (let i = 0; i < str.length; i++) {
        h = (h << 5) - h + str.charCodeAt(i);
        h |= 0;
    }
    return Math.abs(h);
}

const CLAUSE_LIBRARY = [
    { title: 'Limitation of Liability', ref: '§ 7.1' },
    { title: 'Indemnification', ref: '§ 9.3' },
    { title: 'Confidentiality', ref: '§ 4.2' },
    { title: 'Termination for Convenience', ref: '§ 11.0' },
    { title: 'Governing Law & Venue', ref: '§ 14.5' },
    { title: 'Data Processing & Privacy', ref: '§ 6.4' },
    { title: 'Payment Terms', ref: '§ 3.1' },
    { title: 'Force Majeure', ref: '§ 12.2' },
];

const STATUS_COPY = {
    compliant: {
        label: 'Compliant',
        lines: [
            'Language matches the standard playbook position with no material deviation.',
            'Terms fall within acceptable risk tolerance and require no redline.',
        ],
    },
    flag: {
        label: 'Needs review',
        lines: [
            'Wording is non-standard and should be checked against current policy before signature.',
            'Threshold or timeframe differs from the preferred fallback — confirm it is acceptable.',
        ],
    },
    violation: {
        label: 'Violation',
        lines: [
            'Clause conflicts with a required minimum position and should be redlined before execution.',
            'Missing language that policy requires as a condition of signature.',
        ],
    },
};

function analyzeFile(file) {
    const seed = hashString(file.name + file.size);
    const clauseCount = 3 + (seed % 3); // 3–5 findings per document
    const findings = [];

    for (let i = 0; i < clauseCount; i++) {
        const clause = CLAUSE_LIBRARY[(seed + i * 7) % CLAUSE_LIBRARY.length];
        const roll = (seed + i * 13) % 10;
        const status = roll < 6 ? 'compliant' : roll < 8 ? 'flag' : 'violation';
        const copy = STATUS_COPY[status];
        const line = copy.lines[(seed + i) % copy.lines.length];
        findings.push({ ...clause, status, label: copy.label, text: line });
    }

    return findings;
}

function fileIconSvg() {
    return `<svg class="file-icon" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6"/></svg>`;
}

analyzeBtn.addEventListener('click', () => {
    if (uploadedFiles.length === 0) return;

    analyzeBtn.disabled = true;
    uploadBtn.disabled = true;
    clearBtn.disabled = true;
    resultsDiv.innerHTML = '';
    analysisDone = false;
    updateButtonStates();

    setStatus(`Reviewing ${uploadedFiles.length} document${uploadedFiles.length > 1 ? 's' : ''}…`, 'info');

    setTimeout(() => {
        const stampRow = document.createElement('div');
        stampRow.className = 'stamp-row';
        stampRow.innerHTML = `<div class="stamp">REVIEWED</div>`;
        resultsDiv.appendChild(stampRow);

        let totalViolations = 0;

        uploadedFiles.forEach(file => {
            const findings = analyzeFile(file);
            totalViolations += findings.filter(f => f.status === 'violation').length;

            const block = document.createElement('div');
            block.className = 'doc-block';

            const heading = document.createElement('h3');
            heading.innerHTML = `${fileIconSvg()} ${escapeHtml(file.name)}`;
            block.appendChild(heading);

            findings.forEach(f => {
                const finding = document.createElement('div');
                finding.className = `finding status-${f.status}`;
                finding.innerHTML = `
                    <span class="badge">${f.label}</span>
                    <div class="body">
                        <div class="clause-title">${f.title}<span class="clause-ref">${f.ref}</span></div>
                        <p>${f.text}</p>
                    </div>
                `;
                block.appendChild(finding);
            });

            resultsDiv.appendChild(block);
        });

        analysisDone = true;
        analyzeBtn.disabled = false;
        uploadBtn.disabled = false;
        clearBtn.disabled = false;
        updateButtonStates();

        if (totalViolations > 0) {
            setStatus(`Review complete — ${totalViolations} clause${totalViolations > 1 ? 's' : ''} need attention.`, 'error');
        } else {
            setStatus('Review complete — no violations found.', 'success');
        }
    }, 1100 + Math.random() * 600);
});

/* ---------------- follow-up question ---------------- */
askBtn.addEventListener('click', handleAsk);
promptInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') handleAsk();
});

function handleAsk() {
    const question = promptInput.value.trim();
    if (!question) return;

    const qa = document.createElement('div');
    qa.className = 'qa-block';

    let answer;
    if (analysisDone) {
        const fileNames = uploadedFiles.map(f => f.name).join(', ');
        answer = `Based on the reviewed clauses across ${uploadedFiles.length} document${uploadedFiles.length > 1 ? 's' : ''} (${fileNames}), this is illustrative output only — confirm specifics against the source text and your compliance playbook before relying on it.`;
    } else if (uploadedFiles.length > 0) {
        answer = `I can speak to this once the uploaded document${uploadedFiles.length > 1 ? 's are' : ' is'} analyzed — click "Analyze Documents" and ask again for clause-specific detail. For now: ${question}`;
    } else {
        answer = `Upload a PDF and analyze it first for document-specific answers. In general terms: ${question}`;
    }

    qa.innerHTML = `
        <div class="q">Q — ${escapeHtml(question)}</div>
        <div class="a">${escapeHtml(answer)}</div>
    `;

    resultsDiv.appendChild(qa);
    promptInput.value = '';
    qa.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

/* ---------------- init ---------------- */
renderFileList();
setStatus(DEFAULT_STATUS, 'info');
