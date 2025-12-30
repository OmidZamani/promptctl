# promptctl Design Documentation

## Architecture Overview

promptctl is a Git-backed prompt management system with four main components:

1. **Git Manager** - Version control operations
2. **Prompt Store** - Storage and retrieval
3. **Tag Manager** - Tag-based organization
4. **Batch Manager** - Deferred commit optimization
5. **Daemon** - Auto-commit with conflict resolution

## Key Design Decisions

### 1. GitPython vs libgit2 (pygit2)

**Decision**: Use GitPython

**Rationale**:

| Factor | GitPython | libgit2 |
|--------|-----------|---------|
| Installation | ✅ Simple pip install | ❌ Requires C library |
| API Design | ✅ High-level, Pythonic | ❌ Low-level, verbose |
| Documentation | ✅ Excellent | ⚠️ Limited |
| Performance | ⚠️ ~10-50ms overhead | ✅ Native speed |
| Debugging | ✅ Can see git commands | ❌ Black box |
| Dependencies | ⚠️ Needs git binary | ✅ No git needed |

**Why GitPython wins for promptctl**:

1. **User experience**: Easy installation is critical for CLI tools
2. **Performance**: Our use case (small text files) doesn't need native speed
3. **Maintenance**: Simpler codebase, better community support
4. **Debugging**: Users can reproduce issues with git CLI

**When libgit2 would be better**:
- High-frequency operations (>100 commits/sec)
- Environments without git installed
- Need for fine-grained control over git internals

### 2. Batch Mode Design

**Problem**: Git commits have ~10-50ms overhead each. For bulk operations (importing 1000 prompts), this adds 10-50 seconds of unnecessary delay.

**Solution**: Batch manager that defers commits until N operations complete.

**Implementation**:
```python
# Counter stored in .batch_counter file
# Survives process restarts
# Thread-safe for single process

if batch_mgr.should_commit():
    git_mgr.commit(f"Batch: {n} saves")
    batch_mgr.reset_counter()
```

**Trade-offs**:
- ✅ 5-10x speedup for bulk operations
- ✅ Configurable threshold (default: 5)
- ❌ Less granular git history
- ❌ Risk of losing N operations if crash occurs

**Best practices**:
- Use for bulk imports, data generation
- Don't use for interactive sessions
- Reduce batch size (--batch-size 2) for critical data

### 3. Tag Storage Architecture

**Decision**: Store tags in `.meta.json` files, maintain `.tags_index.json` for fast lookups

**Alternatives considered**:

**Option A**: Single tags.json file
```
{
  "prompt-1": ["tag1", "tag2"],
  "prompt-2": ["tag1", "tag3"]
}
```
- ✅ Simple
- ❌ Doesn't scale (must load entire file)
- ❌ Merge conflicts on every tag operation

**Option B**: Tags in prompt filenames
```
prompt-1.python.coding.txt
```
- ✅ No metadata files
- ❌ Ugly filenames
- ❌ Limited by filesystem (special chars, length)
- ❌ Hard to rename/reorganize

**Option C**: Separate .meta.json per prompt (chosen)
```
prompts/
  prompt-1.txt
  prompt-1.meta.json  <- {"tags": ["python", "coding"]}
  prompt-2.txt
  prompt-2.meta.json
```
- ✅ Scales well (only load what you need)
- ✅ Clean separation of content and metadata
- ✅ Fewer merge conflicts (only affects one prompt)
- ✅ Can store additional metadata (timestamps, authors, etc.)
- ⚠️ Requires index for fast tag lookups

**Index design**:
```json
{
  "python": ["prompt-1", "prompt-3"],
  "coding": ["prompt-1", "prompt-2"]
}
```
- Fast lookups: O(1) to find prompts by tag
- Rebuilt automatically if corrupted
- Gitignored (can be regenerated)

### 4. Merge Conflict Resolution Strategies

**Problem**: When daemon auto-commits clash with user's manual edits, how do we resolve?

**Four strategies**:

#### 1. TIMESTAMP (default)
```python
# Keep the most recently modified version
local_mtime = file.stat().st_mtime
commit_time = git.log("-1", "--format=%ct", file)

if local_mtime > commit_time:
    keep_ours()
else:
    keep_theirs()
```

**Pros**:
- Automatic resolution
- Usually correct (recent = intended)
- No user intervention needed

**Cons**:
- May not be semantically correct
- Clock skew can cause issues

**Use when**: Development/testing, conflicts are rare

#### 2. OURS
```python
# Always keep local changes
git.checkout("--ours", file)
```

**Pros**:
- Never lose manual work
- Predictable behavior

**Cons**:
- May lose daemon's metadata updates

**Use when**: Manual edits are high-value

#### 3. THEIRS
```python
# Always keep daemon's version
git.checkout("--theirs", file)
```

**Pros**:
- Daemon has consistent state
- Good for one-way sync

**Cons**:
- Can lose manual work

**Use when**: Daemon is authoritative (e.g., syncing from API)

#### 4. MANUAL
```python
# Stop and wait for user
while file in conflicts:
    log.warning("Resolve conflict manually")
    sleep(10)
```

**Pros**:
- User has full control
- No data loss

**Cons**:
- Daemon pauses
- Requires manual intervention

**Use when**: Critical data, conflicts should be rare

**Conflict audit log**:
All resolutions logged to `.conflict_log.txt`:
```
2025-12-30T12:00:00 | timestamp | prompts/prompt-1.txt
2025-12-30T12:05:00 | ours | prompts/prompt-2.meta.json
```

### 5. Tag Filtering Logic

**Two modes**: OR (any) and AND (all)

**OR logic** (default):
```python
# Match prompts with ANY of the tags
result = set()
for tag in tags:
    result.update(get_prompts_with_tag(tag))
```

Use case: "Find all Python OR JavaScript prompts"

**AND logic** (--match-all):
```python
# Match prompts with ALL tags
result = get_prompts_with_tag(tags[0])
for tag in tags[1:]:
    result = result.intersection(get_prompts_with_tag(tag))
```

Use case: "Find prompts that are Python AND production AND reviewed"

**Performance**:
- OR: O(k × n) where k=num_tags, n=avg_prompts_per_tag
- AND: O(k × n) with early termination (best case: O(n))

## File Structure

```
~/.promptctl/
├── .git/                    # Git repository
│   └── ...                  # Standard git internals
│
├── prompts/                 # Prompt storage
│   ├── my-prompt.txt        # Prompt content (plain text)
│   ├── my-prompt.meta.json  # Metadata (tags, timestamps)
│   ├── task-1.txt
│   ├── task-1.meta.json
│   └── ...
│
├── .tags_index.json         # Fast tag lookup index
├── .batch_counter           # Batch mode counter
├── .conflict_log.txt        # Conflict resolution log
├── .gitignore               # Ignore temp files
└── README.md                # Repo documentation
```

## Error Handling Strategy

**Principle**: Fail fast with clear error messages

**Examples**:

```python
# Bad: Silent failure
try:
    prompt = get_prompt(id)
except:
    pass

# Good: Explicit error with context
try:
    prompt = get_prompt(id)
except FileNotFoundError:
    raise ValueError(f"Prompt not found: {id}")
```

**Error categories**:

1. **User errors** (ValueError): Invalid input, missing files
   - Show helpful message
   - Return exit code 1
   
2. **System errors** (OSError, GitError): Disk full, permissions
   - Show error details
   - Suggest fixes if possible
   
3. **Logic errors** (AssertionError): Internal bugs
   - Show error + context
   - Ask user to report

## Performance Characteristics

**Operation timings** (approximate):

| Operation | Without Batch | With Batch (n=5) |
|-----------|---------------|------------------|
| Save prompt | 50ms | 10ms |
| Add tags | 45ms | 8ms |
| List prompts | 5ms | 5ms |
| Filter by tags | 3ms | 3ms |
| Daemon check | 20ms | 20ms |

**Scalability**:

- ✅ Handles 10,000+ prompts efficiently
- ✅ Tag filtering stays fast (indexed)
- ⚠️ Git operations slow down after 100k commits
- ⚠️ Large prompts (>1MB) should be avoided

## Security Considerations

**Current implementation**:

1. **No authentication**: Local-only, relies on filesystem permissions
2. **No encryption**: Prompts stored in plain text
3. **No access control**: All prompts accessible to anyone with repo access

**For production use, consider**:

1. **Encryption at rest**: Use git-crypt or similar
2. **Remote access**: Add SSH/HTTPS authentication
3. **Role-based access**: Implement permission system
4. **Audit trail**: Already have git history + conflict log
5. **Secrets management**: Never store API keys in prompts

## Testing Strategy

**Unit tests**: Each component tested independently
- GitManager: Repository operations
- PromptStore: Save/load/list
- TagManager: Tag operations
- BatchManager: Counter logic

**Integration tests**: Components working together
- Full save-tag-list-show workflow
- Batch mode with commits
- Conflict resolution (mocked)

**Manual testing**: Real-world scenarios
```bash
# Quick smoke test
./tests/smoke_test.sh
```

## Future Enhancements

### Phase 2: Remote Sync
```bash
promptctl remote add origin git@github.com:user/prompts.git
promptctl push
promptctl pull
```

### Phase 3: Search
```bash
promptctl search "Python function" --tags coding
```

### Phase 4: Templates
```bash
promptctl save --template \
  "Write a {{language}} function that {{task}}"
  
promptctl render my-template language=Python task="sorts arrays"
```

### Phase 5: History
```bash
promptctl history my-prompt
promptctl diff my-prompt HEAD~1
promptctl restore my-prompt --version abc123
```

## Contributing Guidelines

**Code style**:
- Type hints required
- Docstrings for all public methods
- Maximum line length: 100 characters

**Testing**:
- Unit tests for new features
- Update integration tests if needed
- Manual test with examples in PR

**Documentation**:
- Update README.md for user-facing changes
- Update DESIGN.md for architectural changes
- Add examples to demonstrate new features

## License

MIT License - See LICENSE file
