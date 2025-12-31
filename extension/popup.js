/**
 * PromptCtl Browser Extension - Popup Script
 * 
 * Handles UI interactions and sends prompts to local CLI via socket
 * Now with DSPy integration for optimization, evaluation, and job tracking
 */

const SOCKET_URL = 'http://localhost:9090';
const DEFAULT_TIMEOUT = 5000;
const POLL_INTERVAL = 3000;

// DOM Elements
let promptText, promptName, promptTags, autoTagCheckbox, autoOptimizeCheckbox;
let saveBtn, saveOptimizeBtn, messageDiv, statusDot, statusText;
let promptsList, jobsList, promptSearch;

// State
let allPrompts = [];
let pollInterval = null;

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
  
  // Load saved preferences
  loadPreferences();
  
  // Check connection
  checkConnection();
  
  // Load selected text from page
  loadSelectedText();
  
  // Event listeners
  saveBtn.addEventListener('click', () => handleSave(false));
  saveOptimizeBtn.addEventListener('click', () => handleSave(true));
  autoTagCheckbox.addEventListener('change', handleAutoTagToggle);
  autoOptimizeCheckbox.addEventListener('change', savePreferences);
  
  // Tab navigation
  document.querySelectorAll('.tab').forEach(tab => {
    tab.addEventListener('click', () => switchTab(tab.dataset.tab));
  });
  
  // Refresh buttons
  document.getElementById('refreshPrompts')?.addEventListener('click', loadPrompts);
  document.getElementById('refreshJobs')?.addEventListener('click', loadJobs);
  
  // Search
  promptSearch?.addEventListener('input', filterPrompts);
  
  // Keyboard shortcuts
  document.addEventListener('keydown', (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
      handleSave(autoOptimizeCheckbox?.checked || false);
    }
  });
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

async function checkConnection() {
  try {
    const response = await fetch(`${SOCKET_URL}/health`, {
      method: 'GET',
      signal: AbortSignal.timeout(DEFAULT_TIMEOUT)
    });
    
    if (response.ok) {
      const data = await response.json();
      const pipelineStatus = data.pipeline ? ' + Pipeline' : '';
      const jobsInfo = data.jobs_running > 0 ? ` (${data.jobs_running} running)` : '';
      setStatus('connected', `Connected${pipelineStatus}${jobsInfo}`);
      saveBtn.disabled = false;
      if (saveOptimizeBtn) saveOptimizeBtn.disabled = false;
    } else {
      setStatus('disconnected', 'Daemon not responding');
      saveBtn.disabled = true;
      if (saveOptimizeBtn) saveOptimizeBtn.disabled = true;
    }
  } catch (error) {
    setStatus('disconnected', 'Daemon not running');
    saveBtn.disabled = true;
    if (saveOptimizeBtn) saveOptimizeBtn.disabled = true;
    showMessage('Start daemon: promptctl daemon --socket', 'info');
  }
}

function setStatus(state, text) {
  statusDot.className = `status-dot ${state}`;
  statusText.textContent = text;
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
    
    const payload = {
      content: text,
      name: promptName.value.trim() || null,
      tags: tags.length > 0 ? tags : [],
      auto_optimize: withOptimize || autoOptimizeCheckbox?.checked || false
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
        message += ` (optimizing: ${result.job_id})`;
        // Start polling for job status
        startJobPolling(result.job_id);
      }
      
      showMessage(message, 'success');
      
      // Clear form
      setTimeout(() => {
        promptText.value = '';
        promptName.value = '';
        if (!autoTagCheckbox.checked) {
          promptTags.value = '';
        }
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

function showMessage(text, type = 'info') {
  messageDiv.textContent = text;
  messageDiv.className = `message ${type}`;
  
  if (type === 'success') {
    setTimeout(() => {
      messageDiv.className = 'message';
    }, 3000);
  }
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
  } else if (tabName === 'jobs') {
    loadJobs();
    startJobPolling();
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
  
  promptsList.innerHTML = prompts.map(p => `
    <div class="prompt-item" data-id="${escapeHtml(p.id)}">
      <div class="prompt-name">${escapeHtml(p.id)}</div>
      <div class="prompt-tags">${(p.tags || []).map(t => `#${t}`).join(' ') || 'No tags'}</div>
      <div class="prompt-actions">
        <button class="action-btn copy-btn" data-id="${escapeHtml(p.id)}">Copy ID</button>
        <button class="action-btn optimize-btn" data-id="${escapeHtml(p.id)}">Optimize</button>
      </div>
    </div>
  `).join('');
  
  // Attach event listeners via delegation
  promptsList.querySelectorAll('.copy-btn').forEach(btn => {
    btn.addEventListener('click', () => copyPromptId(btn.dataset.id));
  });
  promptsList.querySelectorAll('.optimize-btn').forEach(btn => {
    btn.addEventListener('click', () => optimizePrompt(btn.dataset.id));
  });
}

function filterPrompts() {
  const query = promptSearch.value.toLowerCase();
  const filtered = allPrompts.filter(p => 
    p.id.toLowerCase().includes(query) ||
    (p.tags || []).some(t => t.toLowerCase().includes(query))
  );
  renderPrompts(filtered);
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
  
  jobsList.innerHTML = jobs.map(j => `
    <div class="job-item">
      <div class="job-status ${j.status}">${statusIcons[j.status] || '?'}</div>
      <div class="job-info">
        <div class="job-type">${j.job_type}</div>
        <div class="job-id">${j.id}</div>
      </div>
      <div class="job-progress">
        ${j.status === 'running' ? `${j.progress.toFixed(0)}%` : j.status}
      </div>
    </div>
  `).join('');
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

// Optimize a prompt
async function optimizePrompt(promptId) {
  try {
    showMessage(`Starting optimization for ${promptId}...`, 'info');
    
    const response = await fetch(`${SOCKET_URL}/optimize`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        prompt_id: promptId,
        rounds: 3,
        async: true
      })
    });
    
    if (response.ok) {
      const result = await response.json();
      showMessage(`Optimization queued: ${result.job_id}`, 'success');
      startJobPolling(result.job_id);
      switchTab('jobs');
    } else {
      showMessage('Failed to start optimization', 'error');
    }
  } catch (error) {
    showMessage(`Error: ${error.message}`, 'error');
  }
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

