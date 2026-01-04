"""
Prompt Store - Core storage layer for prompts

Handles saving, loading, and listing prompts with metadata support.
Supports prompt chaining for conversation threads.
"""

import json
import uuid
import hashlib
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
    
    def _compute_hash(self, content: str) -> str:
        """Compute short hash of content for quick lookup."""
        return hashlib.sha256(content.encode()).hexdigest()[:12]
    
    def save_prompt(
        self,
        content: str,
        name: Optional[str] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict] = None,
        parent_id: Optional[str] = None
    ) -> str:
        """
        Save a prompt to the repository.
        
        Args:
            content: The prompt text
            name: Optional prompt name (used as ID if provided)
            tags: Optional list of tags
            metadata: Optional metadata dictionary
            parent_id: Optional ID of parent prompt (for chaining)
        
        Returns:
            The prompt ID
        """
        # Generate ID
        prompt_id = name or str(uuid.uuid4())
        
        # Save content
        prompt_file = self.prompts_dir / f"{prompt_id}.txt"
        prompt_file.write_text(content)
        
        # Compute content hash
        content_hash = self._compute_hash(content)
        
        # Save metadata
        meta = metadata or {}
        meta["id"] = prompt_id
        meta["created_at"] = datetime.now().isoformat()
        meta["tags"] = tags or []
        meta["content_hash"] = content_hash
        
        # Handle chaining
        if parent_id:
            parent = self.get_prompt(parent_id)
            parent_meta = parent.get("metadata", {})
            
            # Chain ID is the root prompt's ID
            meta["parent_id"] = parent_id
            meta["chain_id"] = parent_meta.get("chain_id", parent_id)
            meta["chain_position"] = parent_meta.get("chain_position", 1) + 1
            
            # If parent doesn't have chain_id, update it
            if "chain_id" not in parent_meta:
                parent_meta["chain_id"] = parent_id
                parent_meta["chain_position"] = 1
                self.update_metadata(parent_id, parent_meta)
        
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
    
    def list_prompts(self, include_content: bool = True) -> List[Dict]:
        """
        List all prompts in the repository.
        
        Args:
            include_content: Whether to include content preview (default True for search)
        
        Returns:
            List of prompt dictionaries with basic info
        """
        prompts = []
        
        for prompt_file in sorted(self.prompts_dir.glob("*.txt"), reverse=True):  # Newest first
            prompt_id = prompt_file.stem
            meta_file = self.prompts_dir / f"{prompt_id}.meta.json"
            
            metadata = {}
            if meta_file.exists():
                try:
                    metadata = json.loads(meta_file.read_text())
                except json.JSONDecodeError:
                    pass
            
            prompt_data = {
                "id": prompt_id,
                "tags": metadata.get("tags", []),
                "metadata": metadata
            }
            
            # Include content for client-side search
            if include_content:
                try:
                    content = prompt_file.read_text()
                    prompt_data["content"] = content
                except Exception:
                    prompt_data["content"] = ""
            
            prompts.append(prompt_data)
        
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
    
    def update_metadata(self, prompt_id: str, metadata: Dict) -> None:
        """
        Update metadata for a prompt.
        
        Args:
            prompt_id: The prompt identifier
            metadata: New metadata dictionary
        """
        meta_file = self.prompts_dir / f"{prompt_id}.meta.json"
        meta_file.write_text(json.dumps(metadata, indent=2))
    
    def get_chain(self, prompt_id: str) -> List[Dict]:
        """
        Get all prompts in a chain.
        
        Args:
            prompt_id: Any prompt ID in the chain
        
        Returns:
            List of prompts in chain order (oldest first)
        """
        prompt = self.get_prompt(prompt_id)
        chain_id = prompt.get("metadata", {}).get("chain_id", prompt_id)
        
        # Find all prompts with this chain_id or that are the chain root
        chain_prompts = []
        for p in self.list_prompts():
            p_chain_id = p.get("metadata", {}).get("chain_id")
            if p["id"] == chain_id or p_chain_id == chain_id:
                # Get full prompt with content
                full_prompt = self.get_prompt(p["id"])
                chain_prompts.append(full_prompt)
        
        # Sort by chain_position
        chain_prompts.sort(key=lambda x: x.get("metadata", {}).get("chain_position", 1))
        return chain_prompts
    
    def get_children(self, prompt_id: str) -> List[Dict]:
        """
        Get direct children of a prompt.
        
        Args:
            prompt_id: The parent prompt ID
        
        Returns:
            List of child prompts
        """
        children = []
        for p in self.list_prompts():
            if p.get("metadata", {}).get("parent_id") == prompt_id:
                children.append(self.get_prompt(p["id"]))
        return children
    
    def search_prompts(self, query: str, limit: int = 20) -> List[Dict]:
        """
        Search prompts by content, ID, tags, or hash.
        
        Args:
            query: Search query string
            limit: Maximum results to return
        
        Returns:
            List of matching prompts
        """
        query_lower = query.lower()
        results = []
        
        for prompt_file in self.prompts_dir.glob("*.txt"):
            prompt_id = prompt_file.stem
            
            # Check ID match
            if query_lower in prompt_id.lower():
                results.append(self.get_prompt(prompt_id))
                continue
            
            # Check content match
            content = prompt_file.read_text()
            if query_lower in content.lower():
                results.append(self.get_prompt(prompt_id))
                continue
            
            # Check metadata (tags, hash)
            meta_file = self.prompts_dir / f"{prompt_id}.meta.json"
            if meta_file.exists():
                try:
                    meta = json.loads(meta_file.read_text())
                    # Check tags
                    tags = meta.get("tags", [])
                    if any(query_lower in t.lower() for t in tags):
                        results.append(self.get_prompt(prompt_id))
                        continue
                    # Check hash
                    if query_lower == meta.get("content_hash", "").lower():
                        results.append(self.get_prompt(prompt_id))
                        continue
                except json.JSONDecodeError:
                    pass
            
            if len(results) >= limit:
                break
        
        return results[:limit]
    
    def has_chain(self, prompt_id: str) -> bool:
        """
        Check if a prompt is part of a chain.
        
        Args:
            prompt_id: The prompt ID
        
        Returns:
            True if prompt has parent or children
        """
        prompt = self.get_prompt(prompt_id)
        meta = prompt.get("metadata", {})
        
        # Has parent?
        if meta.get("parent_id"):
            return True
        
        # Has children?
        return len(self.get_children(prompt_id)) > 0
