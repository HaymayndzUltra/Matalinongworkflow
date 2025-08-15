"""
Challenge Generator Module
Generates and verifies dynamic liveness challenges

This module implements:
- Dynamic challenge generation
- Script templates with variations
- Challenge verification logic
- Anti-replay protection
- Difficulty scaling
"""

import random
import hashlib
import time
import json
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta

# ============= CHALLENGE TYPES =============

class ChallengeAction(Enum):
    """Types of challenge actions"""
    TURN_LEFT = "turn_left"
    TURN_RIGHT = "turn_right"
    LOOK_UP = "look_up"
    LOOK_DOWN = "look_down"
    BLINK = "blink"
    SMILE = "smile"
    OPEN_MOUTH = "open_mouth"
    NOD = "nod"
    SHAKE_HEAD = "shake_head"
    TILT_LEFT = "tilt_left"
    TILT_RIGHT = "tilt_right"
    MOVE_CLOSER = "move_closer"
    MOVE_FARTHER = "move_farther"


class ChallengeDifficulty(Enum):
    """Challenge difficulty levels"""
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"
    EXPERT = "expert"


@dataclass
class ChallengeStep:
    """Individual challenge step"""
    action: ChallengeAction
    duration_ms: int
    instruction: str
    validation_params: Dict[str, Any]
    order: int
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'action': self.action.value,
            'duration_ms': self.duration_ms,
            'instruction': self.instruction,
            'validation_params': self.validation_params,
            'order': self.order
        }


@dataclass
class ChallengeScript:
    """Complete challenge script"""
    challenge_id: str
    session_id: str
    steps: List[ChallengeStep]
    difficulty: ChallengeDifficulty
    created_at: float
    expires_at: float
    max_attempts: int = 3
    anti_replay_token: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'challenge_id': self.challenge_id,
            'session_id': self.session_id,
            'steps': [step.to_dict() for step in self.steps],
            'difficulty': self.difficulty.value,
            'created_at': self.created_at,
            'expires_at': self.expires_at,
            'max_attempts': self.max_attempts,
            'anti_replay_token': self.anti_replay_token,
            'metadata': self.metadata
        }
    
    def get_total_duration_ms(self) -> int:
        """Get total duration of all steps"""
        return sum(step.duration_ms for step in self.steps)


@dataclass
class ChallengeResult:
    """Challenge verification result"""
    challenge_id: str
    passed: bool
    score: float
    steps_completed: int
    steps_total: int
    failure_reasons: List[str]
    completion_time_ms: int
    metadata: Dict[str, Any] = field(default_factory=dict)


# ============= CHALLENGE TEMPLATES =============

class ChallengeTemplates:
    """Pre-defined challenge templates"""
    
    @staticmethod
    def get_easy_templates() -> List[List[ChallengeAction]]:
        """Easy challenge templates (2-3 actions)"""
        return [
            [ChallengeAction.TURN_LEFT, ChallengeAction.TURN_RIGHT],
            [ChallengeAction.LOOK_UP, ChallengeAction.LOOK_DOWN],
            [ChallengeAction.BLINK, ChallengeAction.NOD],
            [ChallengeAction.SMILE, ChallengeAction.BLINK],
            [ChallengeAction.TILT_LEFT, ChallengeAction.TILT_RIGHT],
        ]
    
    @staticmethod
    def get_medium_templates() -> List[List[ChallengeAction]]:
        """Medium challenge templates (3-4 actions)"""
        return [
            [ChallengeAction.TURN_LEFT, ChallengeAction.NOD, ChallengeAction.TURN_RIGHT],
            [ChallengeAction.LOOK_UP, ChallengeAction.BLINK, ChallengeAction.LOOK_DOWN],
            [ChallengeAction.SMILE, ChallengeAction.TURN_LEFT, ChallengeAction.BLINK, ChallengeAction.TURN_RIGHT],
            [ChallengeAction.TILT_LEFT, ChallengeAction.NOD, ChallengeAction.TILT_RIGHT],
            [ChallengeAction.OPEN_MOUTH, ChallengeAction.SHAKE_HEAD, ChallengeAction.BLINK],
        ]
    
    @staticmethod
    def get_hard_templates() -> List[List[ChallengeAction]]:
        """Hard challenge templates (4-5 actions)"""
        return [
            [ChallengeAction.TURN_LEFT, ChallengeAction.LOOK_UP, ChallengeAction.BLINK, 
             ChallengeAction.TURN_RIGHT, ChallengeAction.NOD],
            [ChallengeAction.SMILE, ChallengeAction.TILT_LEFT, ChallengeAction.OPEN_MOUTH,
             ChallengeAction.TILT_RIGHT, ChallengeAction.BLINK],
            [ChallengeAction.LOOK_DOWN, ChallengeAction.TURN_LEFT, ChallengeAction.LOOK_UP,
             ChallengeAction.TURN_RIGHT, ChallengeAction.SHAKE_HEAD],
            [ChallengeAction.MOVE_CLOSER, ChallengeAction.BLINK, ChallengeAction.NOD,
             ChallengeAction.MOVE_FARTHER, ChallengeAction.SMILE],
        ]
    
    @staticmethod
    def get_expert_templates() -> List[List[ChallengeAction]]:
        """Expert challenge templates (5-7 actions)"""
        return [
            [ChallengeAction.TURN_LEFT, ChallengeAction.LOOK_UP, ChallengeAction.BLINK,
             ChallengeAction.TURN_RIGHT, ChallengeAction.LOOK_DOWN, ChallengeAction.NOD,
             ChallengeAction.SMILE],
            [ChallengeAction.TILT_LEFT, ChallengeAction.OPEN_MOUTH, ChallengeAction.TURN_LEFT,
             ChallengeAction.BLINK, ChallengeAction.TURN_RIGHT, ChallengeAction.TILT_RIGHT,
             ChallengeAction.SHAKE_HEAD],
        ]


# ============= INSTRUCTION GENERATOR =============

class InstructionGenerator:
    """Generates human-readable instructions"""
    
    INSTRUCTION_TEMPLATES = {
        ChallengeAction.TURN_LEFT: [
            "Please turn your head to the left",
            "Look to your left",
            "Turn left slowly"
        ],
        ChallengeAction.TURN_RIGHT: [
            "Please turn your head to the right",
            "Look to your right", 
            "Turn right slowly"
        ],
        ChallengeAction.LOOK_UP: [
            "Please look up",
            "Tilt your head up",
            "Look towards the ceiling"
        ],
        ChallengeAction.LOOK_DOWN: [
            "Please look down",
            "Tilt your head down",
            "Look towards the floor"
        ],
        ChallengeAction.BLINK: [
            "Please blink once",
            "Blink your eyes",
            "Close and open your eyes"
        ],
        ChallengeAction.SMILE: [
            "Please smile",
            "Show a smile",
            "Smile naturally"
        ],
        ChallengeAction.OPEN_MOUTH: [
            "Please open your mouth",
            "Open your mouth slightly",
            "Part your lips"
        ],
        ChallengeAction.NOD: [
            "Please nod your head",
            "Nod once",
            "Move your head up and down"
        ],
        ChallengeAction.SHAKE_HEAD: [
            "Please shake your head",
            "Shake your head side to side",
            "Move your head left and right"
        ],
        ChallengeAction.TILT_LEFT: [
            "Please tilt your head to the left",
            "Lean your head left",
            "Tilt left slightly"
        ],
        ChallengeAction.TILT_RIGHT: [
            "Please tilt your head to the right",
            "Lean your head right",
            "Tilt right slightly"
        ],
        ChallengeAction.MOVE_CLOSER: [
            "Please move closer to the camera",
            "Come closer",
            "Move your face closer"
        ],
        ChallengeAction.MOVE_FARTHER: [
            "Please move away from the camera",
            "Move back slightly",
            "Move your face farther"
        ]
    }
    
    @classmethod
    def get_instruction(cls, action: ChallengeAction, variation: Optional[int] = None) -> str:
        """Get instruction for an action"""
        instructions = cls.INSTRUCTION_TEMPLATES.get(action, ["Perform action"])
        
        if variation is not None:
            return instructions[variation % len(instructions)]
        
        return random.choice(instructions)


# ============= VALIDATION PARAMETERS =============

class ValidationParameters:
    """Parameters for validating challenge actions"""
    
    @staticmethod
    def get_params(action: ChallengeAction) -> Dict[str, Any]:
        """Get validation parameters for an action"""
        params = {
            ChallengeAction.TURN_LEFT: {
                'yaw_min': -30,
                'yaw_max': -15,
                'tolerance': 5
            },
            ChallengeAction.TURN_RIGHT: {
                'yaw_min': 15,
                'yaw_max': 30,
                'tolerance': 5
            },
            ChallengeAction.LOOK_UP: {
                'pitch_min': 10,
                'pitch_max': 25,
                'tolerance': 5
            },
            ChallengeAction.LOOK_DOWN: {
                'pitch_min': -25,
                'pitch_max': -10,
                'tolerance': 5
            },
            ChallengeAction.BLINK: {
                'eye_aspect_ratio_threshold': 0.2,
                'min_duration_ms': 100,
                'max_duration_ms': 500
            },
            ChallengeAction.SMILE: {
                'mouth_aspect_ratio_min': 0.3,
                'lip_distance_increase': 1.2
            },
            ChallengeAction.OPEN_MOUTH: {
                'mouth_aspect_ratio_min': 0.5,
                'jaw_opening_min': 10
            },
            ChallengeAction.NOD: {
                'pitch_delta_min': 10,
                'pitch_cycles': 1
            },
            ChallengeAction.SHAKE_HEAD: {
                'yaw_delta_min': 15,
                'yaw_cycles': 1
            },
            ChallengeAction.TILT_LEFT: {
                'roll_min': -20,
                'roll_max': -10,
                'tolerance': 5
            },
            ChallengeAction.TILT_RIGHT: {
                'roll_min': 10,
                'roll_max': 20,
                'tolerance': 5
            },
            ChallengeAction.MOVE_CLOSER: {
                'bbox_scale_min': 1.15,
                'bbox_scale_max': 1.5
            },
            ChallengeAction.MOVE_FARTHER: {
                'bbox_scale_min': 0.7,
                'bbox_scale_max': 0.85
            }
        }
        
        return params.get(action, {})


# ============= CHALLENGE GENERATOR =============

class ChallengeGenerator:
    """Main challenge generation system"""
    
    def __init__(self, 
                 min_steps: int = 2,
                 max_steps: int = 7,
                 default_duration_ms: int = 2000,
                 expiry_seconds: int = 60):
        self.min_steps = min_steps
        self.max_steps = max_steps
        self.default_duration_ms = default_duration_ms
        self.expiry_seconds = expiry_seconds
        
        # Cache for active challenges
        self.active_challenges: Dict[str, ChallengeScript] = {}
    
    def generate_challenge(self,
                          session_id: str,
                          difficulty: ChallengeDifficulty = ChallengeDifficulty.MEDIUM,
                          custom_actions: Optional[List[ChallengeAction]] = None) -> ChallengeScript:
        """Generate a new challenge script"""
        
        # Generate unique challenge ID
        challenge_id = self._generate_challenge_id(session_id)
        
        # Get actions based on difficulty or custom
        if custom_actions:
            actions = custom_actions
        else:
            actions = self._select_actions(difficulty)
        
        # Create challenge steps
        steps = []
        for i, action in enumerate(actions):
            step = ChallengeStep(
                action=action,
                duration_ms=self._get_action_duration(action),
                instruction=InstructionGenerator.get_instruction(action, i),
                validation_params=ValidationParameters.get_params(action),
                order=i + 1
            )
            steps.append(step)
        
        # Create challenge script
        now = time.time()
        script = ChallengeScript(
            challenge_id=challenge_id,
            session_id=session_id,
            steps=steps,
            difficulty=difficulty,
            created_at=now,
            expires_at=now + self.expiry_seconds,
            anti_replay_token=self._generate_anti_replay_token(challenge_id)
        )
        
        # Store in cache
        self.active_challenges[challenge_id] = script
        
        # Clean up expired challenges
        self._cleanup_expired()
        
        return script
    
    def verify_challenge(self,
                        challenge_id: str,
                        responses: List[Dict[str, Any]],
                        completion_time_ms: int) -> ChallengeResult:
        """Verify challenge responses"""
        
        # Get challenge script
        if challenge_id not in self.active_challenges:
            return ChallengeResult(
                challenge_id=challenge_id,
                passed=False,
                score=0.0,
                steps_completed=0,
                steps_total=0,
                failure_reasons=["Challenge not found or expired"],
                completion_time_ms=completion_time_ms
            )
        
        script = self.active_challenges[challenge_id]
        
        # Check expiry
        if time.time() > script.expires_at:
            return ChallengeResult(
                challenge_id=challenge_id,
                passed=False,
                score=0.0,
                steps_completed=0,
                steps_total=len(script.steps),
                failure_reasons=["Challenge expired"],
                completion_time_ms=completion_time_ms
            )
        
        # Verify each step
        steps_passed = 0
        failure_reasons = []
        
        for i, step in enumerate(script.steps):
            if i >= len(responses):
                failure_reasons.append(f"Step {i+1}: No response provided")
                continue
            
            response = responses[i]
            if self._verify_step(step, response):
                steps_passed += 1
            else:
                failure_reasons.append(f"Step {i+1} ({step.action.value}): Failed validation")
        
        # Calculate score
        score = steps_passed / len(script.steps) if script.steps else 0.0
        
        # Determine pass/fail (require at least 80% success)
        passed = score >= 0.8
        
        # Remove challenge from cache (one-time use)
        del self.active_challenges[challenge_id]
        
        return ChallengeResult(
            challenge_id=challenge_id,
            passed=passed,
            score=score,
            steps_completed=steps_passed,
            steps_total=len(script.steps),
            failure_reasons=failure_reasons if not passed else [],
            completion_time_ms=completion_time_ms
        )
    
    def _select_actions(self, difficulty: ChallengeDifficulty) -> List[ChallengeAction]:
        """Select actions based on difficulty"""
        templates = ChallengeTemplates()
        
        if difficulty == ChallengeDifficulty.EASY:
            template_list = templates.get_easy_templates()
        elif difficulty == ChallengeDifficulty.MEDIUM:
            template_list = templates.get_medium_templates()
        elif difficulty == ChallengeDifficulty.HARD:
            template_list = templates.get_hard_templates()
        else:  # EXPERT
            template_list = templates.get_expert_templates()
        
        # Select random template
        template = random.choice(template_list)
        
        # Optionally shuffle order for variation
        if random.random() > 0.5:
            template = list(template)
            random.shuffle(template)
        
        return template
    
    def _get_action_duration(self, action: ChallengeAction) -> int:
        """Get duration for an action in milliseconds"""
        durations = {
            ChallengeAction.BLINK: 1000,
            ChallengeAction.SMILE: 1500,
            ChallengeAction.OPEN_MOUTH: 1500,
            ChallengeAction.NOD: 2000,
            ChallengeAction.SHAKE_HEAD: 2000,
            ChallengeAction.MOVE_CLOSER: 2500,
            ChallengeAction.MOVE_FARTHER: 2500
        }
        
        return durations.get(action, self.default_duration_ms)
    
    def _verify_step(self, step: ChallengeStep, response: Dict[str, Any]) -> bool:
        """Verify a single challenge step"""
        
        # Basic validation - check if action was detected
        if 'action_detected' not in response:
            return False
        
        if response['action_detected'] != step.action.value:
            return False
        
        # Check timing (allow some tolerance)
        if 'duration_ms' in response:
            expected_duration = step.duration_ms
            actual_duration = response['duration_ms']
            tolerance = 0.5  # 50% tolerance
            
            if actual_duration < expected_duration * (1 - tolerance):
                return False
            if actual_duration > expected_duration * (1 + tolerance * 2):
                return False
        
        # Check validation parameters if provided
        if 'metrics' in response and step.validation_params:
            metrics = response['metrics']
            
            # Check yaw for turn actions
            if 'yaw_min' in step.validation_params:
                yaw = metrics.get('yaw', 0)
                if yaw < step.validation_params['yaw_min']:
                    return False
                if 'yaw_max' in step.validation_params:
                    if yaw > step.validation_params['yaw_max']:
                        return False
            
            # Check pitch for look actions
            if 'pitch_min' in step.validation_params:
                pitch = metrics.get('pitch', 0)
                if pitch < step.validation_params['pitch_min']:
                    return False
                if 'pitch_max' in step.validation_params:
                    if pitch > step.validation_params['pitch_max']:
                        return False
            
            # Check roll for tilt actions
            if 'roll_min' in step.validation_params:
                roll = metrics.get('roll', 0)
                if roll < step.validation_params['roll_min']:
                    return False
                if 'roll_max' in step.validation_params:
                    if roll > step.validation_params['roll_max']:
                        return False
        
        return True
    
    def _generate_challenge_id(self, session_id: str) -> str:
        """Generate unique challenge ID"""
        timestamp = str(time.time())
        random_component = str(random.randint(1000, 9999))
        data = f"{session_id}:{timestamp}:{random_component}"
        return hashlib.sha256(data.encode()).hexdigest()[:16]
    
    def _generate_anti_replay_token(self, challenge_id: str) -> str:
        """Generate anti-replay token"""
        secret = str(time.time()) + str(random.random())
        data = f"{challenge_id}:{secret}"
        return hashlib.sha256(data.encode()).hexdigest()[:32]
    
    def _cleanup_expired(self):
        """Remove expired challenges from cache"""
        current_time = time.time()
        expired = [
            cid for cid, script in self.active_challenges.items()
            if current_time > script.expires_at
        ]
        
        for cid in expired:
            del self.active_challenges[cid]
    
    def get_active_challenge(self, challenge_id: str) -> Optional[ChallengeScript]:
        """Get active challenge by ID"""
        return self.active_challenges.get(challenge_id)
    
    def cancel_challenge(self, challenge_id: str) -> bool:
        """Cancel an active challenge"""
        if challenge_id in self.active_challenges:
            del self.active_challenges[challenge_id]
            return True
        return False


# ============= DIFFICULTY SELECTOR =============

class DifficultySelector:
    """Selects appropriate difficulty based on user behavior"""
    
    @staticmethod
    def select_difficulty(
        attempt_count: int,
        previous_scores: List[float],
        avg_completion_time_ms: Optional[float] = None
    ) -> ChallengeDifficulty:
        """Select difficulty based on history"""
        
        # First attempt - start with easy or medium
        if attempt_count == 0:
            return ChallengeDifficulty.EASY
        
        # Check recent performance
        if previous_scores:
            avg_score = sum(previous_scores[-3:]) / len(previous_scores[-3:])
            
            if avg_score < 0.5:
                return ChallengeDifficulty.EASY
            elif avg_score < 0.7:
                return ChallengeDifficulty.MEDIUM
            elif avg_score < 0.9:
                return ChallengeDifficulty.HARD
            else:
                return ChallengeDifficulty.EXPERT
        
        # Escalate difficulty with attempts
        if attempt_count <= 2:
            return ChallengeDifficulty.MEDIUM
        elif attempt_count <= 4:
            return ChallengeDifficulty.HARD
        else:
            return ChallengeDifficulty.EXPERT


# ============= UTILITY FUNCTIONS =============

def generate_challenge_script(
    session_id: str,
    complexity: int = 2,
    generator: Optional[ChallengeGenerator] = None
) -> Dict[str, Any]:
    """Generate challenge script with specified complexity"""
    
    if generator is None:
        generator = ChallengeGenerator()
    
    # Map complexity to difficulty
    if complexity <= 1:
        difficulty = ChallengeDifficulty.EASY
    elif complexity == 2:
        difficulty = ChallengeDifficulty.MEDIUM
    elif complexity == 3:
        difficulty = ChallengeDifficulty.HARD
    else:
        difficulty = ChallengeDifficulty.EXPERT
    
    # Generate challenge
    script = generator.generate_challenge(session_id, difficulty)
    
    return script.to_dict()


def verify_challenge_response(
    challenge_id: str,
    responses: List[Dict[str, Any]],
    completion_time_ms: int,
    generator: Optional[ChallengeGenerator] = None
) -> Dict[str, Any]:
    """Verify challenge response"""
    
    if generator is None:
        generator = ChallengeGenerator()
    
    result = generator.verify_challenge(challenge_id, responses, completion_time_ms)
    
    return {
        'challenge_id': result.challenge_id,
        'passed': result.passed,
        'score': result.score,
        'steps_completed': result.steps_completed,
        'steps_total': result.steps_total,
        'failure_reasons': result.failure_reasons,
        'completion_time_ms': result.completion_time_ms
    }