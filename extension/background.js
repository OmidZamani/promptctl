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
      // Query for active tab - try multiple strategies
      let tabs = await chrome.tabs.query({ active: true, currentWindow: true });
      
      // If no current window, try last focused window
      if (!tabs || tabs.length === 0) {
        tabs = await chrome.tabs.query({ active: true, lastFocusedWindow: true });
      }
      
      // Still no tabs? Try any active tab
      if (!tabs || tabs.length === 0) {
        tabs = await chrome.tabs.query({ active: true });
      }
      
      if (!tabs || tabs.length === 0) {
        console.log('No active tab found - cannot save selection');
        showNotification('PromptCtl', 'No active tab found. Open a webpage first.');
        return;
      }
      
      const tab = tabs[0];
      
      // Make sure tab has a valid ID and URL
      if (!tab.id || tab.id === chrome.tabs.TAB_ID_NONE) {
        console.log('Invalid tab ID');
        showNotification('PromptCtl', 'Cannot access this tab.');
        return;
      }
      
      // Skip chrome:// and extension pages
      if (tab.url && (tab.url.startsWith('chrome://') || tab.url.startsWith('chrome-extension://'))) {
        showNotification('PromptCtl', 'Cannot capture from browser internal pages.');
        return;
      }
      
      // Send message to content script to get selection
      chrome.tabs.sendMessage(tab.id, { action: 'getSelection' }, async (response) => {
        // Check for errors
        if (chrome.runtime.lastError) {
          console.log('Content script not ready:', chrome.runtime.lastError.message);
          // Try to open popup as fallback - but handle the error gracefully
          try {
            await chrome.action.openPopup();
          } catch (popupError) {
            console.log('Could not open popup:', popupError.message);
            showNotification('PromptCtl', 'Click the extension icon to open.');
          }
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
          // No selection, try to open popup
          try {
            await chrome.action.openPopup();
          } catch (popupError) {
            console.log('Could not open popup:', popupError.message);
            showNotification('PromptCtl', 'No text selected. Click extension icon to open.');
          }
        }
      });
    } catch (error) {
      console.error('Keyboard shortcut error:', error);
      showNotification('PromptCtl', 'Shortcut failed. Try clicking the extension icon.');
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
