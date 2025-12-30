"""
Tag Manager - Handle prompt tagging operations

Provides comprehensive tag management including:
- Adding/removing tags from prompts
- Listing all tags with usage counts
- Filtering prompts by tags (AND/OR logic)
- Tag persistence using JSON metadata files
"""

import json
from pathlib import Path
from typing import Set, List, Dict
from collections import defaultdict


class TagManager:
    """Manages tags for prompts stored in the repository."""
    
    def __init__(self, repo_path: str):
        """
        Initialize tag manager.
        
        Args:
            repo_path: Path to the promptctl repository
        """
        self.repo_path = Path(repo_path)
        self.prompts_dir = self.repo_path / "prompts"
        self.tags_index = self.repo_path / ".tags_index.json"
        
        # Ensure directories exist
        self.prompts_dir.mkdir(parents=True, exist_ok=True)
        
        # Load or initialize tag index
        self._load_index()
    
    def _load_index(self) -> None:
        """Load the tag index from disk."""
        if self.tags_index.exists():
            try:
                self._index = json.loads(self.tags_index.read_text())
            except json.JSONDecodeError:
                self._index = {}
        else:
            self._index = {}
    
    def _save_index(self) -> None:
        """Save the tag index to disk."""
        self.tags_index.write_text(json.dumps(self._index, indent=2))
    
    def _get_metadata_path(self, prompt_id: str) -> Path:
        """Get path to prompt metadata file."""
        return self.prompts_dir / f"{prompt_id}.meta.json"
    
    def _load_metadata(self, prompt_id: str) -> Dict:
        """Load metadata for a prompt."""
        meta_path = self._get_metadata_path(prompt_id)
        if meta_path.exists():
            return json.loads(meta_path.read_text())
        return {}
    
    def _save_metadata(self, prompt_id: str, metadata: Dict) -> None:
        """Save metadata for a prompt."""
        meta_path = self._get_metadata_path(prompt_id)
        meta_path.write_text(json.dumps(metadata, indent=2))
    
    def add_tags(self, prompt_id: str, tags: List[str]) -> None:
        """
        Add tags to a prompt.
        
        Args:
            prompt_id: The prompt identifier
            tags: List of tags to add
        
        Raises:
            ValueError: If prompt doesn't exist
        """
        # Validate prompt exists
        prompt_file = self.prompts_dir / f"{prompt_id}.txt"
        if not prompt_file.exists():
            raise ValueError(f"Prompt not found: {prompt_id}")
        
        # Normalize tags (lowercase, strip whitespace)
        normalized_tags = [tag.lower().strip() for tag in tags]
        
        # Load existing metadata
        metadata = self._load_metadata(prompt_id)
        existing_tags = set(metadata.get("tags", []))
        
        # Add new tags
        existing_tags.update(normalized_tags)
        metadata["tags"] = sorted(existing_tags)
        
        # Save metadata
        self._save_metadata(prompt_id, metadata)
        
        # Update index
        for tag in normalized_tags:
            if tag not in self._index:
                self._index[tag] = []
            if prompt_id not in self._index[tag]:
                self._index[tag].append(prompt_id)
        
        self._save_index()
    
    def remove_tags(self, prompt_id: str, tags: List[str]) -> None:
        """
        Remove tags from a prompt.
        
        Args:
            prompt_id: The prompt identifier
            tags: List of tags to remove
        
        Raises:
            ValueError: If prompt doesn't exist
        """
        # Validate prompt exists
        prompt_file = self.prompts_dir / f"{prompt_id}.txt"
        if not prompt_file.exists():
            raise ValueError(f"Prompt not found: {prompt_id}")
        
        # Normalize tags
        normalized_tags = [tag.lower().strip() for tag in tags]
        
        # Load existing metadata
        metadata = self._load_metadata(prompt_id)
        existing_tags = set(metadata.get("tags", []))
        
        # Remove tags
        existing_tags.difference_update(normalized_tags)
        metadata["tags"] = sorted(existing_tags)
        
        # Save metadata
        self._save_metadata(prompt_id, metadata)
        
        # Update index
        for tag in normalized_tags:
            if tag in self._index and prompt_id in self._index[tag]:
                self._index[tag].remove(prompt_id)
                # Clean up empty tag entries
                if not self._index[tag]:
                    del self._index[tag]
        
        self._save_index()
    
    def get_tags(self, prompt_id: str) -> Set[str]:
        """
        Get all tags for a prompt.
        
        Args:
            prompt_id: The prompt identifier
        
        Returns:
            Set of tags for the prompt
        """
        metadata = self._load_metadata(prompt_id)
        return set(metadata.get("tags", []))
    
    def get_all_tags_with_counts(self) -> Dict[str, int]:
        """
        Get all tags in the repository with usage counts.
        
        Returns:
            Dictionary mapping tag names to prompt counts
        """
        tag_counts = defaultdict(int)
        
        # Count from all metadata files
        for meta_file in self.prompts_dir.glob("*.meta.json"):
            try:
                metadata = json.loads(meta_file.read_text())
                for tag in metadata.get("tags", []):
                    tag_counts[tag] += 1
            except (json.JSONDecodeError, OSError):
                continue
        
        return dict(tag_counts)
    
    def filter_by_tags(
        self,
        tags: List[str],
        match_all: bool = False
    ) -> Set[str]:
        """
        Filter prompts by tags.
        
        Args:
            tags: List of tags to filter by
            match_all: If True, prompt must have ALL tags (AND logic)
                      If False, prompt must have ANY tag (OR logic)
        
        Returns:
            Set of prompt IDs matching the filter
        """
        normalized_tags = [tag.lower().strip() for tag in tags]
        
        if not normalized_tags:
            return set()
        
        if match_all:
            # AND logic: prompt must have all tags
            result = None
            for tag in normalized_tags:
                tag_prompts = self._get_prompts_by_tag(tag)
                if result is None:
                    result = tag_prompts
                else:
                    result = result.intersection(tag_prompts)
            return result or set()
        else:
            # OR logic: prompt must have at least one tag
            result = set()
            for tag in normalized_tags:
                result.update(self._get_prompts_by_tag(tag))
            return result
    
    def _get_prompts_by_tag(self, tag: str) -> Set[str]:
        """Get all prompts with a specific tag."""
        prompts = set()
        
        # Search through all metadata files
        for meta_file in self.prompts_dir.glob("*.meta.json"):
            try:
                metadata = json.loads(meta_file.read_text())
                if tag in metadata.get("tags", []):
                    # Extract prompt ID from filename
                    prompt_id = meta_file.stem.replace(".meta", "")
                    prompts.add(prompt_id)
            except (json.JSONDecodeError, OSError):
                continue
        
        return prompts
    
    def rebuild_index(self) -> None:
        """
        Rebuild the tag index from scratch by scanning all metadata files.
        
        Useful for recovering from index corruption or migration.
        """
        self._index = {}
        
        for meta_file in self.prompts_dir.glob("*.meta.json"):
            try:
                metadata = json.loads(meta_file.read_text())
                prompt_id = meta_file.stem.replace(".meta", "")
                
                for tag in metadata.get("tags", []):
                    if tag not in self._index:
                        self._index[tag] = []
                    if prompt_id not in self._index[tag]:
                        self._index[tag].append(prompt_id)
            except (json.JSONDecodeError, OSError):
                continue
        
        self._save_index()
