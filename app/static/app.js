/**
 * Security Manual Assistant - Frontend Application
 */

// API base URL
const API_BASE = '/api';

// DOM Elements
const chatMessages = document.getElementById('chatMessages');
const queryForm = document.getElementById('queryForm');
const queryInput = document.getElementById('queryInput');
const sendBtn = document.getElementById('sendBtn');
const brandFilter = document.getElementById('brandFilter');
const settingsBtn = document.getElementById('settingsBtn');
const settingsModal = document.getElementById('settingsModal');
const closeSettings = document.getElementById('closeSettings');
const uploadForm = document.getElementById('uploadForm');

// Event Listeners
document.addEventListener('DOMContentLoaded', init);
queryForm.addEventListener('submit', handleQuery);
settingsBtn.addEventListener('click', openSettings);
closeSettings.addEventListener('click', closeSettingsModal);
settingsModal.addEventListener('click', (e) => {
    if (e.target === settingsModal) closeSettingsModal();
});
uploadForm.addEventListener('submit', handleUpload);

/**
 * Initialize the application
 */
function init() {
    queryInput.focus();
}

/**
 * Handle query submission
 */
async function handleQuery(e) {
    e.preventDefault();
    
    const query = queryInput.value.trim();
    if (!query) return;
    
    // Add user message
    addMessage(query, 'user');
    
    // Clear input
    queryInput.value = '';
    sendBtn.disabled = true;
    
    // Show loading
    const loadingId = addLoadingMessage();
    
    try {
        const brand = brandFilter.value;
        const url = brand 
            ? `${API_BASE}/query?brand=${encodeURIComponent(brand)}`
            : `${API_BASE}/query`;
        
        const response = await fetch(url, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ query })
        });
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const data = await response.json();
        
        // Remove loading message
        removeMessage(loadingId);
        
        // Add assistant response
        addAssistantMessage(data.answer, data.citations);
        
    } catch (error) {
        console.error('Query error:', error);
        removeMessage(loadingId);
        addMessage(
            'Sorry, there was an error processing your query. Please try again.',
            'assistant',
            true
        );
    } finally {
        sendBtn.disabled = false;
        queryInput.focus();
    }
}

/**
 * Add a message to the chat
 */
function addMessage(content, type, isError = false) {
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${type}-message`;
    if (isError) messageDiv.classList.add('error');
    
    const contentDiv = document.createElement('div');
    contentDiv.className = 'message-content';
    contentDiv.innerHTML = `<p>${escapeHtml(content)}</p>`;
    
    messageDiv.appendChild(contentDiv);
    chatMessages.appendChild(messageDiv);
    scrollToBottom();
    
    return messageDiv;
}

/**
 * Add assistant message with citations
 */
function addAssistantMessage(answer, citations) {
    const messageDiv = document.createElement('div');
    messageDiv.className = 'message assistant-message';
    
    const contentDiv = document.createElement('div');
    contentDiv.className = 'message-content';
    
    // Format answer with paragraphs
    const paragraphs = answer.split('\n\n').filter(p => p.trim());
    const formattedAnswer = paragraphs.map(p => `<p>${formatText(p)}</p>`).join('');
    contentDiv.innerHTML = formattedAnswer;
    
    // Add citations if available
    if (citations && citations.length > 0) {
        const citationsDiv = document.createElement('div');
        citationsDiv.className = 'citations';
        citationsDiv.innerHTML = `
            <div class="citations-title">Sources</div>
            <div class="citation-list">
                ${citations.map(c => `
                    <span class="citation-tag">
                        <span class="brand">${escapeHtml(c.brand)}</span>
                        ${escapeHtml(c.manual_name)} • Page ${c.page_number}
                    </span>
                `).join('')}
            </div>
        `;
        contentDiv.appendChild(citationsDiv);
    }
    
    messageDiv.appendChild(contentDiv);
    chatMessages.appendChild(messageDiv);
    scrollToBottom();
}

/**
 * Add loading message
 */
function addLoadingMessage() {
    const id = 'loading-' + Date.now();
    const messageDiv = document.createElement('div');
    messageDiv.id = id;
    messageDiv.className = 'message assistant-message loading-message';
    messageDiv.innerHTML = `
        <div class="message-content">
            <div class="loading-dots">
                <span></span>
                <span></span>
                <span></span>
            </div>
        </div>
    `;
    chatMessages.appendChild(messageDiv);
    scrollToBottom();
    return id;
}

/**
 * Remove a message by ID
 */
function removeMessage(id) {
    const message = document.getElementById(id);
    if (message) message.remove();
}

/**
 * Scroll chat to bottom
 */
function scrollToBottom() {
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

/**
 * Open settings modal
 */
function openSettings() {
    settingsModal.classList.remove('hidden');
    checkHealth();
}

/**
 * Close settings modal
 */
function closeSettingsModal() {
    settingsModal.classList.add('hidden');
}

/**
 * Check system health
 */
async function checkHealth() {
    const apiStatus = document.getElementById('apiStatus');
    const qdrantStatus = document.getElementById('qdrantStatus');
    const openaiStatus = document.getElementById('openaiStatus');
    
    try {
        const response = await fetch(`${API_BASE}/health`);
        const data = await response.json();
        
        apiStatus.textContent = 'Connected';
        apiStatus.className = 'status-value ok';
        
        qdrantStatus.textContent = data.qdrant_connected ? 'Connected' : 'Disconnected';
        qdrantStatus.className = `status-value ${data.qdrant_connected ? 'ok' : 'error'}`;
        
        openaiStatus.textContent = data.openai_configured ? 'Configured' : 'Not Configured';
        openaiStatus.className = `status-value ${data.openai_configured ? 'ok' : 'error'}`;
        
    } catch (error) {
        apiStatus.textContent = 'Error';
        apiStatus.className = 'status-value error';
        qdrantStatus.textContent = 'Unknown';
        qdrantStatus.className = 'status-value error';
        openaiStatus.textContent = 'Unknown';
        openaiStatus.className = 'status-value error';
    }
}

/**
 * Handle file upload
 */
async function handleUpload(e) {
    e.preventDefault();
    
    const brand = document.getElementById('uploadBrand').value;
    const file = document.getElementById('uploadFile').files[0];
    const statusDiv = document.getElementById('uploadStatus');
    
    if (!brand || !file) return;
    
    const formData = new FormData();
    formData.append('file', file);
    formData.append('brand', brand);
    
    statusDiv.textContent = 'Uploading...';
    statusDiv.className = 'upload-status loading';
    
    try {
        const response = await fetch(`${API_BASE}/upload`, {
            method: 'POST',
            body: formData
        });
        
        const data = await response.json();
        
        if (response.ok) {
            statusDiv.textContent = data.message;
            statusDiv.className = 'upload-status success';
            uploadForm.reset();
        } else {
            throw new Error(data.detail || 'Upload failed');
        }
        
    } catch (error) {
        statusDiv.textContent = `Error: ${error.message}`;
        statusDiv.className = 'upload-status error';
    }
}

/**
 * Ingest manuals for a brand
 */
async function ingestBrand(brand) {
    const statusDiv = document.getElementById('ingestStatus');
    
    statusDiv.textContent = `Processing ${brand} manuals...`;
    statusDiv.className = 'ingest-status loading';
    
    try {
        const response = await fetch(`${API_BASE}/ingest`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ brand })
        });
        
        const data = await response.json();
        
        if (response.ok) {
            statusDiv.textContent = data.message;
            statusDiv.className = 'ingest-status success';
        } else {
            throw new Error(data.detail || 'Ingestion failed');
        }
        
    } catch (error) {
        statusDiv.textContent = `Error: ${error.message}`;
        statusDiv.className = 'ingest-status error';
    }
}

/**
 * Load statistics
 */
async function loadStats() {
    const container = document.getElementById('statsContainer');
    
    try {
        const response = await fetch(`${API_BASE}/stats`);
        const data = await response.json();
        
        container.innerHTML = `
            <button class="btn btn-outline" onclick="loadStats()">Refresh Stats</button>
            <pre>${JSON.stringify(data, null, 2)}</pre>
        `;
        
    } catch (error) {
        container.innerHTML = `
            <button class="btn btn-outline" onclick="loadStats()">Retry</button>
            <p class="error">Error loading stats: ${error.message}</p>
        `;
    }
}

/**
 * Format text with basic markdown-like syntax
 */
function formatText(text) {
    // Handle line breaks
    text = text.replace(/\n/g, '<br>');
    
    // Handle **bold**
    text = text.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
    
    // Handle bullet points
    text = text.replace(/^- (.+)/gm, '• $1');
    
    return text;
}

/**
 * Escape HTML to prevent XSS
 */
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}
