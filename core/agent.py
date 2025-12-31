"""
Agentic Mode - Autonomous prompt testing and self-improvement

This module provides an agentic framework that:
- Executes prompts against LLMs autonomously
- Scores results using metrics
- Self-improves through iterative feedback
- Tracks quality over multiple rounds
- Reports progress and results

Usage:
    agent = PromptAgent(prompt_id="my-prompt")
    best_version, score = agent.run(rounds=5)
"""

import json
import logging
import time
from pathlib import Path
from typing import List, Dict, Any, Optional, Callable, Tuple
from datetime import datetime
from dataclasses import dataclass, asdict

# Optional requests for LLM integration
try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False
    logging.warning("requests not installed. Install with: pip install requests")

from .prompt_store import PromptStore
from .git_manager import GitManager
from .tag_manager import TagManager


logger = logging.getLogger(__name__)


@dataclass
class TestResult:
    """Result from a single test execution."""
    test_input: str
    expected: str
    actual: str
    score: float
    execution_time: float
    timestamp: str


@dataclass
class AgentRound:
    """Results from one agent improvement round."""
    round_num: int
    prompt_version: str
    test_results: List[TestResult]
    average_score: float
    improvements_made: List[str]
    timestamp: str


class PromptAgent:
    """
    Autonomous agent for prompt testing and improvement.
    
    Features:
    - Auto-execution against LLM
    - Self-testing loop with metrics
    - Iterative refinement
    - Quality scoring (0-100)
    - Progress tracking and reporting
    """
    
    def __init__(
        self,
        prompt_id: str,
        repo_path: str = "~/.promptctl",
        test_cases: Optional[List[Dict[str, str]]] = None,
        llm_url: str = "http://localhost:11434/api/generate",
        llm_model: str = "phi3.5"
    ):
        """
        Initialize the agent.
        
        Args:
            prompt_id: ID of prompt to work with
            repo_path: Path to promptctl repository
            test_cases: Optional list of {"input": str, "expected": str}
            llm_url: LLM API endpoint (default: Ollama)
            llm_model: Model to use for execution
        """
        self.prompt_id = prompt_id
        self.repo_path = Path(repo_path).expanduser()
        self.llm_url = llm_url
        self.llm_model = llm_model
        
        # Initialize managers
        self.store = PromptStore(str(self.repo_path))
        self.git_mgr = GitManager(str(self.repo_path))
        self.tag_mgr = TagManager(str(self.repo_path))
        
        # Load initial prompt
        self.initial_prompt = self.store.get_prompt(prompt_id)
        self.current_prompt = self.initial_prompt['content']
        
        # Test cases
        self.test_cases = test_cases or self._generate_default_test_cases()
        
        # History
        self.rounds: List[AgentRound] = []
        self.best_score = 0.0
        self.best_prompt = self.current_prompt
        
        if not HAS_REQUESTS:
            logger.warning("requests not installed, LLM execution will be simulated")
        
        logger.info(f"PromptAgent initialized for prompt: {prompt_id}")
    
    def _generate_default_test_cases(self) -> List[Dict[str, str]]:
        """Generate default test cases based on prompt content."""
        # Simple default test cases
        return [
            {"input": "Test input 1", "expected": "Expected output 1"},
            {"input": "Test input 2", "expected": "Expected output 2"},
            {"input": "Test input 3", "expected": "Expected output 3"}
        ]
    
    def execute_prompt(
        self,
        prompt: str,
        test_input: str,
        timeout: float = 30.0
    ) -> Tuple[str, float]:
        """
        Execute a prompt with given input against LLM.
        
        Args:
            prompt: The prompt to execute
            test_input: Input to pass to the prompt
            timeout: Timeout in seconds
        
        Returns:
            Tuple of (output, execution_time)
        """
        start_time = time.time()
        
        if not HAS_REQUESTS:
            # Simulate execution
            output = f"[SIMULATED] Output for: {test_input}"
            execution_time = 0.5
            return output, execution_time
        
        try:
            # Combine prompt with input
            full_prompt = f"{prompt}\n\nInput: {test_input}\nOutput:"
            
            response = requests.post(
                self.llm_url,
                json={
                    "model": self.llm_model,
                    "prompt": full_prompt,
                    "stream": False,
                    "options": {"temperature": 0.7}
                },
                timeout=timeout
            )
            
            if response.status_code == 200:
                result = response.json()
                output = result.get("response", "").strip()
                execution_time = time.time() - start_time
                return output, execution_time
            else:
                logger.warning(f"LLM request failed: {response.status_code}")
                return f"[ERROR] Status {response.status_code}", time.time() - start_time
        
        except Exception as e:
            logger.error(f"Execution failed: {e}")
            return f"[ERROR] {str(e)}", time.time() - start_time
    
    def score_result(
        self,
        actual: str,
        expected: str,
        metric_fn: Optional[Callable[[str, str], float]] = None
    ) -> float:
        """
        Score a result against expected output.
        
        Args:
            actual: Actual output from LLM
            expected: Expected output
            metric_fn: Optional custom scoring function
        
        Returns:
            Score from 0-100
        """
        if metric_fn:
            return metric_fn(actual, expected)
        
        # Default metric: fuzzy substring matching with case insensitivity
        actual_lower = actual.lower()
        expected_lower = expected.lower()
        
        # Exact match
        if actual_lower == expected_lower:
            return 100.0
        
        # Substring match
        if expected_lower in actual_lower:
            return 80.0
        
        # Word overlap scoring
        actual_words = set(actual_lower.split())
        expected_words = set(expected_lower.split())
        
        if not expected_words:
            return 0.0
        
        overlap = len(actual_words & expected_words)
        overlap_ratio = overlap / len(expected_words)
        
        return overlap_ratio * 60.0  # Max 60 points for word overlap
    
    def test_prompt(
        self,
        prompt: str,
        metric_fn: Optional[Callable[[str, str], float]] = None
    ) -> List[TestResult]:
        """
        Test a prompt against all test cases.
        
        Args:
            prompt: The prompt to test
            metric_fn: Optional custom scoring function
        
        Returns:
            List of TestResult objects
        """
        results = []
        
        for test_case in self.test_cases:
            test_input = test_case['input']
            expected = test_case['expected']
            
            # Execute
            actual, exec_time = self.execute_prompt(prompt, test_input)
            
            # Score
            score = self.score_result(actual, expected, metric_fn)
            
            result = TestResult(
                test_input=test_input,
                expected=expected,
                actual=actual,
                score=score,
                execution_time=exec_time,
                timestamp=datetime.now().isoformat()
            )
            
            results.append(result)
            logger.debug(f"Test '{test_input}': score={score:.2f}")
        
        return results
    
    def analyze_results(self, results: List[TestResult]) -> str:
        """
        Analyze test results and generate improvement suggestions.
        
        Args:
            results: List of test results
        
        Returns:
            Improvement suggestions as text
        """
        avg_score = sum(r.score for r in results) / len(results) if results else 0.0
        
        suggestions = []
        
        # Overall performance
        if avg_score < 30:
            suggestions.append("Major rewrite needed: prompt is not producing relevant outputs")
        elif avg_score < 60:
            suggestions.append("Significant improvements needed: add more context and examples")
        elif avg_score < 85:
            suggestions.append("Good performance: refine edge cases and improve clarity")
        else:
            suggestions.append("Excellent performance: minor optimizations only")
        
        # Find failing cases
        failing = [r for r in results if r.score < 50]
        if failing:
            suggestions.append(f"Focus on {len(failing)} failing test cases")
            for result in failing[:2]:  # Show top 2
                suggestions.append(f"  - Input '{result.test_input}' needs work")
        
        # Execution time
        avg_time = sum(r.execution_time for r in results) / len(results)
        if avg_time > 10.0:
            suggestions.append("Consider optimizing for faster execution")
        
        return " | ".join(suggestions)
    
    def improve_prompt(
        self,
        current_prompt: str,
        feedback: str,
        results: List[TestResult]
    ) -> str:
        """
        Generate an improved version of the prompt.
        
        Args:
            current_prompt: Current prompt text
            feedback: Feedback from analysis
            results: Test results
        
        Returns:
            Improved prompt text
        """
        if not HAS_REQUESTS:
            # Simulated improvement
            return f"{current_prompt}\n\n[IMPROVED based on: {feedback}]"
        
        try:
            # Create improvement prompt
            improvement_prompt = f"""You are a prompt engineering expert. Improve this prompt based on test results.

Current prompt:
{current_prompt}

Test feedback:
{feedback}

Test results summary:
{self._summarize_results(results)}

Generate an improved version that addresses the issues. Return ONLY the improved prompt, no explanation.

Improved prompt:"""
            
            response = requests.post(
                self.llm_url,
                json={
                    "model": self.llm_model,
                    "prompt": improvement_prompt,
                    "stream": False,
                    "options": {"temperature": 0.8}
                },
                timeout=60.0
            )
            
            if response.status_code == 200:
                result = response.json()
                improved = result.get("response", "").strip()
                return improved if improved else current_prompt
        
        except Exception as e:
            logger.error(f"Improvement generation failed: {e}")
        
        return current_prompt
    
    def _summarize_results(self, results: List[TestResult]) -> str:
        """Create a summary of test results."""
        if not results:
            return "No results"
        
        avg_score = sum(r.score for r in results) / len(results)
        passed = sum(1 for r in results if r.score >= 70)
        
        summary = f"Average: {avg_score:.1f}/100, Passed: {passed}/{len(results)}"
        
        # Add worst case
        worst = min(results, key=lambda r: r.score)
        summary += f" | Worst: '{worst.test_input}' ({worst.score:.1f})"
        
        return summary
    
    def run(
        self,
        rounds: int = 5,
        metric_fn: Optional[Callable[[str, str], float]] = None,
        min_score: float = 90.0
    ) -> Tuple[str, float]:
        """
        Run the autonomous agent for N rounds.
        
        Args:
            rounds: Number of improvement rounds
            metric_fn: Optional custom scoring function
            min_score: Stop early if this score is reached
        
        Returns:
            Tuple of (best_prompt_id, best_score)
        """
        logger.info(f"Starting agent run: {rounds} rounds, target score: {min_score}")
        
        for round_num in range(1, rounds + 1):
            logger.info(f"\n=== ROUND {round_num}/{rounds} ===")
            
            # Test current prompt
            results = self.test_prompt(self.current_prompt, metric_fn)
            avg_score = sum(r.score for r in results) / len(results) if results else 0.0
            
            logger.info(f"Round {round_num} score: {avg_score:.2f}/100")
            
            # Track best
            if avg_score > self.best_score:
                self.best_score = avg_score
                self.best_prompt = self.current_prompt
                logger.info(f"New best score: {avg_score:.2f}")
            
            # Analyze and improve
            feedback = self.analyze_results(results)
            logger.info(f"Feedback: {feedback}")
            
            # Save round data
            round_data = AgentRound(
                round_num=round_num,
                prompt_version=self.current_prompt[:100] + "...",
                test_results=results,
                average_score=avg_score,
                improvements_made=[feedback],
                timestamp=datetime.now().isoformat()
            )
            self.rounds.append(round_data)
            
            # Check if target reached
            if avg_score >= min_score:
                logger.info(f"Target score {min_score} reached! Stopping early.")
                break
            
            # Generate improvement for next round
            if round_num < rounds:
                self.current_prompt = self.improve_prompt(
                    self.current_prompt,
                    feedback,
                    results
                )
        
        # Save best version
        best_id = self._save_best_version()
        
        logger.info(f"\n=== AGENT RUN COMPLETE ===")
        logger.info(f"Best score: {self.best_score:.2f}/100")
        logger.info(f"Best version saved as: {best_id}")
        
        return best_id, self.best_score
    
    def _save_best_version(self) -> str:
        """Save the best prompt version."""
        best_id = self.store.save_prompt(
            content=self.best_prompt,
            name=f"{self.prompt_id}_agent_optimized",
            tags=["agent-optimized", "tested"],
            metadata={
                "source_prompt": self.prompt_id,
                "agent_rounds": len(self.rounds),
                "final_score": self.best_score,
                "optimized_at": datetime.now().isoformat()
            }
        )
        
        self.git_mgr.commit(
            f"Agent optimization: {self.prompt_id} -> {best_id} "
            f"(score: {self.best_score:.2f}, rounds: {len(self.rounds)})"
        )
        
        return best_id
    
    def get_report(self) -> Dict[str, Any]:
        """
        Generate a detailed report of the agent run.
        
        Returns:
            Report dictionary with all round data
        """
        report = {
            "prompt_id": self.prompt_id,
            "total_rounds": len(self.rounds),
            "best_score": self.best_score,
            "initial_score": self.rounds[0].average_score if self.rounds else 0.0,
            "improvement": self.best_score - (self.rounds[0].average_score if self.rounds else 0.0),
            "rounds": [asdict(r) for r in self.rounds],
            "test_cases_count": len(self.test_cases),
            "generated_at": datetime.now().isoformat()
        }
        
        return report
    
    def print_report(self):
        """Print a human-readable report."""
        report = self.get_report()
        
        print("\n" + "=" * 60)
        print("AGENT OPTIMIZATION REPORT")
        print("=" * 60)
        print(f"Prompt ID: {report['prompt_id']}")
        print(f"Rounds: {report['total_rounds']}")
        print(f"Test cases: {report['test_cases_count']}")
        print(f"\nInitial score: {report['initial_score']:.2f}/100")
        print(f"Final score: {report['best_score']:.2f}/100")
        print(f"Improvement: +{report['improvement']:.2f}")
        print("\n" + "-" * 60)
        print("ROUND BREAKDOWN")
        print("-" * 60)
        
        for round_data in report['rounds']:
            print(f"\nRound {round_data['round_num']}:")
            print(f"  Score: {round_data['average_score']:.2f}/100")
            print(f"  Improvements: {', '.join(round_data['improvements_made'])}")
        
        print("\n" + "=" * 60)


def quick_test(
    prompt_id: str,
    test_cases: List[Dict[str, str]],
    repo_path: str = "~/.promptctl"
) -> float:
    """
    Quick test utility function.
    
    Args:
        prompt_id: Prompt to test
        test_cases: List of test cases
        repo_path: Repository path
    
    Returns:
        Average score
    """
    agent = PromptAgent(prompt_id, repo_path, test_cases)
    results = agent.test_prompt(agent.current_prompt)
    avg_score = sum(r.score for r in results) / len(results) if results else 0.0
    
    print(f"\nTest Results for {prompt_id}:")
    print(f"Average score: {avg_score:.2f}/100")
    for i, result in enumerate(results, 1):
        print(f"  Test {i}: {result.score:.2f}/100")
    
    return avg_score
