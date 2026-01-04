/**
 * PromptCtl Browser Extension - Popup Script
 * 
 * Handles UI interactions and sends prompts to local CLI via socket
 * Now with DSPy integration for optimization, evaluation, and job tracking
 */

const SOCKET_URL = 'http://localhost:9090';
const DEFAULT_TIMEOUT = 5000;
const HEALTH_TIMEOUT = 2000;  // Fast timeout for health checks
const INTENT_TIMEOUT = 30000; // Longer timeout for AI analysis
const POLL_INTERVAL = 3000;
const HEARTBEAT_INTERVAL = 2500; // Connection check every 2.5s
const ANALYZE_DEBOUNCE = 1500;

// DOM Elements
let promptText, promptName, promptTags, autoTagCheckbox, autoOptimizeCheckbox;
let saveBtn, saveOptimizeBtn, messageDiv, statusDot, statusText;
let promptsList, jobsList, promptSearch;
let intentType, intentAudience, intentOutcome, intentConstraints, intentQuestions;
let analyzeIntentBtn, analyzeSpinner, analyzeText;
let parentPromptSelect, chainIndicator;
let promptDetail, detailTitle, detailContent, detailMeta, detailChain, detailCli;

// State
let allPrompts = [];
let pollInterval = null;
let heartbeatInterval = null;
let analyzeDebounceTimer = null;
let currentIntent = null;
let isConnected = false;
let consecutiveFailures = 0;
let recentSaves = [];  // Track recent saves for display
let currentDetailPrompt = null;  // Currently viewed prompt
let searchDebounceTimer = null;
let pendingOptimizePromptId = null;  // Prompt ID waiting for optimization goal
let currentSettings = null;  // Cached provider settings

// Initialize
document.addEventListener('DOMContentLoaded', init);

function init() {
  // Get DOM elements
  promptText = document.getElementById('promptText');
  promptName = document.getElementById('promptName');
  promptTags = document.getElementById('promptTags');
  autoTagCheckbox = document.getElementById('autoTag');
  autoOptimizeCheckbox = document.getElementById('autoOptimize');
  saveBtn = document.getElementById('saveBtn');
  saveOptimizeBtn = document.getElementById('saveOptimizeBtn');
  messageDiv = document.getElementById('message');
  statusDot = document.getElementById('statusDot');
  statusText = document.getElementById('statusText');
  promptsList = document.getElementById('promptsList');
  jobsList = document.getElementById('jobsList');
  promptSearch = document.getElementById('promptSearch');
  
  // Intent elements
  intentType = document.getElementById('intentType');
  intentAudience = document.getElementById('intentAudience');
  intentOutcome = document.getElementById('intentOutcome');
  intentConstraints = document.getElementById('intentConstraints');
  intentQuestions = document.getElementById('intentQuestions');
  analyzeIntentBtn = document.getElementById('analyzeIntentBtn');
  analyzeSpinner = document.getElementById('analyzeSpinner');
  analyzeText = document.getElementById('analyzeText');
  
  // Chain elements
  parentPromptSelect = document.getElementById('parentPrompt');
  chainIndicator = document.getElementById('chainIndicator');
  
  // Detail panel elements
  promptDetail = document.getElementById('promptDetail');
  detailTitle = document.getElementById('detailTitle');
  detailContent = document.getElementById('detailContent');
  detailMeta = document.getElementById('detailMeta');
  detailChain = document.getElementById('detailChain');
  detailCli = document.getElementById('detailCli');
  
  // Load saved preferences
  loadPreferences();
  
  // Check connection and start heartbeat
  checkConnection();
  startHeartbeat();
  
  // Load selected text from page
  loadSelectedText();
  
  // Event listeners
  saveBtn.addEventListener('click', () => handleSave(false));
  saveOptimizeBtn.addEventListener('click', () => handleSave(true));
  autoTagCheckbox.addEventListener('change', handleAutoTagToggle);
  autoOptimizeCheckbox.addEventListener('change', savePreferences);
  
  // Intent event listeners
  analyzeIntentBtn?.addEventListener('click', analyzeIntent);
  promptText?.addEventListener('input', handlePromptChange);
  
  // Tab navigation
  document.querySelectorAll('.tab').forEach(tab => {
    tab.addEventListener('click', () => switchTab(tab.dataset.tab));
  });
  
  // Refresh buttons
  document.getElementById('refreshPrompts')?.addEventListener('click', loadPrompts);
  document.getElementById('refreshJobs')?.addEventListener('click', loadJobs);
  
  // Search - with debounced content search
  promptSearch?.addEventListener('input', handleSearch);
  
  // Detail panel events
  document.getElementById('closeDetail')?.addEventListener('click', closePromptDetail);
  document.getElementById('copyCli')?.addEventListener('click', copyCli);
  document.getElementById('detailOptimize')?.addEventListener('click', () => {
    if (currentDetailPrompt) optimizePrompt(currentDetailPrompt.id);
  });
  document.getElementById('detailViewChain')?.addEventListener('click', viewCurrentChain);
  document.getElementById('detailLinkNew')?.addEventListener('click', linkNewPrompt);
  
  // Parent prompt selector
  parentPromptSelect?.addEventListener('change', updateChainIndicator);
  
  // Optimization modal events
  document.getElementById('closeOptimizeModal')?.addEventListener('click', closeOptimizeModal);
  document.getElementById('cancelOptimize')?.addEventListener('click', closeOptimizeModal);
  document.getElementById('confirmOptimize')?.addEventListener('click', confirmOptimization);
  
  // Close modal on overlay click
  document.getElementById('optimizeModal')?.addEventListener('click', (e) => {
    if (e.target.id === 'optimizeModal') closeOptimizeModal();
  });
  
  // Keyboard shortcuts
  document.addEventListener('keydown', (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
      handleSave(autoOptimizeCheckbox?.checked || false);
    }
    // Escape to close modal
    if (e.key === 'Escape') {
      closeOptimizeModal();
    }
  });
  
  // Load settings for modal display
  loadCurrentSettings();
}

async function loadPreferences() {
  const prefs = await chrome.storage.sync.get(['autoTag', 'autoOptimize']);
  if (prefs.autoTag !== undefined) {
    autoTagCheckbox.checked = prefs.autoTag;
  }
  if (prefs.autoOptimize !== undefined && autoOptimizeCheckbox) {
    autoOptimizeCheckbox.checked = prefs.autoOptimize;
  }
}

async function savePreferences() {
  await chrome.storage.sync.set({
    autoTag: autoTagCheckbox.checked,
    autoOptimize: autoOptimizeCheckbox?.checked || false
  });
}

function handleAutoTagToggle() {
  savePreferences();
  if (autoTagCheckbox.checked) {
    updateTagsFromDomain();
  }
}

async function loadSelectedText() {
  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    
    chrome.tabs.sendMessage(tab.id, { action: 'getSelection' }, (response) => {
      if (chrome.runtime.lastError) {
        console.log('No content script running, ignoring');
        return;
      }
      
      if (response && response.text) {
        promptText.value = response.text;
        
        if (autoTagCheckbox.checked) {
          updateTagsFromDomain(tab.url);
        }
      }
    });
  } catch (error) {
    console.error('Failed to load selected text:', error);
  }
}

function updateTagsFromDomain(url) {
  if (!url) {
    chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
      if (tabs[0]) {
        updateTagsFromDomain(tabs[0].url);
      }
    });
    return;
  }
  
  try {
    const domain = new URL(url).hostname.replace('www.', '');
    const domainTag = domain.split('.')[0];
    
    const currentTags = promptTags.value.split(',').map(t => t.trim()).filter(Boolean);
    if (!currentTags.includes(domainTag) && !currentTags.includes(domain)) {
      currentTags.push(domainTag);
      promptTags.value = currentTags.join(', ');
    }
  } catch (error) {
    console.error('Failed to parse domain:', error);
  }
}

async function checkConnection(isHeartbeat = false) {
  try {
    const response = await fetch(`${SOCKET_URL}/health`, {
      method: 'GET',
      signal: AbortSignal.timeout(HEALTH_TIMEOUT)
    });
    
    if (response.ok) {
      const data = await response.json();
      consecutiveFailures = 0;
      
      // Build status text
      let statusParts = ['Connected'];
      if (data.pipeline) statusParts.push('Pipeline');
      if (data.dspy_available) statusParts.push('DSPy');
      
      let statusInfo = statusParts.join(' + ');
      if (data.jobs_running > 0) {
        statusInfo += ` (${data.jobs_running} job${data.jobs_running > 1 ? 's' : ''} running)`;
      }
      
      setStatus('connected', statusInfo);
      setConnected(true, data);
      
      // Only show reconnect message if we were disconnected
      if (!isConnected && isHeartbeat) {
        showMessage('Reconnected to daemon', 'success');
      }
      isConnected = true;
      
    } else {
      handleDisconnect('Daemon not responding', isHeartbeat);
    }
  } catch (error) {
    handleDisconnect('Daemon not running', isHeartbeat);
  }
}

function handleDisconnect(reason, isHeartbeat) {
  consecutiveFailures++;
  isConnected = false;
  
  // Show reconnecting state for first few failures
  if (consecutiveFailures <= 2) {
    setStatus('reconnecting', 'Reconnecting...');
  } else {
    setStatus('disconnected', reason);
    if (!isHeartbeat) {
      showMessage('Start daemon: promptctl daemon --socket', 'info');
    }
  }
  
  setConnected(false);
}

function setConnected(connected, healthData = null) {
  // Enable/disable buttons based on connection
  if (saveBtn) saveBtn.disabled = !connected;
  
  // Only enable optimize buttons if DSPy is available
  const dspyAvailable = connected && healthData?.pipeline;
  if (saveOptimizeBtn) {
    saveOptimizeBtn.disabled = !dspyAvailable;
    saveOptimizeBtn.title = dspyAvailable ? 'Save and optimize with DSPy' : 'DSPy not available';
  }
  if (analyzeIntentBtn) {
    analyzeIntentBtn.disabled = !dspyAvailable;
  }
}

function startHeartbeat() {
  // Clear any existing heartbeat
  if (heartbeatInterval) {
    clearInterval(heartbeatInterval);
  }
  
  // Start heartbeat polling
  heartbeatInterval = setInterval(() => {
    checkConnection(true);
  }, HEARTBEAT_INTERVAL);
}

function stopHeartbeat() {
  if (heartbeatInterval) {
    clearInterval(heartbeatInterval);
    heartbeatInterval = null;
  }
}

function setStatus(state, text) {
  if (statusDot) statusDot.className = `status-dot ${state}`;
  if (statusText) statusText.textContent = text;
}

async function handleSave(withOptimize = false) {
  const text = promptText.value.trim();
  
  if (!text) {
    showMessage('Please enter prompt text', 'error');
    return;
  }
  
  const btn = withOptimize ? saveOptimizeBtn : saveBtn;
  btn.disabled = true;
  btn.textContent = withOptimize ? '🚀 Saving...' : '💾 Saving...';
  
  try {
    const tags = promptTags.value
      .split(',')
      .map(t => t.trim())
      .filter(Boolean);
    
    // Build intent object from form
    const intent = buildIntentFromForm();
    
    // Get parent prompt for chaining
    const parentId = parentPromptSelect?.value || null;
    
    const payload = {
      content: text,
      name: promptName.value.trim() || null,
      tags: tags.length > 0 ? tags : [],
      auto_optimize: withOptimize || autoOptimizeCheckbox?.checked || false,
      intent: intent,
      parent_id: parentId
    };
    
    const response = await fetch(`${SOCKET_URL}/save`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(payload),
      signal: AbortSignal.timeout(DEFAULT_TIMEOUT)
    });
    
    if (response.ok) {
      const result = await response.json();
      let message = `Saved: ${result.prompt_id}`;
      
      if (result.job_id) {
        const jobType = result.stages?.includes('optimize_intent_queued') ? 'intent-aware optimizing' : 'optimizing';
        message += ` (${jobType}...)`;
        // Start polling for job status
        startJobPolling(result.job_id);
      }
      
      showMessage(message, 'success');
      
      // Track recent save and update UI
      addRecentSave({
        id: result.prompt_id,
        content: text.substring(0, 50) + (text.length > 50 ? '...' : ''),
        tags: tags,
        job_id: result.job_id,
        timestamp: new Date().toISOString()
      });
      
      // Refresh prompts list in background
      loadPrompts();
      
      // Clear form
      setTimeout(() => {
        clearForm();
      }, 1500);
    } else {
      const error = await response.text();
      showMessage(`Error: ${error}`, 'error');
    }
  } catch (error) {
    showMessage(`Failed to save: ${error.message}`, 'error');
  } finally {
    btn.disabled = false;
    btn.textContent = withOptimize ? '🚀 Save & Optimize' : '💾 Save';
  }
}

// Build intent object from form fields
function buildIntentFromForm() {
  const type = intentType?.value || '';
  const audience = intentAudience?.value?.trim() || '';
  const outcome = intentOutcome?.value?.trim() || '';
  const constraints = intentConstraints?.value?.trim() || '';
  
  // Only include intent if at least one field is filled
  if (!type && !audience && !outcome && !constraints && !currentIntent) {
    return null;
  }
  
  return {
    prompt_type: type || currentIntent?.prompt_type || 'general',
    target_audience: audience || currentIntent?.target_audience || '',
    desired_outcome: outcome || currentIntent?.desired_outcome || '',
    constraints: constraints || '',
    optimization_goals: currentIntent?.optimization_goals || []
  };
}

// Clear the form
function clearForm() {
  promptText.value = '';
  promptName.value = '';
  if (!autoTagCheckbox.checked) {
    promptTags.value = '';
  }
  // Clear intent
  if (intentType) intentType.value = '';
  if (intentAudience) intentAudience.value = '';
  if (intentOutcome) intentOutcome.value = '';
  if (intentConstraints) intentConstraints.value = '';
  if (intentQuestions) intentQuestions.innerHTML = '';
  currentIntent = null;
  // Clear chain selector
  if (parentPromptSelect) parentPromptSelect.value = '';
  if (chainIndicator) chainIndicator.style.display = 'none';
}

// Handle prompt text change - debounced auto-analyze
function handlePromptChange() {
  // Clear previous timer
  if (analyzeDebounceTimer) {
    clearTimeout(analyzeDebounceTimer);
  }
  
  // Don't auto-analyze short prompts
  const text = promptText?.value?.trim() || '';
  if (text.length < 20) {
    return;
  }
  
  // Debounce - analyze after user stops typing
  analyzeDebounceTimer = setTimeout(() => {
    // Only auto-analyze if intent fields are empty
    if (!intentType?.value && !intentAudience?.value && !intentOutcome?.value) {
      analyzeIntent();
    }
  }, ANALYZE_DEBOUNCE);
}

// Analyze prompt intent using AI
async function analyzeIntent() {
  const text = promptText?.value?.trim();
  
  if (!text || text.length < 10) {
    showMessage('Enter more text to analyze intent', 'info');
    return;
  }
  
  // Show loading state
  if (analyzeSpinner) analyzeSpinner.classList.remove('hidden');
  if (analyzeText) analyzeText.textContent = 'Analyzing...';
  if (analyzeIntentBtn) analyzeIntentBtn.disabled = true;
  
  try {
    const response = await fetch(`${SOCKET_URL}/analyze-intent`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ content: text }),
      signal: AbortSignal.timeout(INTENT_TIMEOUT)
    });
    
    if (response.ok) {
      const intent = await response.json();
      currentIntent = intent;
      
      // Populate form fields
      if (intentType && intent.prompt_type) {
        intentType.value = intent.prompt_type;
      }
      if (intentAudience && intent.target_audience) {
        intentAudience.value = intent.target_audience;
      }
      if (intentOutcome && intent.desired_outcome) {
        intentOutcome.value = intent.desired_outcome;
      }
      
      // Show clarifying questions
      if (intentQuestions && intent.clarifying_questions?.length > 0) {
        intentQuestions.innerHTML = `
          <div class="questions-label">AI suggests asking:</div>
          ${intent.clarifying_questions.map(q => `<div class="question-item">• ${escapeHtml(q)}</div>`).join('')}
        `;
      }
      
      showMessage(`Intent: ${intent.prompt_type}`, 'success');
      
    } else {
      const error = await response.json();
      showMessage(`Analysis failed: ${error.error || 'Unknown error'}`, 'error');
    }
  } catch (error) {
    if (error.name === 'TimeoutError') {
      showMessage('Analysis timed out - try again', 'error');
    } else {
      showMessage(`Analysis failed: ${error.message}`, 'error');
    }
  } finally {
    // Reset button state
    if (analyzeSpinner) analyzeSpinner.classList.add('hidden');
    if (analyzeText) analyzeText.textContent = 'Analyze';
    if (analyzeIntentBtn) analyzeIntentBtn.disabled = false;
  }
}

function showMessage(text, type = 'info') {
  messageDiv.textContent = text;
  messageDiv.className = `message ${type}`;
  
  if (type === 'success') {
    setTimeout(() => {
      messageDiv.className = 'message';
    }, 3000);
  }
}

// Recent saves tracking
function addRecentSave(saveInfo) {
  // Add to beginning of array, keep only last 3
  recentSaves.unshift(saveInfo);
  if (recentSaves.length > 3) {
    recentSaves.pop();
  }
  
  // Update display
  renderRecentSaves();
}

function renderRecentSaves() {
  const container = document.getElementById('recentSaves');
  if (!container) return;
  
  if (recentSaves.length === 0) {
    container.innerHTML = '';
    container.style.display = 'none';
    return;
  }
  
  container.style.display = 'block';
  container.innerHTML = `
    <div class="recent-header">Recent Saves</div>
    ${recentSaves.map(s => `
      <div class="recent-item">
        <div class="recent-id">${escapeHtml(s.id)}</div>
        <div class="recent-preview">${escapeHtml(s.content)}</div>
        ${s.job_id ? '<span class="recent-badge">optimizing</span>' : ''}
      </div>
    `).join('')}
  `;
}

// Tab switching
function switchTab(tabName) {
  // Update tab buttons
  document.querySelectorAll('.tab').forEach(tab => {
    tab.classList.toggle('active', tab.dataset.tab === tabName);
  });
  
  // Update tab content
  document.querySelectorAll('.tab-content').forEach(content => {
    content.classList.toggle('active', content.id === `tab-${tabName}`);
  });
  
  // Load data for the tab
  if (tabName === 'prompts') {
    loadPrompts();
    stopJobPolling();
  } else if (tabName === 'jobs') {
    loadJobs();
    startJobPolling();
  } else if (tabName === 'settings') {
    initSettings();
    stopJobPolling();
  } else {
    stopJobPolling();
  }
}

// Load prompts list
async function loadPrompts() {
  try {
    const response = await fetch(`${SOCKET_URL}/prompts?limit=50`, {
      signal: AbortSignal.timeout(DEFAULT_TIMEOUT)
    });
    
    if (response.ok) {
      const data = await response.json();
      allPrompts = data.prompts || [];
      renderPrompts(allPrompts);
    } else {
      promptsList.innerHTML = '<p class="empty">Failed to load prompts</p>';
    }
  } catch (error) {
    promptsList.innerHTML = '<p class="empty">Connection error</p>';
  }
}

function renderPrompts(prompts) {
  if (prompts.length === 0) {
    promptsList.innerHTML = '<p class="empty">No prompts found</p>';
    return;
  }
  
  promptsList.innerHTML = prompts.map(p => {
    const hasChain = p.metadata?.parent_id || p.metadata?.chain_id;
    const preview = p.content ? p.content.substring(0, 60) + (p.content.length > 60 ? '...' : '') : '';
    const hash = p.metadata?.content_hash || '';
    
    return `
      <div class="prompt-item ${hasChain ? 'has-chain' : ''}" data-id="${escapeHtml(p.id)}">
        <div class="prompt-header">
          <div class="prompt-name">${escapeHtml(p.id)}</div>
          ${hasChain ? '<span class="chain-badge">🔗 chain</span>' : ''}
        </div>
        ${preview ? `<div class="prompt-preview">${escapeHtml(preview)}</div>` : ''}
        <div class="prompt-tags">
          ${(p.tags || []).map(t => `#${t}`).join(' ') || ''}
          ${hash ? `<span style="opacity:0.5"> · ${hash}</span>` : ''}
        </div>
      </div>
    `;
  }).join('');
  
  // Click to open detail view
  promptsList.querySelectorAll('.prompt-item').forEach(item => {
    item.addEventListener('click', (e) => {
      if (!e.target.closest('.action-btn')) {
        openPromptDetail(item.dataset.id);
      }
    });
  });
  
  // Also populate parent prompt selector
  updateParentPromptSelector();
}

// Search handler with debounce for content search
function handleSearch() {
  const query = promptSearch?.value?.trim() || '';
  
  // Clear previous timer
  if (searchDebounceTimer) {
    clearTimeout(searchDebounceTimer);
  }
  
  // For empty queries, show all
  if (!query) {
    renderPrompts(allPrompts);
    return;
  }
  
  // Always do local filter first for immediate feedback
  filterPromptsLocal(query);
  
  // Then try server search for better results (if query >= 3 chars)
  if (query.length >= 3) {
    searchDebounceTimer = setTimeout(() => {
      searchPromptsServer(query);
    }, 500);
  }
}

function filterPromptsLocal(query) {
  if (!query) {
    renderPrompts(allPrompts);
    return;
  }
  const q = query.toLowerCase();
  const filtered = allPrompts.filter(p => {
    // Match by ID
    if (p.id.toLowerCase().includes(q)) return true;
    // Match by tags
    if ((p.tags || []).some(t => t.toLowerCase().includes(q))) return true;
    // Match by content (if available)
    if (p.content && p.content.toLowerCase().includes(q)) return true;
    // Match by content hash
    if (p.metadata?.content_hash && p.metadata.content_hash.toLowerCase().includes(q)) return true;
    return false;
  });
  renderPrompts(filtered);
}

async function searchPromptsServer(query) {
  try {
    const response = await fetch(`${SOCKET_URL}/search?q=${encodeURIComponent(query)}&limit=20`, {
      signal: AbortSignal.timeout(DEFAULT_TIMEOUT)
    });
    
    if (response.ok) {
      const data = await response.json();
      renderPrompts(data.results || []);
    } else {
      // Server doesn't have /search endpoint or other error - fall back to local
      filterPromptsLocal(query);
    }
  } catch (error) {
    console.error('Search error:', error);
    filterPromptsLocal(query);
  }
}

// Open prompt detail panel
async function openPromptDetail(promptId) {
  try {
    const response = await fetch(`${SOCKET_URL}/prompts/${promptId}`, {
      signal: AbortSignal.timeout(DEFAULT_TIMEOUT)
    });
    
    if (!response.ok) {
      showMessage('Failed to load prompt', 'error');
      return;
    }
    
    const prompt = await response.json();
    currentDetailPrompt = prompt;
    
    // Populate detail panel
    if (detailTitle) detailTitle.textContent = prompt.id;
    if (detailContent) detailContent.textContent = prompt.content || '(empty)';
    
    // Meta info
    if (detailMeta) {
      const meta = prompt.metadata || {};
      let metaHtml = '';
      if (meta.content_hash) metaHtml += `<span>Hash: ${meta.content_hash}</span>`;
      if (meta.created_at) metaHtml += `<span>Created: ${new Date(meta.created_at).toLocaleString()}</span>`;
      if (prompt.tags?.length) metaHtml += `<span>Tags: ${prompt.tags.join(', ')}</span>`;
      detailMeta.innerHTML = metaHtml;
    }
    
    // CLI command - full docker exec command
    if (detailCli) {
      const dockerCmd = `docker exec promptctl python3 /app/promptctl.py --repo /home/promptctl/.promptctl show ${prompt.id}`;
      detailCli.textContent = dockerCmd;
    }
    
    // Check if this prompt has an optimized version
    const optimizedId = prompt.metadata?.optimized_version;
    const viewOptimizedBtn = document.getElementById('detailViewOptimized');
    if (viewOptimizedBtn) {
      if (optimizedId) {
        viewOptimizedBtn.style.display = 'inline-block';
        viewOptimizedBtn.onclick = () => openPromptDetail(optimizedId);
      } else {
        viewOptimizedBtn.style.display = 'none';
      }
    }
    
    // Check if this is an optimized version (show source)
    const sourceId = prompt.metadata?.source_prompt;
    const viewSourceBtn = document.getElementById('detailViewSource');
    if (viewSourceBtn) {
      if (sourceId) {
        viewSourceBtn.style.display = 'inline-block';
        viewSourceBtn.onclick = () => openPromptDetail(sourceId);
      } else {
        viewSourceBtn.style.display = 'none';
      }
    }
    
    // Load chain if exists
    if (prompt.has_chain) {
      loadChainForPrompt(promptId);
      document.getElementById('detailViewChain')?.style.setProperty('display', 'inline-block');
    } else {
      if (detailChain) detailChain.style.display = 'none';
      document.getElementById('detailViewChain')?.style.setProperty('display', 'none');
    }
    
    // Show detail panel
    if (promptDetail) promptDetail.style.display = 'block';
    
  } catch (error) {
    showMessage(`Error: ${error.message}`, 'error');
  }
}

function closePromptDetail() {
  if (promptDetail) promptDetail.style.display = 'none';
  currentDetailPrompt = null;
}

async function loadChainForPrompt(promptId) {
  try {
    const response = await fetch(`${SOCKET_URL}/prompts/${promptId}/chain`, {
      signal: AbortSignal.timeout(DEFAULT_TIMEOUT)
    });
    
    if (response.ok) {
      const data = await response.json();
      renderChain(data.chain || [], promptId);
    }
  } catch (error) {
    console.error('Failed to load chain:', error);
  }
}

function renderChain(chain, currentId) {
  if (!detailChain || chain.length <= 1) {
    if (detailChain) detailChain.style.display = 'none';
    return;
  }
  
  detailChain.style.display = 'block';
  detailChain.innerHTML = `
    <div class="chain-title">🔗 Prompt Chain (${chain.length} prompts)</div>
    ${chain.map((p, i) => `
      <div class="chain-item ${p.id === currentId ? 'current' : ''}" data-id="${escapeHtml(p.id)}">
        <span class="chain-position">${i + 1}</span>
        <span>${escapeHtml(p.id)}</span>
      </div>
    `).join('')}
  `;
  
  // Click to switch to different prompt in chain
  detailChain.querySelectorAll('.chain-item').forEach(item => {
    item.addEventListener('click', () => {
      openPromptDetail(item.dataset.id);
    });
  });
}

function copyCli() {
  if (currentDetailPrompt) {
    const cmd = `docker exec promptctl python3 /app/promptctl.py --repo /home/promptctl/.promptctl show ${currentDetailPrompt.id}`;
    navigator.clipboard.writeText(cmd);
    showMessage('CLI command copied!', 'success');
  }
}

function viewCurrentChain() {
  if (currentDetailPrompt) {
    loadChainForPrompt(currentDetailPrompt.id);
  }
}

function linkNewPrompt() {
  if (currentDetailPrompt && parentPromptSelect) {
    // Switch to capture tab with this prompt as parent
    parentPromptSelect.value = currentDetailPrompt.id;
    updateChainIndicator();
    closePromptDetail();
    switchTab('capture');
  }
}

// Parent prompt selector for chaining
function updateParentPromptSelector() {
  if (!parentPromptSelect) return;
  
  const currentValue = parentPromptSelect.value;
  parentPromptSelect.innerHTML = '<option value="">-- New conversation --</option>';
  
  // Add recent prompts as options
  const recent = allPrompts.slice(0, 20);
  recent.forEach(p => {
    const opt = document.createElement('option');
    opt.value = p.id;
    opt.textContent = p.id.length > 30 ? p.id.substring(0, 30) + '...' : p.id;
    parentPromptSelect.appendChild(opt);
  });
  
  // Restore selection if still valid
  if (currentValue && recent.some(p => p.id === currentValue)) {
    parentPromptSelect.value = currentValue;
  }
}

function updateChainIndicator() {
  if (!chainIndicator || !parentPromptSelect) return;
  
  const parentId = parentPromptSelect.value;
  if (parentId) {
    chainIndicator.style.display = 'block';
    chainIndicator.innerHTML = `🔗 This prompt will be linked as a follow-up to: <strong>${escapeHtml(parentId)}</strong>`;
  } else {
    chainIndicator.style.display = 'none';
  }
}

// Load jobs list
async function loadJobs() {
  try {
    const response = await fetch(`${SOCKET_URL}/jobs?limit=20`, {
      signal: AbortSignal.timeout(DEFAULT_TIMEOUT)
    });
    
    if (response.ok) {
      const data = await response.json();
      renderJobs(data.jobs || []);
    } else {
      jobsList.innerHTML = '<p class="empty">Failed to load jobs</p>';
    }
  } catch (error) {
    jobsList.innerHTML = '<p class="empty">Connection error</p>';
  }
}

function renderJobs(jobs) {
  if (jobs.length === 0) {
    jobsList.innerHTML = '<p class="empty">No jobs</p>';
    return;
  }
  
  const statusIcons = {
    completed: '✓',
    running: '⟳',
    pending: '○',
    failed: '✗'
  };
  
  const jobTypeLabels = {
    optimize: '🔧 Optimize',
    optimize_intent: '🎯 Intent Optimize',
    evaluate: '📊 Evaluate',
    chain: '🔗 Chain',
    agent: '🤖 Agent'
  };
  
  jobsList.innerHTML = jobs.map(j => {
    // Format progress display
    let progressDisplay = j.status;
    let viewResultHtml = '';
    
    if (j.status === 'running') {
      progressDisplay = `${j.progress.toFixed(0)}%`;
    } else if (j.status === 'completed') {
      if (j.result?.score) {
        progressDisplay = `✓ ${j.result.score.toFixed(1)}`;
      } else {
        progressDisplay = '✓ Done';
      }
      // Add view result link for completed optimization jobs
      if (j.result?.optimized_id) {
        viewResultHtml = `<button class="view-result-btn" data-id="${j.result.optimized_id}">👁️ View</button>`;
      }
    } else if (j.status === 'failed') {
      progressDisplay = `✗ ${j.error ? j.error.substring(0, 20) : 'Failed'}`;
    }
    
    return `
      <div class="job-item">
        <div class="job-status ${j.status}">${statusIcons[j.status] || '?'}</div>
        <div class="job-info">
          <div class="job-type">${jobTypeLabels[j.job_type] || j.job_type}</div>
          <div class="job-id">${j.id}</div>
        </div>
        <div class="job-progress">
          ${progressDisplay}
          ${viewResultHtml}
        </div>
      </div>
    `;
  }).join('');
  
  // Add click handlers for view result buttons
  jobsList.querySelectorAll('.view-result-btn').forEach(btn => {
    btn.addEventListener('click', (e) => {
      e.stopPropagation();
      const promptId = btn.dataset.id;
      switchTab('prompts');
      setTimeout(() => openPromptDetail(promptId), 100);
    });
  });
}

// Job polling
function startJobPolling(jobId = null) {
  stopJobPolling();
  
  pollInterval = setInterval(async () => {
    if (jobId) {
      // Poll specific job
      try {
        const response = await fetch(`${SOCKET_URL}/jobs/${jobId}`);
        if (response.ok) {
          const job = await response.json();
          if (job.status === 'completed') {
            showMessage(`Optimization complete! Score: ${job.result?.score?.toFixed(1) || 'N/A'}`, 'success');
            stopJobPolling();
          } else if (job.status === 'failed') {
            showMessage(`Optimization failed: ${job.error}`, 'error');
            stopJobPolling();
          }
        }
      } catch (e) {
        console.error('Job poll error:', e);
      }
    } else {
      // Refresh jobs list if on jobs tab
      const jobsTab = document.querySelector('#tab-jobs.active');
      if (jobsTab) {
        loadJobs();
      }
    }
  }, POLL_INTERVAL);
}

function stopJobPolling() {
  if (pollInterval) {
    clearInterval(pollInterval);
    pollInterval = null;
  }
}

// Optimize a prompt - now shows modal first to get optimization goal
function optimizePrompt(promptId) {
  pendingOptimizePromptId = promptId;
  showOptimizeModal();
}

// Show optimization goal modal
function showOptimizeModal() {
  const modal = document.getElementById('optimizeModal');
  if (!modal) return;
  
  // Update modal with current settings info
  updateModalInfo();
  
  // Reset form
  const goalSelect = document.getElementById('optimizeGoal');
  const notesInput = document.getElementById('optimizeNotes');
  if (goalSelect) goalSelect.value = 'general';
  if (notesInput) notesInput.value = '';
  
  modal.style.display = 'flex';
}

function closeOptimizeModal() {
  const modal = document.getElementById('optimizeModal');
  if (modal) modal.style.display = 'none';
  pendingOptimizePromptId = null;
}

function updateModalInfo() {
  const providerBadge = document.getElementById('modalProviderBadge');
  const roundsBadge = document.getElementById('modalRoundsBadge');
  
  if (currentSettings) {
    const provider = currentSettings.provider || 'ollama';
    const providerNames = {
      ollama: '🤖 Ollama',
      openai: '🧠 OpenAI',
      anthropic: '🔮 Anthropic'
    };
    const providerModels = {
      ollama: currentSettings.model || 'phi3.5:latest',
      openai: currentSettings.openai_model || 'gpt-4o',
      anthropic: currentSettings.anthropic_model || 'claude-3-5-sonnet'
    };
    
    if (providerBadge) {
      providerBadge.textContent = `${providerNames[provider]} (${providerModels[provider]})`;
      providerBadge.className = `provider-badge ${provider}`;
    }
    
    const rounds = currentSettings.optimization_rounds || 3;
    if (roundsBadge) {
      roundsBadge.textContent = `${rounds} round${rounds > 1 ? 's' : ''}`;
    }
  }
}

async function confirmOptimization() {
  if (!pendingOptimizePromptId) {
    closeOptimizeModal();
    return;
  }
  
  const goalSelect = document.getElementById('optimizeGoal');
  const notesInput = document.getElementById('optimizeNotes');
  const confirmBtn = document.getElementById('confirmOptimize');
  
  const goal = goalSelect?.value || 'general';
  const notes = notesInput?.value?.trim() || '';
  
  // Disable button during request
  if (confirmBtn) {
    confirmBtn.disabled = true;
    confirmBtn.textContent = '⏳ Starting...';
  }
  
  try {
    // Get current settings to pass provider info
    const settings = currentSettings || DEFAULT_SETTINGS;
    
    // Build intent from optimization goal
    const goalToIntent = {
      clarity: { prompt_type: 'general', desired_outcome: 'Improve clarity and make the prompt easier to understand', optimization_goals: ['clarity', 'readability'] },
      accuracy: { prompt_type: 'general', desired_outcome: 'Improve precision and correctness of the prompt', optimization_goals: ['accuracy', 'precision'] },
      conciseness: { prompt_type: 'general', desired_outcome: 'Make the prompt shorter without losing meaning', optimization_goals: ['conciseness', 'brevity'] },
      completeness: { prompt_type: 'general', desired_outcome: 'Add missing details or context to the prompt', optimization_goals: ['completeness', 'coverage'] },
      style: { prompt_type: 'general', desired_outcome: 'Improve tone, voice, and formatting', optimization_goals: ['style', 'tone'] },
      safety: { prompt_type: 'general', desired_outcome: 'Make the prompt safer and more responsible', optimization_goals: ['safety', 'responsibility'] },
      engagement: { prompt_type: 'general', desired_outcome: 'Make the prompt more compelling and persuasive', optimization_goals: ['engagement', 'persuasion'] },
      specificity: { prompt_type: 'general', desired_outcome: 'Add more specific instructions or constraints', optimization_goals: ['specificity', 'detail'] },
      general: { prompt_type: 'general', desired_outcome: 'Overall improvement across all aspects', optimization_goals: ['clarity', 'effectiveness'] }
    };
    
    const intent = goalToIntent[goal] || goalToIntent.general;
    if (notes) {
      intent.constraints = notes;
    }
    
    // Use intent-aware optimization endpoint
    const response = await fetch(`${SOCKET_URL}/optimize-with-intent`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        prompt_id: pendingOptimizePromptId,
        intent: intent,
        rounds: settings.optimization_rounds || 3,
        async: true,
        // Pass provider settings to backend
        provider_settings: {
          provider: settings.provider,
          ollama_url: settings.ollama_url,
          model: settings.model,
          openai_key: settings.openai_key,
          openai_model: settings.openai_model,
          anthropic_key: settings.anthropic_key,
          anthropic_model: settings.anthropic_model
        }
      })
    });
    
    if (response.ok) {
      const result = await response.json();
      showMessage(`Optimization started: ${result.job_id}`, 'success');
      startJobPolling(result.job_id);
      closeOptimizeModal();
      switchTab('jobs');
    } else {
      const error = await response.text();
      showMessage(`Failed to start optimization: ${error}`, 'error');
    }
  } catch (error) {
    showMessage(`Error: ${error.message}`, 'error');
  } finally {
    if (confirmBtn) {
      confirmBtn.disabled = false;
      confirmBtn.textContent = '🚀 Start Optimization';
    }
    pendingOptimizePromptId = null;
  }
}

// Load current settings for modal display
async function loadCurrentSettings() {
  try {
    const response = await fetch(`${SOCKET_URL}/settings`, {
      signal: AbortSignal.timeout(HEALTH_TIMEOUT)
    });
    
    if (response.ok) {
      currentSettings = await response.json();
      return;
    }
  } catch (e) {
    // Ignore
  }
  
  // Fallback to local storage
  const stored = await chrome.storage.local.get(['promptctl_settings']);
  currentSettings = stored.promptctl_settings || DEFAULT_SETTINGS;
}

// Copy prompt ID
function copyPromptId(id) {
  navigator.clipboard.writeText(id);
  showMessage(`Copied: ${id}`, 'success');
}

// Escape HTML
function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

// Listen for messages from background script
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === 'fillText') {
    promptText.value = request.text;
    if (autoTagCheckbox.checked && request.url) {
      updateTagsFromDomain(request.url);
    }
  }
});

// ===== Settings Management =====

// Settings DOM elements
let settingsProvider, settingsOllamaUrl, settingsModel;
let settingsOpenaiKey, settingsOpenaiModel;
let settingsAnthropicKey, settingsAnthropicModel;
let settingsEnableDspy, settingsRounds;
let settingsStatus, saveSettingsBtn, testConnectionBtn;

// Default settings
const DEFAULT_SETTINGS = {
  provider: 'ollama',
  ollama_url: 'http://localhost:11434',
  model: 'phi3.5:latest',
  openai_key: '',
  openai_model: 'gpt-4o-mini',
  anthropic_key: '',
  anthropic_model: 'claude-3-5-sonnet-20241022',
  dspy_enabled: true,
  optimization_rounds: 3
};

// Initialize settings when tab is shown
function initSettings() {
  // Get settings DOM elements
  settingsProvider = document.getElementById('settingsProvider');
  settingsOllamaUrl = document.getElementById('settingsOllamaUrl');
  settingsModel = document.getElementById('settingsModel');
  settingsOpenaiKey = document.getElementById('settingsOpenaiKey');
  settingsOpenaiModel = document.getElementById('settingsOpenaiModel');
  settingsAnthropicKey = document.getElementById('settingsAnthropicKey');
  settingsAnthropicModel = document.getElementById('settingsAnthropicModel');
  settingsEnableDspy = document.getElementById('settingsEnableDspy');
  settingsRounds = document.getElementById('settingsRounds');
  settingsStatus = document.getElementById('settingsStatus');
  saveSettingsBtn = document.getElementById('saveSettingsBtn');
  testConnectionBtn = document.getElementById('testConnectionBtn');
  
  // Add event listeners
  settingsProvider?.addEventListener('change', handleProviderChange);
  saveSettingsBtn?.addEventListener('click', saveSettings);
  testConnectionBtn?.addEventListener('click', testProviderConnection);
  
  // Load current settings
  loadSettings();
}

async function loadSettings() {
  try {
    // First try to get from backend
    const response = await fetch(`${SOCKET_URL}/settings`, {
      signal: AbortSignal.timeout(HEALTH_TIMEOUT)
    });
    
    if (response.ok) {
      const settings = await response.json();
      applySettingsToUI(settings);
      return;
    }
  } catch (e) {
    console.log('Could not load settings from backend, using local');
  }
  
  // Fallback to local storage
  const stored = await chrome.storage.local.get(['promptctl_settings']);
  const settings = stored.promptctl_settings || DEFAULT_SETTINGS;
  applySettingsToUI(settings);
}

function applySettingsToUI(settings) {
  if (settingsProvider) settingsProvider.value = settings.provider || 'ollama';
  if (settingsOllamaUrl) settingsOllamaUrl.value = settings.ollama_url || DEFAULT_SETTINGS.ollama_url;
  if (settingsModel) settingsModel.value = settings.model || DEFAULT_SETTINGS.model;
  if (settingsOpenaiKey) settingsOpenaiKey.value = settings.openai_key || '';
  if (settingsOpenaiModel) settingsOpenaiModel.value = settings.openai_model || DEFAULT_SETTINGS.openai_model;
  if (settingsAnthropicKey) settingsAnthropicKey.value = settings.anthropic_key || '';
  if (settingsAnthropicModel) settingsAnthropicModel.value = settings.anthropic_model || DEFAULT_SETTINGS.anthropic_model;
  if (settingsEnableDspy) settingsEnableDspy.checked = settings.dspy_enabled !== false;
  if (settingsRounds) settingsRounds.value = settings.optimization_rounds || 3;
  
  // Show correct provider settings
  handleProviderChange();
}

function handleProviderChange() {
  const provider = settingsProvider?.value || 'ollama';
  
  // Hide all provider settings
  document.getElementById('ollamaSettings')?.style.setProperty('display', 'none');
  document.getElementById('openaiSettings')?.style.setProperty('display', 'none');
  document.getElementById('anthropicSettings')?.style.setProperty('display', 'none');
  
  // Show selected provider settings
  document.getElementById(`${provider}Settings`)?.style.setProperty('display', 'block');
}

async function saveSettings() {
  const settings = {
    provider: settingsProvider?.value || 'ollama',
    ollama_url: settingsOllamaUrl?.value || DEFAULT_SETTINGS.ollama_url,
    model: settingsModel?.value || DEFAULT_SETTINGS.model,
    openai_key: settingsOpenaiKey?.value || '',
    openai_model: settingsOpenaiModel?.value || DEFAULT_SETTINGS.openai_model,
    anthropic_key: settingsAnthropicKey?.value || '',
    anthropic_model: settingsAnthropicModel?.value || DEFAULT_SETTINGS.anthropic_model,
    dspy_enabled: settingsEnableDspy?.checked !== false,
    optimization_rounds: parseInt(settingsRounds?.value) || 3
  };
  
  // Update currentSettings so modal shows correct info
  currentSettings = settings;
  
  // Save to local storage first
  await chrome.storage.local.set({ promptctl_settings: settings });
  
  // Try to save to backend
  try {
    const response = await fetch(`${SOCKET_URL}/settings`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(settings),
      signal: AbortSignal.timeout(DEFAULT_TIMEOUT)
    });
    
    if (response.ok) {
      showSettingsStatus('Settings saved successfully!', 'success');
    } else {
      showSettingsStatus('Saved locally (backend unavailable)', 'info');
    }
  } catch (e) {
    showSettingsStatus('Saved locally (backend unavailable)', 'info');
  }
}

async function testProviderConnection() {
  const provider = settingsProvider?.value || 'ollama';
  testConnectionBtn.disabled = true;
  testConnectionBtn.textContent = '🔄 Testing...';
  
  try {
    if (provider === 'ollama') {
      const ollamaUrl = settingsOllamaUrl?.value || DEFAULT_SETTINGS.ollama_url;
      
      // Try /api/tags first (official endpoint)
      let modelCount = 0;
      let modelNames = [];
      
      try {
        const response = await fetch(`${ollamaUrl}/api/tags`, {
          signal: AbortSignal.timeout(5000)
        });
        
        if (response.ok) {
          const data = await response.json();
          // Handle both array format and object format
          if (Array.isArray(data.models)) {
            modelCount = data.models.length;
            modelNames = data.models.map(m => m.name || m.model || m).slice(0, 3);
          } else if (data.models && typeof data.models === 'object') {
            modelCount = Object.keys(data.models).length;
          }
        }
      } catch (e) {
        // Try alternative endpoint
        console.log('Trying alternative Ollama endpoint...');
      }
      
      // If no models found, try a simple generate test
      if (modelCount === 0) {
        try {
          // Just test if Ollama responds at all
          const testResponse = await fetch(`${ollamaUrl}/api/version`, {
            signal: AbortSignal.timeout(3000)
          });
          if (testResponse.ok) {
            showSettingsStatus(`✅ Ollama connected! Use 'ollama list' to verify models.`, 'success');
            return;
          }
        } catch (e) {
          // Fall through to connected message
        }
      }
      
      if (modelCount > 0) {
        const modelList = modelNames.length > 0 ? ` (${modelNames.join(', ')}...)` : '';
        showSettingsStatus(`✅ Ollama connected! ${modelCount} models available${modelList}`, 'success');
      } else {
        // Connection works but API returns empty - this is normal for some Ollama setups
        showSettingsStatus(`✅ Ollama connected! Verify models with 'ollama list' in terminal.`, 'success');
      }
    } else if (provider === 'openai') {
      const apiKey = settingsOpenaiKey?.value;
      if (!apiKey) {
        showSettingsStatus('❌ API key required', 'error');
        return;
      }
      // For security, we'll test via the backend
      showSettingsStatus('Save settings and backend will verify API key', 'info');
    } else if (provider === 'anthropic') {
      const apiKey = settingsAnthropicKey?.value;
      if (!apiKey) {
        showSettingsStatus('❌ API key required', 'error');
        return;
      }
      showSettingsStatus('Save settings and backend will verify API key', 'info');
    }
  } catch (error) {
    showSettingsStatus(`❌ Connection failed: ${error.message}`, 'error');
  } finally {
    testConnectionBtn.disabled = false;
    testConnectionBtn.textContent = '🔌 Test Connection';
  }
}

function showSettingsStatus(message, type) {
  if (settingsStatus) {
    settingsStatus.textContent = message;
    settingsStatus.className = `settings-status ${type}`;
    
    if (type === 'success') {
      setTimeout(() => {
        settingsStatus.className = 'settings-status';
      }, 3000);
    }
  }
}

