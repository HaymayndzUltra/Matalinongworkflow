"""
Face Scan Module
Backend-only implementation for face verification

Modules:
- geometry: Pure functions for face geometry analysis
- threshold_validator: Strict threshold validation
- burst_processor: Multi-frame processing and consensus
"""

from .geometry import (
    # Data classes
    BoundingBox,
    PoseAngles,
    BrightnessMetrics,
    GeometryResult,
    StabilityTracker,
    QualityIssue,
    
    # Core functions
    calculate_occupancy_ratio,
    evaluate_occupancy,
    calculate_centering_offset,
    evaluate_centering,
    calculate_pose_from_landmarks,
    evaluate_pose,
    calculate_brightness_metrics,
    evaluate_brightness,
    calculate_tenengrad_sharpness,
    evaluate_sharpness,
    
    # High-level functions
    analyze_face_geometry,
    format_geometry_feedback
)

from .threshold_validator import (
    FaceThresholdValidator,
    get_validator,
    ValidationResult,
    ThresholdType,
    ThresholdDefinition
)

from .burst_processor import (
    FrameQualityLevel,
    FrameMetadata,
    FrameQualityScore,
    ConsensusResult,
    BurstAnalysisResult,
    calculate_geometry_score,
    calculate_frame_quality,
    evaluate_temporal_consistency,
    detect_attack_consensus,
    evaluate_consensus,
    process_burst,
    format_burst_feedback
)

__all__ = [
    # Geometry exports
    'BoundingBox',
    'PoseAngles',
    'BrightnessMetrics',
    'GeometryResult',
    'StabilityTracker',
    'QualityIssue',
    'calculate_occupancy_ratio',
    'evaluate_occupancy',
    'calculate_centering_offset',
    'evaluate_centering',
    'calculate_pose_from_landmarks',
    'evaluate_pose',
    'calculate_brightness_metrics',
    'evaluate_brightness',
    'calculate_tenengrad_sharpness',
    'evaluate_sharpness',
    'analyze_face_geometry',
    'format_geometry_feedback',
    
    # Threshold validator exports
    'FaceThresholdValidator',
    'get_validator',
    'ValidationResult',
    'ThresholdType',
    'ThresholdDefinition',
    
    # Burst processor exports
    'FrameQualityLevel',
    'FrameMetadata',
    'FrameQualityScore',
    'ConsensusResult',
    'BurstAnalysisResult',
    'calculate_geometry_score',
    'calculate_frame_quality',
    'evaluate_temporal_consistency',
    'detect_attack_consensus',
    'evaluate_consensus',
    'process_burst',
    'format_burst_feedback'
]