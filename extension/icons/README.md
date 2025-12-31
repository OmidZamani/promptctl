# Extension Icons

The extension requires three icon sizes:
- `16x16.png` - Toolbar icon (small)
- `48x48.png` - Extension management
- `128x128.png` - Chrome Web Store

## Creating Icons

You can create simple placeholder icons or design custom ones:

### Quick Placeholder Creation (macOS/Linux):

```bash
# Install ImageMagick if needed
brew install imagemagick  # macOS
# sudo apt install imagemagick  # Linux

# Create simple text-based icons
convert -size 16x16 xc:purple -pointsize 10 -fill white -gravity center \
  -annotate +0+0 "P" 16x16.png

convert -size 48x48 xc:purple -pointsize 30 -fill white -gravity center \
  -annotate +0+0 "P" 48x48.png

convert -size 128x128 xc:purple -pointsize 80 -fill white -gravity center \
  -annotate +0+0 "P" 128x128.png
```

### Or Use Online Tools:
- https://www.favicon-generator.org/
- https://realfavicongenerator.net/

### Design Guidelines:
- Use simple, recognizable symbols (e.g., 📝, 💾, or "P")
- High contrast for visibility
- Brand colors: Purple gradient (#667eea → #764ba2)
- Clear at small sizes

The extension will work with these placeholder icons until you replace them with professional designs.
