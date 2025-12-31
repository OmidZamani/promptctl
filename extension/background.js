/**
 * PromptCtl Browser Extension - Background Script
 * 
 * Handles context menus, keyboard shortcuts, and message passing
 */

const SOCKET_URL = 'http://localhost:9090';

// Create context menu on install
chrome.runtime.onInstalled.addListener(() => {
  chrome.contextMenus.create({
    id: 'save-to-promptctl',
    title: 'Save to PromptCtl',
    contexts: ['selection']
  });
  
  console.log('PromptCtl extension installed');
});

// Helper to show notifications safely
function showNotification(title, message) {
  try {
    chrome.notifications.create({
      type: 'basic',
      iconUrl: chrome.runtime.getURL('icons/48x48.png'),
      title: title,
      message: message
    }, (notificationId) => {
      if (chrome.runtime.lastError) {
        console.log('Notification error:', chrome.runtime.lastError.message);
      }
    });
  } catch (e) {
    console.log('Notification failed:', e);
  }
}

// Handle context menu clicks
chrome.contextMenus.onClicked.addListener(async (info, tab) => {
  if (info.menuItemId === 'save-to-promptctl') {
    const selectedText = info.selectionText;
    
    if (selectedText) {
      // Try to save directly
      try {
        await savePromptDirect(selectedText, tab.url);
        showNotification('PromptCtl', 'Prompt saved successfully!');
      } catch (error) {
        console.error('Save failed:', error);
        showNotification('PromptCtl Error', 'Could not save prompt. Is daemon running?');
      }
    }
  }
});

// Handle keyboard shortcuts
chrome.commands.onCommand.addListener(async (command) => {
  if (command === 'save-prompt') {
    try {
      // Query for active tab
      const tabs = await chrome.tabs.query({ active: true, currentWindow: true });
      if (!tabs || tabs.length === 0) {
        console.error('No active tab found');
        return;
      }
      
      const tab = tabs[0];
      
      // Send message to content script to get selection
      chrome.tabs.sendMessage(tab.id, { action: 'getSelection' }, async (response) => {
        // Check for errors
        if (chrome.runtime.lastError) {
          console.log('Content script not ready:', chrome.runtime.lastError.message);
          // Just open popup instead
          chrome.action.openPopup();
          return;
        }
        
        if (response && response.text) {
          try {
            await savePromptDirect(response.text, tab.url);
            showNotification('PromptCtl', 'Prompt saved successfully!');
          } catch (error) {
            console.error('Save failed:', error);
            showNotification('PromptCtl Error', 'Could not save. Is daemon running?');
          }
        } else {
          // No selection, just open popup
          chrome.action.openPopup();
        }
      });
    } catch (error) {
      console.error('Keyboard shortcut error:', error);
    }
  }
});

// Direct save function
async function savePromptDirect(text, url) {
  // Extract domain for auto-tagging
  const domain = new URL(url).hostname.replace('www.', '');
  const domainTag = domain.split('.')[0];
  
  const payload = {
    action: 'save',
    content: text,
    name: null,
    tags: [domainTag, 'browser-capture']
  };
  
  const response = await fetch(`${SOCKET_URL}/save`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify(payload),
    signal: AbortSignal.timeout(5000)
  });
  
  if (!response.ok) {
    throw new Error(`Save failed: ${response.status}`);
  }
  
  return await response.json();
}

// Listen for messages from popup
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === 'checkConnection') {
    checkConnection().then(sendResponse);
    return true; // Keep channel open for async response
  }
});

async function checkConnection() {
  try {
    const response = await fetch(`${SOCKET_URL}/health`, {
      method: 'GET',
      signal: AbortSignal.timeout(2000)
    });
    return { connected: response.ok };
  } catch (error) {
    return { connected: false };
  }
}
