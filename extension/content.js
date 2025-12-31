/**
 * PromptCtl Browser Extension - Content Script
 * 
 * Runs on all web pages to extract selected text and DOM elements
 */

// Listen for messages from popup or background script
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === 'getSelection') {
    const selection = window.getSelection();
    const text = selection.toString().trim();
    
    sendResponse({
      text: text,
      url: window.location.href
    });
  }
  
  return true; // Keep channel open for async response
});

// Optional: Add visual feedback when text is saved
function showSaveConfirmation() {
  const notification = document.createElement('div');
  notification.style.cssText = `
    position: fixed;
    top: 20px;
    right: 20px;
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    color: white;
    padding: 16px 24px;
    border-radius: 8px;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
    z-index: 999999;
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    font-size: 14px;
    font-weight: 500;
    animation: slideIn 0.3s ease-out;
  `;
  notification.textContent = '✓ Saved to PromptCtl';
  
  document.body.appendChild(notification);
  
  setTimeout(() => {
    notification.style.animation = 'slideOut 0.3s ease-out';
    setTimeout(() => notification.remove(), 300);
  }, 2000);
}

// Add CSS animations
const style = document.createElement('style');
style.textContent = `
  @keyframes slideIn {
    from {
      transform: translateX(400px);
      opacity: 0;
    }
    to {
      transform: translateX(0);
      opacity: 1;
    }
  }
  
  @keyframes slideOut {
    from {
      transform: translateX(0);
      opacity: 1;
    }
    to {
      transform: translateX(400px);
      opacity: 0;
    }
  }
`;
document.head.appendChild(style);

// Listen for keyboard shortcut trigger
document.addEventListener('keydown', (e) => {
  if ((e.ctrlKey || e.metaKey) && e.shiftKey && e.key === 'S') {
    e.preventDefault();
    
    const selection = window.getSelection();
    const text = selection.toString().trim();
    
    if (text) {
      // Send to background script for saving
      chrome.runtime.sendMessage({
        action: 'saveSelection',
        text: text,
        url: window.location.href
      });
      
      showSaveConfirmation();
    }
  }
});

// Helper function to extract text from specific DOM elements
function extractElementText(selector) {
  const element = document.querySelector(selector);
  return element ? element.textContent.trim() : '';
}

// Helper function to extract code blocks
function extractCodeBlocks() {
  const codeBlocks = document.querySelectorAll('pre code, pre, code');
  return Array.from(codeBlocks).map(block => block.textContent.trim());
}

// Listen for advanced extraction requests
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === 'extractElement') {
    const text = extractElementText(request.selector);
    sendResponse({ text: text });
  } else if (request.action === 'extractCodeBlocks') {
    const blocks = extractCodeBlocks();
    sendResponse({ blocks: blocks });
  }
  
  return true;
});
