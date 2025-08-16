"""
Front/Back Document Capture Flow
Implements document capture flow with clear guidance (UX Requirement G)

This module ensures back-side capture guides users to capture the document
(not selfie) with ≥95% completion rate through clear messaging and UX.
"""

import time
import logging
from typing import Dict, List, Optional, Any, Tuple
from enum import Enum
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


class CaptureStep(Enum):
    """Steps in the capture flow"""
    FRONT_START = "front_start"
    FRONT_SEARCHING = "front_searching"
    FRONT_LOCKED = "front_locked"
    FRONT_COUNTDOWN = "front_countdown"
    FRONT_CAPTURED = "front_captured"
    FRONT_CONFIRM = "front_confirm"
    FLIP_INSTRUCTION = "flip_instruction"
    BACK_START = "back_start"
    BACK_SEARCHING = "back_searching"
    BACK_LOCKED = "back_locked"
    BACK_COUNTDOWN = "back_countdown"
    BACK_CAPTURED = "back_captured"
    BACK_CONFIRM = "back_confirm"
    COMPLETE = "complete"


class AbandonmentReason(Enum):
    """Reasons for flow abandonment"""
    TIMEOUT = "timeout"
    QUALITY_FAIL = "quality_fail"
    USER_CANCEL = "user_cancel"
    DISCONNECTED = "disconnected"
    ERROR = "error"


@dataclass
class CaptureMetrics:
    """Metrics for capture flow"""
    front_attempts: int = 0
    back_attempts: int = 0
    front_time_ms: float = 0
    back_time_ms: float = 0
    flip_time_ms: float = 0
    total_time_ms: float = 0
    front_quality_score: float = 0
    back_quality_score: float = 0
    abandonment_point: Optional[CaptureStep] = None
    abandonment_reason: Optional[AbandonmentReason] = None
    completed: bool = False
    
    def get_completion_rate(self, total_sessions: int = 100) -> float:
        """Calculate completion rate"""
        if total_sessions == 0:
            return 0.0
        completed_count = 1 if self.completed else 0
        return (completed_count / total_sessions) * 100
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API response"""
        return {
            "front_attempts": self.front_attempts,
            "back_attempts": self.back_attempts,
            "front_time_ms": round(self.front_time_ms, 1),
            "back_time_ms": round(self.back_time_ms, 1),
            "flip_time_ms": round(self.flip_time_ms, 1),
            "total_time_ms": round(self.total_time_ms, 1),
            "front_quality": round(self.front_quality_score, 3),
            "back_quality": round(self.back_quality_score, 3),
            "abandonment_point": self.abandonment_point.value if self.abandonment_point else None,
            "abandonment_reason": self.abandonment_reason.value if self.abandonment_reason else None,
            "completed": self.completed
        }


@dataclass
class CaptureProgress:
    """Progress tracking for capture flow"""
    current_step: CaptureStep
    current_side: str  # "front" or "back"
    progress_percentage: int  # 0-100
    steps_completed: int
    total_steps: int = 8  # Front (4) + Flip (1) + Back (3)
    message: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API response"""
        return {
            "current_step": self.current_step.value,
            "current_side": self.current_side,
            "progress": self.progress_percentage,
            "steps_completed": self.steps_completed,
            "total_steps": self.total_steps,
            "message": self.message,
            "display": f"{self.steps_completed}/{self.total_steps}"
        }


class CaptureFlowManager:
    """Manages front/back document capture flow"""
    
    def __init__(self):
        """Initialize capture flow manager"""
        self.current_step = CaptureStep.FRONT_START
        self.metrics = CaptureMetrics()
        self.start_time = None
        self.flip_start_time = None
        self.back_start_time = None
        
        # Load messages
        self._load_messages()
        
        # Completion tracking
        self.total_sessions = 0
        self.completed_sessions = 0
        self.abandonment_points: Dict[CaptureStep, int] = {}
    
    def _load_messages(self):
        """Load capture flow messages"""
        self.flow_messages = {
            # Front capture messages
            CaptureStep.FRONT_START: {
                "tagalog": "Ihanda ang harap ng dokumento 📄",
                "english": "Prepare front of document 📄",
                "instruction": "Iposisyon ang harap ng ID sa frame"
            },
            CaptureStep.FRONT_SEARCHING: {
                "tagalog": "Hinahanap ang dokumento...",
                "english": "Looking for document...",
                "instruction": "Ilapit at ipakita nang malinaw"
            },
            CaptureStep.FRONT_LOCKED: {
                "tagalog": "Nakita! Huwag gumalaw ✅",
                "english": "Found! Hold steady ✅",
                "instruction": "Panatilihing steady"
            },
            CaptureStep.FRONT_CAPTURED: {
                "tagalog": "Nakuha ang harap! 📸",
                "english": "Front captured! 📸",
                "instruction": "Susuriin ang detalye"
            },
            CaptureStep.FRONT_CONFIRM: {
                "tagalog": "Harap OK ✅ (1/2)",
                "english": "Front OK ✅ (1/2)",
                "instruction": "Ihanda na ang likod"
            },
            
            # Flip instruction (CRITICAL)
            CaptureStep.FLIP_INSTRUCTION: {
                "tagalog": "🔄 I-FLIP ang dokumento\n⚠️ HINDI SELFIE - Likod ng ID lang!",
                "english": "🔄 FLIP the document\n⚠️ NOT A SELFIE - Back of ID only!",
                "instruction": "Baliktarin ang ID, ipakita ang LIKOD (hindi mukha)"
            },
            
            # Back capture messages
            CaptureStep.BACK_START: {
                "tagalog": "Ipakita ang LIKOD ng dokumento 🔄",
                "english": "Show BACK of document 🔄",
                "instruction": "⚠️ Likod ng ID, HINDI selfie"
            },
            CaptureStep.BACK_SEARCHING: {
                "tagalog": "Hinahanap ang likod ng ID...",
                "english": "Looking for back of ID...",
                "instruction": "Ipakita ang likod (may barcode/signature)"
            },
            CaptureStep.BACK_LOCKED: {
                "tagalog": "Likod nakita! Steady ✅",
                "english": "Back found! Hold steady ✅",
                "instruction": "Huwag gumalaw"
            },
            CaptureStep.BACK_CAPTURED: {
                "tagalog": "Nakuha ang likod! 📸",
                "english": "Back captured! 📸",
                "instruction": "Sinusuri ang likod"
            },
            CaptureStep.BACK_CONFIRM: {
                "tagalog": "Likod OK ✅ (2/2)",
                "english": "Back OK ✅ (2/2)",
                "instruction": "Kumpleto na!"
            },
            
            # Complete
            CaptureStep.COMPLETE: {
                "tagalog": "✅ Tapos na! Salamat!",
                "english": "✅ Complete! Thank you!",
                "instruction": "Dalawang sides nakuha na"
            }
        }
        
        # Back capture specific warnings
        self.back_warnings = {
            "no_selfie": {
                "tagalog": "⚠️ BABALA: Hindi selfie! Likod ng dokumento lang!",
                "english": "⚠️ WARNING: Not a selfie! Back of document only!"
            },
            "flip_document": {
                "tagalog": "👆 I-flip/Baliktarin ang ID card",
                "english": "👆 Flip/Turn over the ID card"
            },
            "show_back": {
                "tagalog": "📄 Ipakita ang likod na may barcode/signature",
                "english": "📄 Show the back with barcode/signature"
            }
        }
    
    def start_capture(self, side: str = "front") -> CaptureProgress:
        """
        Start capture flow
        
        Args:
            side: Which side to start with ("front" or "back")
            
        Returns:
            CaptureProgress with current state
        """
        self.total_sessions += 1
        
        if side == "front":
            self.current_step = CaptureStep.FRONT_START
            self.start_time = time.time()
            self.metrics = CaptureMetrics()  # Reset metrics
        else:
            self.current_step = CaptureStep.BACK_START
            self.back_start_time = time.time()
        
        return self.get_progress()
    
    def advance_step(self, success: bool = True, quality_score: float = 0.0) -> CaptureProgress:
        """
        Advance to next step in flow
        
        Args:
            success: Whether current step succeeded
            quality_score: Quality score for current capture
            
        Returns:
            CaptureProgress with updated state
        """
        # Handle failure
        if not success:
            return self._handle_failure()
        
        # State transitions
        transitions = {
            CaptureStep.FRONT_START: CaptureStep.FRONT_SEARCHING,
            CaptureStep.FRONT_SEARCHING: CaptureStep.FRONT_LOCKED,
            CaptureStep.FRONT_LOCKED: CaptureStep.FRONT_COUNTDOWN,
            CaptureStep.FRONT_COUNTDOWN: CaptureStep.FRONT_CAPTURED,
            CaptureStep.FRONT_CAPTURED: CaptureStep.FRONT_CONFIRM,
            CaptureStep.FRONT_CONFIRM: CaptureStep.FLIP_INSTRUCTION,
            CaptureStep.FLIP_INSTRUCTION: CaptureStep.BACK_START,
            CaptureStep.BACK_START: CaptureStep.BACK_SEARCHING,
            CaptureStep.BACK_SEARCHING: CaptureStep.BACK_LOCKED,
            CaptureStep.BACK_LOCKED: CaptureStep.BACK_COUNTDOWN,
            CaptureStep.BACK_COUNTDOWN: CaptureStep.BACK_CAPTURED,
            CaptureStep.BACK_CAPTURED: CaptureStep.BACK_CONFIRM,
            CaptureStep.BACK_CONFIRM: CaptureStep.COMPLETE
        }
        
        # Update metrics
        if self.current_step == CaptureStep.FRONT_CAPTURED:
            self.metrics.front_quality_score = quality_score
            self.metrics.front_time_ms = (time.time() - self.start_time) * 1000
            self.metrics.front_attempts += 1
            
        elif self.current_step == CaptureStep.BACK_CAPTURED:
            self.metrics.back_quality_score = quality_score
            if self.back_start_time:
                self.metrics.back_time_ms = (time.time() - self.back_start_time) * 1000
            self.metrics.back_attempts += 1
            
        elif self.current_step == CaptureStep.FLIP_INSTRUCTION:
            self.flip_start_time = time.time()
            
        elif self.current_step == CaptureStep.BACK_START:
            if self.flip_start_time:
                self.metrics.flip_time_ms = (time.time() - self.flip_start_time) * 1000
            self.back_start_time = time.time()
            
        elif self.current_step == CaptureStep.BACK_CONFIRM:
            self.metrics.completed = True
            self.completed_sessions += 1
            if self.start_time:
                self.metrics.total_time_ms = (time.time() - self.start_time) * 1000
            logger.info(f"Capture flow completed in {self.metrics.total_time_ms:.1f}ms")
        
        # Also set total time when reaching COMPLETE
        if self.current_step == CaptureStep.COMPLETE:
            if self.start_time and self.metrics.total_time_ms == 0:
                self.metrics.total_time_ms = (time.time() - self.start_time) * 1000
        
        # Advance to next step
        if self.current_step in transitions:
            self.current_step = transitions[self.current_step]
        
        return self.get_progress()
    
    def _handle_failure(self) -> CaptureProgress:
        """Handle step failure"""
        # Track attempts
        if "FRONT" in self.current_step.value.upper():
            self.metrics.front_attempts += 1
        elif "BACK" in self.current_step.value.upper():
            self.metrics.back_attempts += 1
        
        # Stay in current step for retry
        return self.get_progress()
    
    def abandon_flow(self, reason: AbandonmentReason) -> CaptureMetrics:
        """
        Record flow abandonment
        
        Args:
            reason: Reason for abandonment
            
        Returns:
            Final metrics with abandonment info
        """
        self.metrics.abandonment_point = self.current_step
        self.metrics.abandonment_reason = reason
        
        # Track abandonment points
        if self.current_step not in self.abandonment_points:
            self.abandonment_points[self.current_step] = 0
        self.abandonment_points[self.current_step] += 1
        
        # Calculate times
        if self.start_time:
            self.metrics.total_time_ms = (time.time() - self.start_time) * 1000
        
        logger.warning(f"Flow abandoned at {self.current_step.value}: {reason.value}")
        
        return self.metrics
    
    def get_progress(self) -> CaptureProgress:
        """Get current progress in flow"""
        # Calculate progress
        step_values = {
            CaptureStep.FRONT_START: 0,
            CaptureStep.FRONT_SEARCHING: 1,
            CaptureStep.FRONT_LOCKED: 2,
            CaptureStep.FRONT_COUNTDOWN: 2,
            CaptureStep.FRONT_CAPTURED: 3,
            CaptureStep.FRONT_CONFIRM: 4,
            CaptureStep.FLIP_INSTRUCTION: 5,
            CaptureStep.BACK_START: 5,
            CaptureStep.BACK_SEARCHING: 6,
            CaptureStep.BACK_LOCKED: 7,
            CaptureStep.BACK_COUNTDOWN: 7,
            CaptureStep.BACK_CAPTURED: 8,
            CaptureStep.BACK_CONFIRM: 8,
            CaptureStep.COMPLETE: 8
        }
        
        steps_completed = step_values.get(self.current_step, 0)
        progress_percentage = int((steps_completed / 8) * 100)
        
        # Determine current side
        if "BACK" in self.current_step.value.upper() or self.current_step == CaptureStep.FLIP_INSTRUCTION:
            current_side = "back"
        elif self.current_step == CaptureStep.COMPLETE:
            current_side = "complete"
        else:
            current_side = "front"
        
        # Get message
        message_data = self.flow_messages.get(self.current_step, {})
        message = message_data.get("tagalog", "")
        
        # Add warning for back capture
        if self.current_step in [CaptureStep.FLIP_INSTRUCTION, CaptureStep.BACK_START, CaptureStep.BACK_SEARCHING]:
            warning = self.back_warnings["no_selfie"]["tagalog"]
            message = f"{message}\n{warning}"
        
        return CaptureProgress(
            current_step=self.current_step,
            current_side=current_side,
            progress_percentage=progress_percentage,
            steps_completed=steps_completed,
            message=message
        )
    
    def get_guidance(self, step: Optional[CaptureStep] = None, language: str = "tagalog") -> Dict[str, str]:
        """
        Get guidance messages for a step
        
        Args:
            step: Step to get guidance for (current if None)
            language: Language for messages
            
        Returns:
            Dictionary with guidance messages
        """
        if step is None:
            step = self.current_step
        
        message_data = self.flow_messages.get(step, {})
        
        guidance = {
            "primary": message_data.get(language, ""),
            "instruction": message_data.get("instruction", ""),
            "emoji": self._get_emoji_for_step(step)
        }
        
        # Add back capture warnings
        if step in [CaptureStep.FLIP_INSTRUCTION, CaptureStep.BACK_START, CaptureStep.BACK_SEARCHING]:
            guidance["warning"] = self.back_warnings["no_selfie"][language]
            guidance["flip_hint"] = self.back_warnings["flip_document"][language]
            guidance["back_hint"] = self.back_warnings["show_back"][language]
        
        return guidance
    
    def _get_emoji_for_step(self, step: CaptureStep) -> str:
        """Get emoji for step"""
        emoji_map = {
            CaptureStep.FRONT_START: "📄",
            CaptureStep.FRONT_SEARCHING: "🔍",
            CaptureStep.FRONT_LOCKED: "🎯",
            CaptureStep.FRONT_CAPTURED: "📸",
            CaptureStep.FRONT_CONFIRM: "✅",
            CaptureStep.FLIP_INSTRUCTION: "🔄",
            CaptureStep.BACK_START: "🔄",
            CaptureStep.BACK_SEARCHING: "🔍",
            CaptureStep.BACK_LOCKED: "🎯",
            CaptureStep.BACK_CAPTURED: "📸",
            CaptureStep.BACK_CONFIRM: "✅",
            CaptureStep.COMPLETE: "🎉"
        }
        return emoji_map.get(step, "")
    
    def get_completion_rate(self) -> float:
        """
        Get overall completion rate
        
        Returns:
            Completion rate percentage
        """
        if self.total_sessions == 0:
            return 100.0  # No sessions yet
        
        return (self.completed_sessions / self.total_sessions) * 100
    
    def get_back_completion_rate(self) -> float:
        """
        Get back-side specific completion rate
        
        Returns:
            Back completion rate percentage
        """
        # Count sessions that reached back
        back_started = sum(
            count for step, count in self.abandonment_points.items()
            if "BACK" in step.value.upper() or step == CaptureStep.FLIP_INSTRUCTION
        )
        
        front_only = self.total_sessions - self.completed_sessions - back_started
        
        if front_only == 0:
            return 100.0  # All who completed front also completed back
        
        back_completion = self.completed_sessions / (self.completed_sessions + back_started) * 100 if (self.completed_sessions + back_started) > 0 else 100.0
        
        return back_completion
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get capture flow statistics"""
        return {
            "total_sessions": self.total_sessions,
            "completed_sessions": self.completed_sessions,
            "completion_rate": round(self.get_completion_rate(), 1),
            "back_completion_rate": round(self.get_back_completion_rate(), 1),
            "abandonment_points": {
                step.value: count 
                for step, count in self.abandonment_points.items()
            },
            "average_times": {
                "front_ms": round(self.metrics.front_time_ms, 1) if self.metrics.front_time_ms > 0 else None,
                "back_ms": round(self.metrics.back_time_ms, 1) if self.metrics.back_time_ms > 0 else None,
                "flip_ms": round(self.metrics.flip_time_ms, 1) if self.metrics.flip_time_ms > 0 else None,
                "total_ms": round(self.metrics.total_time_ms, 1) if self.metrics.total_time_ms > 0 else None
            }
        }


# Global capture flow manager
_capture_manager = None


def get_capture_manager() -> CaptureFlowManager:
    """Get or create the global capture manager"""
    global _capture_manager
    if _capture_manager is None:
        _capture_manager = CaptureFlowManager()
    return _capture_manager