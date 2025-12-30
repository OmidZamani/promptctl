#!/usr/bin/env python3
"""
Test suite for promptctl

Run with: python -m pytest tests/test_promptctl.py
"""

import pytest
import tempfile
import shutil
from pathlib import Path
import sys

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.git_manager import GitManager
from core.prompt_store import PromptStore
from core.tag_manager import TagManager
from core.batch_manager import BatchManager


@pytest.fixture
def temp_repo():
    """Create a temporary repository for testing."""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir)


class TestGitManager:
    """Test git operations."""
    
    def test_init_repository(self, temp_repo):
        """Test repository initialization."""
        git_mgr = GitManager(temp_repo)
        assert not git_mgr.is_initialized()
        
        git_mgr.init()
        assert git_mgr.is_initialized()
        assert (Path(temp_repo) / ".git").exists()
        assert (Path(temp_repo) / "prompts").exists()
    
    def test_commit(self, temp_repo):
        """Test committing changes."""
        git_mgr = GitManager(temp_repo)
        git_mgr.init()
        
        # Create a file
        test_file = Path(temp_repo) / "test.txt"
        test_file.write_text("test content")
        
        # Commit
        sha = git_mgr.commit("Test commit")
        assert len(sha) == 40  # SHA is 40 characters
    
    def test_status(self, temp_repo):
        """Test getting repository status."""
        git_mgr = GitManager(temp_repo)
        git_mgr.init()
        
        status = git_mgr.get_status()
        assert "branch" in status
        assert "modified" in status
        assert "untracked" in status


class TestPromptStore:
    """Test prompt storage operations."""
    
    def test_save_prompt(self, temp_repo):
        """Test saving a prompt."""
        store = PromptStore(temp_repo)
        
        prompt_id = store.save_prompt(
            content="Test prompt",
            name="test-prompt",
            tags=["test", "demo"]
        )
        
        assert prompt_id == "test-prompt"
        assert (Path(temp_repo) / "prompts" / "test-prompt.txt").exists()
    
    def test_get_prompt(self, temp_repo):
        """Test retrieving a prompt."""
        store = PromptStore(temp_repo)
        
        prompt_id = store.save_prompt(
            content="Test content",
            name="test",
            tags=["tag1", "tag2"]
        )
        
        prompt = store.get_prompt(prompt_id)
        assert prompt["id"] == "test"
        assert prompt["content"] == "Test content"


class TestTagManager:
    """Test tag management operations."""
    
    def test_add_tags(self, temp_repo):
        """Test adding tags to a prompt."""
        store = PromptStore(temp_repo)
        prompt_id = store.save_prompt("Test", name="test", tags=["initial"])
        
        tag_mgr = TagManager(temp_repo)
        tag_mgr.add_tags(prompt_id, ["new1", "new2"])
        
        tags = tag_mgr.get_tags(prompt_id)
        assert "initial" in tags
        assert "new1" in tags


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
