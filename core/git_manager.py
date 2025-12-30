"""
Git Manager - Handle git operations for prompt storage

DESIGN DECISION: GitPython vs libgit2 (pygit2)
==============================================

This implementation uses GitPython. Here's a detailed analysis of the trade-offs:

GitPython (chosen):
  Pros:
    + Pure Python, easier installation (pip install GitPython)
    + No system dependencies or compilation required
    + Higher-level API, more Pythonic and intuitive
    + Better documentation and more Stack Overflow answers
    + Wider adoption in Python ecosystem
    + Works by shelling out to git CLI, so behavior matches user expectations
    + Easier to debug (can see actual git commands being run)
    + Better cross-platform support out of the box
  
  Cons:
    - Slower for some operations (subprocess overhead)
    - Requires git binary installed on system
    - Less control over low-level git internals
    - Higher memory overhead for large operations

libgit2 (pygit2):
  Pros:
    + Faster for many operations (native C bindings)
    + Lower memory footprint
    + No git binary dependency (pure library approach)
    + More control over low-level git operations
    + Better for high-performance scenarios
    + Can work without full git installation
  
  Cons:
    - Complex installation (requires libgit2 C library)
    - Platform-specific compilation issues common
    - Lower-level API, more verbose code
    - Steeper learning curve
    - Less documentation and community support
    - Behavior can differ subtly from git CLI
    - Version compatibility issues between pygit2 and libgit2

For promptctl, GitPython is the better choice because:
1. Ease of installation is critical for a CLI tool
2. Performance difference is negligible for our use case (small text files)
3. Users expect git-cli-like behavior for debugging
4. Simpler maintenance and fewer installation support issues

If we needed to optimize for performance (e.g., handling thousands of prompts
per second), libgit2 would be worth reconsidering.
"""

import os
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime

try:
    from git import Repo, GitCommandError, InvalidGitRepositoryError
    from git.exc import GitError
except ImportError:
    raise ImportError(
        "GitPython is required. Install with: pip install GitPython"
    )


class GitManager:
    """Manages git operations for the prompt repository."""
    
    def __init__(self, repo_path: str):
        """
        Initialize git manager.
        
        Args:
            repo_path: Path to the git repository
        """
        self.repo_path = Path(repo_path)
        self._repo: Optional[Repo] = None
    
    @property
    def repo(self) -> Repo:
        """Get the git repository object, initializing if needed."""
        if self._repo is None:
            if not self.is_initialized():
                raise ValueError(f"Repository not initialized: {self.repo_path}")
            self._repo = Repo(self.repo_path)
        return self._repo
    
    def is_initialized(self) -> bool:
        """
        Check if the repository is initialized.
        
        Returns:
            True if valid git repository exists
        """
        try:
            Repo(self.repo_path)
            return True
        except (InvalidGitRepositoryError, GitError):
            return False
    
    def init(self) -> None:
        """
        Initialize a new git repository.
        
        Creates the repository directory if it doesn't exist and
        initializes it as a git repository with an initial commit.
        """
        self.repo_path.mkdir(parents=True, exist_ok=True)
        
        # Initialize repository
        self._repo = Repo.init(self.repo_path)
        
        # Create initial structure
        (self.repo_path / "prompts").mkdir(exist_ok=True)
        (self.repo_path / ".gitignore").write_text(
            "# promptctl files\n"
            ".batch_counter\n"
            "*.tmp\n"
            ".DS_Store\n"
        )
        
        # Create README
        readme_path = self.repo_path / "README.md"
        readme_path.write_text(
            "# promptctl repository\n\n"
            "This repository stores prompts managed by promptctl.\n"
        )
        
        # Initial commit
        self._repo.index.add([".gitignore", "README.md"])
        self._repo.index.commit("Initial commit")
    
    def commit(self, message: str, author: Optional[Dict[str, str]] = None) -> str:
        """
        Commit current changes.
        
        Args:
            message: Commit message
            author: Optional author dict with 'name' and 'email' keys
        
        Returns:
            Commit SHA
        
        Raises:
            ValueError: If there are no changes to commit
        """
        # Add all changes
        self.repo.git.add(A=True)
        
        # Check if there are changes
        if not self.repo.is_dirty() and not self.repo.untracked_files:
            raise ValueError("No changes to commit")
        
        # Create commit
        if author:
            commit = self.repo.index.commit(
                message,
                author=f"{author['name']} <{author['email']}>"
            )
        else:
            commit = self.repo.index.commit(message)
        
        return commit.hexsha
    
    def get_status(self) -> Dict[str, List[str]]:
        """
        Get repository status.
        
        Returns:
            Dictionary with 'modified', 'untracked', and 'branch' keys
        """
        return {
            "modified": [item.a_path for item in self.repo.index.diff(None)],
            "untracked": self.repo.untracked_files,
            "branch": self.repo.active_branch.name if not self.repo.head.is_detached else "HEAD"
        }
    
    def get_diff(self, staged: bool = False) -> str:
        """
        Get diff of changes.
        
        Args:
            staged: If True, show staged changes; if False, show unstaged
        
        Returns:
            Diff text
        """
        if staged:
            return self.repo.git.diff("--cached")
        else:
            return self.repo.git.diff()
    
    def has_changes(self) -> bool:
        """
        Check if repository has uncommitted changes.
        
        Returns:
            True if there are uncommitted changes
        """
        return self.repo.is_dirty() or len(self.repo.untracked_files) > 0
    
    def get_changed_files(self) -> List[str]:
        """
        Get list of changed files (modified + untracked).
        
        Returns:
            List of changed file paths
        """
        changed = []
        
        # Modified files
        for item in self.repo.index.diff(None):
            changed.append(item.a_path)
        
        # Untracked files
        changed.extend(self.repo.untracked_files)
        
        return changed
    
    def pull(self, remote: str = "origin", branch: str = "main") -> None:
        """
        Pull changes from remote.
        
        Args:
            remote: Remote name
            branch: Branch name
        
        Raises:
            GitCommandError: If pull fails
        """
        self.repo.git.pull(remote, branch)
    
    def push(self, remote: str = "origin", branch: str = "main") -> None:
        """
        Push changes to remote.
        
        Args:
            remote: Remote name
            branch: Branch name
        
        Raises:
            GitCommandError: If push fails
        """
        self.repo.git.push(remote, branch)
    
    def get_merge_conflicts(self) -> List[str]:
        """
        Get list of files with merge conflicts.
        
        Returns:
            List of file paths with conflicts
        """
        try:
            # Files with conflicts have 'U' status
            conflicts = []
            for item in self.repo.index.diff(None):
                if item.change_type == 'U':
                    conflicts.append(item.a_path)
            return conflicts
        except GitError:
            return []
    
    def resolve_conflict_ours(self, file_path: str) -> None:
        """
        Resolve conflict by keeping our version.
        
        Args:
            file_path: Path to conflicted file
        """
        self.repo.git.checkout("--ours", file_path)
        self.repo.index.add([file_path])
    
    def resolve_conflict_theirs(self, file_path: str) -> None:
        """
        Resolve conflict by keeping their version.
        
        Args:
            file_path: Path to conflicted file
        """
        self.repo.git.checkout("--theirs", file_path)
        self.repo.index.add([file_path])
    
    def get_file_mtime(self, file_path: str) -> Optional[float]:
        """
        Get last modification time of a file.
        
        Args:
            file_path: Relative path from repo root
        
        Returns:
            Modification timestamp or None if file doesn't exist
        """
        full_path = self.repo_path / file_path
        if full_path.exists():
            return full_path.stat().st_mtime
        return None
