#!/usr/bin/env python3
"""
promptctl - A Git-backed prompt management CLI

Commands:
  save      Save a prompt with optional tags
  tag       Add/remove/list/filter tags on prompts
  list      List all prompts with optional filtering
  show      Show a specific prompt
  daemon    Run auto-commit daemon
  diff      Show changes in working directory
  status    Show repository status
"""

import argparse
import shutil
import sys
from pathlib import Path
from typing import Optional

from core.git_manager import GitManager
from core.prompt_store import PromptStore
from core.tag_manager import TagManager
from core.daemon import PromptDaemon
from core.batch_manager import BatchManager
from core.dspy_optimizer import PromptOptimizer
from core.agent import PromptAgent
from core.pipeline import DSPyPipeline, PipelineConfig


def check_git_available() -> bool:
    """Check if git CLI is available in PATH."""
    return shutil.which("git") is not None


def cmd_save(args: argparse.Namespace) -> int:
    """Save a prompt with optional tags and batch mode."""
    try:
        store = PromptStore(args.repo)
        
        # Read prompt content
        if args.file:
            content = Path(args.file).read_text()
        elif args.message:
            content = args.message
        else:
            print("Reading from stdin (Ctrl+D to finish)...")
            content = sys.stdin.read()
        
        # Save prompt
        prompt_id = store.save_prompt(
            content=content,
            name=args.name,
            tags=args.tags or [],
            metadata={"description": args.description} if args.description else None
        )
        
        print(f"Saved prompt: {prompt_id}")
        if args.tags:
            print(f"Tags: {', '.join(args.tags)}")
        
        # Handle batch mode
        if args.batch:
            batch_mgr = BatchManager(args.repo, batch_size=args.batch_size)
            if batch_mgr.should_commit():
                git_mgr = GitManager(args.repo)
                pending = batch_mgr.get_pending_count()
                git_mgr.commit(f"Batch commit: {pending} prompts saved")
                batch_mgr.reset_counter()
                print(f"\n✓ Batch commit triggered ({pending} saves)")
            else:
                pending = batch_mgr.get_pending_count()
                print(f"Pending saves: {pending}/{args.batch_size}")
        else:
            # Immediate commit (default)
            git_mgr = GitManager(args.repo)
            git_mgr.commit(f"Save prompt: {args.name or prompt_id}")
        
        return 0
        
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def cmd_tag(args: argparse.Namespace) -> int:
    """Manage tags on prompts."""
    try:
        tag_mgr = TagManager(args.repo)
        
        if args.action == "add":
            if not args.prompt_id or not args.tags:
                print("Error: --prompt-id and --tags required for add", file=sys.stderr)
                return 1
            
            tag_mgr.add_tags(args.prompt_id, args.tags)
            print(f"Added tags to {args.prompt_id}: {', '.join(args.tags)}")
            
            if not args.no_commit:
                git_mgr = GitManager(args.repo)
                git_mgr.commit(f"Add tags to {args.prompt_id}: {', '.join(args.tags)}")
        
        elif args.action == "remove":
            if not args.prompt_id or not args.tags:
                print("Error: --prompt-id and --tags required for remove", file=sys.stderr)
                return 1
            
            tag_mgr.remove_tags(args.prompt_id, args.tags)
            print(f"Removed tags from {args.prompt_id}: {', '.join(args.tags)}")
            
            if not args.no_commit:
                git_mgr = GitManager(args.repo)
                git_mgr.commit(f"Remove tags from {args.prompt_id}: {', '.join(args.tags)}")
        
        elif args.action == "list":
            if args.prompt_id:
                # List tags for specific prompt
                tags = tag_mgr.get_tags(args.prompt_id)
                print(f"Tags for {args.prompt_id}:")
                for tag in sorted(tags):
                    print(f"  • {tag}")
            else:
                # List all tags with counts
                tag_counts = tag_mgr.get_all_tags_with_counts()
                print("All tags:")
                for tag, count in sorted(tag_counts.items(), key=lambda x: (-x[1], x[0])):
                    print(f"  {tag:20} ({count} prompts)")
        
        elif args.action == "filter":
            if not args.tags:
                print("Error: --tags required for filter", file=sys.stderr)
                return 1
            
            prompts = tag_mgr.filter_by_tags(
                tags=args.tags,
                match_all=args.match_all
            )
            
            mode = "ALL" if args.match_all else "ANY"
            print(f"Prompts matching {mode} of tags {args.tags}:")
            for prompt_id in sorted(prompts):
                prompt_tags = tag_mgr.get_tags(prompt_id)
                print(f"  {prompt_id:40} [{', '.join(sorted(prompt_tags))}]")
            
            print(f"\nTotal: {len(prompts)} prompts")
        
        return 0
        
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def cmd_list(args: argparse.Namespace) -> int:
    """List prompts with optional tag filtering."""
    try:
        store = PromptStore(args.repo)
        
        # Get all prompts
        prompts = store.list_prompts()
        
        # Filter by tags if specified
        if args.tags:
            tag_mgr = TagManager(args.repo)
            filtered_ids = tag_mgr.filter_by_tags(args.tags, match_all=args.match_all)
            prompts = [p for p in prompts if p["id"] in filtered_ids]
        
        # Display
        print(f"Found {len(prompts)} prompts:")
        for prompt in prompts:
            tags_str = f"[{', '.join(prompt.get('tags', []))}]" if prompt.get('tags') else ""
            print(f"  {prompt['id']:40} {tags_str}")
            if args.verbose and prompt.get('metadata'):
                for key, value in prompt['metadata'].items():
                    print(f"    {key}: {value}")
        
        return 0
        
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def cmd_show(args: argparse.Namespace) -> int:
    """Show a specific prompt."""
    try:
        store = PromptStore(args.repo)
        prompt = store.get_prompt(args.prompt_id)
        
        print(f"Prompt: {prompt['id']}")
        if prompt.get('tags'):
            print(f"Tags: {', '.join(prompt['tags'])}")
        if prompt.get('metadata'):
            print(f"Metadata: {prompt['metadata']}")
        print("\n" + "=" * 60)
        print(prompt['content'])
        print("=" * 60)
        
        return 0
        
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def cmd_daemon(args: argparse.Namespace) -> int:
    """Run the auto-commit daemon."""
    try:
        daemon = PromptDaemon(
            repo_path=args.repo,
            watch_interval=args.interval,
            conflict_strategy=args.conflict_strategy,
            use_llm=args.use_llm,
            llm_model=args.llm_model,
            enable_socket=args.socket,
            socket_port=args.socket_port,
            auto_optimize=args.auto_optimize,
            optimization_rounds=args.optimization_rounds
        )
        
        print(f"Starting promptctl daemon (interval: {args.interval}s)")
        print(f"Conflict strategy: {args.conflict_strategy}")
        if args.use_llm:
            print(f"LLM commit generation: enabled ({args.llm_model})")
        if args.socket:
            print(f"Socket server: http://localhost:{args.socket_port}")
        if args.auto_optimize:
            print(f"Auto-optimize: enabled (rounds: {args.optimization_rounds})")
        print("Press Ctrl+C to stop\n")
        
        daemon.run()
        return 0
        
    except KeyboardInterrupt:
        print("\nDaemon stopped")
        return 0
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def cmd_status(args: argparse.Namespace) -> int:
    """Show repository status."""
    try:
        git_mgr = GitManager(args.repo)
        status = git_mgr.get_status()
        
        print("Repository status:")
        print(f"  Branch: {status['branch']}")
        print(f"  Modified: {len(status['modified'])}")
        print(f"  Untracked: {len(status['untracked'])}")
        
        if args.verbose:
            if status['modified']:
                print("\nModified files:")
                for file in status['modified']:
                    print(f"  • {file}")
            if status['untracked']:
                print("\nUntracked files:")
                for file in status['untracked']:
                    print(f"  • {file}")
        
        return 0
        
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def cmd_diff(args: argparse.Namespace) -> int:
    """Show diff of working directory."""
    try:
        git_mgr = GitManager(args.repo)
        diff = git_mgr.get_diff(staged=args.staged)
        
        if diff:
            print(diff)
        else:
            print("No changes")
        
        return 0
        
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def cmd_optimize(args: argparse.Namespace) -> int:
    """Optimize a prompt using DSPy."""
    try:
        optimizer = PromptOptimizer(
            repo_path=args.repo,
            use_local_ollama=args.use_ollama
        )
        
        print(f"Optimizing prompt: {args.prompt_id}")
        print(f"Rounds: {args.rounds}")
        
        optimized_id, score = optimizer.optimize(
            prompt_id=args.prompt_id,
            rounds=args.rounds
        )
        
        print(f"\n✓ Optimization complete!")
        print(f"Optimized prompt: {optimized_id}")
        print(f"Final score: {score:.2f}/100")
        
        return 0
        
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def cmd_chain(args: argparse.Namespace) -> int:
    """Chain multiple prompts together."""
    try:
        optimizer = PromptOptimizer(
            repo_path=args.repo,
            use_local_ollama=args.use_ollama
        )
        
        print(f"Chaining {len(args.prompts)} prompts...")
        
        chain_id = optimizer.chain_prompts(
            prompt_ids=args.prompts,
            chain_name=args.name
        )
        
        print(f"\n✓ Chain created: {chain_id}")
        
        return 0
        
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def cmd_evaluate(args: argparse.Namespace) -> int:
    """Evaluate a prompt against test cases."""
    try:
        optimizer = PromptOptimizer(
            repo_path=args.repo,
            use_local_ollama=args.use_ollama
        )
        
        # Load test cases from file if provided
        test_cases = []
        if args.test_file:
            import json
            with open(args.test_file) as f:
                test_cases = json.load(f)
        
        report = optimizer.evaluate(
            prompt_id=args.prompt_id,
            test_cases=test_cases
        )
        
        print(f"\nEvaluation Report: {args.prompt_id}")
        print("=" * 60)
        print(f"Test cases: {report['test_count']}")
        print(f"Average score: {report['average_score']:.2f}/100")
        print("\nResults:")
        for i, result in enumerate(report['results'], 1):
            print(f"  Test {i}: {result['score']:.2f}/100")
        
        return 0
        
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def cmd_agent(args: argparse.Namespace) -> int:
    """Run autonomous agent to test and improve prompt."""
    try:
        # Load test cases from file if provided
        test_cases = None
        if args.test_file:
            import json
            with open(args.test_file) as f:
                test_cases = json.load(f)
        
        agent = PromptAgent(
            prompt_id=args.prompt_id,
            repo_path=args.repo,
            test_cases=test_cases
        )
        
        print(f"Starting agent for prompt: {args.prompt_id}")
        print(f"Rounds: {args.rounds}")
        print(f"Target score: {args.min_score}")
        print("\n" + "=" * 60 + "\n")
        
        best_id, score = agent.run(
            rounds=args.rounds,
            min_score=args.min_score
        )
        
        # Print report
        if args.report:
            agent.print_report()
        else:
            print(f"\n✓ Agent run complete!")
            print(f"Best version: {best_id}")
            print(f"Final score: {score:.2f}/100")
        
        return 0
        
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def cmd_test(args: argparse.Namespace) -> int:
    """Quick test a prompt."""
    try:
        # Load test cases
        test_cases = []
        if args.test_file:
            import json
            with open(args.test_file) as f:
                test_cases = json.load(f)
        else:
            # Use default test cases
            test_cases = [
                {"input": "Test 1", "expected": "Output 1"},
                {"input": "Test 2", "expected": "Output 2"},
                {"input": "Test 3", "expected": "Output 3"}
            ]
        
        from core.agent import quick_test
        score = quick_test(args.prompt_id, test_cases, args.repo)
        
        return 0 if score >= 70 else 1
        
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def cmd_pipeline(args: argparse.Namespace) -> int:
    """Run DSPy pipeline operations."""
    try:
        config = PipelineConfig(
            auto_optimize=args.auto_optimize,
            optimization_rounds=args.rounds,
            use_local_ollama=args.use_ollama,
            auto_commit=not args.no_commit
        )
        
        pipeline = DSPyPipeline(args.repo, config)
        
        if args.action == "save":
            # Read content
            if args.file:
                content = Path(args.file).read_text()
            elif args.message:
                content = args.message
            else:
                print("Reading from stdin (Ctrl+D to finish)...")
                content = sys.stdin.read()
            
            result = pipeline.process_prompt(
                content=content,
                name=args.name,
                tags=args.tags,
                auto_optimize=args.auto_optimize,
                source="cli"
            )
            
            print(f"\n✓ Pipeline complete")
            print(f"Prompt ID: {result.prompt_id}")
            print(f"Stages: {', '.join(result.stages_completed)}")
            if result.job_id:
                print(f"Optimization job: {result.job_id}")
        
        elif args.action == "status":
            if args.job_id:
                status = pipeline.get_job_status(args.job_id)
                if status:
                    print(f"Job: {status['id']}")
                    print(f"Type: {status['job_type']}")
                    print(f"Status: {status['status']}")
                    print(f"Progress: {status['progress']:.1f}%")
                    if status.get('result'):
                        print(f"Result: {status['result']}")
                    if status.get('error'):
                        print(f"Error: {status['error']}")
                else:
                    print(f"Job not found: {args.job_id}")
            else:
                jobs = pipeline.list_jobs(10)
                print(f"Recent jobs ({len(jobs)}):")
                for job in jobs:
                    status_icon = {
                        'completed': '✓',
                        'running': '⟳',
                        'pending': '○',
                        'failed': '✗'
                    }.get(job['status'], '?')
                    print(f"  {status_icon} {job['id']:10} {job['job_type']:10} {job['status']}")
        
        elif args.action == "jobs":
            jobs = pipeline.list_jobs(args.limit)
            print(f"Jobs ({len(jobs)}):")
            for job in jobs:
                status_icon = {
                    'completed': '✓',
                    'running': '⟳',
                    'pending': '○',
                    'failed': '✗'
                }.get(job['status'], '?')
                progress = f"{job['progress']:.0f}%" if job['status'] == 'running' else ''
                print(f"  {status_icon} {job['id']:10} {job['job_type']:12} {job['status']:10} {progress}")
        
        return 0
        
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def main() -> int:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="promptctl - Git-backed prompt management",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument(
        "--repo",
        default=str(Path.home() / ".promptctl"),
        help="Repository path (default: ~/.promptctl)"
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Commands")
    
    # Save command
    save_parser = subparsers.add_parser("save", help="Save a prompt")
    save_parser.add_argument("--name", help="Prompt name")
    save_parser.add_argument("--tags", nargs="+", help="Tags to apply")
    save_parser.add_argument("--description", help="Prompt description")
    save_parser.add_argument("--file", "-f", help="Read prompt from file")
    save_parser.add_argument("--message", "-m", help="Prompt content (inline)")
    save_parser.add_argument("--batch", action="store_true", help="Enable batch mode")
    save_parser.add_argument("--batch-size", type=int, default=5, help="Commits after N saves (default: 5)")
    
    # Tag command
    tag_parser = subparsers.add_parser("tag", help="Manage tags")
    tag_parser.add_argument(
        "action",
        choices=["add", "remove", "list", "filter"],
        help="Tag action"
    )
    tag_parser.add_argument("--prompt-id", help="Prompt ID")
    tag_parser.add_argument("--tags", nargs="+", help="Tags")
    tag_parser.add_argument("--match-all", action="store_true", help="Require all tags (AND logic)")
    tag_parser.add_argument("--no-commit", action="store_true", help="Skip auto-commit")
    
    # List command
    list_parser = subparsers.add_parser("list", help="List prompts")
    list_parser.add_argument("--tags", nargs="+", help="Filter by tags")
    list_parser.add_argument("--match-all", action="store_true", help="Require all tags")
    list_parser.add_argument("--verbose", "-v", action="store_true", help="Show metadata")
    
    # Show command
    show_parser = subparsers.add_parser("show", help="Show a prompt")
    show_parser.add_argument("prompt_id", help="Prompt ID")
    
    # Daemon command
    daemon_parser = subparsers.add_parser("daemon", help="Run auto-commit daemon")
    daemon_parser.add_argument("--interval", type=int, default=60, help="Watch interval in seconds")
    daemon_parser.add_argument(
        "--conflict-strategy",
        choices=["ours", "theirs", "manual", "timestamp"],
        default="timestamp",
        help="Merge conflict resolution strategy"
    )
    daemon_parser.add_argument(
        "--use-llm",
        action="store_true",
        help="Use LLM for commit message generation (requires Ollama)"
    )
    daemon_parser.add_argument(
        "--llm-model",
        default="phi3.5",
        help="Ollama model name for LLM (default: phi3.5)"
    )
    daemon_parser.add_argument(
        "--socket",
        action="store_true",
        help="Enable HTTP socket server for browser extension"
    )
    daemon_parser.add_argument(
        "--socket-port",
        type=int,
        default=9090,
        help="Socket server port (default: 9090)"
    )
    daemon_parser.add_argument(
        "--auto-optimize",
        action="store_true",
        help="Auto-optimize prompts saved via socket (requires DSPy)"
    )
    daemon_parser.add_argument(
        "--optimization-rounds",
        type=int,
        default=3,
        help="Optimization rounds for auto-optimize (default: 3)"
    )
    
    # Status command
    status_parser = subparsers.add_parser("status", help="Show status")
    status_parser.add_argument("--verbose", "-v", action="store_true")
    
    # Diff command
    diff_parser = subparsers.add_parser("diff", help="Show diff")
    diff_parser.add_argument("--staged", action="store_true", help="Show staged changes")
    
    # Optimize command (DSPy)
    optimize_parser = subparsers.add_parser("optimize", help="Optimize prompt with DSPy")
    optimize_parser.add_argument("prompt_id", help="Prompt ID to optimize")
    optimize_parser.add_argument("--rounds", type=int, default=3, help="Optimization rounds")
    optimize_parser.add_argument("--use-ollama", action="store_true", help="Use local Ollama")
    
    # Chain command (DSPy)
    chain_parser = subparsers.add_parser("chain", help="Chain prompts together")
    chain_parser.add_argument("prompts", nargs="+", help="Prompt IDs to chain")
    chain_parser.add_argument("--name", help="Chain name")
    chain_parser.add_argument("--use-ollama", action="store_true", help="Use local Ollama")
    
    # Evaluate command (DSPy)
    evaluate_parser = subparsers.add_parser("evaluate", help="Evaluate prompt")
    evaluate_parser.add_argument("prompt_id", help="Prompt ID to evaluate")
    evaluate_parser.add_argument("--test-file", help="JSON file with test cases")
    evaluate_parser.add_argument("--use-ollama", action="store_true", help="Use local Ollama")
    
    # Agent command
    agent_parser = subparsers.add_parser("agent", help="Run autonomous agent")
    agent_parser.add_argument("prompt_id", help="Prompt ID to optimize")
    agent_parser.add_argument("--rounds", type=int, default=5, help="Agent rounds")
    agent_parser.add_argument("--min-score", type=float, default=90.0, help="Target score")
    agent_parser.add_argument("--test-file", help="JSON file with test cases")
    agent_parser.add_argument("--report", action="store_true", help="Print detailed report")
    
    # Test command
    test_parser = subparsers.add_parser("test", help="Quick test prompt")
    test_parser.add_argument("prompt_id", help="Prompt ID to test")
    test_parser.add_argument("--test-file", help="JSON file with test cases")
    
    # Pipeline command
    pipeline_parser = subparsers.add_parser("pipeline", help="DSPy pipeline operations")
    pipeline_parser.add_argument(
        "action",
        choices=["save", "status", "jobs"],
        help="Pipeline action"
    )
    pipeline_parser.add_argument("--name", help="Prompt name (for save)")
    pipeline_parser.add_argument("--tags", nargs="+", help="Tags (for save)")
    pipeline_parser.add_argument("--file", "-f", help="Read content from file (for save)")
    pipeline_parser.add_argument("--message", "-m", help="Content inline (for save)")
    pipeline_parser.add_argument("--auto-optimize", action="store_true", help="Enable auto-optimization")
    pipeline_parser.add_argument("--rounds", type=int, default=3, help="Optimization rounds")
    pipeline_parser.add_argument("--use-ollama", action="store_true", default=True, help="Use local Ollama")
    pipeline_parser.add_argument("--no-commit", action="store_true", help="Skip auto-commit")
    pipeline_parser.add_argument("--job-id", help="Job ID (for status)")
    pipeline_parser.add_argument("--limit", type=int, default=50, help="Limit for jobs list")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 1
    
    # Check if git is available
    if not check_git_available():
        print("ERROR: git is not installed or not in PATH.", file=sys.stderr)
        print("\nprompctl requires git to be installed.", file=sys.stderr)
        print("\nInstallation instructions:", file=sys.stderr)
        print("  macOS:   brew install git", file=sys.stderr)
        print("  Ubuntu:  sudo apt-get install git", file=sys.stderr)
        print("  Windows: https://git-scm.com/download/win", file=sys.stderr)
        return 1
    
    # Initialize repo if needed
    if args.command != "daemon":
        git_mgr = GitManager(args.repo)
        if not git_mgr.is_initialized():
            git_mgr.init()
            print(f"Initialized repository at {args.repo}")
    
    # Dispatch to command handler
    handlers = {
        "save": cmd_save,
        "tag": cmd_tag,
        "list": cmd_list,
        "show": cmd_show,
        "daemon": cmd_daemon,
        "status": cmd_status,
        "diff": cmd_diff,
        "optimize": cmd_optimize,
        "chain": cmd_chain,
        "evaluate": cmd_evaluate,
        "agent": cmd_agent,
        "test": cmd_test,
        "pipeline": cmd_pipeline,
    }
    
    return handlers[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
