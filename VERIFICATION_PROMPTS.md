# Copy-Paste Prompts for Remaining Verification Scripts

Your `install_verify.sh` is complete and tested (14/14 ✅).

Use these prompts to generate the other 5 verification scripts when needed.

---

## 🔴 PROMPT #1: Verify Phase 1 Core Features

Copy-paste this to Warp:

```
I have a working promptctl installation at ~/dev/promptctl with Phase 1 complete.

Create verify_phase1.sh that tests:
1. Save command - echo "test" | python promptctl.py save --name test1 --tags demo
2. List command - python promptctl.py list
3. Show command - python promptctl.py show test1
4. Tag add - python promptctl.py tag add --prompt-id test1 --tags new
5. Tag filter (OR) - python promptctl.py tag filter --tags demo new
6. Tag filter (AND) - python promptctl.py tag filter --tags demo new --match-all
7. Batch mode - 5 saves with --batch --batch-size 3
8. Daemon starts - python promptctl.py daemon --help works
9. Status command - python promptctl.py status
10. Diff command - python promptctl.py diff

The script should:
- Create a temp test repo (not ~/.promptctl)
- Run each test
- Print ✅ PASS or ❌ FAIL for each
- Clean up temp repo
- Exit 0 if all pass, exit 1 if any fail

Make it 80-100 lines with clear output.
```

---

## 🟠 PROMPT #2: Verify Phase 2 AI Integration

Copy-paste this to Warp:

```
I have promptctl with LLM integration (Ollama + Phi-3.5) at ~/dev/promptctl.

Create verify_phase2.sh that tests:
1. Ollama service is running
2. Phi-3.5 model is available  
3. LLMCommitGenerator class can be imported
4. LLMCommitGenerator with enabled=True connects to Ollama
5. generate_commit_message() returns non-fallback message
6. Daemon accepts --use-llm flag
7. Daemon with --use-llm creates AI commits
8. Fallback works when Ollama unavailable

The script should:
- Test each component independently
- Show example AI-generated commit message
- Test fallback by temporarily stopping Ollama
- Print ✅/❌ for each test
- Restore Ollama state after testing

Make it 100-120 lines with detailed output showing AI messages vs defaults.
```

---

## 🟡 PROMPT #3: End-to-End Integration Test

Copy-paste this to Warp:

```
I need an integration test for complete promptctl system (Phase 1 + Phase 2).

Create integration_test.sh that:
1. Starts fresh test environment
2. Saves 10 prompts with different tags
3. Tests all tag filtering combinations
4. Runs batch mode with verification
5. Starts daemon WITH --use-llm in background
6. Makes file changes that daemon will commit
7. Waits and verifies AI commits appear
8. Tests conflict resolution
9. Validates git history quality
10. Generates final report

The script should:
- Use test repo (not ~/.promptctl)
- Run daemon in background properly
- Wait for commits with timeouts
- Show git log with AI messages
- Compare Phase 1 vs Phase 2 commits
- Clean up processes and files
- Generate detailed report

Make it 150-180 lines with progress indicators and clear sections.
```

---

## 🟢 PROMPT #4: Documentation Audit

Copy-paste this to Warp:

```
I need to audit all promptctl documentation at ~/dev/promptctl.

Create audit_docs.sh that checks:
1. README.md exists and has all expected sections
2. QUICKSTART.md has working examples  
3. DESIGN.md explains architecture
4. QUICK_REFERENCE.md has common commands
5. PHASE_1_AND_2_COMPLETE.md summarizes project
6. All code examples in docs are valid syntax
7. All file references point to existing files
8. No broken internal links

The script should:
- Check each doc file exists
- Validate markdown syntax
- Extract code blocks and verify they're runnable
- Check for required sections (## Installation, ## Usage, etc.)
- Verify file paths mentioned actually exist
- Generate completeness score

Make it 70-90 lines with section-by-section reporting.
Output: "Doc Quality: 95%" at the end.
```

---

## 🔵 PROMPT #5: Code Quality Report

Copy-paste this to Warp:

```
I need a code quality report for promptctl at ~/dev/promptctl.

Create code_quality.py that analyzes:
1. Total lines of code per file
2. Function and class count
3. Docstring coverage
4. Type hint coverage  
5. Error handling patterns
6. Import organization
7. Code complexity estimate

The script should:
- Parse all .py files in project
- Count functions/classes with docstrings
- Check for type hints in function signatures
- Find try/except blocks
- Calculate metrics per file
- Generate overall quality score

Output format:
```
Code Quality Report
===================
Total Lines: 1,482
Functions: 45 (40 with docstrings = 89%)
Type Hints: 42/45 functions (93%)
Error Handling: 15 try/except blocks
Quality Score: A+ (95/100)
```

Make it 120-150 lines Python with clear metric calculations.
```

---

## 📊 Usage Order

Recommended order to run these:

1. **Already done**: `./install_verify.sh` ✅
2. Generate `verify_phase1.sh` with PROMPT #1
3. Generate `verify_phase2.sh` with PROMPT #2  
4. Generate `integration_test.sh` with PROMPT #3
5. Generate `audit_docs.sh` with PROMPT #4
6. Generate `code_quality.py` with PROMPT #5

## ⚡ Quick Test

After generating each script:
```bash
# Make executable
chmod +x verify_phase1.sh

# Run it
./verify_phase1.sh

# Check result
echo $?  # Should be 0 for success
```

## 💡 Notes

- Each prompt is self-contained
- Copy the entire code block to Warp
- Warp will generate a working script
- Save the script and make it executable
- Run and verify results

---

**Status**: Prompts ready for scripts #1-5  
**Script #6**: ✅ COMPLETE (install_verify.sh tested, 14/14 pass)
