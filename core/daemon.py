"""
Prompt Daemon - Auto-commit daemon with conflict resolution

MERGE CONFLICT HANDLING STRATEGIES
===================================

When local edits clash with daemon auto-commits, we need a resolution strategy:

1. OURS (--conflict-strategy=ours)
   - Always keep local changes
   - Discard daemon's auto-commits on conflict
   - Pro: Never lose manual edits
   - Con: May lose some automated metadata updates
   - Use when: Manual edits are high-value and shouldn't be overwritten

2. THEIRS (--conflict-strategy=theirs)
   - Always keep daemon's changes
   - Discard local edits on conflict
   - Pro: Ensures daemon state is consistent
   - Con: Can lose manual work
   - Use when: Daemon has authoritative state (e.g., syncing from server)

3. MANUAL (--conflict-strategy=manual)
   - Stop and require user intervention
   - Daemon pauses on conflict until resolved
   - Pro: User has full control
   - Con: Requires manual intervention, daemon may stay paused
   - Use when: Data is critical and conflicts are rare

4. TIMESTAMP (--conflict-strategy=timestamp) [RECOMMENDED DEFAULT]
   - Keep the most recently modified version
   - Compare file mtimes to determine which is newer
   - Pro: Usually correct (recent change is what user wants)
   - Con: May not always be semantically correct
   - Use when: You want automatic resolution with reasonable heuristic

Implementation notes:
- Conflicts typically occur when:
  a) User manually edits prompt files while daemon is running
  b) Multiple daemon instances running (misconfiguration)
  c) Manual git operations interfere with daemon commits
  
- For text files (prompts), git's merge is usually smart enough to avoid
  conflicts unless both sides modified the same lines
  
- For metadata files (.meta.json), conflicts are more likely since they're
  structured data that can't be line-merged easily

Best practices:
1. Use timestamp strategy by default
2. Add file locking for critical operations
3. Log all conflict resolutions for audit trail
4. Provide 'promptctl daemon status' to see conflict history
"""

import time
import logging
from pathlib import Path
from typing import Optional, Literal
from datetime import datetime

from .git_manager import GitManager

# Optional: requests for LLM integration
try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


ConflictStrategy = Literal["ours", "theirs", "manual", "timestamp"]


class LLMCommitGenerator:
    """
    Optional LLM-powered commit message generator.
    
    Uses local Ollama + Phi-3.5 to generate smart commit messages.
    Falls back to default messages if LLM is unavailable.
    """
    
    def __init__(self, enabled: bool = False, model: str = "phi3.5"):
        """
        Initialize LLM generator.
        
        Args:
            enabled: Whether to use LLM for commit messages
            model: Ollama model name (default: phi3.5)
        """
        self.enabled = enabled
        self.model = model
        self.api_url = "http://localhost:11434/api/generate"
        
        if enabled and not HAS_REQUESTS:
            logger.warning(
                "LLM commit generation requested but 'requests' not installed. "
                "Install with: pip install requests"
            )
            self.enabled = False
        
        if enabled:
            # Test connection to Ollama
            try:
                response = requests.get("http://localhost:11434/api/tags", timeout=2)
                if response.status_code != 200:
                    logger.warning("Ollama not available, disabling LLM commit generation")
                    self.enabled = False
            except Exception as e:
                logger.warning(f"Cannot connect to Ollama ({e}), disabling LLM")
                self.enabled = False
    
    def generate_commit_message(
        self,
        changed_files: list[str],
        fallback_msg: str
    ) -> str:
        """
        Generate commit message using LLM or fallback.
        
        Args:
            changed_files: List of changed file paths
            fallback_msg: Default message if LLM unavailable
        
        Returns:
            Generated or fallback commit message
        """
        if not self.enabled:
            return fallback_msg
        
        try:
            # Build context from changed files
            file_list = ", ".join(changed_files[:5])  # Max 5 files
            if len(changed_files) > 5:
                file_list += f" and {len(changed_files) - 5} more"
            
            prompt = f"""Write ONLY a git commit message (max 50 chars, no quotes or explanation) for:
Files: {file_list}
Message:"""
            
            response = requests.post(
                self.api_url,
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.3,  # Lower = more consistent
                        "num_predict": 50    # Short messages only
                    }
                },
                timeout=10
            )
            
            if response.status_code == 200:
                result = response.json()
                message = result.get("response", "").strip()
                
                # Clean up message
                message = message.split('\n')[0]  # First line only
                message = message.strip('`"\' ')   # Remove quotes/backticks
                
                if message and len(message) <= 72:
                    logger.debug(f"LLM generated: {message}")
                    return message
        
        except Exception as e:
            logger.debug(f"LLM generation failed: {e}")
        
        # Always fallback on any error
        return fallback_msg


class PromptDaemon:
    """Auto-commit daemon for prompt repository."""
    
    def __init__(
        self,
        repo_path: str,
        watch_interval: int = 60,
        conflict_strategy: ConflictStrategy = "timestamp",
        use_llm: bool = False,
        llm_model: str = "phi3.5"
    ):
        """
        Initialize daemon.
        
        Args:
            repo_path: Path to promptctl repository
            watch_interval: Seconds between checks
            conflict_strategy: How to resolve merge conflicts
            use_llm: Use LLM for commit message generation
            llm_model: Ollama model name for LLM
        """
        self.repo_path = Path(repo_path)
        self.watch_interval = watch_interval
        self.conflict_strategy = conflict_strategy
        self.git_mgr = GitManager(repo_path)
        
        # Ensure repository is initialized
        if not self.git_mgr.is_initialized():
            logger.info("Initializing repository")
            self.git_mgr.init()
        
        # Conflict resolution log
        self.conflict_log = self.repo_path / ".conflict_log.txt"
        
        # Optional LLM commit generator
        self.llm_generator = LLMCommitGenerator(enabled=use_llm, model=llm_model)
        if use_llm and self.llm_generator.enabled:
            logger.info(f"LLM commit generation enabled ({llm_model})")
        elif use_llm and not self.llm_generator.enabled:
            logger.warning("LLM requested but unavailable, using default messages")
    
    def run(self) -> None:
        """
        Run the daemon main loop.
        
        Continuously monitors for changes and commits them.
        Press Ctrl+C to stop.
        """
        logger.info(f"Daemon started (interval: {self.watch_interval}s)")
        
        while True:
            try:
                self._check_and_commit()
            except KeyboardInterrupt:
                raise
            except Exception as e:
                logger.error(f"Error in daemon loop: {e}")
            
            time.sleep(self.watch_interval)
    
    def _check_and_commit(self) -> None:
        """Check for changes and commit if found."""
        if not self.git_mgr.has_changes():
            logger.debug("No changes detected")
            return
        
        # Check for merge conflicts first
        conflicts = self.git_mgr.get_merge_conflicts()
        if conflicts:
            logger.warning(f"Merge conflicts detected: {conflicts}")
            self._resolve_conflicts(conflicts)
        
        # Commit changes
        try:
            # Get list of changed files for LLM context
            changed_files = self.git_mgr.get_changed_files()
            
            # Generate commit message (LLM or default)
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            fallback_msg = f"Auto-commit: {timestamp}"
            commit_msg = self.llm_generator.generate_commit_message(
                changed_files=changed_files,
                fallback_msg=fallback_msg
            )
            
            sha = self.git_mgr.commit(commit_msg)
            logger.info(f"Committed changes: {sha[:8]}")
        
        except ValueError as e:
            # No changes to commit (race condition)
            logger.debug(str(e))
        except Exception as e:
            logger.error(f"Commit failed: {e}")
    
    def _resolve_conflicts(self, conflicts: list[str]) -> None:
        """
        Resolve merge conflicts using configured strategy.
        
        Args:
            conflicts: List of file paths with conflicts
        """
        logger.info(f"Resolving {len(conflicts)} conflicts using '{self.conflict_strategy}' strategy")
        
        for file_path in conflicts:
            try:
                if self.conflict_strategy == "ours":
                    self._resolve_ours(file_path)
                
                elif self.conflict_strategy == "theirs":
                    self._resolve_theirs(file_path)
                
                elif self.conflict_strategy == "manual":
                    self._resolve_manual(file_path)
                
                elif self.conflict_strategy == "timestamp":
                    self._resolve_timestamp(file_path)
                
                # Log resolution
                self._log_conflict_resolution(file_path, self.conflict_strategy)
            
            except Exception as e:
                logger.error(f"Failed to resolve conflict in {file_path}: {e}")
    
    def _resolve_ours(self, file_path: str) -> None:
        """Keep our version (local edits)."""
        logger.info(f"Keeping local version: {file_path}")
        self.git_mgr.resolve_conflict_ours(file_path)
    
    def _resolve_theirs(self, file_path: str) -> None:
        """Keep their version (daemon commits)."""
        logger.info(f"Keeping daemon version: {file_path}")
        self.git_mgr.resolve_conflict_theirs(file_path)
    
    def _resolve_manual(self, file_path: str) -> None:
        """Require manual intervention."""
        logger.warning(
            f"Manual intervention required for: {file_path}\n"
            f"Please resolve the conflict and run: git add {file_path}"
        )
        # Pause daemon until resolved
        while file_path in self.git_mgr.get_merge_conflicts():
            logger.info("Waiting for manual conflict resolution...")
            time.sleep(10)
        
        logger.info(f"Conflict resolved manually: {file_path}")
    
    def _resolve_timestamp(self, file_path: str) -> None:
        """Keep the most recently modified version."""
        # Get modification times for both versions
        local_mtime = self.git_mgr.get_file_mtime(file_path)
        
        # For simplicity, we'll use 'ours' if we can't determine time
        # In a production system, you'd want to parse the conflict markers
        # and compare timestamps from git history
        
        if local_mtime is None:
            logger.warning(f"Cannot determine modification time, keeping local: {file_path}")
            self._resolve_ours(file_path)
            return
        
        # Check git history for their version time
        try:
            # Get last commit time for this file
            commit_time = self.git_mgr.repo.git.log(
                "-1", "--format=%ct", "--", file_path
            )
            commit_timestamp = float(commit_time) if commit_time else 0
            
            if local_mtime > commit_timestamp:
                logger.info(f"Local version is newer: {file_path}")
                self._resolve_ours(file_path)
            else:
                logger.info(f"Daemon version is newer: {file_path}")
                self._resolve_theirs(file_path)
        
        except Exception as e:
            logger.warning(f"Error comparing timestamps, keeping local: {e}")
            self._resolve_ours(file_path)
    
    def _log_conflict_resolution(self, file_path: str, strategy: str) -> None:
        """
        Log conflict resolution to audit trail.
        
        Args:
            file_path: Path to conflicted file
            strategy: Resolution strategy used
        """
        timestamp = datetime.now().isoformat()
        log_entry = f"{timestamp} | {strategy} | {file_path}\n"
        
        with open(self.conflict_log, "a") as f:
            f.write(log_entry)
