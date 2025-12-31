/**
 * PromptCtl Browser Extension - Popup Script
 * 
 * Handles UI interactions and sends prompts to local CLI via socket
 */

const SOCKET_URL = 'http://localhost:9090';
const DEFAULT_TIMEOUT = 5000;

// DOM Elements
let promptText, promptName, promptTags, autoTagCheckbox, saveBtn, messageDiv;
let statusDot, statusText;

// Initialize
document.addEventListener('DOMContentLoaded', init);

function init() {
  // Get DOM elements
  promptText = document.getElementById('promptText');
  promptName = document.getElementById('promptName');
  promptTags = document.getElementById('promptTags');
  autoTagCheckbox = document.getElementById('autoTag');
  saveBtn = document.getElementById('saveBtn');
  messageDiv = document.getElementById('message');
  statusDot = document.getElementById('statusDot');
  statusText = document.getElementById('statusText');
  
  // Load saved preferences
  loadPreferences();
  
  // Check connection
  checkConnection();
  
  // Load selected text from page
  loadSelectedText();
  
  // Event listeners
  saveBtn.addEventListener('click', handleSave);
  autoTagCheckbox.addEventListener('change', handleAutoTagToggle);
  
  // Keyboard shortcuts
  document.addEventListener('keydown', (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
      handleSave();
    }
  });
}

async function loadPreferences() {
  const prefs = await chrome.storage.sync.get(['autoTag']);
  if (prefs.autoTag !== undefined) {
    autoTagCheckbox.checked = prefs.autoTag;
  }
}

async function savePreferences() {
  await chrome.storage.sync.set({
    autoTag: autoTagCheckbox.checked
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
      setStatus('connected', 'Connected to promptctl');
      saveBtn.disabled = false;
    } else {
      setStatus('disconnected', 'Daemon not responding');
      saveBtn.disabled = true;
    }
  } catch (error) {
    setStatus('disconnected', 'Daemon not running');
    saveBtn.disabled = true;
    showMessage('Start daemon: promptctl daemon --socket', 'info');
  }
}

function setStatus(state, text) {
  statusDot.className = `status-dot ${state}`;
  statusText.textContent = text;
}

async function handleSave() {
  const text = promptText.value.trim();
  
  if (!text) {
    showMessage('Please enter prompt text', 'error');
    return;
  }
  
  saveBtn.disabled = true;
  saveBtn.textContent = '💾 Saving...';
  
  try {
    const tags = promptTags.value
      .split(',')
      .map(t => t.trim())
      .filter(Boolean);
    
    const payload = {
      action: 'save',
      content: text,
      name: promptName.value.trim() || null,
      tags: tags.length > 0 ? tags : null
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
      showMessage(`Saved: ${result.prompt_id}`, 'success');
      
      // Clear form
      setTimeout(() => {
        promptText.value = '';
        promptName.value = '';
        if (!autoTagCheckbox.checked) {
          promptTags.value = '';
        }
      }, 1000);
    } else {
      const error = await response.text();
      showMessage(`Error: ${error}`, 'error');
    }
  } catch (error) {
    showMessage(`Failed to save: ${error.message}`, 'error');
  } finally {
    saveBtn.disabled = false;
    saveBtn.textContent = '💾 Save Prompt';
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

// Listen for messages from background script
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === 'fillText') {
    promptText.value = request.text;
    if (autoTagCheckbox.checked && request.url) {
      updateTagsFromDomain(request.url);
    }
  }
});
