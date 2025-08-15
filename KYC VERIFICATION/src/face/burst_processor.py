"""
Burst Frame Processor
Handles multi-frame capture, quality scoring, and consensus evaluation

This module implements:
- Frame quality assessment
- Multi-frame consensus scoring
- Temporal consistency checks
- Best frame selection
- Attack detection across frames
"""

import math
import numpy as np
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass, field
from enum import Enum
from collections import Counter
import hashlib
import time

from .geometry import (
    BoundingBox,
    analyze_face_geometry,
    GeometryResult,
    QualityIssue
)
from .pad_scorer import (
    analyze_pad,
    PADResult,
    AttackType
)


# ============= DATA STRUCTURES =============

class FrameQualityLevel(Enum):
    """Frame quality classifications"""
    EXCELLENT = "excellent"  # > 0.9
    GOOD = "good"           # 0.7 - 0.9
    ACCEPTABLE = "acceptable"  # 0.5 - 0.7
    POOR = "poor"           # 0.3 - 0.5
    UNUSABLE = "unusable"   # < 0.3


@dataclass
class FrameMetadata:
    """Metadata for a single frame"""
    frame_index: int
    timestamp_ms: int
    bbox: BoundingBox
    landmarks: Optional[Dict[str, Tuple[float, float]]] = None
    
    def to_hash(self) -> str:
        """Generate hash for frame identification"""
        data = f"{self.frame_index}:{self.timestamp_ms}:{self.bbox.x}:{self.bbox.y}"
        return hashlib.md5(data.encode()).hexdigest()[:8]


@dataclass
class FrameQualityScore:
    """Quality assessment for a single frame"""
    frame_index: int
    timestamp_ms: int
    overall_score: float
    geometry_score: float
    sharpness_score: float
    brightness_score: float
    pad_score: float
    quality_level: FrameQualityLevel
    issues: List[str] = field(default_factory=list)
    
    @property
    def is_usable(self) -> bool:
        """Check if frame meets minimum quality"""
        return self.quality_level not in [FrameQualityLevel.POOR, FrameQualityLevel.UNUSABLE]


@dataclass
class ConsensusResult:
    """Result of multi-frame consensus evaluation"""
    passed: bool
    confidence: float
    median_score: float
    mean_score: float
    std_deviation: float
    usable_frame_count: int
    total_frame_count: int
    best_frames: List[int]  # Indices of best frames
    attack_consensus: Optional[AttackType] = None
    temporal_consistency: float = 0.0
    reasons: List[str] = field(default_factory=list)


@dataclass
class BurstAnalysisResult:
    """Complete burst analysis result"""
    burst_id: str
    frame_scores: List[FrameQualityScore]
    consensus: ConsensusResult
    processing_time_ms: float
    selected_frame_index: Optional[int] = None
    attack_detected: bool = False
    attack_type: Optional[AttackType] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


# ============= QUALITY SCORING =============

def calculate_geometry_score(
    geometry_result: GeometryResult,
    weights: Optional[Dict[str, float]] = None
) -> float:
    """
    Calculate geometry quality score from geometry analysis
    
    Args:
        geometry_result: Result from geometry analysis
        weights: Optional weight overrides
    
    Returns:
        Score between 0 and 1
    """
    if weights is None:
        weights = {
            'occupancy': 0.2,
            'centering': 0.2,
            'pose': 0.3,
            'brightness': 0.15,
            'sharpness': 0.15
        }
    
    score = 1.0
    
    # Penalize for each issue
    issue_penalties = {
        QualityIssue.FACE_TOO_SMALL: 0.4,
        QualityIssue.FACE_TOO_LARGE: 0.3,
        QualityIssue.OFF_CENTER: 0.2,
        QualityIssue.EXCESSIVE_YAW: 0.3,
        QualityIssue.EXCESSIVE_PITCH: 0.3,
        QualityIssue.EXCESSIVE_ROLL: 0.2,
        QualityIssue.TOO_DARK: 0.3,
        QualityIssue.TOO_BRIGHT: 0.3,
        QualityIssue.LOW_CONTRAST: 0.2,
        QualityIssue.BLUR_DETECTED: 0.4,
        QualityIssue.UNSTABLE: 0.2
    }
    
    for issue in geometry_result.issues:
        penalty = issue_penalties.get(issue, 0.1)
        score *= (1 - penalty)
    
    # Apply positive scoring based on metrics
    if geometry_result.occupancy_ratio:
        # Ideal occupancy is 0.4-0.6
        ideal_occupancy = 0.5
        occupancy_score = 1.0 - min(abs(geometry_result.occupancy_ratio - ideal_occupancy) * 2, 1.0)
        score *= (1 - weights['occupancy']) + weights['occupancy'] * occupancy_score
    
    if geometry_result.centering_offset:
        # Perfect centering is (0, 0)
        centering_distance = math.sqrt(
            geometry_result.centering_offset[0]**2 + 
            geometry_result.centering_offset[1]**2
        )
        centering_score = max(0, 1.0 - centering_distance * 3)
        score *= (1 - weights['centering']) + weights['centering'] * centering_score
    
    return max(0.0, min(1.0, score))


def calculate_frame_quality(
    frame_metadata: FrameMetadata,
    gray_image: np.ndarray,
    rgb_image: np.ndarray,
    frame_width: int,
    frame_height: int,
    thresholds: Optional[Dict[str, Any]] = None
) -> FrameQualityScore:
    """
    Calculate comprehensive quality score for a single frame
    
    Args:
        frame_metadata: Frame metadata
        gray_image: Grayscale face region
        rgb_image: RGB face region
        frame_width: Full frame width
        frame_height: Full frame height
        thresholds: Optional threshold overrides
    
    Returns:
        FrameQualityScore with detailed metrics
    """
    start_time = time.time()
    issues = []
    
    # Analyze geometry
    geometry_result = analyze_face_geometry(
        face_bbox=frame_metadata.bbox,
        frame_width=frame_width,
        frame_height=frame_height,
        gray_face_region=gray_image,
        landmarks=frame_metadata.landmarks,
        thresholds=thresholds
    )
    
    geometry_score = calculate_geometry_score(geometry_result)
    
    # Extract specific scores
    sharpness_score = min(1.0, geometry_result.sharpness_score / 1000) if geometry_result.sharpness_score else 0.5
    
    brightness_score = 1.0
    if geometry_result.brightness:
        # Ideal brightness is 120-140
        ideal_brightness = 130
        brightness_diff = abs(geometry_result.brightness.mean - ideal_brightness)
        brightness_score = max(0, 1.0 - brightness_diff / 100)
    
    # Analyze PAD
    pad_result = analyze_pad(
        gray_image=gray_image,
        rgb_image=rgb_image,
        thresholds=thresholds
    )
    
    pad_score = pad_result.overall_score
    
    # Calculate overall score (weighted average)
    weights = {
        'geometry': 0.3,
        'sharpness': 0.25,
        'brightness': 0.15,
        'pad': 0.3
    }
    
    overall_score = (
        weights['geometry'] * geometry_score +
        weights['sharpness'] * sharpness_score +
        weights['brightness'] * brightness_score +
        weights['pad'] * pad_score
    )
    
    # Determine quality level
    if overall_score >= 0.9:
        quality_level = FrameQualityLevel.EXCELLENT
    elif overall_score >= 0.7:
        quality_level = FrameQualityLevel.GOOD
    elif overall_score >= 0.5:
        quality_level = FrameQualityLevel.ACCEPTABLE
    elif overall_score >= 0.3:
        quality_level = FrameQualityLevel.POOR
        issues.append("Frame quality below acceptable threshold")
    else:
        quality_level = FrameQualityLevel.UNUSABLE
        issues.append("Frame quality too low for verification")
    
    # Add specific issues
    if geometry_result.issues:
        for issue in geometry_result.issues:
            issues.append(f"Geometry: {issue.value}")
    
    if not pad_result.is_live:
        issues.append(f"PAD: Possible {pad_result.attack_type_probabilities}")
    
    return FrameQualityScore(
        frame_index=frame_metadata.frame_index,
        timestamp_ms=frame_metadata.timestamp_ms,
        overall_score=round(overall_score, 3),
        geometry_score=round(geometry_score, 3),
        sharpness_score=round(sharpness_score, 3),
        brightness_score=round(brightness_score, 3),
        pad_score=round(pad_score, 3),
        quality_level=quality_level,
        issues=issues
    )


# ============= CONSENSUS EVALUATION =============

def evaluate_temporal_consistency(
    frame_scores: List[FrameQualityScore],
    max_variance: float = 0.15
) -> Tuple[float, List[str]]:
    """
    Evaluate temporal consistency across frames
    
    Args:
        frame_scores: List of frame quality scores
        max_variance: Maximum acceptable variance
    
    Returns:
        Tuple of (consistency_score, issues)
    """
    if len(frame_scores) < 2:
        return 1.0, []
    
    issues = []
    
    # Check PAD score consistency
    pad_scores = [f.pad_score for f in frame_scores]
    pad_variance = np.var(pad_scores)
    
    if pad_variance > max_variance:
        issues.append(f"Inconsistent PAD scores (variance: {pad_variance:.3f})")
    
    # Check geometry consistency
    geometry_scores = [f.geometry_score for f in frame_scores]
    geometry_variance = np.var(geometry_scores)
    
    if geometry_variance > max_variance:
        issues.append(f"Inconsistent geometry (variance: {geometry_variance:.3f})")
    
    # Check for sudden quality drops
    for i in range(1, len(frame_scores)):
        score_diff = abs(frame_scores[i].overall_score - frame_scores[i-1].overall_score)
        if score_diff > 0.3:
            issues.append(f"Sudden quality change at frame {i}")
    
    # Calculate consistency score
    avg_variance = (pad_variance + geometry_variance) / 2
    consistency_score = max(0, 1.0 - avg_variance * 3)
    
    return consistency_score, issues


def detect_attack_consensus(
    frame_scores: List[FrameQualityScore],
    pad_results: Optional[List[PADResult]] = None
) -> Tuple[bool, Optional[AttackType]]:
    """
    Detect if there's consensus on an attack type across frames
    
    Args:
        frame_scores: Frame quality scores
        pad_results: Optional detailed PAD results
    
    Returns:
        Tuple of (attack_detected, attack_type)
    """
    # Count frames with low PAD scores
    low_pad_frames = sum(1 for f in frame_scores if f.pad_score < 0.7)
    
    if low_pad_frames > len(frame_scores) * 0.5:
        # Majority of frames indicate possible attack
        
        # If we have detailed PAD results, determine attack type
        if pad_results:
            attack_types = []
            for result in pad_results:
                if result.attack_type_probabilities:
                    # Get most likely attack type
                    max_prob = 0
                    likely_attack = None
                    for attack_type, prob in result.attack_type_probabilities.items():
                        if prob > max_prob and attack_type != AttackType.GENUINE:
                            max_prob = prob
                            likely_attack = attack_type
                    if likely_attack:
                        attack_types.append(likely_attack)
            
            if attack_types:
                # Return most common attack type
                attack_counter = Counter(attack_types)
                most_common = attack_counter.most_common(1)[0][0]
                return True, most_common
        
        return True, AttackType.UNKNOWN
    
    return False, None


def evaluate_consensus(
    frame_scores: List[FrameQualityScore],
    min_frames: int = 3,
    min_median_score: float = 0.7,
    min_usable_ratio: float = 0.6,
    top_k: int = 5
) -> ConsensusResult:
    """
    Evaluate consensus across multiple frames
    
    Args:
        frame_scores: List of frame quality scores
        min_frames: Minimum frames required
        min_median_score: Minimum median score required
        min_usable_ratio: Minimum ratio of usable frames
        top_k: Number of top frames to consider
    
    Returns:
        ConsensusResult with detailed metrics
    """
    if not frame_scores:
        return ConsensusResult(
            passed=False,
            confidence=0.0,
            median_score=0.0,
            mean_score=0.0,
            std_deviation=0.0,
            usable_frame_count=0,
            total_frame_count=0,
            best_frames=[],
            reasons=["No frames to evaluate"]
        )
    
    # Extract scores
    overall_scores = [f.overall_score for f in frame_scores]
    usable_frames = [f for f in frame_scores if f.is_usable]
    
    # Calculate statistics
    median_score = np.median(overall_scores)
    mean_score = np.mean(overall_scores)
    std_deviation = np.std(overall_scores)
    
    # Get top K frames
    sorted_frames = sorted(frame_scores, key=lambda f: f.overall_score, reverse=True)
    top_frames = sorted_frames[:min(top_k, len(sorted_frames))]
    best_frame_indices = [f.frame_index for f in top_frames]
    
    # Calculate top K statistics
    top_scores = [f.overall_score for f in top_frames]
    top_median = np.median(top_scores) if top_scores else 0
    
    # Evaluate temporal consistency
    consistency_score, consistency_issues = evaluate_temporal_consistency(frame_scores)
    
    # Detect attack consensus
    attack_detected, attack_type = detect_attack_consensus(frame_scores)
    
    # Determine if consensus passes
    reasons = []
    passed = True
    
    # Check frame count
    if len(usable_frames) < min_frames:
        passed = False
        reasons.append(f"Insufficient usable frames: {len(usable_frames)} < {min_frames}")
    
    # Check usable ratio
    usable_ratio = len(usable_frames) / len(frame_scores)
    if usable_ratio < min_usable_ratio:
        passed = False
        reasons.append(f"Too many poor quality frames: {usable_ratio:.1%} usable")
    
    # Check median score
    if top_median < min_median_score:
        passed = False
        reasons.append(f"Top frames median score too low: {top_median:.3f} < {min_median_score}")
    
    # Check consistency
    if consistency_score < 0.5:
        passed = False
        reasons.extend(consistency_issues)
    
    # Check for attacks
    if attack_detected:
        passed = False
        reasons.append(f"Potential {attack_type.value if attack_type else 'unknown'} attack detected")
    
    # Calculate confidence
    confidence = (
        0.3 * (len(usable_frames) / max(len(frame_scores), 1)) +  # Usable ratio
        0.3 * min(top_median, 1.0) +  # Quality score
        0.2 * consistency_score +  # Consistency
        0.2 * (1.0 if not attack_detected else 0.0)  # No attacks
    )
    
    if passed and not reasons:
        reasons.append("All consensus criteria met")
    
    return ConsensusResult(
        passed=passed,
        confidence=round(confidence, 3),
        median_score=round(median_score, 3),
        mean_score=round(mean_score, 3),
        std_deviation=round(std_deviation, 3),
        usable_frame_count=len(usable_frames),
        total_frame_count=len(frame_scores),
        best_frames=best_frame_indices,
        attack_consensus=attack_type,
        temporal_consistency=round(consistency_score, 3),
        reasons=reasons
    )


# ============= BURST PROCESSING =============

def process_burst(
    frames: List[Dict[str, Any]],
    frame_width: int = 640,
    frame_height: int = 480,
    thresholds: Optional[Dict[str, Any]] = None
) -> BurstAnalysisResult:
    """
    Process a burst of frames and evaluate consensus
    
    Args:
        frames: List of frame data with metadata
        frame_width: Frame width
        frame_height: Frame height
        thresholds: Optional threshold overrides
    
    Returns:
        BurstAnalysisResult with complete analysis
    """
    start_time = time.time()
    
    # Generate burst ID
    burst_id = hashlib.sha256(
        f"{time.time()}{len(frames)}".encode()
    ).hexdigest()[:16]
    
    # Process each frame
    frame_scores = []
    pad_results = []
    
    for i, frame_data in enumerate(frames):
        # Extract metadata
        timestamp_ms = frame_data.get('timestamp_ms', i * 100)
        bbox_data = frame_data.get('bbox', {
            'x': 100, 'y': 100, 'width': 200, 'height': 200
        })
        
        bbox = BoundingBox(
            x=bbox_data.get('x', 100),
            y=bbox_data.get('y', 100),
            width=bbox_data.get('width', 200),
            height=bbox_data.get('height', 200)
        )
        
        frame_metadata = FrameMetadata(
            frame_index=i,
            timestamp_ms=timestamp_ms,
            bbox=bbox,
            landmarks=frame_data.get('landmarks')
        )
        
        # Create dummy images for testing (in production, would use actual images)
        gray_image = np.random.randint(100, 200, (100, 100), dtype=np.uint8)
        rgb_image = np.random.randint(100, 200, (100, 100, 3), dtype=np.uint8)
        
        # Calculate frame quality
        quality_score = calculate_frame_quality(
            frame_metadata=frame_metadata,
            gray_image=gray_image,
            rgb_image=rgb_image,
            frame_width=frame_width,
            frame_height=frame_height,
            thresholds=thresholds
        )
        
        frame_scores.append(quality_score)
        
        # Store PAD result for attack consensus
        pad_result = analyze_pad(gray_image, rgb_image, thresholds)
        pad_results.append(pad_result)
    
    # Evaluate consensus
    consensus = evaluate_consensus(
        frame_scores=frame_scores,
        min_frames=thresholds.get('burst_consensus_frame_min_count', 3) if thresholds else 3,
        min_median_score=thresholds.get('burst_consensus_median_min', 0.7) if thresholds else 0.7,
        top_k=thresholds.get('burst_consensus_top_k', 5) if thresholds else 5
    )
    
    # Select best frame
    selected_frame_index = None
    if consensus.best_frames:
        selected_frame_index = consensus.best_frames[0]
    
    # Detect attacks
    attack_detected, attack_type = detect_attack_consensus(frame_scores, pad_results)
    
    # Calculate processing time
    processing_time_ms = (time.time() - start_time) * 1000
    
    # Build metadata
    metadata = {
        'frame_timestamps': [f.timestamp_ms for f in frame_scores],
        'quality_distribution': {
            level.value: sum(1 for f in frame_scores if f.quality_level == level)
            for level in FrameQualityLevel
        },
        'avg_pad_score': np.mean([f.pad_score for f in frame_scores]),
        'avg_geometry_score': np.mean([f.geometry_score for f in frame_scores])
    }
    
    return BurstAnalysisResult(
        burst_id=burst_id,
        frame_scores=frame_scores,
        consensus=consensus,
        processing_time_ms=round(processing_time_ms, 1),
        selected_frame_index=selected_frame_index,
        attack_detected=attack_detected,
        attack_type=attack_type,
        metadata=metadata
    )


def format_burst_feedback(result: BurstAnalysisResult) -> Dict[str, Any]:
    """
    Format burst analysis result for user feedback
    
    Args:
        result: BurstAnalysisResult
    
    Returns:
        User-friendly feedback dictionary
    """
    feedback = {
        'burst_id': result.burst_id,
        'consensus_passed': result.consensus.passed,
        'confidence': result.consensus.confidence,
        'frame_summary': {
            'total': result.consensus.total_frame_count,
            'usable': result.consensus.usable_frame_count,
            'excellent': sum(1 for f in result.frame_scores if f.quality_level == FrameQualityLevel.EXCELLENT),
            'good': sum(1 for f in result.frame_scores if f.quality_level == FrameQualityLevel.GOOD)
        },
        'quality_metrics': {
            'median_score': result.consensus.median_score,
            'consistency': result.consensus.temporal_consistency,
            'best_frame': result.selected_frame_index
        },
        'issues': [],
        'recommendations': []
    }
    
    # Add issues
    if result.attack_detected:
        feedback['issues'].append(f"Potential {result.attack_type.value} attack detected")
    
    if result.consensus.usable_frame_count < 3:
        feedback['issues'].append("Too few usable frames")
        feedback['recommendations'].append("Ensure good lighting and hold device steady")
    
    if result.consensus.temporal_consistency < 0.5:
        feedback['issues'].append("Inconsistent quality across frames")
        feedback['recommendations'].append("Maintain consistent position during capture")
    
    # Add specific frame issues
    frame_issues = Counter()
    for frame in result.frame_scores:
        for issue in frame.issues:
            frame_issues[issue] += 1
    
    # Report most common issues
    for issue, count in frame_issues.most_common(3):
        if count > result.consensus.total_frame_count * 0.3:
            feedback['issues'].append(f"{issue} (in {count} frames)")
    
    return feedback