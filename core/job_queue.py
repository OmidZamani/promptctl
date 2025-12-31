"""
Job Queue - Background processing for DSPy operations

Provides asynchronous job processing for long-running DSPy operations:
- Optimization jobs
- Chain creation jobs
- Evaluation jobs
- Agent improvement jobs

Usage:
    queue = JobQueue()
    job_id = queue.submit("optimize", {"prompt_id": "my-prompt", "rounds": 3})
    status = queue.get_status(job_id)
"""

import uuid
import time
import logging
import threading
from queue import Queue, Empty
from typing import Dict, Any, Optional, Callable, List
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum


logger = logging.getLogger(__name__)


class JobStatus(Enum):
    """Job status states."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class Job:
    """Represents a background job."""
    id: str
    job_type: str
    params: Dict[str, Any]
    status: JobStatus = JobStatus.PENDING
    progress: float = 0.0
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert job to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "job_type": self.job_type,
            "params": self.params,
            "status": self.status.value,
            "progress": self.progress,
            "result": self.result,
            "error": self.error,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at
        }


class JobQueue:
    """
    Thread-safe background job queue for DSPy operations.
    
    Features:
    - Async job submission
    - Status tracking
    - Progress updates
    - Result storage
    - Job history
    """
    
    def __init__(self, max_workers: int = 2, max_history: int = 100):
        """
        Initialize job queue.
        
        Args:
            max_workers: Maximum concurrent workers
            max_history: Maximum completed jobs to keep in history
        """
        self.max_workers = max_workers
        self.max_history = max_history
        
        self._queue: Queue = Queue()
        self._jobs: Dict[str, Job] = {}
        self._workers: List[threading.Thread] = []
        self._handlers: Dict[str, Callable] = {}
        self._lock = threading.Lock()
        self._running = False
        
        logger.info(f"JobQueue initialized (workers: {max_workers})")
    
    def register_handler(self, job_type: str, handler: Callable) -> None:
        """
        Register a handler function for a job type.
        
        Args:
            job_type: Type identifier (e.g., "optimize", "chain")
            handler: Callable that takes (job, progress_callback) and returns result dict
        """
        self._handlers[job_type] = handler
        logger.debug(f"Registered handler for job type: {job_type}")
    
    def start(self) -> None:
        """Start the worker threads."""
        if self._running:
            return
        
        self._running = True
        
        for i in range(self.max_workers):
            worker = threading.Thread(
                target=self._worker_loop,
                name=f"JobWorker-{i}",
                daemon=True
            )
            worker.start()
            self._workers.append(worker)
        
        logger.info(f"Started {self.max_workers} job workers")
    
    def stop(self) -> None:
        """Stop the worker threads."""
        self._running = False
        
        # Put None to unblock workers
        for _ in self._workers:
            self._queue.put(None)
        
        # Wait for workers to finish
        for worker in self._workers:
            worker.join(timeout=5)
        
        self._workers.clear()
        logger.info("Job workers stopped")
    
    def submit(
        self,
        job_type: str,
        params: Dict[str, Any],
        job_id: Optional[str] = None
    ) -> str:
        """
        Submit a new job.
        
        Args:
            job_type: Type of job (must have registered handler)
            params: Job parameters
            job_id: Optional custom job ID
        
        Returns:
            Job ID
        
        Raises:
            ValueError: If no handler registered for job type
        """
        if job_type not in self._handlers:
            raise ValueError(f"No handler registered for job type: {job_type}")
        
        job = Job(
            id=job_id or str(uuid.uuid4())[:8],
            job_type=job_type,
            params=params
        )
        
        with self._lock:
            self._jobs[job.id] = job
        
        self._queue.put(job.id)
        
        logger.info(f"Submitted job: {job.id} ({job_type})")
        return job.id
    
    def get_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        """
        Get status of a job.
        
        Args:
            job_id: Job identifier
        
        Returns:
            Job status dict or None if not found
        """
        with self._lock:
            job = self._jobs.get(job_id)
            if job:
                return job.to_dict()
        return None
    
    def get_all_jobs(self, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Get all jobs (most recent first).
        
        Args:
            limit: Maximum number of jobs to return
        
        Returns:
            List of job status dicts
        """
        with self._lock:
            jobs = list(self._jobs.values())
            jobs.sort(key=lambda j: j.created_at, reverse=True)
            return [j.to_dict() for j in jobs[:limit]]
    
    def cancel(self, job_id: str) -> bool:
        """
        Cancel a pending job.
        
        Args:
            job_id: Job identifier
        
        Returns:
            True if cancelled, False if not found or already running
        """
        with self._lock:
            job = self._jobs.get(job_id)
            if job and job.status == JobStatus.PENDING:
                job.status = JobStatus.CANCELLED
                job.completed_at = datetime.now().isoformat()
                logger.info(f"Cancelled job: {job_id}")
                return True
        return False
    
    def _worker_loop(self) -> None:
        """Worker thread main loop."""
        while self._running:
            try:
                job_id = self._queue.get(timeout=1)
                
                if job_id is None:
                    break
                
                self._process_job(job_id)
                
            except Empty:
                continue
            except Exception as e:
                logger.error(f"Worker error: {e}")
    
    def _process_job(self, job_id: str) -> None:
        """Process a single job."""
        with self._lock:
            job = self._jobs.get(job_id)
            if not job or job.status != JobStatus.PENDING:
                return
            
            job.status = JobStatus.RUNNING
            job.started_at = datetime.now().isoformat()
        
        handler = self._handlers.get(job.job_type)
        if not handler:
            self._fail_job(job_id, f"No handler for job type: {job.job_type}")
            return
        
        logger.info(f"Processing job: {job_id} ({job.job_type})")
        
        def progress_callback(progress: float, message: str = "") -> None:
            """Update job progress."""
            with self._lock:
                if job_id in self._jobs:
                    self._jobs[job_id].progress = min(100.0, max(0.0, progress))
                    if message:
                        logger.debug(f"Job {job_id}: {progress:.1f}% - {message}")
        
        try:
            result = handler(job.params, progress_callback)
            self._complete_job(job_id, result)
        except Exception as e:
            logger.error(f"Job {job_id} failed: {e}")
            self._fail_job(job_id, str(e))
    
    def _complete_job(self, job_id: str, result: Dict[str, Any]) -> None:
        """Mark job as completed."""
        with self._lock:
            job = self._jobs.get(job_id)
            if job:
                job.status = JobStatus.COMPLETED
                job.progress = 100.0
                job.result = result
                job.completed_at = datetime.now().isoformat()
        
        logger.info(f"Completed job: {job_id}")
        self._cleanup_history()
    
    def _fail_job(self, job_id: str, error: str) -> None:
        """Mark job as failed."""
        with self._lock:
            job = self._jobs.get(job_id)
            if job:
                job.status = JobStatus.FAILED
                job.error = error
                job.completed_at = datetime.now().isoformat()
        
        logger.error(f"Failed job: {job_id} - {error}")
    
    def _cleanup_history(self) -> None:
        """Remove old completed jobs if over limit."""
        with self._lock:
            completed = [
                j for j in self._jobs.values()
                if j.status in (JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED)
            ]
            
            if len(completed) > self.max_history:
                # Remove oldest completed jobs
                completed.sort(key=lambda j: j.completed_at or "")
                to_remove = completed[:len(completed) - self.max_history]
                
                for job in to_remove:
                    del self._jobs[job.id]


# Singleton instance for global access
_default_queue: Optional[JobQueue] = None


def get_queue() -> JobQueue:
    """Get the default job queue instance."""
    global _default_queue
    if _default_queue is None:
        _default_queue = JobQueue()
    return _default_queue


def start_queue() -> JobQueue:
    """Start the default job queue."""
    queue = get_queue()
    queue.start()
    return queue


def stop_queue() -> None:
    """Stop the default job queue."""
    global _default_queue
    if _default_queue:
        _default_queue.stop()
