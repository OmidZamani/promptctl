"""
DSPy Pipeline - Automated workflow orchestrator

Connects the complete automation pipeline:
  Browser Extension → Daemon Socket → PromptStore → DSPy → Git

Features:
- Auto-optimization on save (optional)
- Pipeline configuration
- Webhook notifications
- Batch processing
- Pipeline status tracking

Usage:
    pipeline = DSPyPipeline(repo_path="~/.promptctl")
    result = pipeline.process_prompt(content, name, tags, auto_optimize=True)
"""

import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List, Callable
from datetime import datetime
from dataclasses import dataclass, field

from .prompt_store import PromptStore
from .git_manager import GitManager
from .tag_manager import TagManager
from .job_queue import JobQueue, get_queue, start_queue

# Optional imports
try:
    from .dspy_optimizer import PromptOptimizer, HAS_DSPY
except ImportError:
    HAS_DSPY = False
    PromptOptimizer = None

try:
    from .agent import PromptAgent
    HAS_AGENT = True
except ImportError:
    HAS_AGENT = False
    PromptAgent = None


logger = logging.getLogger(__name__)


@dataclass
class PipelineConfig:
    """Pipeline configuration settings."""
    auto_optimize: bool = False
    optimization_rounds: int = 3
    auto_evaluate: bool = False
    use_local_ollama: bool = True
    min_score_threshold: float = 70.0
    auto_commit: bool = True
    commit_message_llm: bool = False
    webhook_url: Optional[str] = None
    default_tags: List[str] = field(default_factory=list)


@dataclass
class PipelineResult:
    """Result from pipeline processing."""
    prompt_id: str
    success: bool
    stages_completed: List[str]
    optimization_score: Optional[float] = None
    optimized_id: Optional[str] = None
    job_id: Optional[str] = None
    error: Optional[str] = None
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "prompt_id": self.prompt_id,
            "success": self.success,
            "stages_completed": self.stages_completed,
            "optimization_score": self.optimization_score,
            "optimized_id": self.optimized_id,
            "job_id": self.job_id,
            "error": self.error,
            "timestamp": self.timestamp
        }


class DSPyPipeline:
    """
    Complete DSPy automation pipeline.
    
    Orchestrates the full workflow:
    1. Receive prompt (from browser, CLI, or API)
    2. Store in PromptStore
    3. Optionally run DSPy optimization
    4. Commit to Git
    5. Send notifications
    """
    
    def __init__(
        self,
        repo_path: str = "~/.promptctl",
        config: Optional[PipelineConfig] = None
    ):
        """
        Initialize pipeline.
        
        Args:
            repo_path: Path to promptctl repository
            config: Pipeline configuration
        """
        self.repo_path = Path(repo_path).expanduser()
        self.config = config or PipelineConfig()
        
        # Initialize components
        self.store = PromptStore(str(self.repo_path))
        self.git_mgr = GitManager(str(self.repo_path))
        self.tag_mgr = TagManager(str(self.repo_path))
        
        # Ensure repo is initialized
        if not self.git_mgr.is_initialized():
            self.git_mgr.init()
        
        # Initialize job queue
        self.queue = get_queue()
        self._register_handlers()
        
        # Start queue if not running
        start_queue()
        
        logger.info(f"DSPyPipeline initialized (repo: {self.repo_path})")
    
    def _register_handlers(self) -> None:
        """Register job handlers for async processing."""
        self.queue.register_handler("optimize", self._handle_optimize_job)
        self.queue.register_handler("evaluate", self._handle_evaluate_job)
        self.queue.register_handler("chain", self._handle_chain_job)
        self.queue.register_handler("agent", self._handle_agent_job)
    
    def process_prompt(
        self,
        content: str,
        name: Optional[str] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        auto_optimize: Optional[bool] = None,
        source: str = "api"
    ) -> PipelineResult:
        """
        Process a prompt through the pipeline.
        
        Args:
            content: Prompt text content
            name: Optional prompt name
            tags: Optional tags
            metadata: Optional metadata
            auto_optimize: Override config auto_optimize
            source: Source identifier (browser, cli, api)
        
        Returns:
            PipelineResult with processing details
        """
        stages_completed = []
        
        try:
            # Stage 1: Save prompt
            combined_tags = list(set((tags or []) + self.config.default_tags))
            
            prompt_meta = metadata or {}
            prompt_meta["source"] = source
            prompt_meta["pipeline_processed"] = True
            
            prompt_id = self.store.save_prompt(
                content=content,
                name=name,
                tags=combined_tags,
                metadata=prompt_meta
            )
            stages_completed.append("save")
            logger.info(f"Pipeline: Saved prompt {prompt_id}")
            
            # Stage 2: Git commit
            if self.config.auto_commit:
                commit_msg = f"Pipeline: Save prompt {prompt_id}"
                if source == "browser":
                    commit_msg = f"Browser capture: {prompt_id}"
                
                self.git_mgr.commit(commit_msg)
                stages_completed.append("commit")
            
            # Stage 3: Auto-optimize (if enabled)
            should_optimize = auto_optimize if auto_optimize is not None else self.config.auto_optimize
            
            job_id = None
            if should_optimize and HAS_DSPY:
                # Submit optimization job
                job_id = self.queue.submit("optimize", {
                    "prompt_id": prompt_id,
                    "rounds": self.config.optimization_rounds,
                    "use_local_ollama": self.config.use_local_ollama
                })
                stages_completed.append("optimize_queued")
                logger.info(f"Pipeline: Queued optimization job {job_id}")
            
            return PipelineResult(
                prompt_id=prompt_id,
                success=True,
                stages_completed=stages_completed,
                job_id=job_id
            )
        
        except Exception as e:
            logger.error(f"Pipeline error: {e}")
            return PipelineResult(
                prompt_id=name or "unknown",
                success=False,
                stages_completed=stages_completed,
                error=str(e)
            )
    
    def optimize_prompt(
        self,
        prompt_id: str,
        rounds: Optional[int] = None,
        test_cases: Optional[List[Dict[str, str]]] = None,
        async_mode: bool = True
    ) -> Dict[str, Any]:
        """
        Optimize a prompt using DSPy.
        
        Args:
            prompt_id: ID of prompt to optimize
            rounds: Number of optimization rounds
            test_cases: Optional test cases for evaluation
            async_mode: Run asynchronously (returns job_id)
        
        Returns:
            If async: {"job_id": str}
            If sync: {"optimized_id": str, "score": float}
        """
        if not HAS_DSPY:
            return {"error": "DSPy not installed"}
        
        params = {
            "prompt_id": prompt_id,
            "rounds": rounds or self.config.optimization_rounds,
            "use_local_ollama": self.config.use_local_ollama,
            "test_cases": test_cases
        }
        
        if async_mode:
            job_id = self.queue.submit("optimize", params)
            return {"job_id": job_id, "status": "queued"}
        else:
            # Synchronous execution
            result = self._handle_optimize_job(params, lambda p, m: None)
            return result
    
    def evaluate_prompt(
        self,
        prompt_id: str,
        test_cases: List[Dict[str, str]],
        async_mode: bool = True
    ) -> Dict[str, Any]:
        """
        Evaluate a prompt against test cases.
        
        Args:
            prompt_id: ID of prompt to evaluate
            test_cases: Test cases with input/expected
            async_mode: Run asynchronously
        
        Returns:
            Evaluation results or job_id
        """
        if not HAS_DSPY:
            return {"error": "DSPy not installed"}
        
        params = {
            "prompt_id": prompt_id,
            "test_cases": test_cases,
            "use_local_ollama": self.config.use_local_ollama
        }
        
        if async_mode:
            job_id = self.queue.submit("evaluate", params)
            return {"job_id": job_id, "status": "queued"}
        else:
            result = self._handle_evaluate_job(params, lambda p, m: None)
            return result
    
    def chain_prompts(
        self,
        prompt_ids: List[str],
        chain_name: Optional[str] = None,
        async_mode: bool = True
    ) -> Dict[str, Any]:
        """
        Chain multiple prompts together.
        
        Args:
            prompt_ids: List of prompt IDs to chain
            chain_name: Name for the chain
            async_mode: Run asynchronously
        
        Returns:
            Chain result or job_id
        """
        if not HAS_DSPY:
            return {"error": "DSPy not installed"}
        
        params = {
            "prompt_ids": prompt_ids,
            "chain_name": chain_name,
            "use_local_ollama": self.config.use_local_ollama
        }
        
        if async_mode:
            job_id = self.queue.submit("chain", params)
            return {"job_id": job_id, "status": "queued"}
        else:
            result = self._handle_chain_job(params, lambda p, m: None)
            return result
    
    def run_agent(
        self,
        prompt_id: str,
        rounds: int = 5,
        min_score: float = 90.0,
        test_cases: Optional[List[Dict[str, str]]] = None,
        async_mode: bool = True
    ) -> Dict[str, Any]:
        """
        Run autonomous agent on a prompt.
        
        Args:
            prompt_id: ID of prompt to optimize
            rounds: Number of agent rounds
            min_score: Target score to stop early
            test_cases: Optional test cases
            async_mode: Run asynchronously
        
        Returns:
            Agent result or job_id
        """
        if not HAS_AGENT:
            return {"error": "Agent module not available"}
        
        params = {
            "prompt_id": prompt_id,
            "rounds": rounds,
            "min_score": min_score,
            "test_cases": test_cases
        }
        
        if async_mode:
            job_id = self.queue.submit("agent", params)
            return {"job_id": job_id, "status": "queued"}
        else:
            result = self._handle_agent_job(params, lambda p, m: None)
            return result
    
    def get_job_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get status of a background job."""
        return self.queue.get_status(job_id)
    
    def list_jobs(self, limit: int = 50) -> List[Dict[str, Any]]:
        """List all jobs."""
        return self.queue.get_all_jobs(limit)
    
    def list_prompts(
        self,
        tags: Optional[List[str]] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        List prompts with optional filtering.
        
        Args:
            tags: Filter by tags
            limit: Maximum number to return
        
        Returns:
            List of prompt info dicts
        """
        prompts = self.store.list_prompts()
        
        if tags:
            filtered_ids = self.tag_mgr.filter_by_tags(tags)
            prompts = [p for p in prompts if p["id"] in filtered_ids]
        
        return prompts[:limit]
    
    def get_prompt(self, prompt_id: str) -> Dict[str, Any]:
        """Get a specific prompt."""
        return self.store.get_prompt(prompt_id)
    
    # Job handlers
    def _handle_optimize_job(
        self,
        params: Dict[str, Any],
        progress_callback: Callable
    ) -> Dict[str, Any]:
        """Handle optimization job."""
        if not HAS_DSPY or PromptOptimizer is None:
            return {"error": "DSPy not installed"}
        
        progress_callback(10, "Initializing optimizer")
        
        optimizer = PromptOptimizer(
            repo_path=str(self.repo_path),
            use_local_ollama=params.get("use_local_ollama", True)
        )
        
        progress_callback(20, "Starting optimization")
        
        optimized_id, score = optimizer.optimize(
            prompt_id=params["prompt_id"],
            test_cases=params.get("test_cases"),
            rounds=params.get("rounds", 3)
        )
        
        progress_callback(90, "Optimization complete")
        
        # Commit result (if there are changes)
        if self.config.auto_commit:
            try:
                self.git_mgr.commit(
                    f"DSPy optimization: {params['prompt_id']} -> {optimized_id} "
                    f"(score: {score:.2f})"
                )
            except ValueError:
                # No changes to commit - that's fine
                pass
        
        progress_callback(100, "Done")
        
        return {
            "optimized_id": optimized_id,
            "score": score,
            "source_prompt": params["prompt_id"],
            "rounds": params.get("rounds", 3)
        }
    
    def _handle_evaluate_job(
        self,
        params: Dict[str, Any],
        progress_callback: Callable
    ) -> Dict[str, Any]:
        """Handle evaluation job."""
        if not HAS_DSPY or PromptOptimizer is None:
            return {"error": "DSPy not installed"}
        
        progress_callback(10, "Initializing evaluator")
        
        optimizer = PromptOptimizer(
            repo_path=str(self.repo_path),
            use_local_ollama=params.get("use_local_ollama", True)
        )
        
        progress_callback(30, "Running evaluation")
        
        report = optimizer.evaluate(
            prompt_id=params["prompt_id"],
            test_cases=params["test_cases"]
        )
        
        progress_callback(100, "Done")
        
        return report
    
    def _handle_chain_job(
        self,
        params: Dict[str, Any],
        progress_callback: Callable
    ) -> Dict[str, Any]:
        """Handle chain creation job."""
        if not HAS_DSPY or PromptOptimizer is None:
            return {"error": "DSPy not installed"}
        
        progress_callback(10, "Initializing")
        
        optimizer = PromptOptimizer(
            repo_path=str(self.repo_path),
            use_local_ollama=params.get("use_local_ollama", True)
        )
        
        progress_callback(30, "Creating chain")
        
        chain_id = optimizer.chain_prompts(
            prompt_ids=params["prompt_ids"],
            chain_name=params.get("chain_name")
        )
        
        progress_callback(100, "Done")
        
        return {
            "chain_id": chain_id,
            "source_prompts": params["prompt_ids"]
        }
    
    def _handle_agent_job(
        self,
        params: Dict[str, Any],
        progress_callback: Callable
    ) -> Dict[str, Any]:
        """Handle agent job."""
        if not HAS_AGENT or PromptAgent is None:
            return {"error": "Agent module not available"}
        
        progress_callback(10, "Initializing agent")
        
        agent = PromptAgent(
            prompt_id=params["prompt_id"],
            repo_path=str(self.repo_path),
            test_cases=params.get("test_cases")
        )
        
        progress_callback(20, "Running agent")
        
        best_id, score = agent.run(
            rounds=params.get("rounds", 5),
            min_score=params.get("min_score", 90.0)
        )
        
        progress_callback(90, "Agent complete")
        
        # Commit result
        if self.config.auto_commit:
            self.git_mgr.commit(
                f"Agent optimization: {params['prompt_id']} -> {best_id} "
                f"(score: {score:.2f})"
            )
        
        progress_callback(100, "Done")
        
        report = agent.get_report()
        report["best_id"] = best_id
        report["final_score"] = score
        
        return report


# Singleton pipeline instance
_default_pipeline: Optional[DSPyPipeline] = None


def get_pipeline(repo_path: str = "~/.promptctl") -> DSPyPipeline:
    """Get or create the default pipeline instance."""
    global _default_pipeline
    if _default_pipeline is None:
        _default_pipeline = DSPyPipeline(repo_path)
    return _default_pipeline
