"""
Face Scan Microcopy Messages
Implements Tagalog-first messaging with English fallback (UX Requirement C)

This module provides localized user-facing messages for all states and conditions.
Default language is Tagalog with English fallback support.
"""

from typing import Dict, List, Optional, Any
from enum import Enum
from dataclasses import dataclass


class Language(Enum):
    """Supported languages"""
    TAGALOG = "tl"
    ENGLISH = "en"


class MessageType(Enum):
    """Types of messages"""
    STATE = "state"           # State-specific primary message
    INSTRUCTION = "instruction"  # Action instructions
    SUCCESS = "success"        # Success confirmations
    ERROR = "error"           # Error messages
    HINT = "hint"            # Quality hints
    PROMPT = "prompt"        # User prompts


@dataclass
class Message:
    """Message with localization support"""
    key: str
    type: MessageType
    tagalog: str
    english: str
    emoji: Optional[str] = None
    
    def get_text(self, language: Language = Language.TAGALOG) -> str:
        """Get message text in specified language"""
        text = self.tagalog if language == Language.TAGALOG else self.english
        if self.emoji:
            return f"{text} {self.emoji}"
        return text


# ============= STATE MESSAGES =============
STATE_MESSAGES = {
    "searching": Message(
        key="state.searching",
        type=MessageType.STATE,
        tagalog="Hinahanap ang dokumento",
        english="Looking for document"
    ),
    "locked": Message(
        key="state.locked",
        type=MessageType.STATE,
        tagalog="Steady lang… kukunin na",
        english="Hold steady… capturing soon"
    ),
    "countdown": Message(
        key="state.countdown",
        type=MessageType.STATE,
        tagalog="Handa na… huwag gumalaw",
        english="Ready… don't move"
    ),
    "captured": Message(
        key="state.captured",
        type=MessageType.STATE,
        tagalog="Nakuha na!",
        english="Captured!",
        emoji="📸"
    ),
    "confirm": Message(
        key="state.confirm",
        type=MessageType.STATE,
        tagalog="I-check ang kuha",
        english="Review capture"
    ),
    "flip_to_back": Message(
        key="state.flip_to_back",
        type=MessageType.STATE,
        tagalog="🔄 I-FLIP ang dokumento - Likod ng ID (HINDI SELFIE!)",
        english="🔄 FLIP the document - Back of ID (NOT A SELFIE!)"
    ),
    "back_searching": Message(
        key="state.back_searching",
        type=MessageType.STATE,
        tagalog="Hinahanap ang likod... ⚠️ LIKOD ng ID, hindi mukha!",
        english="Looking for back... ⚠️ BACK of ID, not face!"
    ),
    "complete": Message(
        key="state.complete",
        type=MessageType.STATE,
        tagalog="Tapos na!",
        english="Complete!",
        emoji="✅"
    )
}

# ============= SUCCESS MESSAGES =============
SUCCESS_MESSAGES = {
    "front_captured": Message(
        key="success.front_captured",
        type=MessageType.SUCCESS,
        tagalog="Harap OK ✅ (1/2) - Ihanda ang likod",
        english="Front OK ✅ (1/2) - Prepare back side",
        emoji="✅"
    ),
    "back_captured": Message(
        key="success.back_captured",
        type=MessageType.SUCCESS,
        tagalog="Likod OK ✅ (2/2) - Kumpleto na!",
        english="Back OK ✅ (2/2) - Complete!",
        emoji="✅"
    ),
    "lock_achieved": Message(
        key="success.lock_achieved",
        type=MessageType.SUCCESS,
        tagalog="Ayos na ang posisyon",
        english="Position locked"
    ),
    "quality_passed": Message(
        key="success.quality_passed",
        type=MessageType.SUCCESS,
        tagalog="Malinaw ang kuha",
        english="Good quality"
    )
}

# ============= ERROR MESSAGES =============
ERROR_MESSAGES = {
    "cancelled": Message(
        key="error.cancelled",
        type=MessageType.ERROR,
        tagalog="Gumalaw—subukan ulit",
        english="Movement detected—try again"
    ),
    "motion_detected": Message(
        key="error.motion_detected",
        type=MessageType.ERROR,
        tagalog="Gumalaw—subukan ulit",
        english="Movement detected—try again"
    ),
    "focus_lost": Message(
        key="error.focus_lost",
        type=MessageType.ERROR,
        tagalog="Hindi malinaw—steady lang",
        english="Not clear—hold steady"
    ),
    "glare_high": Message(
        key="error.glare_high",
        type=MessageType.ERROR,
        tagalog="Sobrang liwanag—bawas glare",
        english="Too bright—reduce glare"
    ),
    "stability_lost": Message(
        key="error.stability_lost",
        type=MessageType.ERROR,
        tagalog="Hindi stable—hawak nang steady",
        english="Not stable—hold steady"
    ),
    "quality_degraded": Message(
        key="error.quality_degraded",
        type=MessageType.ERROR,
        tagalog="Bumaba ang quality—subukan ulit",
        english="Quality degraded—try again"
    ),
    "timeout": Message(
        key="error.timeout",
        type=MessageType.ERROR,
        tagalog="Nag-timeout. Subukan ulit",
        english="Timeout. Please try again"
    ),
    "quality_failed": Message(
        key="error.quality_failed",
        type=MessageType.ERROR,
        tagalog="Hindi malinaw. Subukan ulit",
        english="Poor quality. Please try again"
    ),
    "document_not_found": Message(
        key="error.document_not_found",
        type=MessageType.ERROR,
        tagalog="Hindi makita ang dokumento",
        english="Document not found"
    ),
    "partial_document": Message(
        key="error.partial_document",
        type=MessageType.ERROR,
        tagalog="Hindi buo ang dokumento sa frame",
        english="Document partially out of frame"
    )
}

# ============= QUALITY HINTS =============
QUALITY_HINTS = {
    "glare_high": Message(
        key="hint.glare_high",
        type=MessageType.HINT,
        tagalog="Bawas glare",
        english="Reduce glare"
    ),
    "motion_high": Message(
        key="hint.motion_high",
        type=MessageType.HINT,
        tagalog="Hawak nang steady",
        english="Hold steady"
    ),
    "focus_low": Message(
        key="hint.focus_low",
        type=MessageType.HINT,
        tagalog="I-focus ang camera",
        english="Focus the camera"
    ),
    "too_dark": Message(
        key="hint.too_dark",
        type=MessageType.HINT,
        tagalog="Kulang ang ilaw",
        english="Too dark"
    ),
    "too_bright": Message(
        key="hint.too_bright",
        type=MessageType.HINT,
        tagalog="Sobrang liwanag",
        english="Too bright"
    ),
    "too_close": Message(
        key="hint.too_close",
        type=MessageType.HINT,
        tagalog="Ilayo ng kaunti",
        english="Move back a bit"
    ),
    "too_far": Message(
        key="hint.too_far",
        type=MessageType.HINT,
        tagalog="Ilapit ng kaunti",
        english="Move closer"
    ),
    "not_centered": Message(
        key="hint.not_centered",
        type=MessageType.HINT,
        tagalog="Ayusin sa loob ng frame",
        english="Center in frame"
    )
}

# ============= INSTRUCTION MESSAGES =============
INSTRUCTION_MESSAGES = {
    "position_document": Message(
        key="instruction.position_document",
        type=MessageType.INSTRUCTION,
        tagalog="Ilagay ang dokumento sa loob ng frame",
        english="Position document within frame"
    ),
    "hold_steady": Message(
        key="instruction.hold_steady",
        type=MessageType.INSTRUCTION,
        tagalog="Hawak nang steady para sa mas malinaw na kuha",
        english="Hold steady for a clear capture"
    ),
    "flip_document": Message(
        key="instruction.flip_document",
        type=MessageType.INSTRUCTION,
        tagalog="⚠️ I-FLIP ang ID - Ipakita ang LIKOD (hindi selfie!)",
        english="⚠️ FLIP the ID - Show the BACK (not a selfie!)"
    ),
    "back_not_selfie": Message(
        key="instruction.back_not_selfie",
        type=MessageType.INSTRUCTION,
        tagalog="⚠️ BABALA: Likod ng ID lang, hindi mukha!",
        english="⚠️ WARNING: Back of ID only, not face!"
    ),
    "show_back_side": Message(
        key="instruction.show_back_side",
        type=MessageType.INSTRUCTION,
        tagalog="Ipakita ang likod na may barcode/signature",
        english="Show the back with barcode/signature"
    ),
    "frame_barcode": Message(
        key="instruction.frame_barcode",
        type=MessageType.INSTRUCTION,
        tagalog="Siguruhing kita ang barcode o QR code",
        english="Make sure barcode or QR code is visible"
    ),
    "tap_to_retry": Message(
        key="instruction.tap_to_retry",
        type=MessageType.INSTRUCTION,
        tagalog="I-tap para subukan ulit",
        english="Tap to try again"
    )
}


class MessageManager:
    """Manages localized messages for face scan"""
    
    def __init__(self, default_language: Language = Language.TAGALOG):
        """
        Initialize message manager
        
        Args:
            default_language: Default language for messages
        """
        self.default_language = default_language
        self.messages = self._load_all_messages()
    
    def _load_all_messages(self) -> Dict[str, Message]:
        """Load all messages into a single dictionary"""
        all_messages = {}
        
        # Combine all message dictionaries
        for msg_dict in [STATE_MESSAGES, SUCCESS_MESSAGES, ERROR_MESSAGES, 
                        QUALITY_HINTS, INSTRUCTION_MESSAGES]:
            for key, message in msg_dict.items():
                all_messages[message.key] = message
        
        return all_messages
    
    def get_message(self, key: str, language: Optional[Language] = None) -> str:
        """
        Get a specific message by key
        
        Args:
            key: Message key
            language: Language override (uses default if None)
            
        Returns:
            Localized message text
        """
        lang = language or self.default_language
        
        # Backward-compatibility: map legacy keys used in tests
        legacy_map = {
            "lock_acquired": STATE_MESSAGES["locked"],
            "quality_motion": ERROR_MESSAGES["motion_detected"],
            "quality_glare": ERROR_MESSAGES["glare_high"],
            "quality_focus": ERROR_MESSAGES["focus_lost"],
            "quality_corners": ERROR_MESSAGES["stability_lost"],
            "quality_partial": ERROR_MESSAGES["partial_document"],
            "front_captured": SUCCESS_MESSAGES["front_captured"],
        }
        if key in self.messages:
            return self.messages[key].get_text(lang)
        if key in legacy_map:
            return legacy_map[key].get_text(lang)
        
        # Fallback to key if message not found
        return key
    
    def get_state_message(self, state: str, language: Optional[Language] = None) -> str:
        """Get message for a specific state"""
        if state in STATE_MESSAGES:
            lang = language or self.default_language
            return STATE_MESSAGES[state].get_text(lang)
        return f"Unknown state: {state}"
    
    def get_quality_hints(self, quality_issues: List[str], 
                         language: Optional[Language] = None) -> List[str]:
        """
        Get quality hint messages for issues
        
        Args:
            quality_issues: List of quality issue keys
            language: Language override
            
        Returns:
            List of localized hint messages
        """
        lang = language or self.default_language
        hints = []
        
        for issue in quality_issues:
            if issue in QUALITY_HINTS:
                hints.append(QUALITY_HINTS[issue].get_text(lang))
        
        # If no specific hints, provide general guidance
        if not hints and quality_issues:
            general_hint = Message(
                key="hint.general",
                type=MessageType.HINT,
                tagalog="Bawas glare / Ayusin sa loob ng frame / Hawak nang steady",
                english="Reduce glare / Center in frame / Hold steady"
            )
            hints.append(general_hint.get_text(lang))
        
        return hints
    
    def get_messages_for_response(self, 
                                 state: str,
                                 success: bool = False,
                                 quality_issues: Optional[List[str]] = None,
                                 error: Optional[str] = None,
                                 language: Optional[Language] = None) -> Dict[str, Any]:
        """
        Get all relevant messages for API response
        
        Args:
            state: Current state
            success: Whether operation succeeded
            quality_issues: List of quality issues
            error: Error key if any
            language: Language override
            
        Returns:
            Dictionary of messages for API response
        """
        lang = language or self.default_language
        
        response_messages = {
            "language": lang.value,
            "primary": self.get_state_message(state, lang)
        }
        
        # Add success message if applicable
        if success:
            if state == "captured":
                if state == "captured":  # Will be enhanced with side tracking
                    response_messages["success"] = SUCCESS_MESSAGES["front_captured"].get_text(lang)
            elif state == "locked":
                response_messages["success"] = SUCCESS_MESSAGES["lock_achieved"].get_text(lang)
        
        # Add error message if applicable
        if error and error in ERROR_MESSAGES:
            response_messages["error"] = ERROR_MESSAGES[error].get_text(lang)
        
        # Add quality hints if there are issues
        if quality_issues:
            hints = self.get_quality_hints(quality_issues, lang)
            if hints:
                response_messages["hints"] = hints
        
        # Add instruction based on state
        if state == "searching":
            response_messages["instruction"] = INSTRUCTION_MESSAGES["position_document"].get_text(lang)
        elif state == "locked" or state == "countdown":
            response_messages["instruction"] = INSTRUCTION_MESSAGES["hold_steady"].get_text(lang)
        elif state == "flip_to_back":
            response_messages["instruction"] = INSTRUCTION_MESSAGES["flip_document"].get_text(lang)
        elif state == "back_searching":
            response_messages["instruction"] = INSTRUCTION_MESSAGES["frame_barcode"].get_text(lang)
        
        return response_messages


# Global message manager instance
_message_manager = None


def get_message_manager(language: Language = Language.TAGALOG) -> MessageManager:
    """
    Get or create the global message manager
    
    Args:
        language: Default language
        
    Returns:
        MessageManager instance
    """
    global _message_manager
    if _message_manager is None:
        _message_manager = MessageManager(language)
    return _message_manager


def set_default_language(language: Language):
    """Set the default language for messages"""
    manager = get_message_manager()
    manager.default_language = language