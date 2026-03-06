// Universal Knowledge Assistant - Frontend JavaScript
// Supports streaming responses, conversation memory, and multi-source ingestion

let currentSessionId = null;
let isLoading = false;

// DOM Elements
const chatMessages = document.getElementById('chatMessages');
const queryForm = document.getElementById('queryForm');
const queryInput = document.getElementById('queryInput');
const sendBtn = document.getElementById('sendBtn');
const brandFilter = document.getElementById('brandFilter');
const settingsModal = document.getElementById('settingsModal');
const settingsBtn = document.getElementById('settingsBtn');
const closeSettings = document.getElementById('closeSettings');
const sessionIdDisplay = document.getElementById('sessionId');
const newChatBtn = document.getElementById('newChatBtn');
const clearSessionBtn = document.getElementById('clearSession');

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    checkHealth();
    setupEventListeners();
    setupTabs();
    loadConversationFromStorage();
});

// Event Listeners
function setupEventListeners() {
    queryForm.addEventListener('submit', handleQuery);
    settingsBtn.addEventListener('click', () => settingsModal.classList.remove('hidden'));
    closeSettings.addEventListener('click', () => settingsModal.classList.add('hidden'));
    newChatBtn.addEventListener('click', startNewConversation);
    clearSessionBtn.addEventListener('click', clearConversation);
    
    // Multi-source forms
    document.getElementById('uploadForm').addEventListener('submit', handleUpload);
    document.getElementById('websiteForm').addEventListener('submit', handleWebsiteIngest);
    document.getElementById('youtubeForm').addEventListener('submit', handleYouTubeIngest);
    document.getElementById('sqlForm').addEventListener('submit', handleSQLIngest);
    document.getElementById('mongoForm').addEventListener('submit', handleMongoIngest);
    
    // Close modal on outside click
    settingsModal.addEventListener('click', (e) => {
        if (e.target === settingsModal) {
            settingsModal.classList.add('hidden');
        }
    });
}

// Tab System
function setupTabs() {
    const tabBtns = document.querySelectorAll('.tab-btn');
    const tabContents = document.querySelectorAll('.tab-content');
    
    tabBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            const tabName = btn.dataset.tab;
            
            // Update buttons
            tabBtns.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            
            // Update content
            tabContents.forEach(content => {
                content.classList.remove('active');
                if (content.id === `${tabName}-tab`) {
                    content.classList.add('active');
                }
            });
        });
    });
}

// Health Check
async function checkHealth() {
    try {
        const response = await fetch('/api/health');
        const data = await response.json();
        
        document.getElementById('apiStatus').textContent = '✅ Connected';
        document.getElementById('apiStatus').className = 'status-value success';
        
        document.getElementById('qdrantStatus').textContent = data.qdrant_connected ? '✅ Connected' : '❌ Disconnected';
        document.getElementById('qdrantStatus').className = `status-value ${data.qdrant_connected ? 'success' : 'error'}`;
        
        document.getElementById('openaiStatus').textContent = data.openai_configured ? '✅ Configured' : '❌ Not Configured';
        document.getElementById('openaiStatus').className = `status-value ${data.openai_configured ? 'success' : 'error'}`;
    } catch (error) {
        document.getElementById('apiStatus').textContent = '❌ Error';
        document.getElementById('apiStatus').className = 'status-value error';
    }
}

// Query with Streaming
async function handleQuery(e) {
    e.preventDefault();
    
    if (isLoading) return;
    
    const query = queryInput.value.trim();
    if (!query) return;
    
    // Add user message
    addMessage(query, 'user');
    queryInput.value = '';
    isLoading = true;
    sendBtn.disabled = true;
    
    // Create assistant message placeholder
    const assistantMsg = addMessage('', 'assistant', true);
    const contentDiv = assistantMsg.querySelector('.message-content');
    const citationsDiv = assistantMsg.querySelector('.citations');
    
    try {
        const brand = brandFilter.value;
        
        // Use conversation endpoint with streaming
        const response = await fetch('/api/conversation/query/stream', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                query: query,
                session_id: currentSessionId,
                brand_filter: brand || null
            })
        });
        
        if (!response.ok) throw new Error('Query failed');
        
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';
        let contentText = '';
        
        while (true) {
            const {done, value} = await reader.read();
            if (done) break;
            
            buffer += decoder.decode(value, {stream: true});
            const lines = buffer.split('\n');
            buffer = lines.pop(); // Keep incomplete line in buffer
            
            for (const line of lines) {
                if (!line.trim()) continue;
                
                try {
                    const data = JSON.parse(line);
                    
                    if (data.type === 'session') {
                        currentSessionId = data.data.session_id;
                        updateSessionDisplay();
                    } else if (data.type === 'citations') {
                        renderCitations(data.data, citationsDiv);
                    } else if (data.type === 'content') {
                        contentText += data.data;
                        contentDiv.innerHTML = formatMarkdown(contentText);
                    } else if (data.type === 'done') {
                        // Stream complete
                    }
                } catch (err) {
                    console.error('Error parsing stream data:', err, line);
                }
            }
        }
        
        // Scroll to bottom
        chatMessages.scrollTop = chatMessages.scrollHeight;
        
        // Save conversation
        saveConversationToStorage();
        
    } catch (error) {
        console.error('Query error:', error);
        contentDiv.innerHTML = '<p class="error">❌ Error processing query. Please try again.</p>';
    } finally {
        isLoading = false;
        sendBtn.disabled = false;
    }
}

// Add Message to Chat
function addMessage(text, role, withCitations = false) {
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${role}-message`;
    
    const contentDiv = document.createElement('div');
    contentDiv.className = 'message-content';
    contentDiv.innerHTML = role === 'user' ? text : formatMarkdown(text);
    
    messageDiv.appendChild(contentDiv);
    
    if (withCitations) {
        const citationsDiv = document.createElement('div');
        citationsDiv.className = 'citations';
        messageDiv.appendChild(citationsDiv);
    }
    
    chatMessages.appendChild(messageDiv);
    chatMessages.scrollTop = chatMessages.scrollHeight;
    
    return messageDiv;
}

// Render Citations
function renderCitations(citations, container) {
    if (!citations || citations.length === 0) return;
    
    container.innerHTML = '<h4>📚 Sources:</h4>';
    const ul = document.createElement('ul');
    
    citations.forEach(citation => {
        const li = document.createElement('li');
        const sourceIcon = getSourceIcon(citation.source_type);
        li.innerHTML = `
            ${sourceIcon} <strong>${citation.manual_name}</strong> 
            (${citation.source_type}, Page/Section ${citation.page_number})
            <span class="relevance-score">${(citation.relevance_score * 100).toFixed(1)}%</span>
            ${citation.source_url ? `<br><small><a href="${citation.source_url}" target="_blank">${citation.source_url}</a></small>` : ''}
        `;
        ul.appendChild(li);
    });
    
    container.appendChild(ul);
}

// Get Source Icon
function getSourceIcon(sourceType) {
    const icons = {
        'pdf': '📄',
        'website': '🌐',
        'youtube': '🎥',
        'database': '🗄️',
        'mongodb': '🗄️'
    };
    return icons[sourceType] || '📄';
}

// Format Markdown (basic)
function formatMarkdown(text) {
    return text
        .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
        .replace(/\*(.*?)\*/g, '<em>$1</em>')
        .replace(/`(.*?)`/g, '<code>$1</code>')
        .replace(/\n/g, '<br>');
}

// Conversation Management
function startNewConversation() {
    if (confirm('Start a new conversation? Current conversation will be cleared.')) {
        currentSessionId = null;
        chatMessages.innerHTML = '';
        updateSessionDisplay();
        saveConversationToStorage();
        
        // Add welcome message
        addMessage('New conversation started. How can I help you?', 'assistant');
    }
}

async function clearConversation() {
    if (!currentSessionId) {
        startNewConversation();
        return;
    }
    
    if (confirm('Clear current conversation?')) {
        try {
            await fetch(`/api/conversation/${currentSessionId}`, {
                method: 'DELETE'
            });
            startNewConversation();
        } catch (error) {
            console.error('Error clearing conversation:', error);
        }
    }
}

function updateSessionDisplay() {
    if (currentSessionId) {
        sessionIdDisplay.textContent = currentSessionId.substring(0, 8) + '...';
    } else {
        sessionIdDisplay.textContent = 'New Session';
    }
}

function saveConversationToStorage() {
    localStorage.setItem('sessionId', currentSessionId || '');
    localStorage.setItem('chatHistory', chatMessages.innerHTML);
}

function loadConversationFromStorage() {
    const savedSessionId = localStorage.getItem('sessionId');
    const savedHistory = localStorage.getItem('chatHistory');
    
    if (savedSessionId) {
        currentSessionId = savedSessionId;
        updateSessionDisplay();
    }
    
    if (savedHistory && savedSessionId) {
        chatMessages.innerHTML = savedHistory;
    }
}

// Multi-Source Ingestion Handlers

async function handleWebsiteIngest(e) {
    e.preventDefault();
    const statusDiv = document.getElementById('websiteStatus');
    statusDiv.innerHTML = '⏳ Processing...';
    
    const urls = document.getElementById('websiteUrls').value.split('\n').filter(u => u.trim());
    const sourceName = document.getElementById('websiteName').value.trim() || null;
    
    try {
        const response = await fetch('/api/ingest/website', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ urls, source_name: sourceName })
        });
        
        const data = await response.json();
        
        if (response.ok) {
            statusDiv.innerHTML = `✅ ${data.message}`;
            statusDiv.className = 'status-message success';
            document.getElementById('websiteForm').reset();
        } else {
            statusDiv.innerHTML = `❌ ${data.detail}`;
            statusDiv.className = 'status-message error';
        }
    } catch (error) {
        statusDiv.innerHTML = `❌ Error: ${error.message}`;
        statusDiv.className = 'status-message error';
    }
}

async function handleYouTubeIngest(e) {
    e.preventDefault();
    const statusDiv = document.getElementById('youtubeStatus');
    statusDiv.innerHTML = '⏳ Processing...';
    
    const urls = document.getElementById('youtubeUrls').value.split('\n').filter(u => u.trim());
    const languages = document.getElementById('youtubeLangs').value.split(',').map(l => l.trim());
    
    try {
        const response = await fetch('/api/ingest/youtube', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ video_urls: urls, languages })
        });
        
        const data = await response.json();
        
        if (response.ok) {
            statusDiv.innerHTML = `✅ ${data.message}`;
            statusDiv.className = 'status-message success';
            document.getElementById('youtubeForm').reset();
        } else {
            statusDiv.innerHTML = `❌ ${data.detail}`;
            statusDiv.className = 'status-message error';
        }
    } catch (error) {
        statusDiv.innerHTML = `❌ Error: ${error.message}`;
        statusDiv.className = 'status-message error';
    }
}

async function handleSQLIngest(e) {
    e.preventDefault();
    const statusDiv = document.getElementById('sqlStatus');
    statusDiv.innerHTML = '⏳ Processing...';
    
    const connection = document.getElementById('sqlConnection').value;
    const table = document.getElementById('sqlTable').value.trim() || null;
    const query = document.getElementById('sqlQuery').value.trim() || null;
    const sourceName = document.getElementById('sqlName').value.trim() || null;
    
    try {
        const response = await fetch('/api/ingest/database', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ 
                connection_string: connection, 
                table_name: table,
                query: query,
                source_name: sourceName
            })
        });
        
        const data = await response.json();
        
        if (response.ok) {
            statusDiv.innerHTML = `✅ ${data.message}`;
            statusDiv.className = 'status-message success';
            document.getElementById('sqlForm').reset();
        } else {
            statusDiv.innerHTML = `❌ ${data.detail}`;
            statusDiv.className = 'status-message error';
        }
    } catch (error) {
        statusDiv.innerHTML = `❌ Error: ${error.message}`;
        statusDiv.className = 'status-message error';
    }
}

async function handleMongoIngest(e) {
    e.preventDefault();
    const statusDiv = document.getElementById('mongoStatus');
    statusDiv.innerHTML = '⏳ Processing...';
    
    const connection = document.getElementById('mongoConnection').value;
    const database = document.getElementById('mongoDatabase').value;
    const collection = document.getElementById('mongoCollection').value;
    const queryStr = document.getElementById('mongoQuery').value.trim();
    const queryFilter = queryStr ? JSON.parse(queryStr) : null;
    
    try {
        const response = await fetch('/api/ingest/mongodb', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ 
                connection_string: connection,
                database_name: database,
                collection_name: collection,
                query_filter: queryFilter
            })
        });
        
        const data = await response.json();
        
        if (response.ok) {
            statusDiv.innerHTML = `✅ ${data.message}`;
            statusDiv.className = 'status-message success';
            document.getElementById('mongoForm').reset();
        } else {
            statusDiv.innerHTML = `❌ ${data.detail}`;
            statusDiv.className = 'status-message error';
        }
    } catch (error) {
        statusDiv.innerHTML = `❌ Error: ${error.message}`;
        statusDiv.className = 'status-message error';
    }
}

// PDF Upload (existing functionality)
async function handleUpload(e) {
    e.preventDefault();
    const statusDiv = document.getElementById('uploadStatus');
    statusDiv.innerHTML = '⏳ Uploading...';
    
    const formData = new FormData();
    formData.append('file', document.getElementById('uploadFile').files[0]);
    formData.append('brand', document.getElementById('uploadBrand').value);
    
    try {
        const response = await fetch('/api/upload', {
            method: 'POST',
            body: formData
        });
        
        const data = await response.json();
        
        if (response.ok) {
            statusDiv.innerHTML = `✅ ${data.message}`;
            statusDiv.className = 'status-message success';
            // Auto-index
            setTimeout(() => ingestBrand(document.getElementById('uploadBrand').value), 1000);
        } else {
            statusDiv.innerHTML = `❌ ${data.detail}`;
            statusDiv.className = 'status-message error';
        }
    } catch (error) {
        statusDiv.innerHTML = `❌ Error: ${error.message}`;
        statusDiv.className = 'status-message error';
    }
}

async function ingestBrand(brand) {
    const statusDiv = document.getElementById('ingestStatus');
    statusDiv.innerHTML = `⏳ Indexing ${brand}...`;
    
    try {
        const response = await fetch('/api/ingest', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ brand })
        });
        
        const data = await response.json();
        
        if (response.ok) {
            statusDiv.innerHTML = `✅ ${data.message}`;
            statusDiv.className = 'status-message success';
        } else {
            statusDiv.innerHTML = `❌ ${data.detail}`;
            statusDiv.className = 'status-message error';
        }
    } catch (error) {
        statusDiv.innerHTML = `❌ Error: ${error.message}`;
        statusDiv.className = 'status-message error';
    }
}

async function loadStats() {
    const container = document.getElementById('statsContainer');
    container.innerHTML = '⏳ Loading...';
    
    try {
        const response = await fetch('/api/stats');
        const data = await response.json();
        
        container.innerHTML = `
            <div class="stats-grid">
                <div class="stat-item">
                    <h4>Total Vectors</h4>
                    <p>${data.vector_store.total_vectors || 0}</p>
                </div>
                <div class="stat-item">
                    <h4>Queries</h4>
                    <p>${data.logging.total_queries || 0}</p>
                </div>
            </div>
        `;
    } catch (error) {
        container.innerHTML = '❌ Error loading stats';
    }
}
