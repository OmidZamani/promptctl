"""
Batch Manager - Handle batched commits for prompt saves

Tracks save operations and triggers commits when a threshold is reached.
This reduces git overhead for high-frequency save operations.
"""

import json
from pathlib import Path
from typing import Optional


class BatchManager:
    """Manages batched commits for prompt operations."""
    
    def __init__(self, repo_path: str, batch_size: int = 5):
        """
        Initialize batch manager.
        
        Args:
            repo_path: Path to the promptctl repository
            batch_size: Number of saves before triggering a commit
        """
        self.repo_path = Path(repo_path)
        self.batch_size = batch_size
        self.counter_file = self.repo_path / ".batch_counter"
        
        # Ensure directory exists
        self.repo_path.mkdir(parents=True, exist_ok=True)
    
    def _read_counter(self) -> int:
        """Read the current batch counter."""
        if self.counter_file.exists():
            try:
                return int(self.counter_file.read_text().strip())
            except (ValueError, OSError):
                return 0
        return 0
    
    def _write_counter(self, count: int) -> None:
        """Write the batch counter."""
        self.counter_file.write_text(str(count))
    
    def increment(self) -> int:
        """
        Increment the batch counter.
        
        Returns:
            The new counter value
        """
        count = self._read_counter() + 1
        self._write_counter(count)
        return count
    
    def should_commit(self) -> bool:
        """
        Check if a commit should be triggered.
        
        Returns:
            True if counter has reached or exceeded batch_size
        """
        count = self.increment()
        return count >= self.batch_size
    
    def reset_counter(self) -> None:
        """Reset the batch counter to zero."""
        self._write_counter(0)
    
    def get_pending_count(self) -> int:
        """
        Get the number of pending saves.
        
        Returns:
            Current counter value
        """
        return self._read_counter()
