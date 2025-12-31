# Package promptctl as Cross-Platform Binary
## Problem Statement
Currently, promptctl requires Python and manual dependency installation. Users need to run `python promptctl.py` and manage virtual environments. We want to package it as a standalone binary that runs on macOS, Linux, and Windows with minimal setup.
## Current State
* Python 3.13.11-based CLI tool
* Dependencies: GitPython (3.1.45), requests (2.32.5), dspy-ai (3.0.4, optional)
* External dependency: git CLI (required by GitPython)
* Entry point: promptctl.py with main() function
* setup.py exists but only defines console_scripts entry point
* No binary packaging infrastructure
## Proposed Solution
Use **PyInstaller** to create standalone executables for each platform, with optional Docker support. PyInstaller bundles Python interpreter + dependencies into a single executable.
### Why PyInstaller?
* Native executables (not containers)
* Cross-platform support (macOS, Linux, Windows)
* Single-file mode available
* Handles Python dependencies automatically
* Battle-tested with large projects
### Alternatives Considered
**cx_Freeze**: Similar to PyInstaller but less mature Windows support
**py2exe**: Windows-only, outdated
**Nuitka**: Compiles to C, but complex setup and longer build times
**Docker only**: Requires Docker runtime, not truly "standalone"
## Implementation Plan
### 1. Add PyInstaller Configuration
Create `promptctl.spec` file to configure build:
* Single-file executable mode
* Include all core/ modules and data files
* Set appropriate permissions
* Configure console entry point
### 2. Update setup.py
Add metadata for proper packaging:
* Author, license, description
* Python version requirements (>=3.8)
* Optional dependencies (dspy-ai, ollama)
### 3. Create Build Scripts
**build.sh** (macOS/Linux):
* Install PyInstaller
* Build executable
* Test binary
* Create distribution archive (.tar.gz)
**build.bat** (Windows):
* Install PyInstaller  
* Build .exe
* Test binary
* Create distribution archive (.zip)
### 4. Add Cross-Platform Build Automation
Create GitHub Actions workflow or Makefile targets:
* Build on macOS (produces macOS binary)
* Build on Linux (produces Linux binary)
* Build on Windows (produces Windows .exe)
* Upload artifacts
### 5. Handle External Dependencies
**git CLI dependency**: 
* Cannot be bundled (binary dependency)
* Update README with clear installation instructions per platform
* Add runtime check in promptctl.py to verify git availability with helpful error message
**Ollama (optional)**: 
* Already optional
* Document as separate installation step
### 6. Create Distribution Package Structure
```warp-runnable-command
promptctl-v1.0.0-macos/
├── promptctl          # Executable
├── README.md          # Quick start
└── LICENSE
promptctl-v1.0.0-linux/
├── promptctl
├── README.md
└── LICENSE
promptctl-v1.0.0-windows/
├── promptctl.exe
├── README.txt
└── LICENSE
```
### 7. Docker Support (Optional Enhancement)
Create multi-stage Dockerfile:
* Stage 1: Build environment with PyInstaller
* Stage 2: Minimal runtime with git + promptctl binary
* Support for volume mounting (~/.promptctl persistence)
Benefit: True zero-install experience (only Docker needed)
### 8. Documentation Updates
Update README.md with:
* Binary installation instructions
* Platform-specific notes
* Building from source instructions
* Comparison: binary vs Python installation
## Testing Strategy
1. Test PyInstaller build on current platform (macOS)
2. Verify binary works without Python in PATH
3. Test core commands: save, list, show, tag, daemon
4. Verify git operations work correctly
5. Test on clean system (no Python/dependencies)
## Limitations
* Binary size: ~20-50MB (includes Python interpreter)
* git CLI still required (document clearly)
* Platform-specific builds needed (can't cross-compile)
* Startup time slightly slower than Python script
## Migration Path for Users
### Binary Installation (Recommended)
```warp-runnable-command
# macOS/Linux
wget https://releases/promptctl-v1.0.0-macos.tar.gz
tar -xzf promptctl-v1.0.0-macos.tar.gz
sudo mv promptctl /usr/local/bin/
promptctl --help
```
### Python Installation (Development)
```warp-runnable-command
git clone repo
pip install -e .
promptctl --help
```
## Success Criteria
* Single binary runs on macOS without Python installed
* Single binary runs on Linux (Ubuntu 20.04+) without Python installed  
* Single .exe runs on Windows 10+ without Python installed
* All core features work identically to Python version
* Clear error message if git CLI not installed
* Distribution size < 100MB per platform
