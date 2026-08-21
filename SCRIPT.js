// hena el url w el API key
const CONFIG = {
    API_BASE_URL: 'http://localhost:8000',
    MAX_FILES: 4,
    MAX_FILE_SIZE: 10 * 1024 * 1024, // 10MB
    ALLOWED_TYPES: ['application/pdf'],
    // TODO: 7ot el API key
    LLM_API_KEY: 'YOUR_LLM_API_KEY_HERE'
};

// el sho5l m3 el load koloh

let uploadedFiles = [];
let analysisResults = null;
let isProcessing = false;

// el elements mn el page nafsha

const fileInput = document.getElementById('fileInput');
const uploadBtn = document.getElementById('uploadBtn');
const analyzeBtn = document.getElementById('analyzeBtn');
const clearBtn = document.getElementById('clearBtn');
const fileList = document.getElementById('fileList');
const resultsDiv = document.getElementById('results');
const statusDiv = document.getElementById('status');

// koloh tamam fe el files? b validate

function validateFile(file) {
    // check no3 el file
    if (!CONFIG.ALLOWED_TYPES.includes(file.type)) {
        throw new Error(`Invalid file type: ${file.type}. Only PDF files are allowed.`);
    }
    
    // check hagm el file
    if (file.size > CONFIG.MAX_FILE_SIZE) {
        throw new Error(`File ${file.name} exceeds 10MB limit.`);
    }
    
    // check duplicate
    const exists = uploadedFiles.some(f => f.name === file.name && f.size === file.size);
    if (exists) {
        throw new Error(`File "${file.name}" is already uploaded.`);
    }
    
    return true;
}

// tanzeem el files

function addFiles(files) {
    const fileArray = Array.from(files);
    let errors = [];
    let added = 0;
    
    // check eno mat7atesh files zeyada
    if (uploadedFiles.length + fileArray.length > CONFIG.MAX_FILES) {
        showStatus(`Maximum ${CONFIG.MAX_FILES} files allowed. You have ${uploadedFiles.length} files.`, 'error');
        return;
    }
    
    // check valid b3den 7ot el files f array
    fileArray.forEach(file => {
        try {
            validateFile(file);
            uploadedFiles.push(file);
            added++;
        } catch (error) {
            errors.push(error.message);
        }
    });
    
    // 7ot el results
    if (added > 0) {
        renderFileList();
        updateUI();
        showStatus(`Added ${added} file(s). ${errors.length > 0 ? errors.join(' ') : ''}`, 'success');
    }
    
    if (errors.length > 0 && added === 0) {
        showStatus(errors.join(' '), 'error');
    }
}

function removeFile(index) {
    uploadedFiles.splice(index, 1);
    renderFileList();
    updateUI();
    if (uploadedFiles.length === 0) {
        resultsDiv.innerHTML = '';
    }
}

function clearAllFiles() {
    uploadedFiles = [];
    analysisResults = null;
    fileInput.value = '';
    renderFileList();
    updateUI();
    resultsDiv.innerHTML = '';
    showStatus('All files cleared', 'info');
}

// elly be7ot el files

function renderFileList() {
    if (uploadedFiles.length === 0) {
        fileList.innerHTML = '<p style="color: #666;">No files uploaded</p>';
        return;
    }
    
    let html = '<ul style="list-style: none; padding: 0;">';
    uploadedFiles.forEach((file, index) => {
        const sizeKB = (file.size / 1024).toFixed(1);
        const sizeMB = (file.size / (1024 * 1024)).toFixed(2);
        const displaySize = file.size > 1024 * 1024 ? `${sizeMB} MB` : `${sizeKB} KB`;
        
        html += `
            <li style="padding: 8px; margin: 5px 0; background: #f5f5f5; border-radius: 4px; display: flex; justify-content: space-between; align-items: center;">
                <span>
                    <strong>${file.name}</strong>
                    <span style="color: #666; font-size: 0.9em;"> (${displaySize})</span>
                </span>
                <button onclick="removeFile(${index})" style="background: #dc3545; color: white; border: none; padding: 4px 10px; border-radius: 3px; cursor: pointer;">
                    Remove
                </button>
            </li>
        `;
    });
    html += '</ul>';
    fileList.innerHTML = html;
}

function renderResults(data) {
    if (!data) {
        resultsDiv.innerHTML = '';
        return;
    }
    
    if (!data.compliance_alerts || data.compliance_alerts.length === 0) {
        resultsDiv.innerHTML = `
            <div style="padding: 20px; background: #d4edda; border-radius: 4px; border: 1px solid #c3e6cb;">
                <h3 style="color: #155724;">✅ No compliance issues found</h3>
                <p style="color: #155724;">All documents appear to be compliant.</p>
                <p style="color: #155724;">Documents analyzed: ${data.documents_analyzed || 0}</p>
            </div>
        `;
        return;
    }
    
    let html = `
        <div style="padding: 15px; background: #f8f9fa; border-radius: 4px; border: 1px solid #dee2e6;">
            <h3>📋 Compliance Analysis Results</h3>
            <p><strong>Documents Analyzed:</strong> ${data.documents_analyzed || 0}</p>
            <p><strong>Total Issues Found:</strong> ${data.compliance_alerts.length}</p>
            <hr style="border: 1px solid #dee2e6;">
        </div>
    `;
    
    data.compliance_alerts.forEach((alert, index) => {
        const severityColors = {
            high: { bg: '#f8d7da', border: '#f5c6cb', color: '#721c24' },
            medium: { bg: '#fff3cd', border: '#ffeeba', color: '#856404' },
            low: { bg: '#d1ecf1', border: '#bee5eb', color: '#0c5460' }
        };
        
        const severity = (alert.severity || 'medium').toLowerCase();
        const colors = severityColors[severity] || severityColors.medium;
        
        html += `
            <div style="border: 1px solid ${colors.border}; background: ${colors.bg}; margin: 10px 0; padding: 15px; border-radius: 4px;">
                <h4 style="color: ${colors.color}; margin-top: 0;">Issue #${index + 1}</h4>
                <p><strong>Severity:</strong> <span style="text-transform: uppercase; font-weight: bold; color: ${colors.color};">${severity}</span></p>
                <p><strong>Type:</strong> ${alert.type || 'General'}</p>
                <p><strong>Description:</strong> ${alert.description || 'No description provided'}</p>
                ${alert.citation ? `<p><strong>Citation:</strong> ${alert.citation}</p>` : ''}
                ${alert.suggested_action ? `<p><strong>Suggested Action:</strong> ${alert.suggested_action}</p>` : ''}
                ${alert.document_reference ? `<p><strong>Document:</strong> ${alert.document_reference}</p>` : ''}
            </div>
        `;
    });
    
    resultsDiv.innerHTML = html;
}

// UI updat

function updateUI() {
    analyzeBtn.disabled = uploadedFiles.length === 0 || isProcessing;
    analyzeBtn.textContent = isProcessing ? '⏳ Processing...' : '🔍 Analyze Documents';
    clearBtn.style.display = uploadedFiles.length > 0 ? 'inline-block' : 'none';
    uploadBtn.disabled = uploadedFiles.length >= CONFIG.MAX_FILES;
    uploadBtn.textContent = uploadedFiles.length >= CONFIG.MAX_FILES ? '📁 Max Files Reached' : '📁 Browse Files';
}

function showStatus(message, type = 'info') {
    statusDiv.textContent = message;
    statusDiv.className = type;
    statusDiv.style.display = 'block';
    statusDiv.style.padding = '10px';
    statusDiv.style.margin = '10px 0';
    statusDiv.style.borderRadius = '4px';
    
    // 7ot colors on diff type
    const colors = {
        success: { bg: '#d4edda', color: '#155724', border: '#c3e6cb' },
        error: { bg: '#f8d7da', color: '#721c24', border: '#f5c6cb' },
        info: { bg: '#d1ecf1', color: '#0c5460', border: '#bee5eb' }
    };
    
    const style = colors[type] || colors.info;
    statusDiv.style.background = style.bg;
    statusDiv.style.color = style.color;
    statusDiv.style.border = `1px solid ${style.border}`;
    
    // hide el result type
    if (type !== 'error') {
        if (window.statusTimeout) {
            clearTimeout(window.statusTimeout);
        }
        window.statusTimeout = setTimeout(() => {
            statusDiv.style.display = 'none';
        }, 5000);
    }
}

// API comms

async function analyzeDocuments() {
    if (uploadedFiles.length === 0) {
        showStatus('Please upload at least one document', 'error');
        return;
    }
    
    isProcessing = true;
    updateUI();
    resultsDiv.innerHTML = '<p style="text-align: center;">⏳ Analyzing documents... Please wait.</p>';
    showStatus('Processing documents...', 'info');
    
    try {
        const formData = new FormData();
        
        // add el files
        uploadedFiles.forEach(file => {
            formData.append('files', file);
        });
        
        // add document metadata
        const docTypes = ['nda', 'compliance', 'privacy', 'tos'];
        uploadedFiles.forEach((file, index) => {
            if (index < docTypes.length) {
                formData.append('doc_types', docTypes[index]);
            }
        });
        
        // 70t el API key
        if (CONFIG.LLM_API_KEY && CONFIG.LLM_API_KEY !== 'YOUR_LLM_API_KEY_HERE') {
            formData.append('llm_api_key', CONFIG.LLM_API_KEY);
        }
        
        const response = await fetch(`${CONFIG.API_BASE_URL}/api/analyze`, {
            method: 'POST',
            body: formData
        });
        
        // check response is ok
        if (!response.ok) {
            let errorMessage = `Server error: ${response.status}`;
            try {
                const errorData = await response.json();
                if (errorData.detail) {
                    errorMessage = errorData.detail;
                }
            } catch (e) {
                // if response isn't JSON, try text
                try {
                    const text = await response.text();
                    if (text) errorMessage = text;
                } catch (e2) {
                }
            }
            throw new Error(errorMessage);
        }
        
        // parse json
        let data;
        try {
            data = await response.json();
        } catch (e) {
            throw new Error('Invalid response format from server. Expected JSON.');
        }
        
        // validate response
        if (!data.compliance_alerts) {
            throw new Error('Invalid response: missing compliance_alerts field');
        }
        
        analysisResults = data;
        renderResults(data);
        showStatus('✅ Analysis complete!', 'success');
        
    } catch (error) {
        console.error('Analysis error:', error);
        showStatus(`❌ Error: ${error.message}`, 'error');
        resultsDiv.innerHTML = `
            <div style="padding: 15px; background: #f8d7da; border: 1px solid #f5c6cb; border-radius: 4px; color: #721c24;">
                <h4>❌ Error</h4>
                <p>${error.message}</p>
                <p style="font-size: 0.9em; margin-top: 10px;">Make sure the backend server is running and CORS is enabled.</p>
            </div>
        `;
    } finally {
        isProcessing = false;
        updateUI();
    }
}

async function checkHealth() {
    try {
        const response = await fetch(`${CONFIG.API_BASE_URL}/health`);
        if (response.ok) {
            const data = await response.json();
            showStatus(`✅ Backend server is running: ${data.message || 'OK'}`, 'success');
            return true;
        } else {
            showStatus(`⚠️ Backend server responded with status: ${response.status}`, 'error');
            return false;
        }
    } catch (error) {
        showStatus('❌ Cannot connect to backend server. Make sure it\'s running on port 8000', 'error');
        console.error('Health check error:', error);
        return false;
    }
}

// event handler

// input change
fileInput.addEventListener('change', function() {
    if (this.files.length > 0) {
        addFiles(this.files);
        this.value = '';
    }
});

// upload button
uploadBtn.addEventListener('click', function() {
    if (uploadedFiles.length < CONFIG.MAX_FILES) {
        fileInput.click();
    } else {
        showStatus(`Maximum ${CONFIG.MAX_FILES} files already uploaded`, 'error');
    }
});

// analyze button
analyzeBtn.addEventListener('click', analyzeDocuments);

// clear button
clearBtn.addEventListener('click', clearAllFiles);

// drag and drop support
const dropZone = document.getElementById('dropZone');

dropZone.addEventListener('dragover', function(e) {
    e.preventDefault();
    this.style.borderColor = '#007bff';
    this.style.background = '#f0f8ff';
});

dropZone.addEventListener('dragleave', function(e) {
    e.preventDefault();
    this.style.borderColor = '#ccc';
    this.style.background = 'transparent';
});

dropZone.addEventListener('drop', function(e) {
    e.preventDefault();
    this.style.borderColor = '#ccc';
    this.style.background = 'transparent';
    
    const files = e.dataTransfer.files;
    if (files.length > 0) {
        addFiles(files);
    }
});

dropZone.addEventListener('click', function() {
    if (uploadedFiles.length < CONFIG.MAX_FILES) {
        fileInput.click();
    } else {
        showStatus(`Maximum ${CONFIG.MAX_FILES} files already uploaded`, 'error');
    }
});

// init

function init() {
    renderFileList();
    updateUI();
    
    // check backend responses
    setTimeout(() => {
        checkHealth();
    }, 500);
    
    showStatus('Ready. Upload PDF documents to analyze. (Max 4 files, 10MB each)', 'info');
    console.log('📄 Contract Compliance Analyzer initialized');
    console.log(`🔗 Backend URL: ${CONFIG.API_BASE_URL}`);
    console.log(`📁 Max files: ${CONFIG.MAX_FILES}`);
}

// start the app when docs is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
} else {
    init();
}

// global functions lel onclick
window.removeFile = removeFile;
window.analyzeDocuments = analyzeDocuments;
window.clearAllFiles = clearAllFiles;