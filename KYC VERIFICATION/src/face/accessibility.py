"""
Accessibility Support Module
Handles reduced motion, screen reader support, and alternative responses

Implements accessibility requirements including detection of user preferences
and providing appropriate alternative responses for reduced motion mode.
"""

import logging
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


# ============= ACCESSIBILITY PREFERENCES =============

class AccessibilityMode(Enum):
    """Accessibility mode preferences"""
    STANDARD = "standard"
    REDUCED_MOTION = "reduced_motion"
    SCREEN_READER = "screen_reader"
    HIGH_CONTRAST = "high_contrast"
    SIMPLIFIED = "simplified"


class MotionPreference(Enum):
    """Motion preference levels"""
    FULL = "full"  # All animations enabled
    REDUCED = "reduced"  # Minimal animations
    NONE = "none"  # No animations


@dataclass
class AccessibilitySettings:
    """User accessibility preferences"""
    mode: AccessibilityMode = AccessibilityMode.STANDARD
    motion_preference: MotionPreference = MotionPreference.FULL
    screen_reader_active: bool = False
    high_contrast: bool = False
    simplified_language: bool = False
    extended_timeouts: bool = False
    keyboard_navigation: bool = False
    font_size_multiplier: float = 1.0
    
    @classmethod
    def from_headers(cls, headers: Dict[str, str]) -> 'AccessibilitySettings':
        """
        Create settings from HTTP headers
        
        Args:
            headers: Request headers
            
        Returns:
            AccessibilitySettings instance
        """
        settings = cls()
        
        # Check for prefers-reduced-motion
        if headers.get('Prefers-Reduced-Motion') == 'reduce':
            settings.motion_preference = MotionPreference.REDUCED
            settings.mode = AccessibilityMode.REDUCED_MOTION
        
        # Check for screen reader
        if headers.get('Screen-Reader-Active') == 'true':
            settings.screen_reader_active = True
            settings.mode = AccessibilityMode.SCREEN_READER
        
        # Check for high contrast
        if headers.get('Prefers-High-Contrast') == 'more':
            settings.high_contrast = True
            settings.mode = AccessibilityMode.HIGH_CONTRAST
        
        # Check for simplified mode
        if headers.get('Prefers-Simplified') == 'true':
            settings.simplified_language = True
            settings.mode = AccessibilityMode.SIMPLIFIED
        
        # Check for extended timeouts
        if headers.get('Needs-Extended-Timeouts') == 'true':
            settings.extended_timeouts = True
        
        # Check for keyboard navigation
        if headers.get('Keyboard-Navigation') == 'true':
            settings.keyboard_navigation = True
        
        # Font size preference
        try:
            font_size = headers.get('Font-Size-Multiplier', '1.0')
            settings.font_size_multiplier = float(font_size)
        except ValueError:
            pass
        
        return settings
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API response"""
        return {
            "mode": self.mode.value,
            "motion_preference": self.motion_preference.value,
            "screen_reader_active": self.screen_reader_active,
            "high_contrast": self.high_contrast,
            "simplified_language": self.simplified_language,
            "extended_timeouts": self.extended_timeouts,
            "keyboard_navigation": self.keyboard_navigation,
            "font_size_multiplier": self.font_size_multiplier
        }


@dataclass
class AccessibleResponse:
    """Accessibility-enhanced response structure"""
    content: Dict[str, Any]
    aria_labels: Dict[str, str] = field(default_factory=dict)
    screen_reader_text: Optional[str] = None
    semantic_structure: Dict[str, Any] = field(default_factory=dict)
    keyboard_hints: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API response"""
        result = self.content.copy()
        
        # Add accessibility metadata
        result['accessibility'] = {
            'aria_labels': self.aria_labels,
            'screen_reader_text': self.screen_reader_text,
            'semantic_structure': self.semantic_structure,
            'keyboard_hints': self.keyboard_hints
        }
        
        return result


class AccessibilityAdapter:
    """Adapts responses based on accessibility settings"""
    
    def __init__(self):
        """Initialize accessibility adapter"""
        self.reduced_motion_overrides = self._load_reduced_motion_overrides()
        self.screen_reader_templates = self._load_screen_reader_templates()
        logger.info("Accessibility Adapter initialized")
    
    def _load_reduced_motion_overrides(self) -> Dict[str, Any]:
        """Load reduced motion configuration overrides"""
        return {
            # Disable all animations
            'animations': {
                'countdown_duration_ms': 0,  # Instant capture
                'state_transition_ms': 0,    # Instant transitions
                'flip_animation_ms': 0,      # No flip animation
                'success_animation_ms': 0,   # No success animation
                'error_shake_ms': 0,         # No error shake
                'pulse_interval_ms': None    # No pulsing
            },
            # Simplified states
            'states': {
                'skip_countdown': True,       # Skip countdown state
                'auto_confirm': True,         # Auto-confirm captures
                'simplified_flow': True       # Use simplified flow
            },
            # Extended timeouts
            'timeouts': {
                'session_timeout_ms': 600000,  # 10 minutes
                'lock_timeout_ms': 10000,      # 10 seconds
                'capture_timeout_ms': 30000     # 30 seconds
            },
            # Static indicators
            'indicators': {
                'quality_display': 'static',    # Static quality bars
                'progress_display': 'numeric',  # Numeric progress
                'status_display': 'text'        # Text status only
            }
        }
    
    def _load_screen_reader_templates(self) -> Dict[str, str]:
        """Load screen reader message templates"""
        return {
            'state_change': "State changed to {state}. {instruction}",
            'quality_update': "Quality {level}. {issues}",
            'capture_progress': "Capture {percent}% complete. {message}",
            'error_occurred': "Error: {error}. {suggestion}",
            'success': "Success! {message}. {next_step}",
            'instruction': "To {action}, {method}"
        }
    
    def adapt_response(self, 
                       response: Dict[str, Any],
                       settings: AccessibilitySettings) -> Dict[str, Any]:
        """
        Adapt response based on accessibility settings
        
        Args:
            response: Original API response
            settings: User's accessibility settings
            
        Returns:
            Adapted response
        """
        adapted = response.copy()
        
        # Apply reduced motion adaptations
        if settings.motion_preference in [MotionPreference.REDUCED, MotionPreference.NONE]:
            adapted = self._apply_reduced_motion(adapted, settings)
        
        # Apply screen reader adaptations
        if settings.screen_reader_active:
            adapted = self._apply_screen_reader_support(adapted)
        
        # Apply simplified language
        if settings.simplified_language:
            adapted = self._apply_simplified_language(adapted)
        
        # Apply high contrast hints
        if settings.high_contrast:
            adapted = self._apply_high_contrast_hints(adapted)
        
        # Add accessibility metadata
        adapted['accessibility_settings'] = settings.to_dict()
        
        # Track telemetry
        self._track_accessibility_usage(settings)
        
        return adapted
    
    def _apply_reduced_motion(self, 
                              response: Dict[str, Any],
                              settings: AccessibilitySettings) -> Dict[str, Any]:
        """Apply reduced motion adaptations"""
        overrides = self.reduced_motion_overrides
        
        # Override animation timings
        if 'timing' in response:
            response['timing'].update(overrides['animations'])
        else:
            response['timing'] = overrides['animations']
        
        # Simplify state machine
        if 'state' in response:
            state_info = response['state']
            
            # Skip countdown state
            if state_info.get('current') == 'countdown':
                state_info['current'] = 'captured'
                state_info['skip_countdown'] = True
            
            # Add simplified flow flag
            state_info['simplified_flow'] = True
        
        # Extend timeouts
        if 'timeouts' in response:
            response['timeouts'].update(overrides['timeouts'])
        
        # Use static indicators
        if 'indicators' in response:
            response['indicators'].update(overrides['indicators'])
        
        # Add reduced motion flag
        response['reduced_motion'] = True
        
        # Provide alternative instructions
        if 'messages' in response:
            messages = response['messages']
            if settings.motion_preference == MotionPreference.NONE:
                messages['primary'] = messages.get('primary', '').replace(
                    'Huwag gumalaw', 'I-click kapag handa na'
                )
                messages['primary_en'] = messages.get('primary_en', '').replace(
                    'Hold steady', 'Click when ready'
                )
        
        return response
    
    def _apply_screen_reader_support(self, response: Dict[str, Any]) -> Dict[str, Any]:
        """Apply screen reader support enhancements"""
        templates = self.screen_reader_templates
        
        # Add screen reader text
        sr_text_parts = []
        
        # Announce state changes
        if 'state' in response:
            state = response['state'].get('current', '')
            instruction = response.get('messages', {}).get('instruction', '')
            sr_text = templates['state_change'].format(
                state=state,
                instruction=instruction
            )
            sr_text_parts.append(sr_text)
        
        # Announce quality updates
        if 'quality_gates' in response:
            quality = response['quality_gates']
            level = quality.get('level', '')
            issues = ', '.join(quality.get('hints', []))
            if issues:
                sr_text = templates['quality_update'].format(
                    level=level,
                    issues=issues
                )
                sr_text_parts.append(sr_text)
        
        # Announce progress
        if 'capture_progress' in response:
            progress = response['capture_progress']
            percent = progress.get('progress', 0)
            message = progress.get('message', '')
            sr_text = templates['capture_progress'].format(
                percent=percent,
                message=message
            )
            sr_text_parts.append(sr_text)
        
        # Add ARIA labels
        aria_labels = {
            'main': 'Document capture interface',
            'state': f"Current state: {response.get('state', {}).get('current', 'unknown')}",
            'progress': f"Progress: {response.get('capture_progress', {}).get('display', 'unknown')}",
            'quality': f"Quality: {response.get('quality_gates', {}).get('level', 'unknown')}"
        }
        
        # Add semantic structure
        semantic = {
            'role': 'application',
            'live_region': 'polite',
            'atomic': True,
            'relevant': 'additions text'
        }
        
        # Add to response
        response['screen_reader'] = {
            'text': ' '.join(sr_text_parts),
            'aria_labels': aria_labels,
            'semantic': semantic
        }
        
        return response
    
    def _apply_simplified_language(self, response: Dict[str, Any]) -> Dict[str, Any]:
        """Apply simplified language adaptations"""
        # Simplification mappings
        simplifications = {
            # Tagalog simplifications
            'Hinahanap ang dokumento': 'Hanapin ID',
            'Nakita! Huwag gumalaw': 'OK na! Steady',
            'I-flip ang dokumento': 'Baliktarin ID',
            'Nakuha na!': 'OK na!',
            
            # English simplifications
            'Looking for document': 'Find ID',
            'Found! Hold steady': 'OK! Stay still',
            'Flip the document': 'Turn over ID',
            'Captured!': 'Done!'
        }
        
        # Apply simplifications to messages
        if 'messages' in response:
            messages = response['messages']
            for key in ['primary', 'primary_en', 'instruction']:
                if key in messages:
                    original = messages[key]
                    for complex_text, simple_text in simplifications.items():
                        original = original.replace(complex_text, simple_text)
                    messages[key] = original
        
        # Simplify hints
        if 'messages' in response and 'hints' in response['messages']:
            hints = response['messages']['hints']
            response['messages']['hints'] = [
                hint[:50] + '...' if len(hint) > 50 else hint
                for hint in hints[:2]  # Limit to 2 hints
            ]
        
        return response
    
    def _apply_high_contrast_hints(self, response: Dict[str, Any]) -> Dict[str, Any]:
        """Add high contrast mode hints"""
        response['high_contrast'] = {
            'enabled': True,
            'color_scheme': 'high_contrast',
            'focus_indicators': 'enhanced',
            'border_width': 3,
            'minimum_contrast_ratio': 7.0  # WCAG AAA
        }
        
        # Add visual hints
        if 'messages' in response:
            if 'hints' not in response['messages']:
                response['messages']['hints'] = []
            response['messages']['hints'].append(
                "High contrast mode active"
            )
        
        return response
    
    def _track_accessibility_usage(self, settings: AccessibilitySettings):
        """Track accessibility feature usage"""
        try:
            from .ux_telemetry import track_ux_event
            
            # Track accessibility mode usage
            track_ux_event(
                event_type="accessibility.mode_used",
                session_id="a11y_tracking",
                data={
                    "mode": settings.mode.value,
                    "motion_preference": settings.motion_preference.value,
                    "screen_reader": settings.screen_reader_active,
                    "high_contrast": settings.high_contrast,
                    "simplified": settings.simplified_language,
                    "extended_timeouts": settings.extended_timeouts
                }
            )
        except ImportError:
            pass  # Telemetry not available
    
    def get_timeout_multiplier(self, settings: AccessibilitySettings) -> float:
        """
        Get timeout multiplier based on accessibility needs
        
        Args:
            settings: Accessibility settings
            
        Returns:
            Multiplier for timeouts (1.0 = standard)
        """
        multiplier = 1.0
        
        if settings.extended_timeouts:
            multiplier *= 2.0
        
        if settings.screen_reader_active:
            multiplier *= 1.5
        
        if settings.motion_preference == MotionPreference.NONE:
            multiplier *= 1.5
        
        return multiplier
    
    def get_simplified_state_flow(self) -> List[str]:
        """
        Get simplified state flow for accessibility
        
        Returns:
            List of states in simplified flow
        """
        return [
            "searching",
            "locked",
            "captured",  # Skip countdown
            "confirm",   # Auto-confirm option
            "complete"
        ]
    
    def format_for_screen_reader(self, 
                                 text: str,
                                 context: Optional[str] = None) -> str:
        """
        Format text for screen reader announcement
        
        Args:
            text: Text to format
            context: Optional context
            
        Returns:
            Screen reader friendly text
        """
        # Remove emojis
        import re
        text = re.sub(r'[^\w\s\.\,\!\?]', '', text)
        
        # Add context if provided
        if context:
            text = f"{context}: {text}"
        
        # Add pauses for better comprehension
        text = text.replace('.', '. ').replace('!', '! ')
        
        return text.strip()


# Global accessibility adapter
_adapter = None


def get_accessibility_adapter() -> AccessibilityAdapter:
    """Get or create the global accessibility adapter"""
    global _adapter
    if _adapter is None:
        _adapter = AccessibilityAdapter()
    return _adapter


def detect_accessibility_settings(
    headers: Optional[Dict[str, str]] = None,
    params: Optional[Dict[str, str]] = None
) -> AccessibilitySettings:
    """
    Detect accessibility settings from request
    
    Args:
        headers: HTTP headers
        params: Query parameters
        
    Returns:
        Detected accessibility settings
    """
    settings = AccessibilitySettings()
    
    # Check headers
    if headers:
        settings = AccessibilitySettings.from_headers(headers)
    
    # Override with params if provided
    if params:
        if params.get('reduced_motion') == 'true':
            settings.motion_preference = MotionPreference.REDUCED
            settings.mode = AccessibilityMode.REDUCED_MOTION
        
        if params.get('screen_reader') == 'true':
            settings.screen_reader_active = True
            settings.mode = AccessibilityMode.SCREEN_READER
        
        if params.get('high_contrast') == 'true':
            settings.high_contrast = True
            settings.mode = AccessibilityMode.HIGH_CONTRAST
        
        if params.get('simplified') == 'true':
            settings.simplified_language = True
            settings.mode = AccessibilityMode.SIMPLIFIED
    
    return settings


def adapt_response_for_accessibility(
    response: Dict[str, Any],
    headers: Optional[Dict[str, str]] = None,
    params: Optional[Dict[str, str]] = None
) -> Dict[str, Any]:
    """
    Adapt API response for accessibility
    
    Args:
        response: Original response
        headers: Request headers
        params: Query parameters
        
    Returns:
        Adapted response
    """
    # Detect settings
    settings = detect_accessibility_settings(headers, params)
    
    # Get adapter
    adapter = get_accessibility_adapter()
    
    # Adapt response
    return adapter.adapt_response(response, settings)


def get_wcag_compliance_hints() -> Dict[str, Any]:
    """
    Get WCAG 2.1 AA compliance hints
    
    Returns:
        Dictionary of compliance hints
    """
    return {
        'perceivable': {
            'text_alternatives': True,
            'time_based_media': True,
            'adaptable': True,
            'distinguishable': True
        },
        'operable': {
            'keyboard_accessible': True,
            'enough_time': True,
            'seizures_safe': True,
            'navigable': True,
            'input_modalities': True
        },
        'understandable': {
            'readable': True,
            'predictable': True,
            'input_assistance': True
        },
        'robust': {
            'compatible': True,
            'future_proof': True
        },
        'compliance_level': 'AA',
        'version': '2.1'
    }