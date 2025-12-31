# Browser Extension Guide

Quick capture prompts from your browser directly to promptctl.

## Features

✅ Right-click context menu  
✅ Keyboard shortcut (Ctrl+Shift+S)  
✅ Quick popup interface  
✅ Auto-tagging by domain  
✅ Real-time sync with CLI  
✅ Works with Chrome, Firefox, Edge  

## Installation

### Step 1: Install Extension

#### Chrome/Edge

1. Open `chrome://extensions/` (Chrome) or `edge://extensions/` (Edge)
2. Enable "Developer mode" (toggle in top-right)
3. Click "Load unpacked"
4. Select `/Users/omid/dev/promptctl/extension/` folder
5. Extension icon appears in toolbar

#### Firefox

1. Open `about:debugging#/runtime/this-firefox`
2. Click "Load Temporary Add-on"
3. Select `extension/manifest.json`
4. Extension loads (temporary until Firefox restart)

**Note**: For permanent Firefox installation, extension needs to be signed by Mozilla.

### Step 2: Create Icons (Optional)

The extension needs 3 icon sizes. Quick placeholder creation:

```bash
cd ~/dev/promptctl/extension/icons/

# Using ImageMagick (install if needed: brew install imagemagick)
convert -size 16x16 xc:purple -pointsize 10 -fill white -gravity center \
  -annotate +0+0 "P" 16x16.png

convert -size 48x48 xc:purple -pointsize 30 -fill white -gravity center \
  -annotate +0+0 "P" 48x48.png

convert -size 128x128 xc:purple -pointsize 80 -fill white -gravity center \
  -annotate +0+0 "P" 128x128.png
```

Or use online tools:
- https://www.favicon-generator.org/
- https://realfavicongenerator.net/

### Step 3: Start Daemon with Socket

The extension needs the daemon running with socket enabled:

```bash
promptctl daemon --socket
```

Default port: 9090

Custom port:
```bash
promptctl daemon --socket --socket-port 8080
```

## Usage

### Method 1: Context Menu

1. Select text on any webpage
2. Right-click
3. Choose "Save to PromptCtl"
4. Prompt saved automatically

### Method 2: Keyboard Shortcut

1. Select text
2. Press `Ctrl+Shift+S` (Windows/Linux) or `Cmd+Shift+S` (Mac)
3. Prompt saved with visual confirmation

### Method 3: Popup Interface

1. Click extension icon in toolbar
2. Paste or type prompt text
3. (Optional) Add name and tags
4. Click "Save Prompt"

## Features Detail

### Auto-Tagging

Extension automatically tags prompts by domain:

- `github.com` → tag: `github`
- `stackoverflow.com` → tag: `stackoverflow`
- `docs.python.org` → tag: `python`

Enable/disable in popup UI with checkbox.

### Status Indicator

Popup shows connection status:
- 🟢 Green: Connected to daemon
- 🔴 Red: Daemon not running
- 🟡 Yellow: Checking connection

### Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Ctrl+Shift+S` | Quick save selected text |
| `Ctrl+Enter` | Save from popup (when popup is open) |

## Configuration

### Custom Port

If you changed the socket port:

1. Edit `extension/popup.js`
2. Change line: `const SOCKET_URL = 'http://localhost:9090';`
3. Reload extension

### Custom Tags

Tags are automatically added. To customize:

1. Open popup
2. Uncheck "Auto-tag from domain"
3. Enter custom tags (comma-separated)
4. Save

## Troubleshooting

### "Daemon not running" error

**Solution:**
```bash
# Start daemon with socket enabled
promptctl daemon --socket
```

### Extension not appearing

**Chrome/Edge:**
1. Go to `chrome://extensions/`
2. Check if extension is enabled
3. Click "Reload" button

**Firefox:**
1. Temporary add-ons are removed on restart
2. Reload from `about:debugging`

### Selected text not captured

1. Make sure content script has loaded (refresh page)
2. Check browser console for errors (F12)
3. Try using popup method instead

### Save button disabled

- Daemon must be running with `--socket`
- Check connection status in popup
- Verify port 9090 is not blocked

### CORS errors

Extension uses `http://localhost:9090`. If using different host:

1. Edit `extension/popup.js` and `extension/background.js`
2. Update `SOCKET_URL`
3. Reload extension

## Examples

### Example 1: Capture Code Snippet

1. Browse to Stack Overflow
2. Find useful code snippet
3. Select code
4. Right-click → "Save to PromptCtl"
5. Auto-tagged with `stackoverflow`

### Example 2: Save ChatGPT Prompt

1. On ChatGPT interface
2. Select your prompt text
3. Press `Ctrl+Shift+S`
4. Saved with tag `openai`

### Example 3: Manual Entry

1. Click extension icon
2. Type or paste prompt
3. Add name: `my-template`
4. Add tags: `template, work`
5. Click "Save Prompt"
6. Confirmation appears

## Architecture

### Components

```
Browser Extension
├── manifest.json       (Config)
├── popup.html         (UI)
├── popup.css          (Styling)
├── popup.js           (UI logic)
├── background.js      (Context menus, shortcuts)
├── content.js         (Page interaction)
└── icons/             (3 sizes)

promptctl Daemon
└── Socket Server (port 9090)
    ├── GET /health    (Health check)
    └── POST /save     (Save prompt)
```

### Data Flow

```
1. User selects text on webpage
2. content.js captures selection
3. background.js sends to socket
4. Daemon receives via HTTP
5. Prompt saved to ~/.promptctl
6. Git commit created
7. Confirmation sent back to extension
```

## Development

### Testing Locally

```bash
# Start daemon with debug logging
promptctl daemon --socket

# Open browser console (F12)
# Check for extension logs

# Test save endpoint
curl -X POST http://localhost:9090/save \
  -H "Content-Type: application/json" \
  -d '{"content":"Test prompt","name":"test","tags":["test"]}'
```

### Modifying Extension

1. Edit files in `extension/` directory
2. Save changes
3. Go to `chrome://extensions/`
4. Click "Reload" on PromptCtl extension
5. Test changes

### Adding Features

**Example: Add new button to popup**

Edit `popup.html`:
```html
<button id="myButton">My Feature</button>
```

Edit `popup.js`:
```javascript
document.getElementById('myButton').addEventListener('click', () => {
  // Your code here
});
```

## Security & Privacy

- **All data stays local**: No external servers
- **HTTP localhost only**: Extension talks to localhost:9090
- **No tracking**: No analytics or telemetry
- **No permissions abuse**: Only uses necessary permissions
- **Open source**: All code is visible and auditable

## Integration with CLI

Extension works seamlessly with CLI:

```bash
# Start daemon with socket
promptctl daemon --socket

# In browser: Save prompts via extension

# In terminal: See them immediately
promptctl list

# Show recent capture
promptctl show <prompt-id>
```

## Uninstallation

### Chrome/Edge
1. Go to `chrome://extensions/`
2. Find "PromptCtl Quick Capture"
3. Click "Remove"

### Firefox
1. Go to `about:addons`
2. Find extension
3. Click "Remove"

## Next Steps

- Set up daemon to run on startup
- Create keyboard shortcut aliases
- Build custom capture workflows
- Integrate with agent mode for testing

See also:
- [README.md](README.md) - Main documentation
- [AGENT_GUIDE.md](AGENT_GUIDE.md) - Agent mode
- [DSPY_GUIDE.md](DSPY_GUIDE.md) - DSPy optimization
