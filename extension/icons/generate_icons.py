#!/usr/bin/env python3
"""
Generate PNG icons from SVG source for Chrome and Firefox extensions.

Required sizes:
- Chrome: 16, 48, 128
- Firefox: 48, 96 (plus 16, 32 optional)
- Combined set: 16, 32, 48, 96, 128

Usage:
    pip install cairosvg pillow
    python generate_icons.py
"""

import subprocess
import sys
from pathlib import Path

SIZES = [16, 32, 48, 96, 128]
SCRIPT_DIR = Path(__file__).parent
SVG_PATH = SCRIPT_DIR / "icon.svg"


def generate_with_cairosvg():
    """Generate PNGs using cairosvg library."""
    try:
        import cairosvg
    except ImportError:
        return False
    
    for size in SIZES:
        output = SCRIPT_DIR / f"{size}x{size}.png"
        cairosvg.svg2png(
            url=str(SVG_PATH),
            write_to=str(output),
            output_width=size,
            output_height=size
        )
        print(f"Generated: {output.name}")
    return True


def generate_with_inkscape():
    """Generate PNGs using Inkscape CLI (fallback)."""
    try:
        for size in SIZES:
            output = SCRIPT_DIR / f"{size}x{size}.png"
            subprocess.run([
                "inkscape",
                str(SVG_PATH),
                "--export-type=png",
                f"--export-filename={output}",
                f"--export-width={size}",
                f"--export-height={size}"
            ], check=True, capture_output=True)
            print(f"Generated: {output.name}")
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def generate_with_rsvg():
    """Generate PNGs using rsvg-convert (fallback)."""
    try:
        for size in SIZES:
            output = SCRIPT_DIR / f"{size}x{size}.png"
            subprocess.run([
                "rsvg-convert",
                "-w", str(size),
                "-h", str(size),
                str(SVG_PATH),
                "-o", str(output)
            ], check=True, capture_output=True)
            print(f"Generated: {output.name}")
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def main():
    if not SVG_PATH.exists():
        print(f"Error: {SVG_PATH} not found", file=sys.stderr)
        sys.exit(1)

    print(f"Generating icons from: {SVG_PATH}")
    print(f"Sizes: {SIZES}")
    print()

    # Try methods in order of preference
    if generate_with_cairosvg():
        print("\nDone (using cairosvg)")
    elif generate_with_rsvg():
        print("\nDone (using rsvg-convert)")
    elif generate_with_inkscape():
        print("\nDone (using Inkscape)")
    else:
        print("\nError: No SVG converter available.", file=sys.stderr)
        print("Install one of: cairosvg, librsvg, or Inkscape", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
