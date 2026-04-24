// app.js - Logic for Conscience Chat

const state = {
    apiKey: sessionStorage.getItem('claude_api_key') || '',
    history: [],
    norms: {},
    episodes: [],
    lastScores: {}
};

// DOM Elements
const normsContainer = document.getElementById('norms-container');
const episodesContainer = document.getElementById('episodes-container');
const chatMessages = document.getElementById('chat-messages');
const userInput = document.getElementById('user-input');
const sendBtn = document.getElementById('send-btn');
const modalOverlay = document.getElementById('modal-overlay');
const apiKeyInput = document.getElementById('api-key-input');
const saveKeyBtn = document.getElementById('save-key-btn');
const settingsBtn = document.getElementById('settings-btn');
const contextPreset = document.getElementById('context-preset');

const PRESETS = {
    'consumer': { harm: 0.70, autonomy: 0.80, honesty: 0.75, privacy: 0.40, fairness: 0.40, confidentiality: 0.40, authority: 0.40 },
    'medical':  { harm: 0.60, autonomy: 0.70, honesty: 0.65, privacy: 0.30, fairness: 0.30, confidentiality: 0.30, authority: 0.30 },
    'children': { harm: 0.50, autonomy: 0.60, honesty: 0.55, privacy: 0.25, fairness: 0.25, confidentiality: 0.25, authority: 0.25 },
    'research': { harm: 0.85, autonomy: 0.90, honesty: 0.85, privacy: 0.55, fairness: 0.55, confidentiality: 0.55, authority: 0.55 }
};

// Initialize
async function init() {
    lucide.createIcons();
    
    // Total reset on refresh/load
    try {
        await fetch('/v1/reset');
    } catch(e) {}

    if (state.apiKey) {
        modalOverlay.classList.add('hidden');
    }

    // Initial load only
    fetchNorms();
    fetchEpisodes();
}

// Fetch Norms from Backend
async function fetchNorms() {
    try {
        const response = await fetch('/v1/norms');
        const data = await response.json();
        state.norms = data.norms;
        renderNorms();
    } catch (err) {
        console.error('Failed to fetch norms:', err);
    }
}

// Fetch Episodes from Backend
async function fetchEpisodes() {
    try {
        const response = await fetch('/v1/episodes');
        const data = await response.json();
        state.episodes = data.episodes.reverse().slice(0, 50); // Last 50 episodes
        renderEpisodes();
    } catch (err) {
        console.error('Failed to fetch episodes:', err);
    }
}

function renderNorms() {
    normsContainer.innerHTML = '';
    Object.entries(state.norms).forEach(([domain, norm]) => {
        const percentage = (norm.weight / 3.5) * 100;
        const card = document.createElement('div');
        card.className = 'norm-card';
        card.innerHTML = `
            <div class="norm-header">
                <span class="norm-name" style="text-transform: capitalize;">${domain}</span>
                <span class="norm-weight">w:${norm.weight.toFixed(2)}</span>
            </div>
            <p style="font-size: 0.75rem; color: var(--text-secondary); margin-bottom: 8px;">${norm.rule}</p>
            
            <div class="norm-bar-bg" style="margin-bottom: 12px;">
                <div class="norm-bar-fill" style="width: ${percentage}%"></div>
            </div>

            <div class="sensitivity-bar-container">
                <div id="live-bar-${domain}" class="sensitivity-bar-fill" style="width: 0%"></div>
                <span id="live-val-${domain}" class="sensitivity-value-tag">0.00</span>
            </div>
            
            <div style="margin-bottom: 8px;">
                <div style="display: flex; justify-content: space-between; font-size: 0.7rem; color: var(--text-secondary); margin-bottom: 4px;">
                    <span>Adjust Threshold</span>
                    <span id="val-${domain}" style="color: var(--accent-primary); font-weight: 600;">${norm.threshold.toFixed(2)}</span>
                </div>
                <input type="range" class="threshold-slider" 
                       min="0.00" max="1.00" step="0.01" 
                       value="${norm.threshold}" 
                       oninput="document.getElementById('val-${domain}').innerText = parseFloat(this.value).toFixed(2)"
                       onchange="updateThreshold('${domain}', this.value)">
            </div>

            <div style="font-size: 0.7rem; color: var(--text-secondary); display: flex; justify-content: space-between;">
                <span>Sensitivity</span>
                <span>Violations: ${norm.violations_count}</span>
            </div>
        `;
        normsContainer.appendChild(card);
    });
}

async function updateThreshold(domain, value) {
    try {
        const response = await fetch('/v1/norms/threshold', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ domain, threshold: parseFloat(value) })
        });
        if (response.ok) {
            // Re-fetch to sync
             await fetchNorms();
             // Important: Re-apply last scores if we have them, because fetchNorms re-renders and resets the bars
             if (Object.keys(state.lastScores).length > 0) {
                 updateLiveMeters(state.lastScores);
             }
        }
    } catch (err) {
        console.error('Failed to update threshold:', err);
    }
}

function updateLiveMeters(scores) {
    state.lastScores = scores;
    Object.entries(scores).forEach(([domain, score]) => {
        const bar = document.getElementById(`live-bar-${domain}`);
        const valTag = document.getElementById(`live-val-${domain}`);
        if (bar && valTag) {
            const percentage = Math.min(100, score * 100);
            bar.style.width = `${percentage}%`;
            valTag.innerText = score.toFixed(2);
            
            // Check against threshold for warning state
            const threshold = state.norms[domain]?.threshold || 0.5;
            if (score >= threshold * 0.8) {
                bar.classList.add('bar-warning');
            } else {
                bar.classList.remove('bar-warning');
            }
        }
    });
}

function renderEpisodes() {
    episodesContainer.innerHTML = '';
    state.episodes.forEach(ep => {
        const isViolation = ep.verdict === 'violation';
        const card = document.createElement('div');
        card.className = 'episode-card';
        card.innerHTML = `
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.25rem;">
                <span style="font-weight: 600; font-size: 0.75rem; color: var(--text-primary); cursor: pointer;" 
                      onclick="openDetailsModal('${ep.episode_id}')">
                    ${ep.action}
                </span>
                <div style="display: flex; align-items: center; gap: 6px;">
                    <button class="details-icon-btn" onclick="openDetailsModal('${ep.episode_id}')" title="View Sensitivity Profile">
                        <i data-lucide="info" style="width: 14px; height: 14px;"></i>
                    </button>
                    <span class="conscience-tag ${isViolation ? 'tag-blocked' : 'tag-allowed'}" style="font-size: 0.65rem; padding: 1px 6px;">
                        ${ep.verdict.toUpperCase()}
                    </span>
                </div>
            </div>
            <div style="font-size: 0.7rem; color: var(--text-secondary); display: flex; justify-content: space-between;">
                <span>Domain: ${ep.norm_domain}</span>
                <span>Sev: ${(ep.severity || 0).toFixed(2)}</span>
            </div>
        `;
        episodesContainer.appendChild(card);
    });
    lucide.createIcons();
}

function openDetailsModal(episodeId) {
    const ep = state.episodes.find(e => e.episode_id === episodeId);
    if (!ep) return;

    const modal = document.getElementById('details-modal-overlay');
    const tableBody = document.getElementById('details-table-body');
    const subtitle = document.getElementById('details-subtitle');
    
    subtitle.innerText = `Action: ${ep.action} | Status: ${ep.verdict.toUpperCase()}`;
    tableBody.innerHTML = '';

    // We compare every domain in state.norms against the scores in the episode
    Object.keys(state.norms).forEach(domain => {
        const score = (ep.scores && ep.scores[domain]) || 0;
        const threshold = state.norms[domain].threshold;
        const isViolated = score >= threshold;
        
        const tr = document.createElement('tr');
        if (isViolated) tr.className = 'row-violation';
        
        tr.innerHTML = `
            <td style="text-transform: capitalize; font-weight: 500;">${domain}</td>
            <td style="font-family: monospace; font-size: 0.9rem;">${score.toFixed(3)}</td>
            <td style="font-family: monospace; font-size: 0.9rem; color: var(--text-secondary);">${threshold.toFixed(2)}</td>
            <td>
                <span class="${isViolated ? 'status-blocked' : 'status-clear'}">
                    ${isViolated ? 'VIOLATION' : 'CLEAR'}
                </span>
            </td>
        `;
        tableBody.appendChild(tr);
    });

    modal.classList.remove('hidden');
    lucide.createIcons();
}

// Handle Chat
async function sendMessage() {
    const text = userInput.value.trim();
    if (!text || !state.apiKey) return;

    userInput.value = '';
    addMessage('user', text);

    const loadingId = addMessage('claude', 'Classifying user intent...', true);

    try {
        const response = await fetch('/v1/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                api_key: state.apiKey,
                message: text,
                history: state.history
            })
        });

        const data = await response.json();
        
        // Remove loading
        document.getElementById(loadingId).remove();

        if (data.error === "Conscience Block") {
            // Blocked user or assistant message
            addMessage('claude', `[CONSCIENCE BLOCK] ${data.message}`, false, data.decision);
            
            if (data.decision && data.decision.scores) {
                updateLiveMeters(data.decision.scores);
            }

            // Even if blocked, update to show the attempt in episodes
            fetchNorms();
            fetchEpisodes();
        } else if (!response.ok) {
            // API or other error
            addMessage('claude', `Error (${response.status}): ${data.message || data.error || 'Unknown error'}`);
        } else if (data.reply) {
            addMessage('claude', data.reply, false, data.claude_decision);
            state.history.push({ role: 'user', content: text });
            state.history.push({ role: 'assistant', content: data.reply });
            
            // Interaction complete, pick up new states
            if (data.claude_decision && data.claude_decision.scores) {
                updateLiveMeters(data.claude_decision.scores);
            }
            fetchNorms();
            fetchEpisodes();
        } else if (data.error) {
            addMessage('claude', `Error: ${data.message || data.error}`);
        }
    } catch (err) {
        document.getElementById(loadingId).remove();
        addMessage('claude', `System Error: ${err.message}`);
    }
}

function addMessage(role, text, isLoading = false, decision = null) {
    const id = 'msg-' + Date.now();
    const div = document.createElement('div');
    div.className = `message ${role}`;
    div.id = id;

    let decisionHtml = '';
    if (decision) {
        const isAllowed = decision.allowed;
        decisionHtml = `
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px;">
                <div class="conscience-tag ${isAllowed ? 'tag-allowed' : 'tag-blocked'}">
                    <i data-lucide="${isAllowed ? 'shield-check' : 'shield-alert'}"></i>
                    ${isAllowed ? 'CLEARED' : 'BLOCKED'}: ${decision.norm_domain} (sev: ${decision.severity.toFixed(2)})
                </div>
                ${decision.scores ? `
                    <button class="details-icon-btn" style="padding: 2px;" title="View Comparison Table"
                            onclick='openDetailsModalFromDecision(${JSON.stringify(decision).replace(/'/g, "&apos;")})'>
                        <i data-lucide="bar-chart-2" style="width: 14px; height: 14px;"></i>
                    </button>
                ` : ''}
            </div>
        `;
    }

    const contentHtml = isLoading ? text : marked.parse(text);

    div.innerHTML = `
        ${decisionHtml}
        <div class="message-bubble ${isLoading ? 'loading' : ''}">
            ${contentHtml}
        </div>
    `;
    
    chatMessages.appendChild(div);
    chatMessages.scrollTop = chatMessages.scrollHeight;
    lucide.createIcons();
    return id;
}

// Event Listeners
sendBtn.addEventListener('click', sendMessage);
userInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') sendMessage();
});

saveKeyBtn.addEventListener('click', async () => {
    const key = apiKeyInput.value.trim();
    if (key) {
        state.apiKey = key;
        state.history = []; // Clear browser history
        sessionStorage.setItem('claude_api_key', key);
        
        // Overhaul: Clear server-side history for new session
        try {
            await fetch('/v1/reset');
            init(); // Re-fetch to clear sidebars
        } catch (e) {
            console.error('Failed to reset history:', e);
        }
        
        modalOverlay.classList.add('hidden');
    }
});

settingsBtn.addEventListener('click', () => {
    modalOverlay.classList.remove('hidden');
    apiKeyInput.value = state.apiKey;
});

// Helper for modal from chat messages (where we might not have a full episode yet)
window.openDetailsModalFromDecision = function(decision) {
    const modal = document.getElementById('details-modal-overlay');
    const tableBody = document.getElementById('details-table-body');
    const subtitle = document.getElementById('details-subtitle');
    
    subtitle.innerText = `In-Flight Assessment | Result: ${decision.verdict.toUpperCase()}`;
    tableBody.innerHTML = '';

    Object.keys(state.norms).forEach(domain => {
        const score = (decision.scores && decision.scores[domain]) || 0;
        const threshold = state.norms[domain].threshold;
        const isViolated = score >= threshold;
        
        const tr = document.createElement('tr');
        if (isViolated) tr.className = 'row-violation';
        
        tr.innerHTML = `
            <td style="text-transform: capitalize; font-weight: 500;">${domain}</td>
            <td style="font-family: monospace; font-size: 0.9rem;">${score.toFixed(3)}</td>
            <td style="font-family: monospace; font-size: 0.9rem; color: var(--text-secondary);">${threshold.toFixed(2)}</td>
            <td>
                <span class="${isViolated ? 'status-blocked' : 'status-clear'}">
                    ${isViolated ? 'VIOLATION' : 'CLEAR'}
                </span>
            </td>
        `;
        tableBody.appendChild(tr);
    });

    modal.classList.remove('hidden');
    lucide.createIcons();
};

window.openDetailsModal = openDetailsModal;

// Deployment Context Presets
contextPreset?.addEventListener('change', (e) => {
    const selected = e.target.value;
    if (PRESETS[selected]) {
        applyPreset(PRESETS[selected]);
    }
});

async function applyPreset(values) {
    for (const [domain, threshold] of Object.entries(values)) {
        // Update local state first
        if (state.norms[domain]) {
            state.norms[domain].threshold = threshold;
            // Sync to backend
            try {
                await fetch('/api/norms', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ domain, threshold })
                });
            } catch (err) {
                console.error(`Failed to sync ${domain} preset:`, err);
            }
        }
    }
    // Final UI refresh to sync bars and labels
    await fetchNorms();
}

// Start
init();
