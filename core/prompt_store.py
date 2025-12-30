"""
Prompt Store - Core storage layer for prompts

Handles saving, loading, and listing prompts with metadata support.
"""

import json
import uuid
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime


class PromptStore:
    """Manages prompt storage and retrieval."""
    
    def __init__(self, repo_path: str):
        """
        Initialize prompt store.
        
        Args:
            repo_path: Path to the promptctl repository
        """
        self.repo_path = Path(repo_path)
        self.prompts_dir = self.repo_path / "prompts"
        self.prompts_dir.mkdir(parents=True, exist_ok=True)
    
    def save_prompt(
        self,
        content: str,
        name: Optional[str] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict] = None
    ) -> str:
        """
        Save a prompt to the repository.
        
        Args:
            content: The prompt text
            name: Optional prompt name (used as ID if provided)
            tags: Optional list of tags
            metadata: Optional metadata dictionary
        
        Returns:
            The prompt ID
        """
        # Generate ID
        prompt_id = name or str(uuid.uuid4())
        
        # Save content
        prompt_file = self.prompts_dir / f"{prompt_id}.txt"
        prompt_file.write_text(content)
        
        # Save metadata
        meta = metadata or {}
        meta["id"] = prompt_id
        meta["created_at"] = datetime.now().isoformat()
        meta["tags"] = tags or []
        
        meta_file = self.prompts_dir / f"{prompt_id}.meta.json"
        meta_file.write_text(json.dumps(meta, indent=2))
        
        return prompt_id
    
    def get_prompt(self, prompt_id: str) -> Dict:
        """
        Retrieve a prompt by ID.
        
        Args:
            prompt_id: The prompt identifier
        
        Returns:
            Dictionary with 'id', 'content', 'tags', and 'metadata' keys
        
        Raises:
            ValueError: If prompt not found
        """
        prompt_file = self.prompts_dir / f"{prompt_id}.txt"
        meta_file = self.prompts_dir / f"{prompt_id}.meta.json"
        
        if not prompt_file.exists():
            raise ValueError(f"Prompt not found: {prompt_id}")
        
        content = prompt_file.read_text()
        
        metadata = {}
        if meta_file.exists():
            metadata = json.loads(meta_file.read_text())
        
        return {
            "id": prompt_id,
            "content": content,
            "tags": metadata.get("tags", []),
            "metadata": metadata
        }
    
    def list_prompts(self) -> List[Dict]:
        """
        List all prompts in the repository.
        
        Returns:
            List of prompt dictionaries with basic info
        """
        prompts = []
        
        for prompt_file in sorted(self.prompts_dir.glob("*.txt")):
            prompt_id = prompt_file.stem
            meta_file = self.prompts_dir / f"{prompt_id}.meta.json"
            
            metadata = {}
            if meta_file.exists():
                try:
                    metadata = json.loads(meta_file.read_text())
                except json.JSONDecodeError:
                    pass
            
            prompts.append({
                "id": prompt_id,
                "tags": metadata.get("tags", []),
                "metadata": metadata
            })
        
        return prompts
    
    def delete_prompt(self, prompt_id: str) -> None:
        """
        Delete a prompt.
        
        Args:
            prompt_id: The prompt identifier
        
        Raises:
            ValueError: If prompt not found
        """
        prompt_file = self.prompts_dir / f"{prompt_id}.txt"
        meta_file = self.prompts_dir / f"{prompt_id}.meta.json"
        
        if not prompt_file.exists():
            raise ValueError(f"Prompt not found: {prompt_id}")
        
        prompt_file.unlink()
        if meta_file.exists():
            meta_file.unlink()
