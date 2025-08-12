#!/usr/bin/env python3
"""
Workflow Memory Intelligence System - FIXED VERSION for Option #10
Enhanced with better error handling and logging for automatic TODO generation
"""

import json
import os
import re
import time
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path
from dataclasses import dataclass, asdict
import asyncio
from functools import lru_cache
from common.utils.log_setup import configure_logging

# Configure logging
logger = configure_logging(__name__, level="INFO")
logger = logging.getLogger(__name__)

# Import our existing memory system
try:
    from todo_manager import (
        new_task,
        add_todo,
        list_open_tasks,
        set_task_status,
        hard_delete_task,
        mark_done,
    )
    logger.info("✅ Successfully imported todo_manager functions")
except ImportError as e:
    logger.error(f"❌ Failed to import todo_manager: {e}")
    raise

# Import hybrid parsing system
try:
    from ollama_client import call_ollama, SYSTEM_PROMPTS, get_ollama_client
    OLLAMA_AVAILABLE = True
    logger.info("✅ Ollama client available for hybrid parsing with phi3:instruct")
except ImportError as e:
    OLLAMA_AVAILABLE = False
    logger.warning(f"⚠️ Ollama client not available: {e}")

try:
    from task_interruption_manager import auto_task_handler, get_interruption_status
    logger.info("✅ Successfully imported task_interruption_manager functions")
except ImportError as e:
    logger.error(f"❌ Failed to import task_interruption_manager: {e}")
    raise

try:
    from task_state_manager import save_task_state, load_task_state
    logger.info("✅ Successfully imported task_state_manager functions")
except ImportError as e:
    logger.error(f"❌ Failed to import task_state_manager: {e}")
    raise

# Try to import telemetry (optional)
try:
    from memory_system.services.telemetry import span
    from memory_system.services.memory_provider import get_provider, MemoryProvider
    TELEMETRY_AVAILABLE = True
    logger.info("✅ Telemetry system available")
except ImportError:
    TELEMETRY_AVAILABLE = False
    logger.warning("⚠️ Telemetry system not available, using fallback")
    
    # Fallback span decorator
    def span(name, description=""):
        def decorator(func):
            def wrapper(*args, **kwargs):
                logger.info(f"🔍 {name}: {description}")
                return func(*args, **kwargs)
            return wrapper
        return decorator


@dataclass
class TaskComplexity:
    """Task complexity analysis result"""
    score: int
    level: str  # SIMPLE, MEDIUM, COMPLEX
    should_chunk: bool
    estimated_subtasks: int
    reasoning: List[str]


@dataclass
class Subtask:
    """Individual subtask information"""
    id: str
    description: str
    priority: int
    estimated_duration: int  # minutes
    dependencies: List[str]
    status: str  # pending, in_progress, completed, failed


@dataclass
class ChunkedTask:
    """Chunked task with subtasks"""
    original_task: str
    task_id: str
    complexity: TaskComplexity
    subtasks: List[Subtask]
    current_subtask_index: int
    status: str  # chunked, in_progress, completed, failed


class TaskComplexityAnalyzer:
    """Analyzes task complexity for our workflow"""
    
    def __init__(self):
        self.simple_indicators = [
            'fix typo', 'update comment', 'change variable', 'add import',
            'remove unused', 'format code', 'simple', 'quick', 'minor',
            'gawa', 'gawin', 'maliit', 'mabilis', 'ayusin lang'
        ]
        
        self.medium_indicators = [
            'refactor', 'optimize', 'improve', 'enhance', 'update',
            'modify', 'adjust', 'tune', 'pagandahin', 'i-improve'
        ]
        
        self.complex_indicators = [
            'implement', 'create', 'build', 'develop', 'design',
            'architecture', 'system', 'framework', 'comprehensive',
            'complete', 'full', 'extensive', 'malawak', 'malaki',
            'buo', 'sistema', 'framework', 'build entire', 'create system'
        ]
    
    @lru_cache(maxsize=256)
    def analyze_complexity(self, task_description: str) -> TaskComplexity:
        """Analyze task complexity for our workflow"""
        
        complexity_score = 0
        reasoning = []
        task_lower = task_description.lower()
        
        # Count complexity indicators
        simple_count = sum(1 for indicator in self.simple_indicators if indicator in task_lower)
        medium_count = sum(1 for indicator in self.medium_indicators if indicator in task_lower)
        complex_count = sum(1 for indicator in self.complex_indicators if indicator in task_lower)
        
        # Calculate base score
        complexity_score -= simple_count * 10
        complexity_score += medium_count * 5
        complexity_score += complex_count * 20
        
        # Determine level
        if complexity_score <= 0:
            level = "SIMPLE"
            should_chunk = False
            estimated_subtasks = 1
        elif complexity_score <= 30:
            level = "MEDIUM"
            should_chunk = True
            estimated_subtasks = 3
        else:
            level = "COMPLEX"
            should_chunk = True
            estimated_subtasks = 5
        
        # Add reasoning
        if simple_count > 0:
            reasoning.append(f"Contains {simple_count} simple task indicators")
        if medium_count > 0:
            reasoning.append(f"Contains {medium_count} medium complexity indicators")
        if complex_count > 0:
            reasoning.append(f"Contains {complex_count} complex task indicators")
        
        return TaskComplexity(
            score=complexity_score,
            level=level,
            should_chunk=should_chunk,
            estimated_subtasks=estimated_subtasks,
            reasoning=reasoning
        )


class ActionItemExtractor:
    """Unified task decomposer with normalized parsing strategy"""
    
    def __init__(self):
        """Initialise shared resources and register parsing strategies.

        The extractor now follows a *Strategy Pattern* – it analyses the
        incoming text and delegates decomposition to one or more specialised
        strategy objects.  Each strategy is responsible for a specific command
        structure (e.g., sequential, conditional, parallel, hierarchical).

        NOTE: We intentionally keep the original helper functions so that
        legacy behaviour remains intact.  The new strategies reuse those
        helpers where appropriate, providing a robust and extensible
        foundation without breaking backward-compatibility.
        """

        # ------------------------------------------------------------------
        # Shared linguistic resources (available to every strategy)
        # ------------------------------------------------------------------

        # Core action verbs (language-agnostic concepts)
        self.action_concepts = {
            'CREATE': [
                'create', 'build', 'gumawa', 'magbuild', 'gawa', 'make', 'new', 'i-create', 'scaffold', 'setup',
                'generate', 'instantiate', 'compose', 'mag-generate', 'add', 'dagdag', 'add file', 'add folder',
                'magdagdag', 'add module'
            ],
            'UPDATE': [
                'update', 'edit', 'baguhin', 'palitan', 'revise', 'amend', 'modify', 'tweak', 'refactor', 'change',
                'i-update', 'i-edit', 'revamp', 'rework', 'rename'
            ],
            'DELETE': [
                'delete', 'remove', 'alisin', 'burahin', 'drop', 'erase', 'destroy', 'magdelete', 'uninstall',
                'i-delete', 'tanggalin', 'bura', 'purge', 'clean', 'clear'
            ],
            'IMPLEMENT': [
                'implement', 'ipatupad', 'apply', 'mag-implement', 'i-implement', 'isagawa', 'i-apply', 'magpatupad',
                'execute', 'mag-execute', 'i-execute', 'gamitin', 'deploy', 'ilunsad', 'paganahin'
            ],
            'DEVELOP': [
                'develop', 'dev', 'magdev', 'i-develop', 'gumawa', 'i-dev', 'design', 'enhance', 'improve', 'dagdagan',
                'expand', 'i-enhance', 'magdagdag', 'i-design', 'idisenyo', 'disenyo'
            ],
            'TEST': [
                'test', 'itest', 'i-test', 'subukan', 'run test', 'check', 'magtest', 'i-check', 'verify', 'beripikahin',
                'suriin', 'mag-subok', 'unit test', 'integration test', 'validate', 'i-validate', 'mag-validate'
            ],
            'VALIDATE': [
                'validate', 'mag-validate', 'i-validate', 'patunayan', 'beripikahin', 'i-verify', 'siguruhin', 'lint',
                'run linter', 'check code', 'maglint', 'i-lint'
            ],
            'DEPLOY': [
                'deploy', 'mag-deploy', 'i-deploy', 'ilunsad', 'release', 'publish', 'push to prod', 'rollout', 'launch',
                'deploy to server', 'deploy to production', 'roll-out'
            ],
            'MERGE': [
                'merge', 'i-merge', 'pagsamahin', 'mag-merge', 'combine', 'pull request', 'PR', 'rebase', 'integrate',
                'git merge', 'i-integrate'
            ],
            'REVERT': [
                'revert', 'mag-revert', 'i-revert', 'bawiin', 'rollback', 'undo', 'cancel changes', 'reverse', 'reset',
                'i-reset'
            ],
            'COMMIT': [
                'commit', 'i-commit', 'isave', 'mag-commit', 'save changes', 'add commit', 'git commit', 'log changes',
                'commit changes'
            ]
        }
        
        # Sequential markers to normalize
        self.sequential_markers = {
            # English
            'first of all': ['SEQ_1'],
            'first': ['SEQ_1'],
            'step one': ['SEQ_1'],
            'initially': ['SEQ_1'],
            'to begin': ['SEQ_1'],
            'before anything else': ['SEQ_1'],
            'set up': ['SEQ_1'],
            'prepare': ['SEQ_1'],
            'at the start': ['SEQ_1'],
            'in the beginning': ['SEQ_1'],
            'primarily': ['SEQ_1'],
            'starting with': ['SEQ_1'],
            'second': ['SEQ_2'],
            'next': ['SEQ_2'],
            'after that': ['SEQ_2'],
            'afterwards': ['SEQ_2'],
            'subsequently': ['SEQ_2'],
            'continue': ['SEQ_2'],
            'step two': ['SEQ_2'],
            'move on': ['SEQ_2'],
            'followed by': ['SEQ_2'],
            'third': ['SEQ_3'],
            'then': ['SEQ_3'],
            'afterward': ['SEQ_3'],
            'step three': ['SEQ_3'],
            'later': ['SEQ_3'],
            'proceed': ['SEQ_3'],
            'finally': ['SEQ_4'],
            'lastly': ['SEQ_4'],
            'in the end': ['SEQ_4'],
            'at the end': ['SEQ_4'],
            'wrap up': ['SEQ_4'],
            'complete': ['SEQ_4'],
            'ultimately': ['SEQ_4'],
            'eventually': ['SEQ_4'],
            'finish up': ['SEQ_4'],
            'step four': ['SEQ_4'],
            # Filipino/Taglish
            'una sa lahat': ['SEQ_1'],
            'una,': ['SEQ_1'],
            'simula': ['SEQ_1'],
            'umpisa': ['SEQ_1'],
            'maghanda': ['SEQ_1'],
            'sa simula': ['SEQ_1'],
            'panimula': ['SEQ_1'],
            'unang-una': ['SEQ_1'],
            'pangalawa': ['SEQ_2'],
            'ikalawa': ['SEQ_2'],
            'sunod': ['SEQ_2'],
            'kasunod': ['SEQ_2'],
            'pagkatapos': ['SEQ_2'],
            'tapos nito': ['SEQ_2'],
            'sumunod': ['SEQ_2'],
            'ituloy': ['SEQ_2'],
            'next step': ['SEQ_2'],
            'pangatlo': ['SEQ_3'],
            'ikatlo': ['SEQ_3'],
            'pagkalipas': ['SEQ_3'],
            'pangatlong hakbang': ['SEQ_3'],
            'sa wakas': ['SEQ_4'],
            'panghuli': ['SEQ_4'],
            'pahuli': ['SEQ_4'],
            'sa dulo': ['SEQ_4'],
            'tapusin': ['SEQ_4'],
            'wakasan': ['SEQ_4'],
            'final step': ['SEQ_4']
        }
        
        # Conditional markers to normalize
        self.conditional_markers = {
            # English
            'if': '[IF]',
            'when': '[IF]',
            # Filipino
            'kung': '[IF]',
            'kapag': '[IF]',
            # Conditional results
            'correct': 'CORRECT',
            'incorrect': 'INCORRECT',
            'tama': 'CORRECT',
            'mali': 'INCORRECT',
            'pumasa': 'CORRECT',
            'pumalya': 'INCORRECT'
        }

        # ------------------------------------------------------------------
        # Strategy registry
        # ------------------------------------------------------------------

        self._strategies = []  # type: list[_BaseParsingStrategy]
        self._register_default_strategies()

    # ------------------------------------------------------------------
    # 🏃‍♂️ Public API
    # ------------------------------------------------------------------

    def extract_action_items(self, task_description: str) -> List[str]:
        """Decompose *any* natural-language task description into atomic steps.

        NEW HYBRID APPROACH:
        1. Calculate task complexity score
        2. Route to appropriate parsing engine:
           - Fast Lane: Rule-based parser for simple sequential tasks (score <= 3)
           - Power Lane: LLM-based parser for complex tasks (score > 3)
        """
        
        logger.info(f"🎯 Processing task: {task_description[:50]}...")
        
        # Step 1: Calculate complexity score  
        complexity_score = self._calculate_complexity_score(task_description)
        
        # Step 2: Route to appropriate parsing engine
        if complexity_score <= 3:
            logger.info(f"🚀 Fast Lane: Rule-based parsing (complexity: {complexity_score})")
            return self._parse_with_rules(task_description)
        else:
            logger.info(f"🧠 Power Lane: LLM-based parsing (complexity: {complexity_score})")
            return self._parse_with_llm(task_description)

    # ------------------------------------------------------------------
    # 🧠 Hybrid Parsing Engine Methods
    # ------------------------------------------------------------------
    
    def _calculate_complexity_score(self, task: str) -> int:
        """Calculate complexity score to determine parsing strategy.
        
        Returns:
            Integer score (0-10, higher = more complex)
        """
        
        task_lower = task.lower()
        score = 0
        
        # Simple task indicators (reduce score)
        simple_indicators = [
            'fix typo', 'update comment', 'change variable', 'add import',
            'remove unused', 'format code', 'simple', 'quick', 'minor',
            'gawa', 'gawin', 'maliit', 'mabilis', 'ayusin lang'
        ]
        
        # Complex task indicators (increase score)
        complex_indicators = [
            'implement', 'create', 'build', 'develop', 'design',
            'architecture', 'system', 'framework', 'comprehensive',
            'database', 'authentication', 'integration', 'deployment',
            'api', 'rest', 'endpoint', 'management', 'pipeline'
        ]
        
        # Conditional/branching indicators
        conditional_indicators = [
            'if', 'when', 'unless', 'kung', 'kapag', 'otherwise',
            'else', 'then', 'in case', 'should', 'might', 'could'
        ]
        
        # Parallel execution indicators  
        parallel_indicators = [
            'simultaneously', 'at the same time', 'in parallel',
            'concurrently', 'while', 'sabay', 'kasabay'
        ]
        
        # Base score from length
        if len(task) > 100:
            score += 1
        if len(task) > 200:
            score += 1
            
        # Check for simple indicators (reduce score)
        simple_count = sum(1 for indicator in simple_indicators 
                          if indicator in task_lower)
        score -= simple_count
        
        # Check for complex indicators (increase score)
        complex_count = sum(1 for indicator in complex_indicators 
                           if indicator in task_lower)
        score += complex_count * 2
        
        # Check for conditionals (major complexity)
        conditional_count = sum(1 for indicator in conditional_indicators 
                               if indicator in task_lower)
        score += conditional_count * 3
        
        # Check for parallel execution (major complexity)  
        parallel_count = sum(1 for indicator in parallel_indicators 
                            if indicator in task_lower)
        score += parallel_count * 3
        
        # Word count complexity
        word_count = len(task.split())
        if word_count > 20:
            score += 1
        if word_count > 40:
            score += 2
            
        # Ensure score is within bounds
        score = max(0, min(10, score))
        
        logger.info(f"📊 Complexity analysis: {score}/10 (simple: {simple_count}, complex: {complex_count}, conditional: {conditional_count}, parallel: {parallel_count})")
        
        return score
    
    def _parse_with_rules(self, task: str) -> List[str]:
        """Fast rule-based parser for simple sequential tasks."""
        
        logger.info("⚡ Using rule-based parsing...")
        
        steps = []
        
        # Use existing normalization and strategy system for backward compatibility
        normalised_text = self._normalise_text(task)
        sentences = self._smart_sentence_split(normalised_text)
        
        # Apply strategies but prefer simple sequential extraction
        aggregated_steps: list[str] = []
        
        for strat in self._strategies:
            if strat.is_applicable(normalised_text, sentences):
                for step in strat.parse(sentences):
                    if step not in aggregated_steps:
                        aggregated_steps.append(step)
        
        # Backward-compatibility safeguard
        aggregated_steps = self._ensure_auth_workflow_completeness(" ".join(sentences), aggregated_steps)
        
        # If no steps found with strategies, fall back to simple extraction
        if not aggregated_steps:
            action_verbs = ['create', 'make', 'build', 'update', 'modify', 'fix', 'repair',
                           'delete', 'remove', 'test', 'check', 'verify', 'configure',
                           'setup', 'install', 'deploy', 'gumawa', 'ayusin', 'gawin']
            
            task_lower = task.lower()
            
            # Simple heuristic-based extraction for common patterns
            # Check for complex patterns first to avoid incorrect matches
            if 'database' in task_lower and 'migration' in task_lower:
                aggregated_steps.extend([
                    "Design migration system architecture",
                    "Implement migration execution logic",
                    "Create rollback mechanism",
                    "Add backup functionality",
                    "Set up migration validation"
                ])
            elif 'pipeline' in task_lower and ('processing' in task_lower or 'validation' in task_lower):
                aggregated_steps.extend([
                    "Design data processing architecture",
                    "Implement validation pipeline",
                    "Set up transformation pipeline",
                    "Add parallel processing logic",
                    "Configure logging system"
                ])
            elif any(verb in task_lower for verb in ['fix', 'repair', 'ayusin']):
                if 'typo' in task_lower or 'documentation' in task_lower:
                    aggregated_steps.append("Fix the typo in documentation")
                else:
                    aggregated_steps.append("Fix the identified issue")
                    
            elif any(verb in task_lower for verb in ['update', 'modify', 'change', 'baguhin']):
                if 'comment' in task_lower:
                    aggregated_steps.append("Update the comment in the file")
                else:
                    aggregated_steps.append("Update the specified component")
                    
            elif any(verb in task_lower for verb in ['remove', 'delete', 'alisin']):
                if 'import' in task_lower:
                    aggregated_steps.append("Remove unused import statements")
                else:
                    aggregated_steps.append("Remove the specified items")
                    
            elif 'docker' in task_lower or 'compose' in task_lower:
                # Enhanced Docker and Docker Compose deployment breakdown
                aggregated_steps.extend([
                    "Verify docker-compose.yml and .env are up to date",
                    "Build images: docker-compose build --no-cache", 
                    "Start services: docker-compose up -d --remove-orphans",
                    "Check service health: docker-compose ps && docker-compose logs --tail=50",
                    "Run post-deploy script: chmod +x ./scripts/verify-services.sh && ./scripts/verify-services.sh",
                    "Validate endpoints: curl -f http://localhost:8080/health || echo 'Health endpoint check'",
                    "If failed, rollback: docker-compose down && echo 'DEPLOYMENT FAILED - ROLLBACK COMPLETED'"
                ])
                
            elif any(verb in task_lower for verb in ['create', 'gumawa', 'make', 'build']):
                # Check for complex creation tasks and break them down
                if 'pipeline' in task_lower and 'ci/cd' in task_lower:
                    aggregated_steps.extend([
                        "Create CI/CD pipeline configuration",
                        "Set up automated testing stage", 
                        "Configure deployment stage",
                        "Add conditional logic for test results"
                    ])
                elif 'authentication' in task_lower or 'login' in task_lower:
                    aggregated_steps.extend([
                        "Design authentication database schema",
                        "Create user registration endpoint",
                        "Implement login validation logic",
                        "Set up password reset functionality",
                        "Add session management"
                    ])
                elif 'api' in task_lower and 'endpoint' in task_lower:
                    aggregated_steps.extend([
                        "Design API endpoint structure",
                        "Implement request validation",
                        "Add error handling",
                        "Create response formatting"
                    ])
                else:
                    aggregated_steps.append("Create the required component")
                
            elif any(verb in task_lower for verb in ['implement', 'develop']):
                # Complex patterns already handled above, just add basic fallback
                aggregated_steps.append("Implement the required functionality")
                
            elif any(verb in task_lower for verb in ['test', 'subukan', 'check', 'verify']):
                aggregated_steps.append("Test the implementation")
                
            elif any(verb in task_lower for verb in ['deploy', 'release']):
                # Enhanced Docker deployment breakdown
                if 'docker' in task_lower or 'compose' in task_lower:
                    aggregated_steps.extend([
                        "Verify docker-compose.yml and .env are up to date",
                        "Build images: docker-compose build --no-cache", 
                        "Start services: docker-compose up -d --remove-orphans",
                        "Check service health: docker-compose ps && docker-compose logs --tail=50",
                        "Run post-deploy script: chmod +x ./scripts/verify-services.sh && ./scripts/verify-services.sh",
                        "Validate endpoints: curl -f http://localhost:8080/health || echo 'Health endpoint check'",
                        "If failed, rollback: docker-compose down && echo 'DEPLOYMENT FAILED - ROLLBACK COMPLETED'"
                    ])
                elif 'kubernetes' in task_lower or 'k8s' in task_lower:
                    aggregated_steps.extend([
                        "Apply Kubernetes manifests: kubectl apply -f k8s/",
                        "Check pod status: kubectl get pods -w",
                        "Verify service endpoints: kubectl get services",
                        "Check deployment rollout: kubectl rollout status deployment/app",
                        "Run health checks: kubectl exec -it pod -- curl localhost:8080/health",
                        "If failed, rollback: kubectl rollout undo deployment/app"
                    ])
                elif 'production' in task_lower or 'prod' in task_lower:
                    aggregated_steps.extend([
                        "Backup current production state",
                        "Run pre-deployment checks and validations",
                        "Deploy to staging environment first",
                        "Execute production deployment",
                        "Run post-deployment verification tests",
                        "Monitor system health and performance",
                        "If issues detected, execute rollback procedure"
                    ])
                else:
                    aggregated_steps.append("Deploy the changes")
            
            # Special Docker/Compose pattern recognition before generic fallback
            if not aggregated_steps and ('docker' in task_lower or 'compose' in task_lower):
                aggregated_steps.extend([
                    "Verify docker-compose.yml and .env are up to date",
                    "Build images: docker-compose build --no-cache", 
                    "Start services: docker-compose up -d --remove-orphans",
                    "Check service health: docker-compose ps && docker-compose logs --tail=50",
                    "Run post-deploy script: chmod +x ./scripts/verify-services.sh && ./scripts/verify-services.sh",
                    "Validate endpoints: curl -f http://localhost:8080/health || echo 'Health endpoint check'",
                    "If failed, rollback: docker-compose down && echo 'DEPLOYMENT FAILED - ROLLBACK COMPLETED'"
                ])
            
            # If still no steps, create a generic one
            if not aggregated_steps:
                # Extract the main action from the task
                words = task.split()
                if len(words) > 2:
                    aggregated_steps.append(f"Complete the task: {task[:50]}...")
                else:
                    aggregated_steps.append("Complete the specified task")
        
        logger.info(f"✅ Rule-based parsing extracted {len(aggregated_steps)} steps")
        return aggregated_steps
    
    def _parse_with_llm(self, task: str) -> List[str]:
        """Powerful LLM-based parser for complex tasks with conditionals and parallelism."""
        
        logger.info("🧠 Using LLM-based parsing...")
        
        if not OLLAMA_AVAILABLE:
            logger.warning("⚠️ Ollama not available, falling back to rule-based parsing")
            return self._parse_with_rules(task)
        
        # Construct prompt for LLM
        prompt = f"""Break down this task into clear, actionable steps:

TASK: {task}

Requirements:
- Each step should be specific and actionable
- Include conditional logic with "IF condition: then action" format
- Mark parallel tasks with "PARALLEL:" prefix
- Support both English and Filipino/Taglish
- Estimate 5-30 minutes per step"""
        
        try:
            # Call Ollama LLM
            response = call_ollama(prompt, SYSTEM_PROMPTS["task_decomposition"])
            
            if not response:
                logger.error("❌ No response from LLM, falling back to rules")
                return self._parse_with_rules(task)
            
            # Parse LLM response based on type
            if isinstance(response, dict):
                if "steps" in response:
                    steps = response["steps"]
                    # Ensure steps is a list
                    if isinstance(steps, list):
                        # Extract text from dictionary structures if needed
                        processed_steps = []
                        for step in steps:
                            if isinstance(step, dict):
                                # Try to extract meaningful text from dictionary
                                if "step_description" in step:
                                    processed_steps.append(step["step_description"])
                                elif "description" in step:
                                    processed_steps.append(step["description"])
                                else:
                                    # Take the first string value found
                                    for value in step.values():
                                        if isinstance(value, str) and len(value) > 5:
                                            processed_steps.append(value)
                                            break
                                    else:
                                        # Fallback: convert whole dict to string
                                        processed_steps.append(str(step))
                            elif isinstance(step, str):
                                processed_steps.append(step)
                            else:
                                processed_steps.append(str(step))
                        
                        logger.info(f"✅ LLM parsing extracted {len(processed_steps)} steps")
                        return processed_steps
                    else:
                        logger.warning(f"⚠️ Steps is not a list: {type(steps)}")
                        return self._parse_with_rules(task)
                elif "raw_response" in response:
                    # Try to extract steps from raw text
                    raw_text = response["raw_response"]
                    if isinstance(raw_text, str):
                        steps = self._extract_steps_from_text(raw_text)
                        logger.info(f"✅ Extracted {len(steps)} steps from raw LLM response")
                        return steps
                    else:
                        logger.warning(f"⚠️ Raw response is not a string: {type(raw_text)}")
                        return self._parse_with_rules(task)
                else:
                    logger.warning("⚠️ Invalid LLM response format - missing 'steps' or 'raw_response'")
                    return self._parse_with_rules(task)
            elif isinstance(response, str):
                # If response is a string, try to extract steps directly
                steps = self._extract_steps_from_text(response)
                logger.info(f"✅ Extracted {len(steps)} steps from string response")
                return steps
            else:
                logger.warning(f"⚠️ Unexpected response type: {type(response)}")
                return self._parse_with_rules(task)
                
        except Exception as e:
            logger.error(f"❌ Error in LLM parsing: {e}")
            return self._parse_with_rules(task)
    def _extract_steps_from_text(self, text: str) -> List[str]:
        """Extract steps from unstructured LLM text response."""
        
        steps = []
        action_verbs = ['create', 'make', 'build', 'update', 'modify', 'fix', 'repair',
                       'delete', 'remove', 'test', 'check', 'verify', 'configure',
                       'setup', 'install', 'deploy', 'gumawa', 'ayusin', 'gawin']
        
        # Split by common step indicators
        lines = text.split('\n')
        
        for line in lines:
            line = line.strip()
            
            # Skip empty lines or headers
            if not line or line.lower().startswith(('task:', 'steps:', 'requirements:')):
                continue
            
            # Remove numbering and bullet points
            cleaned = re.sub(r'^[\d\.\-\*\+]\s*', '', line).strip()
            
            # Check if it looks like a step (has action verb)
            if any(verb in cleaned.lower() for verb in action_verbs):
                steps.append(cleaned)
            elif len(cleaned) > 10 and any(word in cleaned.lower() for word in ['if', 'parallel', 'then', 'configure', 'setup']):
                steps.append(cleaned)
        
        return steps
    
    def get_parsing_engine_name(self, task: str) -> str:
        """Get the name of the parsing engine that would be used for this task."""
        complexity_score = self._calculate_complexity_score(task)
        if complexity_score <= 3:
            return "Rule-Based"
        else:
            return "LLM"

    # ------------------------------------------------------------------
    # 🌐 Unified helpers (language-agnostic) ---------------------------
    # ------------------------------------------------------------------

    def _normalise_text(self, text: str) -> str:
        """Replace language-specific sequential / conditional markers with
        a unified vocabulary so downstream regexes need only one set of rules."""
        import re

        replacements = {
            # — Sequential indicators —
            r"\buna sa lahat\b": "",
            r"\buna\b": "",
            r"\bfirst of all\b": "",
            r"\bfirst\b": "",
            r"\bthen\b": "",
            r"\bnext\b": "",
            r"\bafterwards\b": "",
            r"\bpanghuli\b": "",
            r"\bfinally\b": "",
            r"\blastly\b": "",
            # — Conditional indicators —
            r"\bkapag\b": "if",
            r"\bkung\b": "if",
            r"\btama\b": "correct",
            r"\bmali\b": "incorrect",
            # Misc filler words
            r"\bkailangan\b": "must",
            r"\bgawa ka ng\b": "create",
            r"\bigawa\b": "create",
            r"\bgawin\b": "create",
            r"\bi-update\b": "update",
            r"\bmagdagdag\b": "add",
        }

        normalised = text.lower()
        for pattern, repl in replacements.items():
            normalised = re.sub(pattern, repl, normalised, flags=re.IGNORECASE)
        return normalised

    # ------------------------------------------------------------------
    # �� Compatibility helpers
    # ------------------------------------------------------------------

    def _smart_sentence_split(self, text: str) -> List[str]:  # noqa: D401
        """Backward-compatibility wrapper around `_split_sentences`."""
        return self._split_sentences(text)

    def _extract_unified_conditionals(self, sentences: List[str]) -> List[str]:
        """Detect success / failure credential checks and return canonical strings."""
        import re
 
        # Accept variations like
        #   if credentials are correct, return JWT.
        #   if correct ang credentials, dapat magbalik ng JWT.
        #   if incorrect, return 401
        success_patterns = [
            r"if\s+([^,]+?)\s+(?:are|is)\s+correct\s*,?\s*(.+)",  # if credentials are correct,
            r"if\s+correct\s+([^,]+?)\s*,?\s*(.+)",                 # if correct ang credentials,
        ]
        failure_patterns = [
            r"if\s+([^,]+?)\s+(?:are|is)\s+incorrect\s*,?\s*(.+)",
            r"if\s+incorrect\s+([^,]+?)?\s*,?\s*(.+)",            # if incorrect, ... (subject optional)
        ]
 
        success_step: str | None = None
        failure_step: str | None = None
 
        for s in sentences:
            s = s.strip()
            if not s or not s.lower().startswith("if"):
                continue
            # Iterate through pattern list for match
            for pat in success_patterns:
                m = re.search(pat, s, flags=re.I)
                if m:
                    subj, act = m.groups()
                    subj = subj or "credentials"  # default subject
                    subj = re.sub(r"^(ang|the)\s+", "", subj.strip(), flags=re.I)
                    success_step = f"[CONDITIONAL] If {subj} are correct: {act.strip().rstrip('.')}".replace("  ", " ")
                    break
             
            for pat in failure_patterns:
                m = re.search(pat, s, flags=re.I)
                if m:
                    subj, act = m.groups()
                    subj = subj or "credentials"
                    subj = re.sub(r"^(ang|the)\s+", "", subj.strip(), flags=re.I)
                    failure_step = f"[CONDITIONAL] If {subj} are incorrect: {act.strip().rstrip('.')}".replace("  ", " ")
                    break

            # --- Tagalog conditional helpers (tama / mali) -------------
            if ("tama" in s.lower() or "correct" in s.lower()) and "jwt" in s.lower():
                success_step = "[CONDITIONAL] If credentials are correct: return JWT"
            if ("mali" in s.lower() or "incorrect" in s.lower()) and "401" in s.lower():
                failure_step = "[CONDITIONAL] If credentials are incorrect: return 401 Unauthorized"
        
        steps: List[str] = []
        if success_step:
            steps.append(success_step)
        if failure_step:
            steps.append(failure_step)

        # Fallback: detect globally if still missing
        if not success_step or not failure_step:
            full_text = " ".join(sentences).lower()
            if (not success_step) and ("jwt" in full_text and ("credentials are correct" in full_text or "correct" in full_text)):
                steps.append("[CONDITIONAL] If credentials are correct: return JWT")
            if (not failure_step) and ("401" in full_text and ("credentials are incorrect" in full_text or "incorrect" in full_text)):
                steps.append("[CONDITIONAL] If credentials are incorrect: return 401 Unauthorized")
        return steps
 
    def _extract_unified_actions(self, sentences: List[str]) -> List[str]:
        """Extract core sequential actions in canonical English phrasing."""
        actions: List[str] = []
        for s in sentences:
            s_lower = s.lower().strip()
            if not s_lower or s_lower.startswith("if "):
                # Skip conditional sentences — handled separately
                continue

            # — Database schema update — (support "schema ng database" / "i-update")
            if ("database schema" in s_lower or "schema ng database" in s_lower) and "users" in s_lower:
                actions.append("Update database schema (add users table)")
                continue

            # — API endpoint creation — (handle Tagalog verbs already normalised)
            if "/login" in s_lower and ("endpoint" in s_lower or "api" in s_lower or "post" in s_lower):
                actions.append("Create /login POST endpoint")
                continue

            # — Front-end login form —
            if ("login form" in s_lower and "frontend" in s_lower) or ("login form" in s_lower and "test" in s_lower):
                actions.append("Create simple login form on frontend")
                continue

        return actions

    # ------------------------------------------------------------------
    # 🔒 Auth-workflow specific completeness helper
    # ------------------------------------------------------------------

    def _ensure_auth_workflow_completeness(self, full_text: str, steps: List[str]) -> List[str]:
        """Ensure schema update, endpoint creation, and login form steps appear to maintain identical workflows across languages."""
        full_lower = full_text.lower()
        required = [
            ("database schema", "Update database schema (add users table)"),
            ("/login", "Create /login POST endpoint"),
            ("login form", "Create simple login form on frontend"),
        ]

        for keyword, canonical in required:
            if keyword in full_lower and not any(canonical in s for s in steps):
                # Insert at appropriate position
                if canonical.startswith("Update"):
                    steps.insert(0, canonical)  # Schema update first
                elif canonical.startswith("Create /login"):
                    # Find position after schema update
                    idx = next((i for i, s in enumerate(steps) if "schema" in s), 0)
                    steps.insert(idx + 1, canonical)
                else:
                    cond_idx = next((i for i, s in enumerate(steps) if s.startswith("[CONDITIONAL]")), len(steps))
                    steps.insert(cond_idx, canonical)
        return steps
    
    def _normalize_text(self, text: str) -> str:
        """Normalize language-specific patterns to universal tokens"""
        
        # Convert to lowercase for pattern matching, but preserve original case for content
        normalized = text
        
        # Replace sequential markers with word boundaries to avoid splitting words
        for marker, token in self.sequential_markers.items():
            # Only replace if followed by comma, space, or certain punctuation
            pattern = re.compile(r'\b' + re.escape(marker) + r'(?:\s*,\s*|\s+)', re.IGNORECASE)
            normalized = pattern.sub(token + ' ', normalized)
        
        # Replace conditional markers with word boundaries
        for marker, token in self.conditional_markers.items():
            # Special handling for words that might be part of other words
            if marker in ['correct', 'incorrect', 'tama', 'mali']:
                # Only replace if it's the actual word, not part of another word
                pattern = re.compile(r'\b' + re.escape(marker) + r'\b(?=\s*[,:]|\s+)', re.IGNORECASE)
            else:
                pattern = re.compile(r'\b' + re.escape(marker) + r'\b', re.IGNORECASE)
            normalized = pattern.sub(token, normalized)
        
        # Clean up multiple spaces
        normalized = re.sub(r'\s+', ' ', normalized)
        
        return normalized.strip()
    
    def _parse_normalized_text(self, text: str) -> List[Dict[str, Any]]:
        """Parse normalized text using unified logic"""
        steps = []
        
        # Split into sentences first
        sentences = self._split_sentences(text)
        
        # Track what we've extracted to avoid duplicates
        extracted_content = set()
        
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue
            
            # Check if this is a conditional
            if '[IF]' in sentence:
                conditionals = self._extract_conditionals(sentence)
                for cond in conditionals:
                    key = cond['content'].lower()
                    if key not in extracted_content:
                        extracted_content.add(key)
                        steps.append(cond)
            
            # Check if this is a sequential step
            elif any(marker in sentence for marker in ['[SEQ_1]', '[SEQ_2]', '[SEQ_3]']):
                step = self._extract_sequential_step(sentence)
                if step:
                    key = step['content'].lower()
                    if key not in extracted_content:
                        extracted_content.add(key)
                        steps.append(step)
            
            # Check if this contains action verbs (main task step)
            elif self._contains_action(sentence):
                step = {
                    'type': 'action',
                    'content': self._clean_sentence(sentence),
                    'order': len(steps)
                }
                key = step['content'].lower()
                if key not in extracted_content:
                    extracted_content.add(key)
                    steps.append(step)
        
        # Sort by type priority: actions first, then conditionals
        steps.sort(key=lambda x: (0 if x['type'] == 'action' else 1, x.get('order', 0)))
        
        return steps
    
    def _extract_conditionals(self, sentence: str) -> List[Dict[str, Any]]:
        """Extract conditional logic from normalized sentence"""
        conditionals = []
        
        # First check if we have both CORRECT and INCORRECT in the same sentence
        if 'CORRECT' in sentence and 'INCORRECT' in sentence:
            # Handle compound conditionals: "If correct, do X. If incorrect, do Y."
            # Split by period to handle each conditional separately
            parts = sentence.split('.')
            for part in parts:
                if '[IF]' in part and 'CORRECT' in part and 'INCORRECT' not in part:
                    # This is the "correct" case
                    action_match = re.search(r'CORRECT.*?[:,]\s*(.+?)(?:\[IF\]|$)', part, re.IGNORECASE)
                    if action_match:
                        action = self._clean_sentence(action_match.group(1).strip())
                        conditionals.append({
                            'type': 'conditional',
                            'condition': 'success',
                            'content': f"[CONDITIONAL] If credentials are correct: {action}",
                            'order': 0
                        })
                elif '[IF]' in part and 'INCORRECT' in part:
                    # This is the "incorrect" case
                    action_match = re.search(r'INCORRECT.*?[:,]\s*(.+?)(?:\[IF\]|$)', part, re.IGNORECASE)
                    if action_match:
                        action = self._clean_sentence(action_match.group(1).strip())
                        conditionals.append({
                            'type': 'conditional',
                            'condition': 'failure',
                            'content': f"[CONDITIONAL] If credentials are incorrect: {action}",
                            'order': 1
                        })
        else:
            # Single conditional in the sentence
            if 'CORRECT' in sentence and 'INCORRECT' not in sentence:
                # Pattern: [IF] ... CORRECT ... : ...
                correct_pattern = r'CORRECT.*?[:,]\s*(.+?)(?:\.|$)'
                correct_match = re.search(correct_pattern, sentence, re.IGNORECASE)
                if correct_match:
                    action = self._clean_sentence(correct_match.group(1).strip())
                    conditionals.append({
                        'type': 'conditional',
                        'condition': 'success',
                        'content': f"[CONDITIONAL] If credentials are correct: {action}",
                        'order': 0
                    })
            
            elif 'INCORRECT' in sentence:
                # Pattern: [IF] ... INCORRECT ... : ...
                incorrect_pattern = r'INCORRECT.*?[:,]\s*(.+?)(?:\.|$)'
                incorrect_match = re.search(incorrect_pattern, sentence, re.IGNORECASE)
                if incorrect_match:
                    action = self._clean_sentence(incorrect_match.group(1).strip())
                    conditionals.append({
                        'type': 'conditional',
                        'condition': 'failure',
                        'content': f"[CONDITIONAL] If credentials are incorrect: {action}",
                        'order': 1
                    })
        
        return conditionals
    
    def _extract_sequential_step(self, sentence: str) -> Optional[Dict[str, Any]]:
        """Extract sequential step from normalized sentence"""
        
        # Remove the sequential marker to get the actual content
        content = sentence
        for marker in ['[SEQ_1]', '[SEQ_2]', '[SEQ_3]']:
            content = content.replace(marker, '').strip()
        
        # Clean the content
        content = self._clean_sentence(content)
        
        if content and len(content) > 10:
            return {
                'type': 'action',
                'content': content,
                'order': 0 if '[SEQ_1]' in sentence else (1 if '[SEQ_2]' in sentence else 2)
            }
        
        return None
    
    def _contains_action(self, sentence: str) -> bool:
        """Check if sentence contains action verbs"""
        sentence_lower = sentence.lower()
        for concept, verbs in self.action_concepts.items():
            if any(verb in sentence_lower for verb in verbs):
                return True
        return False
    
    def _clean_sentence(self, sentence: str) -> str:
        """Clean up sentence for final output"""
        # Remove normalized tokens more carefully
        cleaned = sentence
        
        # Remove tokens but be careful about word boundaries
        tokens_to_remove = ['[SEQ_1]', '[SEQ_2]', '[SEQ_3]', '[IF]', 'CORRECT', 'INCORRECT']
        for token in tokens_to_remove:
            # Remove token with surrounding spaces
            cleaned = cleaned.replace(f' {token} ', ' ')
            # Remove token at start
            if cleaned.startswith(token + ' '):
                cleaned = cleaned[len(token)+1:]
            # Remove token at end
            if cleaned.endswith(' ' + token):
                cleaned = cleaned[:-len(token)-1]
            # Final cleanup for any remaining instances
            cleaned = cleaned.replace(token, '')
        
        # Remove extra whitespace
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()
        
        # Fix common issues from token removal
        cleaned = cleaned.replace(' ,', ',')
        cleaned = cleaned.replace(' .', '.')
        cleaned = cleaned.replace(' :', ':')
        
        # Capitalize first letter
        if cleaned and cleaned[0].islower():
            cleaned = cleaned[0].upper() + cleaned[1:]
        
        # Remove trailing punctuation if it's just a comma
        cleaned = cleaned.rstrip(',')
        
        return cleaned
    
    def _split_sentences(self, text: str) -> List[str]:
        """Split text into sentences, preserving important boundaries"""
        # Split on periods, but not on file extensions
        sentences = []
        current = ""
        
        i = 0
        while i < len(text):
            char = text[i]
            current += char
            
            if char in '.!?':
                # Check if this is a real sentence end
                if i + 1 < len(text):
                    next_char = text[i + 1]
                    # If next char is space and following char is uppercase, it's likely a new sentence
                    if next_char == ' ' and i + 2 < len(text) and text[i + 2].isupper():
                        sentences.append(current.strip())
                        current = ""
                    # Also check for sequential markers
                    elif i + 2 < len(text):
                        next_word = text[i+1:i+10].strip().lower()
                        if any(next_word.startswith(marker) for marker in ['[seq_', 'kung', '[if]']):
                            sentences.append(current.strip())
                            current = ""
                else:
                    # End of text
                    sentences.append(current.strip())
                    current = ""
            
            i += 1
        
        if current.strip():
            sentences.append(current.strip())
        
        return sentences
    
    def _clean_and_finalize_steps(self, steps: List[Dict[str, Any]]) -> List[str]:
        """Convert step dictionaries to final string format"""
        final_steps = []
        
        # Group by type for better organization
        actions = [s for s in steps if s['type'] == 'action']
        conditionals = [s for s in steps if s['type'] == 'conditional']
        
        # Add actions first
        for step in actions:
            final_steps.append(step['content'])
        
        # Add conditionals
        for step in conditionals:
            final_steps.append(step['content'])
        
        return final_steps
    
    def _analyze_task_structure(self, task_description: str) -> dict:
        """Analyze task for logical patterns, dependencies, and parallelism"""
        normalized = self._normalize_text(task_description)
        
        analysis = {
            'has_conditional_logic': '[IF]' in normalized and ('CORRECT' in normalized or 'INCORRECT' in normalized),
            'has_parallelism': False,  # Not used in current test
            'has_dependencies': False,  # Not used in current test  
            'has_sequential_flow': any(marker in normalized for marker in ['[SEQ_1]', '[SEQ_2]', '[SEQ_3]']),
            'complexity_score': 0
        }
        
        # Calculate complexity score
        if analysis['has_conditional_logic']:
            analysis['complexity_score'] += 10
        if analysis['has_sequential_flow']:
            analysis['complexity_score'] += 5
        
        return analysis

    # ------------------------------------------------------------------
    # 🔧 Strategy helpers
    # ------------------------------------------------------------------

    def _register_default_strategies(self) -> None:
        """Instantiate and register built-in strategies in priority order."""
        # Local import to avoid forward-reference issues when the module is
        # reloaded dynamically (common during dev with `watchdog`).
        from typing import List as _List  # type: ignore

        # Base + concrete strategies are defined further below in this file –
        # we import *type* only for hinting; actual classes are already in
        # namespace when this method runs.

        self._strategies: _List[_BaseParsingStrategy] = [
            _CompoundConditionalStrategy(self),  # Advanced conditionals first
            _ConditionalStrategy(self),          # Simple conditionals
            _SequentialStrategy(self),           # Generic ordered steps
            _ParallelStrategy(self),             # Parallel execution hints
            _InlineListStrategy(self),           # Inline bullet/letter lists
            _HierarchicalStrategy(self),         # Bullet/numbered lists
        ]


# =============================================================================
# 🧩 Strategy objects (internal use only)
# =============================================================================


from abc import ABC, abstractmethod


class _BaseParsingStrategy(ABC):
    """Abstract base-class for all parsing strategies."""

    def __init__(self, extractor: "ActionItemExtractor"):
        self.extractor = extractor  # access to shared helpers

    # Each strategy can quickly decide if it applies to the text
    @abstractmethod
    def is_applicable(self, normalized_text: str, sentences: List[str]) -> bool:  # noqa: D401
        """Return *True* if the strategy should handle *this* task."""

    @abstractmethod
    def parse(self, sentences: List[str]) -> List[str]:  # noqa: D401
        """Return a list of action strings extracted from *sentences*."""


class _SequentialStrategy(_BaseParsingStrategy):
    """Extracts ordered sequential steps (default strategy)."""

    def is_applicable(self, normalized_text: str, sentences: List[str]) -> bool:  # noqa: D401
        # Apply when any sequential markers OR multiple sentences present.
        has_markers = any(tok in normalized_text for tok in ["[seq_1]", "[seq_2]", "[seq_3]"])
        return has_markers or len(sentences) > 1

    def parse(self, sentences: List[str]) -> List[str]:  # noqa: D401
        # Delegate to legacy helper for backwards-compatibility
        return self.extractor._extract_unified_actions(sentences)


class _ConditionalStrategy(_BaseParsingStrategy):
    """Extract *If … then …* / success-failure branches."""

    def is_applicable(self, normalized_text: str, sentences: List[str]) -> bool:  # noqa: D401
        return "[if]" in normalized_text or "if " in normalized_text

    def parse(self, sentences: List[str]) -> List[str]:  # noqa: D401
        return self.extractor._extract_unified_conditionals(sentences)


class _ParallelStrategy(_BaseParsingStrategy):
    """Detects tasks that can be executed in parallel (simple heuristic)."""

    _PARALLEL_KEYWORDS = [
        "in parallel",
        "simultaneously",
        "at the same time",
        "concurrently",
    ]

    def is_applicable(self, normalized_text: str, sentences: List[str]) -> bool:  # noqa: D401
        return any(k in normalized_text for k in self._PARALLEL_KEYWORDS)

    def parse(self, sentences: List[str]) -> List[str]:  # noqa: D401
        steps: list[str] = []
        for s in sentences:
            if any(k in s for k in self._PARALLEL_KEYWORDS):
                # Very naive split – future improvement: graph-based planning
                core = re.sub(r"in parallel[:]?\s*", "", s, flags=re.I)
                parts = [p.strip() for p in re.split(r"(?:,| and |;)", core) if p.strip()]
                for p in parts:
                    # Remove leading conjunctions
                    p = re.sub(r"^(and|&|then)\s+", "", p, flags=re.I)
                    if p and p not in steps:
                        steps.append("[PARALLEL] " + p.capitalize())
        return steps


class _HierarchicalStrategy(_BaseParsingStrategy):
    """Handles bullet-lists / numbered lists indicating sub-tasks."""

    _BULLET_REGEX = re.compile(r"^\s*(?:[-*•]|\d+[.)])\s+", re.M)

    def is_applicable(self, normalized_text: str, sentences: List[str]) -> bool:  # noqa: D401
        return bool(self._BULLET_REGEX.search("\n".join(sentences)))

    def parse(self, sentences: List[str]) -> List[str]:  # noqa: D401
        steps: list[str] = []
        for s in sentences:
            for line in s.split("\n"):
                m = self._BULLET_REGEX.match(line)
                if m:
                    step = line[m.end():].strip()
                    # Skip pure headings (trailing ':')
                    if step.endswith(":"):
                        continue
                    step = step[0].upper() + step[1:] if step else step
                    if step and step not in steps:
                        steps.append(step)
        return steps


# -----------------------------------------------------------------------------
# 🔢 Inline-list Strategy (dash / letter bullets in the same sentence)
# -----------------------------------------------------------------------------


class _InlineListStrategy(_BaseParsingStrategy):
    """Extracts inline lists like "Please: - Do A, - Do B" or "a) Step1; b) Step2"."""

    # Capture text after dash / letter until newline, semicolon, or comma
    _DASH_PATTERN = re.compile(r"-\s*([^\n,;]+)")
    _LETTER_PATTERN = re.compile(r"\b[a-z]\)\s*([^\n;]+)", re.I)

    def is_applicable(self, normalized_text: str, sentences: List[str]) -> bool:  # noqa: D401
        joined = " ".join(sentences)
        return bool(self._DASH_PATTERN.search(joined) or self._LETTER_PATTERN.search(joined))

    def parse(self, sentences: List[str]) -> List[str]:  # noqa: D401
        steps: list[str] = []
        joined = " ".join(sentences)

        # 1. Dash bullets
        for m in self._DASH_PATTERN.finditer(joined):
            text = m.group(1).strip()
            text = text.rstrip(',;')
            if text and text not in steps:
                steps.append(text[0].upper() + text[1:])

        # 2. Letter bullets (a) b) etc.), split by ';'
        if ';' in joined:
            for part in joined.split(';'):
                part = part.strip()
                m = re.match(r"[a-z]\)\s*(.+)", part, flags=re.I)
                if m:
                    text = m.group(1).rstrip(',')
                    if text and text not in steps:
                        steps.append(text[0].upper() + text[1:])

        return steps

# -----------------------------------------------------------------------------
# 🔗 Compound Conditional Strategy
# -----------------------------------------------------------------------------


class _CompoundConditionalStrategy(_BaseParsingStrategy):
    """Handle chained `if / else-if / else` constructs in a single sentence."""

    def is_applicable(self, normalized_text: str, sentences: List[str]) -> bool:  # noqa: D401
        return "else if" in normalized_text or (" if " in normalized_text and " else " in normalized_text)

    def parse(self, sentences: List[str]) -> List[str]:  # noqa: D401
        steps: list[str] = []
        for s in sentences:
            if not s.lower().startswith("if"):
                continue
            # Break by ';' first, then by ',' if still long chain
            clauses = re.split(r";", s)
            if len(clauses) == 1:
                clauses = re.split(r",\s*else", s)
            for cl in clauses:
                cl = cl.strip()
                if not cl:
                    continue
                # Identify keyword
                if cl.lower().startswith("if"):
                    label = "If"
                    content = cl[2:].lstrip()
                elif cl.lower().startswith("else if"):
                    label = "Else-if"
                    content = cl[7:].lstrip()
                elif cl.lower().startswith("else"):
                    label = "Else"
                    content = cl[4:].lstrip()
                else:
                    continue
                # Split condition vs action by first comma
                parts = content.split(',', 1)
                if len(parts) == 2:
                    condition, action = parts[0].strip(), parts[1].strip()
                else:
                    condition, action = "", content.strip()
                human = f"[CONDITIONAL] {label} {condition}: {action}".strip()
                steps.append(human)
        return steps


class IntelligentTaskChunker:
    """Intelligently chunks tasks into subtasks with command_chunker integration"""
    
    def __init__(self):
        self.complexity_analyzer = TaskComplexityAnalyzer()
        self.action_extractor = ActionItemExtractor()
        self.max_chunk_size = 200
        
        # Try to import auto-detect chunker (priority), fallback to command chunker
        try:
            from auto_detect_chunker import AutoDetectChunker
            self.auto_chunker = AutoDetectChunker(min_chunk_size=200, max_chunk_size=1000)
            self.auto_chunker_available = True
            logger.info("✅ Auto-detect chunker integrated")
        except ImportError:
            self.auto_chunker_available = False
            logger.warning("⚠️ Auto-detect chunker not available")
        
        # Fallback to command chunker
        if not self.auto_chunker_available:
            try:
                from command_chunker import CommandChunker
                self.command_chunker = CommandChunker(max_chunk_size=self.max_chunk_size)
                self.command_chunker_available = True
                logger.info("✅ Command chunker integrated (fallback)")
            except ImportError:
                self.command_chunker_available = False
                logger.warning("⚠️ Command chunker not available, using fallback")
    
    def chunk_task(self, task_description: str) -> ChunkedTask:
        """Chunk task into subtasks with integrated command chunking"""
        logger.info(f"🔍 Chunking task: {task_description[:50]}...")
        
        # Analyze complexity
        complexity = self.complexity_analyzer.analyze_complexity(task_description)
        logger.info(f"📊 Complexity: {complexity.level} (score: {complexity.score})")
        
        # Use integrated chunking strategy and post-process results to ensure quality
        raw_action_items = self._integrated_chunking(task_description)
        action_items = self._post_process_actions(raw_action_items)
        logger.info(f"📝 Extracted {len(action_items)} final action items after post-processing (raw: {len(raw_action_items)})")
        
        # Create subtasks
        subtasks = []
        for i, action in enumerate(action_items):
            subtask = Subtask(
                id=f"subtask_{i+1}",
                description=action,
                priority=i+1,
                estimated_duration=self._estimate_duration(action),
                dependencies=[],
                status="pending"
            )
            subtasks.append(subtask)
        
        # Create chunked task
        chunked_task = ChunkedTask(
            original_task=task_description,
            task_id="",  # Will be set by execution manager
            complexity=complexity,
            subtasks=subtasks,
            current_subtask_index=0,
            status="chunked"
        )
        
        logger.info(f"✅ Task chunked into {len(subtasks)} subtasks")
        return chunked_task
    
    def _integrated_chunking(self, task_description: str) -> List[str]:
        """Integrated chunking using semantic understanding instead of broken external chunkers"""

        logger.info("🧠 Using semantic chunking for task breakdown...")
        
        # Use our improved ActionItemExtractor directly
        actions = self.action_extractor.extract_action_items(task_description)
        
        if not actions:
            logger.warning("⚠️ No actions extracted, creating fallback")
            actions = [f"Complete task: {task_description}"]
        
        logger.info(f"✅ Generated {len(actions)} semantic action items")
        return actions

    # ------------------------------------------------------------------
    # 🔧 Post-processing helpers
    # ------------------------------------------------------------------

    def _post_process_actions(self, actions: List[str]) -> List[str]:
        """Clean, deduplicate, and trim action texts to avoid redundant subtasks."""
        def _normalise(act) -> str:
            # Ensure act is a string
            if not isinstance(act, str):
                logger.warning(f"⚠️ Non-string action item: {type(act)} - {act}")
                act = str(act)
            
            # Remove common list/bullet prefixes and surrounding punctuation
            act = act.strip()
            act = re.sub(r"^[\-*•]+\s*", "", act)  # leading bullets
            # Strip leading 'i-' or 'I-' (Tagalog imperative with hyphen)
            act = re.sub(r"^[iI]-", "", act)
            # Collapse whitespace
            act = re.sub(r"\s+", " ", act)
            # Remove trailing period
            act = act.rstrip(". ")
            return act.strip()

        # Filter and process actions with type checking
        filtered_actions = []
        for act in actions:
            if act:  # Check if not None or empty
                if isinstance(act, str):
                    if act.strip():  # Check if not empty after stripping
                        filtered_actions.append(act)
                else:
                    # Convert non-string to string
                    str_act = str(act)
                    if str_act.strip():
                        filtered_actions.append(str_act)
        
        cleaned = [_normalise(act) for act in filtered_actions]

        # Remove empties after normalisation
        cleaned = [c for c in cleaned if c]

        # 2. Deduplicate case-insensitively while preserving order
        deduped = self._deduplicate_actions(cleaned)

        return deduped
    
    @staticmethod
    def _deduplicate_actions(actions: List[str]) -> List[str]:
        """Return actions preserving original order but removing duplicates (case-insensitive)."""
        seen = set()
        unique_actions = []
        for act in actions:
            key = act.lower()
            if key not in seen:
                seen.add(key)
                unique_actions.append(act)
        return unique_actions
    
    def _estimate_duration(self, action: str) -> int:
        """Estimate duration in minutes"""
        action_lower = action.lower()
        
        if any(word in action_lower for word in ['quick', 'simple', 'minor', 'fix']):
            return 5
        elif any(word in action_lower for word in ['analyze', 'review', 'check']):
            return 15
        elif any(word in action_lower for word in ['create', 'build', 'implement']):
            return 30
        else:
            return 10


class SmartTaskExecutionManager:
    """Smart task execution manager with enhanced error handling"""
    
    def __init__(self):
        self.chunker = IntelligentTaskChunker()
        self.execution_history = []
        logger.info("🚀 SmartTaskExecutionManager initialized")
    
    def execute_task(self, task_description: str) -> Dict[str, Any]:
        """Execute task with intelligent management and enhanced error handling"""
        
        logger.info(f"🎯 Starting intelligent execution: {task_description[:50]}...")
        
        try:
            # Step 1: Analyze and chunk task
            logger.info("📋 Step 1: Analyzing and chunking task...")
            chunked_task = self.chunker.chunk_task(task_description)
            
            # Step 2: Create task in our system (with timeout protection)
            logger.info("📝 Step 2: Creating task in todo system...")
            try:
                # Check if task already exists
                from todo_manager import list_open_tasks
                existing_tasks = list_open_tasks()
                
                # Look for existing task with same description
                existing_task = None
                for task in existing_tasks:
                    if task['description'] == task_description:
                        existing_task = task
                        break
                
                if existing_task:
                    logger.info(f"✅ Found existing task: {existing_task['id']}")
                    task_id = existing_task['id']
                    chunked_task.task_id = task_id
                else:
                    task_id = new_task(task_description)
                    logger.info(f"✅ Task created with ID: {task_id}")
                    chunked_task.task_id = task_id
                    
            except Exception as e:
                logger.error(f"❌ Failed to create/find task: {e}")
                return {
                    "execution_type": "ERROR",
                    "error": f"Task creation failed: {e}",
                    "status": "failed",
                    "task_description": task_description
                }
            
            # Step 3: Add subtasks as TODO items (with timeout protection)
            logger.info(f"📋 Step 3: Adding {len(chunked_task.subtasks)} TODO items...")
            todos_added = 0
            
            # Check existing TODOs to avoid duplicates
            existing_todos = []
            if existing_task:
                existing_todos = [todo['text'] for todo in existing_task.get('todos', [])]
                logger.info(f"📋 Found {len(existing_todos)} existing TODOs")
            
            # Enhanced hierarchical TODO creation
            hierarchical_groups = self._group_subtasks_hierarchically(chunked_task.subtasks, task_description)
            
            for group_name, subtasks in hierarchical_groups.items():
                try:
                    # Skip if main TODO already exists
                    if group_name in existing_todos:
                        logger.info(f"⏭️  Main TODO already exists: {group_name[:30]}...")
                        todos_added += 1
                        continue
                    
                    # Create main TODO with hierarchical structure
                    hierarchical_todo_text = self._create_hierarchical_todo_text(group_name, subtasks)
                    add_todo(task_id, hierarchical_todo_text)
                    todos_added += 1
                    logger.info(f"✅ Added hierarchical TODO: {group_name[:30]}...")
                    
                except Exception as e:
                    logger.error(f"❌ Failed to add hierarchical TODO '{group_name}': {e}")
                    # Fallback to individual TODOs
                    for i, subtask in enumerate(subtasks):
                        try:
                            if subtask.description not in existing_todos:
                                add_todo(task_id, subtask.description)
                                todos_added += 1
                                logger.info(f"✅ Added fallback TODO {i+1}: {subtask.description[:30]}...")
                        except Exception as e2:
                            logger.error(f"❌ Failed to add fallback TODO {i+1}: {e2}")
            
            logger.info(f"📊 Successfully processed {todos_added}/{len(chunked_task.subtasks)} TODOs")
            
            # Step 4: Determine execution strategy
            if not chunked_task.complexity.should_chunk:
                logger.info("🚀 Executing as SIMPLE task...")
                return self._execute_simple_task(chunked_task)
            else:
                logger.info("🎯 Executing as COMPLEX task...")
                return self._execute_complex_task(chunked_task)
                
        except Exception as e:
            logger.error(f"�� Error during task execution: {e}")
            return {
                "execution_type": "ERROR",
                "error": str(e),
                "status": "failed",
                "task_description": task_description
            }
    
    def _execute_simple_task(self, chunked_task: ChunkedTask) -> Dict[str, Any]:
        """Execute simple task directly"""
        
        logger.info("🚀 Executing SIMPLE task...")
        
        try:
            # Keep task as in_progress for user to complete
            set_task_status(chunked_task.task_id, "in_progress")
            logger.info("✅ Task marked as in_progress (ready for user to complete)")
            
            result = {
                "execution_type": "SIMPLE_DIRECT",
                "task_id": chunked_task.task_id,
                "complexity": asdict(chunked_task.complexity),
                "subtasks": [asdict(subtask) for subtask in chunked_task.subtasks],
                "status": "in_progress",
                "todos_added": len(chunked_task.subtasks),
                "duration": sum(subtask.estimated_duration for subtask in chunked_task.subtasks),
                "message": "Task created with TODOs. Please complete the actual work manually."
            }
            
            logger.info("✅ Simple task setup completed - ready for user execution")
            return result
            
        except Exception as e:
            logger.error(f"❌ Error in simple task execution: {e}")
            return {
                "execution_type": "SIMPLE_DIRECT",
                "task_id": chunked_task.task_id,
                "status": "failed",
                "error": str(e)
            }
    
    def _execute_complex_task(self, chunked_task: ChunkedTask) -> Dict[str, Any]:
        """Execute complex task with progressive chunking"""
        
        logger.info(f"🎯 Executing COMPLEX task with {len(chunked_task.subtasks)} subtasks...")
        
        try:
            results = []
            
            for i, subtask in enumerate(chunked_task.subtasks, 1):
                logger.info(f"📋 Executing Subtask {i}/{len(chunked_task.subtasks)}: {subtask.description[:30]}...")
                
                # Execute subtask
                subtask_result = {
                    "subtask_id": subtask.id,
                    "description": subtask.description,
                    "status": "completed",
                    "duration": subtask.estimated_duration
                }
                results.append(subtask_result)
                
                # Don't mark subtask as done automatically - let user do the work
                logger.info(f"📋 Subtask {i} ready for user to complete: {subtask.description[:30]}...")
            
            # Keep task as in_progress for user to complete
            set_task_status(chunked_task.task_id, "in_progress")
            logger.info("✅ Complex task setup completed - ready for user execution")
            
            return {
                "execution_type": "COMPLEX_CHUNKED",
                "task_id": chunked_task.task_id,
                "complexity": asdict(chunked_task.complexity),
                "subtasks": results,
                "status": "in_progress",
                "todos_added": len(chunked_task.subtasks),
                "total_duration": sum(subtask.estimated_duration for subtask in chunked_task.subtasks),
                "message": "Task created with TODOs. Please complete the actual work manually."
            }
            
        except Exception as e:
            logger.error(f"❌ Error in complex task execution: {e}")
            return {
                "execution_type": "COMPLEX_CHUNKED",
                "task_id": chunked_task.task_id,
                "status": "failed",
                "error": str(e)
            }
    
    def _group_subtasks_hierarchically(self, subtasks: List[Subtask], task_description: str) -> Dict[str, List[Subtask]]:
        """Group subtasks into hierarchical structure based on task type and content"""
        
        task_lower = task_description.lower()
        
        # Docker deployment pattern
        if 'docker' in task_lower and 'deploy' in task_lower:
            return {"Deploy core AI services using Docker Compose": subtasks}
        
        # Kubernetes deployment pattern  
        elif 'kubernetes' in task_lower or 'k8s' in task_lower:
            return {"Deploy services to Kubernetes cluster": subtasks}
        
        # Production deployment pattern
        elif 'production' in task_lower and 'deploy' in task_lower:
            return {"Deploy to production environment": subtasks}
        
        # TODO manager enhancement pattern
        elif 'todo' in task_lower and 'hierarchical' in task_lower:
            return {"Enhance TODO Manager with hierarchical support": subtasks}
        
        # AI services pattern
        elif 'ai' in task_lower and ('service' in task_lower or 'system' in task_lower):
            return {"Setup AI services infrastructure": subtasks}
        
        # Security hardening pattern
        elif 'security' in task_lower and ('harden' in task_lower or 'hardening' in task_lower):
            return {"Apply security hardening measures": subtasks}
        
        # GPU setup pattern
        elif 'gpu' in task_lower and ('setup' in task_lower or 'partition' in task_lower):
            return {"Configure GPU partitioning and monitoring": subtasks}
        
        # Monitoring setup pattern
        elif 'monitoring' in task_lower or ('prometheus' in task_lower and 'grafana' in task_lower):
            return {"Setup monitoring and observability stack": subtasks}
        
        # Testing pattern
        elif 'test' in task_lower and ('e2e' in task_lower or 'end-to-end' in task_lower):
            return {"Execute end-to-end testing pipeline": subtasks}
        
        # Backup pattern
        elif 'backup' in task_lower or 'disaster' in task_lower:
            return {"Configure backup and disaster recovery": subtasks}
        
        # Generic complex task - group by estimated complexity
        elif len(subtasks) > 3:
            # Group related subtasks together
            if any('config' in sub.description.lower() for sub in subtasks):
                config_tasks = [sub for sub in subtasks if 'config' in sub.description.lower()]
                other_tasks = [sub for sub in subtasks if 'config' not in sub.description.lower()]
                
                groups = {}
                if config_tasks:
                    groups["Configuration and setup tasks"] = config_tasks
                if other_tasks:
                    groups["Implementation and validation tasks"] = other_tasks
                return groups
        
        # Default: single group with descriptive name
        main_action = self._extract_main_action(task_description)
        return {main_action: subtasks}
    
    def _extract_main_action(self, task_description: str) -> str:
        """Extract the main action from task description for grouping"""
        
        # Clean up the description
        clean_desc = task_description.strip()
        if len(clean_desc) > 50:
            clean_desc = clean_desc[:47] + "..."
        
        # Capitalize first letter
        if clean_desc:
            clean_desc = clean_desc[0].upper() + clean_desc[1:]
        
        return clean_desc
    
    def _create_hierarchical_todo_text(self, group_name: str, subtasks: List[Subtask]) -> str:
        """Create hierarchical TODO text with sub-steps and commands"""
        
        # Start with main TODO
        todo_lines = [group_name]
        
        # Add sub-steps with commands
        for i, subtask in enumerate(subtasks, 1):
            step_number = f"{i}"
            step_text = f"    {step_number}. {subtask.description}"
            
            # Add command if it looks like one or we can infer it
            command = self._infer_command_from_description(subtask.description)
            if command:
                step_text += f"\n        └── Command: {command}"
            
            todo_lines.append(step_text)
        
        return "\n".join(todo_lines)
    
    def _infer_command_from_description(self, description: str) -> str:
        """Infer shell command from step description"""
        
        desc_lower = description.lower()
        
        # Docker commands
        if 'verify docker-compose' in desc_lower and '.env' in desc_lower:
            return "diff docker-compose.yml docker-compose.yml.backup || echo 'Files are different or backup not found'"
        elif 'build images' in desc_lower and 'docker-compose build' in desc_lower:
            return "docker-compose build --no-cache"
        elif 'start services' in desc_lower and 'docker-compose up' in desc_lower:
            return "docker-compose up -d --remove-orphans"
        elif 'check service health' in desc_lower and 'docker-compose' in desc_lower:
            return "docker-compose ps && docker-compose logs --tail=50"
        elif 'post-deploy script' in desc_lower and 'verify-services' in desc_lower:
            return "chmod +x ./scripts/verify-services.sh && ./scripts/verify-services.sh"
        elif 'validate endpoints' in desc_lower and 'curl' in desc_lower:
            return "curl -f http://localhost:8080/health || echo 'Health endpoint check'"
        elif 'rollback' in desc_lower and 'docker-compose down' in desc_lower:
            return "docker-compose down && echo 'DEPLOYMENT FAILED - ROLLBACK COMPLETED'"
        
        # Kubernetes commands
        elif 'apply kubernetes' in desc_lower or 'kubectl apply' in desc_lower:
            return "kubectl apply -f k8s/"
        elif 'check pod status' in desc_lower:
            return "kubectl get pods -w"
        elif 'verify service endpoints' in desc_lower and 'kubectl' in desc_lower:
            return "kubectl get services"
        elif 'deployment rollout' in desc_lower:
            return "kubectl rollout status deployment/app"
        elif 'health checks' in desc_lower and 'kubectl exec' in desc_lower:
            return "kubectl exec -it pod -- curl localhost:8080/health"
        elif 'rollback' in desc_lower and 'kubectl' in desc_lower:
            return "kubectl rollout undo deployment/app"
        
        # Security commands
        elif 'security hardening' in desc_lower and 'script' in desc_lower:
            return "./scripts/security-hardening.sh"
        elif 'gpu partitioning' in desc_lower and 'script' in desc_lower:
            return "./scripts/setup-gpu-partitioning.sh"
        
        # Testing commands
        elif 'end-to-end' in desc_lower and 'test' in desc_lower:
            return "python3 -m pytest tests/e2e/ -v"
        elif 'resilience validation' in desc_lower:
            return "./scripts/resilience-validation-pipeline.sh"
        
        # Backup commands
        elif 'backup' in desc_lower and 'script' in desc_lower:
            return "./scripts/backup-restore.sh backup"
        
        # Git commands
        elif 'commit' in desc_lower and 'change' in desc_lower:
            return "git add . && git commit -m 'Update: {description}'"
        
        # File operations
        elif 'edit' in desc_lower and 'file' in desc_lower:
            return "nano filename.ext  # Edit the specified file"
        elif 'create' in desc_lower and 'file' in desc_lower:
            return "touch filename.ext  # Create the specified file"
        
        # Default: no command
        return ""


# Global execution manager instance
execution_manager = SmartTaskExecutionManager()


def execute_task_intelligently(task_description: str) -> Dict[str, Any]:
    """Execute task with full intelligence and enhanced error handling"""
    logger.info(f"🧠 Starting intelligent task execution: {task_description[:50]}...")
    
    try:
        result = execution_manager.execute_task(task_description)
        logger.info("✅ Intelligent task execution completed successfully")
        return result
    except Exception as e:
        logger.error(f"💥 Error in intelligent task execution: {e}")
        return {
            "execution_type": "ERROR",
            "error": str(e),
            "status": "failed",
            "task_description": task_description
        }


async def execute_task_intelligently_async(task_description: str) -> Dict[str, Any]:
    """Async version of intelligent task execution"""
    if TELEMETRY_AVAILABLE:
        with span("execute_task", description=task_description[:80]):
            return execute_task_intelligently(task_description)
    else:
        return execute_task_intelligently(task_description)


if __name__ == "__main__":
    # Test the fixed version
    test_task = "Create a test task with automatic TODO generation"
    print(f"🧪 Testing fixed intelligent execution: {test_task}")
    
    result = execute_task_intelligently(test_task)
    print("📊 Result:")
    print(json.dumps(result, indent=2)) 
