/**
 * Security Manual Assistant - Agentic RAG Frontend
 */

// === State ===
const state = {
    sessionId: null,
    isLoading: false,
    sources: [],
    activeFilters: [],
    theme: localStorage.getItem('theme') || 'light',
    sidebarOpen: window.innerWidth > 768,
};

// === DOM Elements ===
const chatMessages = document.getElementById('chatMessages');
const queryForm = document.getElementById('queryForm');
const queryInput = document.getElementById('queryInput');
const sendBtn = document.getElementById('sendBtn');
const sidebar = document.getElementById('sidebar');
const sidebarToggle = document.getElementById('sidebarToggle');
const newChatBtn = document.getElementById('newChatBtn');
const themeToggle = document.getElementById('themeToggle');
const clearSession = document.getElementById('clearSession');
const uploadForm = document.getElementById('uploadForm');
const websiteForm = document.getElementById('websiteForm');
const youtubeForm = document.getElementById('youtubeForm');
const sessionInfo = document.getElementById('sessionInfo');

// === Init ===
document.addEventListener('DOMContentLoaded', () => {
    applyTheme(state.theme);
    applySidebarState();
    checkHealth();
    loadSources();
    loadSessionFromStorage();
    setupEventListeners();
    queryInput.focus();
});

// === Event Listeners ===
function setupEventListeners() {
    queryForm.addEventListener('submit', handleQuery);
    sidebarToggle.addEventListener('click', toggleSidebar);
    newChatBtn.addEventListener('click', startNewChat);
    themeToggle.addEventListener('click', toggleTheme);
    clearSession.addEventListener('click', clearConversation);
    uploadForm.addEventListener('submit', handleUpload);
    if (websiteForm) websiteForm.addEventListener('submit', handleWebsiteIngest);
    if (youtubeForm) youtubeForm.addEventListener('submit', handleYouTubeIngest);
}

// === Theme ===
function applyTheme(theme) {
    document.body.setAttribute('data-theme', theme);
    state.theme = theme;
}

function toggleTheme() {
    const newTheme = state.theme === 'light' ? 'dark' : 'light';
    applyTheme(newTheme);
    localStorage.setItem('theme', newTheme);
}

// === Sidebar ===
function toggleSidebar() {
    state.sidebarOpen = !state.sidebarOpen;
    applySidebarState();
}

function applySidebarState() {
    if (window.innerWidth <= 768) {
        sidebar.classList.toggle('open', state.sidebarOpen);
        sidebar.classList.remove('collapsed');
    } else {
        sidebar.classList.toggle('collapsed', !state.sidebarOpen);
        sidebar.classList.remove('open');
    }
}

// === Health Check ===
async function checkHealth() {
    try {
        const response = await fetch('/api/health');
        const data = await response.json();

        setStatusDot('apiDot', 'ok');
        setStatusDot('qdrantDot', data.qdrant_connected ? 'ok' : 'error');
        setStatusDot('geminiDot', data.openai_configured ? 'ok' : 'error');
    } catch {
        setStatusDot('apiDot', 'error');
        setStatusDot('qdrantDot', 'error');
        setStatusDot('geminiDot', 'error');
    }
}

function setStatusDot(id, status) {
    const dot = document.getElementById(id);
    if (dot) {
        dot.className = 'status-dot ' + status;
    }
}

// === Sources ===
async function loadSources() {
    try {
        const response = await fetch('/api/agent/sources');
        const data = await response.json();
        state.sources = data.sources || [];
        renderSourceFilters(state.sources);
        renderDocumentList(state.sources);

        const statsInfo = document.getElementById('statsInfo');
        if (statsInfo) {
            statsInfo.textContent = `Total chunks: ${data.total_chunks || 0}`;
        }
    } catch {
        // Sources endpoint may not work if collection doesn't exist yet
    }
}

function renderSourceFilters(sources) {
    const container = document.getElementById('sourceFilters');
    if (!sources || sources.length === 0) {
        container.innerHTML = '<p class="empty-state">No sources indexed yet</p>';
        return;
    }
    container.innerHTML = sources.map(s => `
        <label class="filter-item">
            <input type="checkbox" value="${escapeHtml(s.brand)}" class="source-checkbox"
                   ${state.activeFilters.includes(s.brand) ? 'checked' : ''}>
            <span class="filter-label">${escapeHtml(s.brand)}</span>
            <span class="filter-count">${s.chunk_count}</span>
        </label>
    `).join('');

    container.querySelectorAll('.source-checkbox').forEach(cb => {
        cb.addEventListener('change', () => {
            if (cb.checked) {
                if (!state.activeFilters.includes(cb.value)) {
                    state.activeFilters.push(cb.value);
                }
            } else {
                state.activeFilters = state.activeFilters.filter(f => f !== cb.value);
            }
        });
    });
}

function renderDocumentList(sources) {
    const container = document.getElementById('documentList');
    if (!sources || sources.length === 0) {
        container.innerHTML = '<p class="empty-state">Upload PDFs to get started</p>';
        return;
    }

    let html = '';
    sources.forEach(s => {
        s.documents.forEach(doc => {
            const typeLabel = (s.source_types && s.source_types[0]) || 'pdf';
            html += `
                <div class="doc-item">
                    <span class="doc-icon">${typeLabel.toUpperCase()}</span>
                    <span>${escapeHtml(doc)}</span>
                </div>
            `;
        });
    });
    container.innerHTML = html || '<p class="empty-state">No documents found</p>';
}

// === Query Handler (Agentic) ===
async function handleQuery(e) {
    e.preventDefault();
    if (state.isLoading) return;

    const query = queryInput.value.trim();
    if (!query) return;

    addUserMessage(query);
    queryInput.value = '';
    state.isLoading = true;
    sendBtn.disabled = true;

    const msgContainer = createAssistantContainer();
    const contentArea = msgContainer.querySelector('.content-area');
    const citationsArea = msgContainer.querySelector('.citations-area');

    try {
        const response = await fetch('/api/agent/query', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                query: query,
                session_id: state.sessionId,
                source_filters: state.activeFilters.length > 0 ? state.activeFilters : null,
                max_iterations: 2,
            }),
        });

        if (!response.ok) throw new Error('Query failed');

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';
        let contentText = '';

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split('\n');
            buffer = lines.pop();

            for (const line of lines) {
                if (!line.trim()) continue;
                try {
                    const event = JSON.parse(line);
                    switch (event.type) {
                        case 'session':
                            state.sessionId = event.data.session_id;
                            updateSessionDisplay();
                            break;
                        case 'citations':
                            renderCitations(citationsArea, event.data);
                            break;
                        case 'content':
                            contentText += event.data;
                            contentArea.innerHTML = formatMarkdown(contentText);
                            scrollToBottom();
                            break;
                    }
                } catch (err) {
                    console.error('Parse error:', err);
                }
            }
        }

        saveSessionToStorage();

    } catch (error) {
        contentArea.innerHTML = '<p class="error-msg">Failed to process query. Please try again.</p>';
        console.error('Agent query error:', error);
    } finally {
        state.isLoading = false;
        sendBtn.disabled = false;
        queryInput.focus();
    }
}

// === Message Rendering ===
function addUserMessage(text) {
    const msgDiv = document.createElement('div');
    msgDiv.className = 'message user-message';
    msgDiv.innerHTML = `
        <div class="message-avatar">You</div>
        <div class="message-body">${escapeHtml(text)}</div>
    `;
    chatMessages.appendChild(msgDiv);
    scrollToBottom();
}

function createAssistantContainer() {
    const msgDiv = document.createElement('div');
    msgDiv.className = 'message assistant-message';
    msgDiv.innerHTML = `
        <div class="message-avatar">AI</div>
        <div class="message-body">
            <div class="content-area"></div>
            <div class="citations-area"></div>
        </div>
    `;
    chatMessages.appendChild(msgDiv);
    scrollToBottom();
    return msgDiv;
}

// === Thinking Steps ===
function renderThinkingStep(container, stepData) {
    const stepEl = document.createElement('div');
    stepEl.className = 'thinking-step';
    stepEl.innerHTML = `
        <div class="step-header">
            <span class="spinner"></span>
            <span class="step-title">${escapeHtml(stepData.title)}</span>
        </div>
        <div class="step-detail">${escapeHtml(stepData.description)}</div>
        ${stepData.data ? `<div class="step-data">${formatStepData(stepData.data)}</div>` : ''}
    `;
    container.appendChild(stepEl);
    scrollToBottom();

    // Mark previous steps as completed
    const steps = container.querySelectorAll('.thinking-step');
    for (let i = 0; i < steps.length - 1; i++) {
        steps[i].classList.add('completed');
    }
}

function formatStepData(data) {
    if (!data) return '';
    let html = '';

    if (data.sub_queries) {
        html += data.sub_queries.map(q => `<span class="tag">${escapeHtml(q)}</span>`).join(' ');
    }
    if (data.brands) {
        html += data.brands.map(b => `<span class="brand-tag">${escapeHtml(b)}</span>`).join(' ');
    }
    if (data.result_count !== undefined) {
        html += `<span class="metric">${data.result_count} results</span> `;
        if (data.top_score !== undefined) {
            html += `<span class="metric">Top: ${(data.top_score * 100).toFixed(0)}%</span>`;
        }
    }
    if (data.quality_score !== undefined) {
        const pct = (data.quality_score * 100).toFixed(0);
        const cls = data.is_sufficient ? 'good' : 'warn';
        html += `<span class="metric ${cls}">Quality: ${pct}%</span>`;
    }
    if (data.intent) {
        html += `<span class="tag">${escapeHtml(data.intent)}</span> `;
    }
    if (data.gaps && data.gaps.length > 0) {
        html += data.gaps.map(g => `<span class="metric warn">${escapeHtml(g)}</span>`).join(' ');
    }

    return html;
}

function finalizeThinkingSteps(container) {
    container.querySelectorAll('.thinking-step').forEach(s => s.classList.add('completed'));

    if (container.children.length > 0) {
        const toggle = document.createElement('button');
        toggle.className = 'thinking-toggle visible';
        toggle.textContent = 'Hide reasoning steps';
        toggle.addEventListener('click', () => {
            container.classList.toggle('collapsed');
            toggle.textContent = container.classList.contains('collapsed')
                ? 'Show reasoning steps'
                : 'Hide reasoning steps';
        });
        container.insertBefore(toggle, container.firstChild);
    }
}

// === Citations ===
function renderCitations(container, citations) {
    if (!citations || citations.length === 0) return;

    container.innerHTML = `
        <div class="citations-title">Sources</div>
        <div class="citation-list">
            ${citations.map(c => `
                <span class="citation-chip">
                    <span class="brand">${escapeHtml(c.brand)}</span>
                    ${escapeHtml(c.manual_name)} &middot; p${c.page_number}
                    <span class="score">${(c.relevance_score * 100).toFixed(0)}%</span>
                </span>
            `).join('')}
        </div>
    `;
}

// === Session Management ===
function updateSessionDisplay() {
    if (state.sessionId) {
        sessionInfo.textContent = 'Session: ' + state.sessionId.substring(0, 8) + '...';
    } else {
        sessionInfo.textContent = 'New session';
    }
}

async function startNewChat() {
    await saveCurrentConversation();
    state.sessionId = null;
    chatMessages.innerHTML = `
        <div class="message assistant-message">
            <div class="message-avatar">AI</div>
            <div class="message-body">
                <div class="content-area">
                    <p>New conversation started. How can I help you?</p>
                </div>
            </div>
        </div>
    `;
    updateSessionDisplay();
    localStorage.setItem('rag_sessionId', '');
    localStorage.setItem('rag_chatHistory', '');
    renderChatHistory();
    queryInput.focus();
}

async function clearConversation() {
    if (state.sessionId) {
        try {
            await fetch(`/api/conversation/${state.sessionId}`, { method: 'DELETE' });
        } catch { /* ignore */ }
    }
    startNewChat();
}

function saveSessionToStorage() {
    localStorage.setItem('rag_sessionId', state.sessionId || '');
    localStorage.setItem('rag_chatHistory', chatMessages.innerHTML);
    saveCurrentConversation(); // fire-and-forget
    renderChatHistory();       // fire-and-forget
}

function loadSessionFromStorage() {
    const savedSession = localStorage.getItem('rag_sessionId');
    const savedHistory = localStorage.getItem('rag_chatHistory');

    if (savedSession) {
        state.sessionId = savedSession;
        updateSessionDisplay();
    }
    if (savedHistory && savedSession) {
        chatMessages.innerHTML = savedHistory;
    }
    renderChatHistory(); // fire-and-forget
}

// === Chat History (Neon Postgres via API) ===
async function saveCurrentConversation() {
    if (!state.sessionId) return;
    const html = chatMessages.innerHTML;
    if (!html) return;

    const tempDiv = document.createElement('div');
    tempDiv.innerHTML = html;
    const firstUserMsg = tempDiv.querySelector('.user-message .message-body');
    const title = (firstUserMsg ? firstUserMsg.textContent.trim().substring(0, 50) : '') || 'Conversation';

    try {
        await fetch('/api/history', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ id: state.sessionId, title, html }),
        });
    } catch (err) {
        console.error('Failed to save conversation:', err);
    }
}

async function renderChatHistory() {
    const container = document.getElementById('chatHistory');
    if (!container) return;

    try {
        const response = await fetch('/api/history');
        const data = await response.json();
        const conversations = data.conversations || [];

        if (conversations.length === 0) {
            container.innerHTML = '<p class="empty-state">No past conversations</p>';
            return;
        }

        container.innerHTML = conversations.map(c => `
            <div class="history-item ${c.id === state.sessionId ? 'active' : ''}" data-id="${escapeHtml(c.id)}">
                <span class="history-title">${escapeHtml(c.title)}</span>
                <button class="history-delete" data-id="${escapeHtml(c.id)}" title="Delete">&#x2715;</button>
            </div>
        `).join('');

        container.querySelectorAll('.history-item').forEach(item => {
            item.addEventListener('click', (e) => {
                if (e.target.classList.contains('history-delete')) return;
                loadConversation(item.dataset.id);
            });
        });

        container.querySelectorAll('.history-delete').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.stopPropagation();
                deleteConversation(btn.dataset.id);
            });
        });
    } catch (err) {
        console.error('Failed to load history:', err);
        container.innerHTML = '<p class="empty-state">Failed to load history</p>';
    }
}

async function loadConversation(id) {
    await saveCurrentConversation();

    try {
        const response = await fetch(`/api/history/${id}`);
        if (!response.ok) return;
        const conv = await response.json();

        state.sessionId = conv.id;
        chatMessages.innerHTML = conv.html;
        localStorage.setItem('rag_sessionId', conv.id);
        localStorage.setItem('rag_chatHistory', conv.html);
        updateSessionDisplay();
        renderChatHistory(); // fire-and-forget
        scrollToBottom();
    } catch (err) {
        console.error('Failed to load conversation:', err);
    }
}

async function deleteConversation(id) {
    try {
        await fetch(`/api/history/${id}`, { method: 'DELETE' });

        if (state.sessionId === id) {
            state.sessionId = null;
            chatMessages.innerHTML = `
                <div class="message assistant-message">
                    <div class="message-avatar">AI</div>
                    <div class="message-body">
                        <div class="content-area">
                            <p>New conversation started. How can I help you?</p>
                        </div>
                    </div>
                </div>
            `;
            localStorage.setItem('rag_sessionId', '');
            localStorage.setItem('rag_chatHistory', '');
            updateSessionDisplay();
        }
        renderChatHistory(); // fire-and-forget
    } catch (err) {
        console.error('Failed to delete conversation:', err);
    }
}

// === Upload ===
async function handleUpload(e) {
    e.preventDefault();
    const statusDiv = document.getElementById('uploadStatus');
    const brand = document.getElementById('uploadBrand').value;
    const fileInput = document.getElementById('uploadFile');
    const file = fileInput.files[0];

    if (!brand || !file) return;

    statusDiv.textContent = 'Uploading...';
    statusDiv.className = 'status-msg loading';

    const formData = new FormData();
    formData.append('file', file);
    formData.append('brand', brand);

    try {
        const uploadResp = await fetch('/api/upload', { method: 'POST', body: formData });
        const uploadData = await uploadResp.json();
        if (!uploadResp.ok) throw new Error(uploadData.detail || 'Upload failed');

        statusDiv.textContent = 'Indexing...';

        const ingestResp = await fetch('/api/ingest', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ brand }),
        });
        const ingestData = await ingestResp.json();
        if (!ingestResp.ok) throw new Error(ingestData.detail || 'Indexing failed');

        statusDiv.textContent = ingestData.message;
        statusDiv.className = 'status-msg success';
        uploadForm.reset();

        // Refresh sources
        loadSources();

    } catch (error) {
        statusDiv.textContent = `Error: ${error.message}`;
        statusDiv.className = 'status-msg error';
    }
}

async function handleWebsiteIngest(e) {
    e.preventDefault();
    const statusDiv = document.getElementById('websiteStatus');
    const urls = document.getElementById('websiteUrls').value.split('\n').map(u => u.trim()).filter(Boolean);
    const sourceName = document.getElementById('websiteSourceName').value.trim() || null;

    if (urls.length === 0) return;

    statusDiv.textContent = 'Ingesting websites...';
    statusDiv.className = 'status-msg loading';

    try {
        const response = await fetch('/api/ingest/website', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ urls, source_name: sourceName }),
        });
        const data = await response.json();
        if (!response.ok) throw new Error(data.detail || 'Website ingestion failed');

        statusDiv.textContent = data.message;
        statusDiv.className = 'status-msg success';
        websiteForm.reset();
        loadSources();
    } catch (error) {
        statusDiv.textContent = `Error: ${error.message}`;
        statusDiv.className = 'status-msg error';
    }
}

async function handleYouTubeIngest(e) {
    e.preventDefault();
    const statusDiv = document.getElementById('youtubeStatus');
    const urls = document.getElementById('youtubeUrls').value.split('\n').map(u => u.trim()).filter(Boolean);
    const languages = document.getElementById('youtubeLangs').value.split(',').map(l => l.trim()).filter(Boolean);

    if (urls.length === 0) return;

    statusDiv.textContent = 'Ingesting YouTube videos...';
    statusDiv.className = 'status-msg loading';

    try {
        const response = await fetch('/api/ingest/youtube', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ video_urls: urls, languages: languages.length > 0 ? languages : ['en', 'bn'] }),
        });
        const data = await response.json();
        if (!response.ok) throw new Error(data.detail || 'YouTube ingestion failed');

        statusDiv.textContent = data.message;
        statusDiv.className = 'status-msg success';
        youtubeForm.reset();
        const langsInput = document.getElementById('youtubeLangs');
        if (langsInput) langsInput.value = 'en,bn';
        loadSources();
    } catch (error) {
        statusDiv.textContent = `Error: ${error.message}`;
        statusDiv.className = 'status-msg error';
    }
}

// === Utilities ===
function scrollToBottom() {
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function formatMarkdown(text) {
    return text
        .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
        .replace(/\*(.*?)\*/g, '<em>$1</em>')
        .replace(/`(.*?)`/g, '<code>$1</code>')
        .replace(/^### (.*$)/gm, '<h4>$1</h4>')
        .replace(/^## (.*$)/gm, '<h3>$1</h3>')
        .replace(/^- (.*$)/gm, '<li>$1</li>')
        .replace(/(<li>.*<\/li>)/s, '<ul>$1</ul>')
        .replace(/\n\n/g, '</p><p>')
        .replace(/\n/g, '<br>');
}
