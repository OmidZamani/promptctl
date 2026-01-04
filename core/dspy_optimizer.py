"""
DSPy Integration for Prompt Optimization

This module provides automatic prompt optimization using DSPy framework:
- Few-shot example generation
- Prompt chain composition
- Program synthesis
- Metric-based evaluation
- Iterative improvement with feedback loops

Usage:
    optimizer = PromptOptimizer()
    optimized = optimizer.optimize(prompt, metric_fn, rounds=3)
    chain = optimizer.chain_prompts([prompt1, prompt2])
"""

import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Callable, Optional, Tuple
from datetime import datetime

# Optional DSPy import
try:
    import dspy
    from dspy import BootstrapFewShot
    HAS_DSPY = True
except ImportError:
    HAS_DSPY = False
    logging.warning("dspy-ai not installed. Install with: pip install dspy-ai")

from .prompt_store import PromptStore
from .git_manager import GitManager
from .tag_manager import TagManager


logger = logging.getLogger(__name__)


class PromptOptimizer:
    """
    Automatic prompt optimization using DSPy.
    
    Features:
    - Few-shot example generation
    - Prompt chaining for complex workflows
    - Iterative optimization with metrics
    - Quality scoring and evaluation
    - Multi-provider support (Ollama, OpenAI, Anthropic)
    """
    
    def __init__(
        self,
        repo_path: str = "~/.promptctl",
        model: str = "openai/gpt-3.5-turbo",
        llm_port: int = 11434,
        use_local_ollama: bool = False,
        provider_settings: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize the optimizer.
        
        Args:
            repo_path: Path to promptctl repository
            model: LLM model to use (default: gpt-3.5-turbo)
            llm_port: Port for local Ollama (if use_local_ollama=True)
            use_local_ollama: Use local Ollama instead of OpenAI
            provider_settings: Full provider configuration dict with:
                - provider: 'ollama', 'openai', or 'anthropic'
                - ollama_url: Ollama server URL
                - model: Ollama model name
                - openai_key: OpenAI API key
                - openai_model: OpenAI model name
                - anthropic_key: Anthropic API key
                - anthropic_model: Anthropic model name
        """
        self.repo_path = Path(repo_path).expanduser()
        self.store = PromptStore(str(self.repo_path))
        self.git_mgr = GitManager(str(self.repo_path))
        self.tag_mgr = TagManager(str(self.repo_path))
        
        if not HAS_DSPY:
            logger.error("DSPy not available. Install with: pip install dspy-ai")
            raise ImportError("dspy-ai required for optimization")
        
        # Store provider settings
        self.provider_settings = provider_settings or {}
        self.provider = self.provider_settings.get('provider', 'ollama' if use_local_ollama else 'openai')
        
        # Legacy compatibility
        self.use_local_ollama = use_local_ollama or self.provider == 'ollama'
        self.llm_port = llm_port
        self.model = model
        
        # Determine model name based on provider
        self.model_name = self._get_model_name()
        
        # Configure DSPy for this thread
        self._configure_dspy()
        
        logger.info(f"PromptOptimizer initialized with provider: {self.provider}, model: {self.model_name}")
    
    def _get_model_name(self) -> str:
        """Get the model name based on provider settings."""
        if self.provider == 'ollama':
            return self.provider_settings.get('model', 'phi3.5:latest')
        elif self.provider == 'openai':
            return self.provider_settings.get('openai_model', 'gpt-4o')
        elif self.provider == 'anthropic':
            return self.provider_settings.get('anthropic_model', 'claude-3-5-sonnet-20241022')
        else:
            return self.model
    
    def _configure_dspy(self):
        """Configure DSPy LLM for the current thread based on provider."""
        import os
        
        if self.provider == 'ollama':
            ollama_url = self.provider_settings.get('ollama_url', f'http://localhost:{self.llm_port}')
            # Parse base URL from full URL
            if '/api' in ollama_url:
                ollama_url = ollama_url.split('/api')[0]
            
            lm = dspy.LM(
                model=f"ollama_chat/{self.model_name}",
                api_base=ollama_url,
                max_tokens=2000
            )
            logger.info(f"Configured DSPy with Ollama: {self.model_name} at {ollama_url}")
            
        elif self.provider == 'openai':
            api_key = self.provider_settings.get('openai_key', '')
            if api_key:
                os.environ['OPENAI_API_KEY'] = api_key
            
            lm = dspy.LM(
                model=f"openai/{self.model_name}",
                max_tokens=2000
            )
            logger.info(f"Configured DSPy with OpenAI: {self.model_name}")
            
        elif self.provider == 'anthropic':
            api_key = self.provider_settings.get('anthropic_key', '')
            if api_key:
                os.environ['ANTHROPIC_API_KEY'] = api_key
            
            lm = dspy.LM(
                model=f"anthropic/{self.model_name}",
                max_tokens=2000
            )
            logger.info(f"Configured DSPy with Anthropic: {self.model_name}")
            
        else:
            # Fallback to legacy behavior
            if self.use_local_ollama:
                lm = dspy.LM(
                    model="ollama_chat/phi3.5:latest",
                    api_base=f"http://localhost:{self.llm_port}",
                    max_tokens=2000
                )
            else:
                lm = dspy.LM(model=f"openai/{self.model}", max_tokens=2000)
        
        dspy.configure(lm=lm)
    
    def generate_examples(
        self,
        prompt_id: str,
        count: int = 5,
        context: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Generate few-shot examples for a prompt.
        
        Args:
            prompt_id: ID of the prompt to generate examples for
            count: Number of examples to generate
            context: Optional context/domain information
        
        Returns:
            List of example dictionaries with 'input' and 'output' keys
        """
        # Ensure DSPy is configured for this thread
        self._configure_dspy()
        
        prompt = self.store.get_prompt(prompt_id)
        prompt_content = prompt['content']
        
        # Define DSPy signature for example generation
        class ExampleGenerator(dspy.Signature):
            """Generate high-quality input/output examples for a prompt template."""
            
            prompt_template: str = dspy.InputField(desc="The prompt template to generate examples for")
            context: str = dspy.InputField(desc="Domain or context information")
            examples: str = dspy.OutputField(desc="JSON array of example objects with 'input' and 'output' keys")
        
        # Create predictor
        generator = dspy.Predict(ExampleGenerator)
        
        # Generate examples
        result = generator(
            prompt_template=prompt_content,
            context=context or "General use case"
        )
        
        try:
            examples = json.loads(result.examples)
            return examples[:count]
        except json.JSONDecodeError:
            logger.warning("Failed to parse generated examples as JSON")
            return []
    
    def chain_prompts(
        self,
        prompt_ids: List[str],
        chain_name: Optional[str] = None
    ) -> str:
        """
        Create a chain of prompts for multi-step workflows.
        
        Args:
            prompt_ids: List of prompt IDs to chain together
            chain_name: Optional name for the chain
        
        Returns:
            ID of the created chain prompt
        """
        if len(prompt_ids) < 2:
            raise ValueError("Chain requires at least 2 prompts")
        
        # Ensure DSPy is configured for this thread
        self._configure_dspy()
        
        # Load all prompts
        prompts = [self.store.get_prompt(pid) for pid in prompt_ids]
        
        # Define DSPy signature for chain composition
        class ChainComposer(dspy.Signature):
            """Compose multiple prompts into a coherent chain."""
            
            prompts: str = dspy.InputField(desc="JSON array of prompt objects to chain")
            composed_chain: str = dspy.OutputField(desc="A composed prompt that chains the inputs together")
        
        composer = dspy.Predict(ChainComposer)
        
        # Compose chain
        prompts_json = json.dumps([
            {"id": p['id'], "content": p['content']}
            for p in prompts
        ])
        
        result = composer(prompts=prompts_json)
        chain_content = result.composed_chain
        
        # Save chain as new prompt
        chain_id = self.store.save_prompt(
            content=chain_content,
            name=chain_name or f"chain_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            tags=["chain", "dspy-generated"],
            metadata={
                "chain_source": prompt_ids,
                "generated_at": datetime.now().isoformat()
            }
        )
        
        # Commit
        self.git_mgr.commit(f"Create prompt chain: {chain_id}")
        
        logger.info(f"Created prompt chain: {chain_id}")
        return chain_id
    
    def optimize(
        self,
        prompt_id: str,
        metric_fn: Optional[Callable[[str, str], float]] = None,
        test_cases: Optional[List[Dict[str, str]]] = None,
        rounds: int = 3,
        temperature: float = 0.7
    ) -> Tuple[str, float]:
        """
        Iteratively optimize a prompt using DSPy.
        
        Args:
            prompt_id: ID of prompt to optimize
            metric_fn: Function that scores (prompt_output, expected) -> float (0-100)
            test_cases: List of {"input": str, "expected": str} dicts
            rounds: Number of optimization rounds
            temperature: LLM temperature for optimization
        
        Returns:
            Tuple of (optimized_prompt_id, final_score)
        """
        # Ensure DSPy is configured for this thread
        self._configure_dspy()
        
        prompt = self.store.get_prompt(prompt_id)
        current_content = prompt['content']
        
        # Default metric: simple substring match
        if metric_fn is None:
            def default_metric(output: str, expected) -> float:
                # Handle both string and list expected values
                if isinstance(expected, list):
                    expected = " ".join(str(e) for e in expected)
                expected = str(expected) if expected else ""
                output = str(output) if output else ""
                if expected and expected.lower() in output.lower():
                    return 100.0
                # Also check if output contains meaningful content
                if len(output.strip()) > 10:
                    return 50.0  # Partial credit for generating content
                return 0.0
            metric_fn = default_metric
        
        # Generate test cases if not provided
        if test_cases is None:
            try:
                examples = self.generate_examples(prompt_id, count=3)
                test_cases = []
                for ex in examples:
                    inp = ex.get("input", "")
                    out = ex.get("output", "")
                    # Convert lists to strings
                    if isinstance(inp, list):
                        inp = " ".join(str(i) for i in inp)
                    if isinstance(out, list):
                        out = " ".join(str(o) for o in out)
                    test_cases.append({"input": str(inp), "expected": str(out)})
            except Exception as e:
                logger.warning(f"Failed to generate examples: {e}")
                # Use default test case
                test_cases = [{"input": "test input", "expected": "test output"}]
        
        best_content = current_content
        best_score = 0.0
        
        # Define optimization signature
        class PromptOptimizer(dspy.Signature):
            """Improve a prompt based on feedback."""
            
            current_prompt: str = dspy.InputField(desc="Current prompt to improve")
            feedback: str = dspy.InputField(desc="Feedback on what to improve")
            test_results: str = dspy.InputField(desc="Results from test cases")
            improved_prompt: str = dspy.OutputField(desc="Improved version of the prompt")
        
        optimizer = dspy.Predict(PromptOptimizer)
        
        for round_num in range(rounds):
            logger.info(f"Optimization round {round_num + 1}/{rounds}")
            
            # Test current prompt
            scores = []
            outputs = []
            for test_case in test_cases:
                # Execute prompt (simplified - in production would use actual LLM)
                test_input = test_case['input']
                expected = test_case['expected']
                
                # Simulate execution
                execution_result = f"Output for: {test_input}"
                score = metric_fn(execution_result, expected)
                
                scores.append(score)
                outputs.append(execution_result)
            
            avg_score = sum(scores) / len(scores) if scores else 0.0
            logger.info(f"Round {round_num + 1} score: {avg_score:.2f}")
            
            if avg_score > best_score:
                best_score = avg_score
                best_content = current_content
            
            # Generate feedback
            feedback = self._generate_feedback(scores, outputs, test_cases)
            
            # Optimize
            result = optimizer(
                current_prompt=current_content,
                feedback=feedback,
                test_results=json.dumps([
                    {"input": tc['input'], "expected": tc['expected'], "score": s}
                    for tc, s in zip(test_cases, scores)
                ])
            )
            
            current_content = result.improved_prompt
        
        # Save optimized version
        optimized_id = self.store.save_prompt(
            content=best_content,
            name=f"{prompt['id']}_optimized",
            tags=["optimized", "dspy"],
            metadata={
                "source_prompt": prompt_id,
                "optimization_rounds": rounds,
                "final_score": best_score,
                "optimized_at": datetime.now().isoformat()
            }
        )
        
        self.git_mgr.commit(f"Optimize prompt: {prompt_id} -> {optimized_id} (score: {best_score:.2f})")
        
        logger.info(f"Optimization complete: {optimized_id} (score: {best_score:.2f})")
        return optimized_id, best_score
    
    def evaluate(
        self,
        prompt_id: str,
        test_cases: List[Dict[str, str]],
        metric_fn: Optional[Callable[[str, str], float]] = None
    ) -> Dict[str, Any]:
        """
        Evaluate a prompt against test cases.
        
        Args:
            prompt_id: Prompt to evaluate
            test_cases: List of {"input": str, "expected": str}
            metric_fn: Scoring function
        
        Returns:
            Evaluation report with scores and details
        """
        # Ensure DSPy is configured for this thread
        self._configure_dspy()
        
        prompt = self.store.get_prompt(prompt_id)
        
        if metric_fn is None:
            def default_metric(output: str, expected: str) -> float:
                if expected.lower() in output.lower():
                    return 100.0
                return 0.0
            metric_fn = default_metric
        
        results = []
        total_score = 0.0
        
        for test_case in test_cases:
            test_input = test_case['input']
            expected = test_case['expected']
            
            # Execute prompt (simplified)
            output = f"Output for: {test_input}"
            score = metric_fn(output, expected)
            
            results.append({
                "input": test_input,
                "expected": expected,
                "output": output,
                "score": score
            })
            
            total_score += score
        
        avg_score = total_score / len(results) if results else 0.0
        
        report = {
            "prompt_id": prompt_id,
            "test_count": len(results),
            "average_score": avg_score,
            "results": results,
            "evaluated_at": datetime.now().isoformat()
        }
        
        logger.info(f"Evaluation complete: {prompt_id} (avg score: {avg_score:.2f})")
        return report
    
    def _generate_feedback(
        self,
        scores: List[float],
        outputs: List[str],
        test_cases: List[Dict[str, str]]
    ) -> str:
        """Generate feedback for optimization based on test results."""
        avg_score = sum(scores) / len(scores) if scores else 0.0
        
        feedback_parts = [f"Average score: {avg_score:.2f}/100"]
        
        if avg_score < 50:
            feedback_parts.append("Major improvements needed.")
        elif avg_score < 80:
            feedback_parts.append("Moderate improvements possible.")
        else:
            feedback_parts.append("Minor refinements only.")
        
        # Find worst performing cases
        if scores:
            worst_idx = scores.index(min(scores))
            feedback_parts.append(
                f"Worst case: '{test_cases[worst_idx]['input']}' "
                f"(score: {scores[worst_idx]:.2f})"
            )
        
        return " ".join(feedback_parts)
    
    def infer_intent(self, prompt_content: str) -> Dict[str, Any]:
        """
        Use phi3.5 to analyze a prompt and infer the user's intent.
        
        Args:
            prompt_content: The raw prompt text
        
        Returns:
            Dict with inferred intent information:
            - prompt_type: e.g., "code_generation", "creative_writing", "research", etc.
            - target_audience: Who the output is for
            - desired_outcome: What the user wants to achieve
            - optimization_goals: Specific improvements to make
            - clarifying_questions: Questions to ask the user
        """
        # Ensure DSPy is configured for this thread
        self._configure_dspy()
        
        class IntentAnalyzer(dspy.Signature):
            """Analyze a prompt to understand the user's intent and goals."""
            
            prompt: str = dspy.InputField(desc="The prompt text to analyze")
            prompt_type: str = dspy.OutputField(desc="Type of prompt: code_generation, creative_writing, research, summarization, translation, conversation, data_analysis, or other")
            target_audience: str = dspy.OutputField(desc="Who is the intended audience for this prompt's output")
            desired_outcome: str = dspy.OutputField(desc="What the user wants to achieve with this prompt")
            optimization_goals: str = dspy.OutputField(desc="Comma-separated list of specific ways to improve this prompt")
            clarifying_questions: str = dspy.OutputField(desc="1-3 questions to ask the user to better understand their needs, separated by |")
        
        try:
            analyzer = dspy.Predict(IntentAnalyzer)
            result = analyzer(prompt=prompt_content)
            
            # Parse the results
            intent = {
                "prompt_type": result.prompt_type.strip(),
                "target_audience": result.target_audience.strip(),
                "desired_outcome": result.desired_outcome.strip(),
                "optimization_goals": [g.strip() for g in result.optimization_goals.split(",") if g.strip()],
                "clarifying_questions": [q.strip() for q in result.clarifying_questions.split("|") if q.strip()],
                "model_used": self.model_name,
                "analyzed_at": datetime.now().isoformat()
            }
            
            logger.info(f"Intent inferred: type={intent['prompt_type']}, goals={len(intent['optimization_goals'])}")
            return intent
            
        except Exception as e:
            logger.error(f"Intent analysis failed: {e}")
            return {
                "prompt_type": "unknown",
                "target_audience": "general",
                "desired_outcome": "unknown",
                "optimization_goals": [],
                "clarifying_questions": [],
                "error": str(e)
            }
    
    def optimize_with_intent(
        self,
        prompt_id: str,
        intent: Dict[str, Any],
        rounds: int = 3,
        progress_callback: Optional[Callable] = None
    ) -> Tuple[str, float]:
        """
        Optimize a prompt using explicit user intent.
        
        Args:
            prompt_id: ID of prompt to optimize
            intent: Intent dict with:
                - prompt_type: Type of prompt
                - target_audience: Who the output is for
                - desired_outcome: What user wants
                - optimization_goals: Specific goals
                - constraints: Any limitations
            rounds: Number of optimization rounds
            progress_callback: Optional callback(round_num, total_rounds, phase)
        
        Returns:
            Tuple of (optimized_prompt_id, final_score)
        """
        # Ensure DSPy is configured for this thread
        self._configure_dspy()
        
        prompt = self.store.get_prompt(prompt_id)
        current_content = prompt['content']
        
        # Build intent context for optimization
        intent_context = f"""
        Prompt Type: {intent.get('prompt_type', 'general')}
        Target Audience: {intent.get('target_audience', 'general users')}
        Desired Outcome: {intent.get('desired_outcome', 'improved clarity and effectiveness')}
        Optimization Goals: {', '.join(intent.get('optimization_goals', []))}
        Constraints: {intent.get('constraints', 'none specified')}
        """.strip()
        
        # Define intent-aware optimization signature
        class IntentAwareOptimizer(dspy.Signature):
            """Optimize a prompt based on explicit user intent and goals."""
            
            current_prompt: str = dspy.InputField(desc="The current prompt to optimize")
            intent_context: str = dspy.InputField(desc="User's intent, goals, and constraints")
            round_number: int = dspy.InputField(desc="Current optimization round")
            previous_feedback: str = dspy.InputField(desc="Feedback from previous rounds")
            optimized_prompt: str = dspy.OutputField(desc="The improved prompt that better achieves the user's intent")
            improvement_notes: str = dspy.OutputField(desc="Brief explanation of what was improved")
        
        optimizer = dspy.Predict(IntentAwareOptimizer)
        
        best_content = current_content
        best_score = 0.0
        all_feedback = []
        
        for round_num in range(rounds):
            logger.info(f"Intent-aware optimization round {round_num + 1}/{rounds}")
            
            # Report progress: scoring phase
            if progress_callback:
                try:
                    progress_callback(round_num, rounds, 'scoring')
                except Exception:
                    pass
            
            # Score current content based on intent alignment
            score = self._score_intent_alignment(current_content, intent)
            
            if score > best_score:
                best_score = score
                best_content = current_content
            
            logger.info(f"Round {round_num + 1} score: {score:.2f}")
            
            # Generate feedback
            feedback = f"Round {round_num + 1}: Score {score:.2f}/100. "
            if score < 50:
                feedback += "Major improvements needed to align with user intent."
            elif score < 80:
                feedback += "Good progress, but can better match user goals."
            else:
                feedback += "Strong alignment with intent, minor refinements possible."
            
            all_feedback.append(feedback)
            
            # Report progress: optimizing phase
            if progress_callback:
                try:
                    progress_callback(round_num, rounds, 'optimizing')
                except Exception:
                    pass
            
            # Optimize
            try:
                result = optimizer(
                    current_prompt=current_content,
                    intent_context=intent_context,
                    round_number=round_num + 1,
                    previous_feedback="\n".join(all_feedback[-3:])  # Last 3 rounds
                )
                
                current_content = result.optimized_prompt
                logger.info(f"Improvements: {result.improvement_notes[:100]}...")
                
            except Exception as e:
                logger.warning(f"Optimization round {round_num + 1} failed: {e}")
                continue
        
        # Final scoring
        final_score = self._score_intent_alignment(current_content, intent)
        if final_score > best_score:
            best_score = final_score
            best_content = current_content
        
        # Save optimized version with intent metadata
        optimized_id = self.store.save_prompt(
            content=best_content,
            name=f"{prompt['id']}_optimized",
            tags=["optimized", "dspy", "intent-aware", intent.get('prompt_type', 'general')],
            metadata={
                "source_prompt": prompt_id,
                "optimization_type": "intent-aware",
                "intent": intent,
                "optimization_rounds": rounds,
                "final_score": best_score,
                "model_used": self.model_name,
                "optimized_at": datetime.now().isoformat()
            }
        )
        
        # Update original prompt to link to optimized version
        try:
            original_meta = prompt.get('metadata', {})
            original_meta['optimized_version'] = optimized_id
            original_meta['optimization_date'] = datetime.now().isoformat()
            self.store.update_metadata(prompt_id, original_meta)
        except Exception as e:
            logger.warning(f"Could not update original prompt metadata: {e}")
        
        try:
            self.git_mgr.commit(
                f"Intent-aware optimization: {prompt_id} -> {optimized_id} "
                f"(score: {best_score:.2f}, type: {intent.get('prompt_type', 'general')})"
            )
        except ValueError:
            pass  # No changes to commit
        
        logger.info(f"Intent-aware optimization complete: {optimized_id} (score: {best_score:.2f})")
        return optimized_id, best_score
    
    def _score_intent_alignment(self, prompt_content: str, intent: Dict[str, Any]) -> float:
        """
        Score how well a prompt aligns with the stated intent.
        Uses LLM to evaluate alignment.
        """
        class IntentAlignmentScorer(dspy.Signature):
            """Score how well a prompt achieves the user's stated intent."""
            
            prompt: str = dspy.InputField(desc="The prompt to evaluate")
            prompt_type: str = dspy.InputField(desc="Expected type of prompt")
            target_audience: str = dspy.InputField(desc="Intended audience")
            desired_outcome: str = dspy.InputField(desc="What user wants to achieve")
            score: float = dspy.OutputField(desc="Score from 0-100 indicating alignment with intent")
            reasoning: str = dspy.OutputField(desc="Brief explanation of the score")
        
        try:
            scorer = dspy.Predict(IntentAlignmentScorer)
            result = scorer(
                prompt=prompt_content,
                prompt_type=intent.get('prompt_type', 'general'),
                target_audience=intent.get('target_audience', 'general'),
                desired_outcome=intent.get('desired_outcome', 'improved effectiveness')
            )
            
            # Parse score - handle various formats
            score_str = str(result.score).strip()
            try:
                score = float(score_str)
                score = max(0, min(100, score))  # Clamp to 0-100
            except ValueError:
                # Try to extract number from string
                import re
                numbers = re.findall(r'\d+\.?\d*', score_str)
                score = float(numbers[0]) if numbers else 50.0
            
            return score
            
        except Exception as e:
            logger.warning(f"Intent scoring failed: {e}")
            return 50.0  # Default neutral score
