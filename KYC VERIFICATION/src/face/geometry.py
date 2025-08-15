"""
Face Geometry & Gating Library
Phase 3: Pure functions for face geometry analysis

This module provides deterministic, pure functions for:
- Face occupancy and bounding box calculations
- Centering and position evaluation
- Pose estimation (yaw, pitch, roll)
- Brightness analysis (mean, percentiles)
- Tenengrad sharpness computation
- Stability tracking

All functions are pure with no I/O side effects.
"""

import math
from typing import Dict, Tuple, List, Optional, Any
from dataclasses import dataclass
from enum import Enum
import numpy as np


class QualityIssue(Enum):
    """Types of quality issues that can be detected"""
    FACE_TOO_SMALL = "face_too_small"
    FACE_TOO_LARGE = "face_too_large"
    OFF_CENTER = "off_center"
    EXCESSIVE_YAW = "excessive_yaw"
    EXCESSIVE_PITCH = "excessive_pitch"
    EXCESSIVE_ROLL = "excessive_roll"
    TOO_DARK = "too_dark"
    TOO_BRIGHT = "too_bright"
    LOW_CONTRAST = "low_contrast"
    BLUR_DETECTED = "blur_detected"
    UNSTABLE = "unstable"


@dataclass
class BoundingBox:
    """Face bounding box representation"""
    x: float
    y: float
    width: float
    height: float
    
    @property
    def center_x(self) -> float:
        """Get center X coordinate"""
        return self.x + self.width / 2
    
    @property
    def center_y(self) -> float:
        """Get center Y coordinate"""
        return self.y + self.height / 2
    
    @property
    def area(self) -> float:
        """Get bounding box area"""
        return self.width * self.height


@dataclass
class PoseAngles:
    """Face pose angles in degrees"""
    yaw: float    # Left/right rotation
    pitch: float  # Up/down rotation
    roll: float   # Tilt rotation
    
    def is_frontal(self, max_angle: float = 30.0) -> bool:
        """Check if pose is frontal within tolerance"""
        return (abs(self.yaw) <= max_angle and 
                abs(self.pitch) <= max_angle and 
                abs(self.roll) <= max_angle)


@dataclass
class BrightnessMetrics:
    """Brightness analysis metrics"""
    mean: float
    std: float
    p05: float  # 5th percentile
    p95: float  # 95th percentile
    
    def is_acceptable(self, 
                     mean_min: float = 60,
                     mean_max: float = 200,
                     p05_min: float = 20,
                     p95_max: float = 235) -> bool:
        """Check if brightness is within acceptable range"""
        return (mean_min <= self.mean <= mean_max and
                self.p05 >= p05_min and
                self.p95 <= p95_max)


@dataclass
class GeometryResult:
    """Complete geometry analysis result"""
    occupancy_ratio: float
    centering_offset: Tuple[float, float]
    pose: PoseAngles
    brightness: BrightnessMetrics
    sharpness_score: float
    issues: List[QualityIssue]
    confidence: float


# ============= OCCUPANCY CALCULATIONS =============

def calculate_occupancy_ratio(face_bbox: BoundingBox, 
                             frame_width: int, 
                             frame_height: int) -> float:
    """
    Calculate face occupancy ratio in frame
    
    Args:
        face_bbox: Face bounding box
        frame_width: Frame width in pixels
        frame_height: Frame height in pixels
    
    Returns:
        Ratio of face area to frame area (0.0 to 1.0)
    """
    if frame_width <= 0 or frame_height <= 0:
        return 0.0
    
    frame_area = frame_width * frame_height
    face_area = face_bbox.area
    
    # Clamp to valid range
    ratio = face_area / frame_area
    return max(0.0, min(1.0, ratio))


def evaluate_occupancy(occupancy_ratio: float,
                      min_ratio: float = 0.3,
                      max_ratio: float = 0.8) -> Tuple[bool, Optional[QualityIssue]]:
    """
    Evaluate if face occupancy is acceptable
    
    Args:
        occupancy_ratio: Calculated occupancy ratio
        min_ratio: Minimum acceptable ratio
        max_ratio: Maximum acceptable ratio
    
    Returns:
        Tuple of (is_acceptable, issue_if_any)
    """
    if occupancy_ratio < min_ratio:
        return False, QualityIssue.FACE_TOO_SMALL
    elif occupancy_ratio > max_ratio:
        return False, QualityIssue.FACE_TOO_LARGE
    else:
        return True, None


# ============= CENTERING CALCULATIONS =============

def calculate_centering_offset(face_bbox: BoundingBox,
                              frame_width: int,
                              frame_height: int) -> Tuple[float, float]:
    """
    Calculate normalized offset from frame center
    
    Args:
        face_bbox: Face bounding box
        frame_width: Frame width in pixels
        frame_height: Frame height in pixels
    
    Returns:
        Tuple of (x_offset, y_offset) normalized to [-1, 1]
    """
    if frame_width <= 0 or frame_height <= 0:
        return (0.0, 0.0)
    
    # Frame center
    frame_center_x = frame_width / 2
    frame_center_y = frame_height / 2
    
    # Face center
    face_center_x = face_bbox.center_x
    face_center_y = face_bbox.center_y
    
    # Normalized offset
    x_offset = (face_center_x - frame_center_x) / (frame_width / 2)
    y_offset = (face_center_y - frame_center_y) / (frame_height / 2)
    
    # Clamp to valid range
    x_offset = max(-1.0, min(1.0, x_offset))
    y_offset = max(-1.0, min(1.0, y_offset))
    
    return (x_offset, y_offset)


def evaluate_centering(offset: Tuple[float, float],
                      tolerance: float = 0.15) -> Tuple[bool, Optional[QualityIssue]]:
    """
    Evaluate if face is adequately centered
    
    Args:
        offset: Normalized centering offset (x, y)
        tolerance: Maximum acceptable offset
    
    Returns:
        Tuple of (is_centered, issue_if_any)
    """
    x_offset, y_offset = offset
    distance = math.sqrt(x_offset**2 + y_offset**2)
    
    if distance > tolerance:
        return False, QualityIssue.OFF_CENTER
    else:
        return True, None


# ============= POSE CALCULATIONS =============

def calculate_pose_from_landmarks(landmarks: Dict[str, Tuple[float, float]]) -> PoseAngles:
    """
    Calculate pose angles from facial landmarks
    
    Args:
        landmarks: Dictionary of landmark points
                  Expected keys: 'left_eye', 'right_eye', 'nose_tip', 
                                'left_mouth', 'right_mouth'
    
    Returns:
        PoseAngles with yaw, pitch, roll in degrees
    """
    # This is a simplified calculation
    # In production, use proper 3D pose estimation
    
    try:
        left_eye = landmarks.get('left_eye', (0, 0))
        right_eye = landmarks.get('right_eye', (0, 0))
        nose_tip = landmarks.get('nose_tip', (0, 0))
        
        # Calculate roll from eye positions
        eye_dx = right_eye[0] - left_eye[0]
        eye_dy = right_eye[1] - left_eye[1]
        roll = math.degrees(math.atan2(eye_dy, eye_dx))
        
        # Calculate yaw from nose position relative to eye center
        eye_center_x = (left_eye[0] + right_eye[0]) / 2
        nose_offset_x = nose_tip[0] - eye_center_x
        eye_distance = math.sqrt(eye_dx**2 + eye_dy**2)
        if eye_distance > 0:
            yaw = math.degrees(math.asin(nose_offset_x / eye_distance * 2))
        else:
            yaw = 0.0
        
        # Calculate pitch from vertical positions
        eye_center_y = (left_eye[1] + right_eye[1]) / 2
        nose_offset_y = nose_tip[1] - eye_center_y
        if eye_distance > 0:
            pitch = math.degrees(math.asin(nose_offset_y / eye_distance * 2))
        else:
            pitch = 0.0
        
        return PoseAngles(yaw=yaw, pitch=pitch, roll=roll)
        
    except (KeyError, TypeError, ValueError):
        # Return neutral pose if calculation fails
        return PoseAngles(yaw=0.0, pitch=0.0, roll=0.0)


def evaluate_pose(pose: PoseAngles,
                 max_angle: float = 30.0) -> Tuple[bool, List[QualityIssue]]:
    """
    Evaluate if face pose is acceptable
    
    Args:
        pose: Calculated pose angles
        max_angle: Maximum acceptable angle for each axis
    
    Returns:
        Tuple of (is_acceptable, list_of_issues)
    """
    issues = []
    
    if abs(pose.yaw) > max_angle:
        issues.append(QualityIssue.EXCESSIVE_YAW)
    
    if abs(pose.pitch) > max_angle:
        issues.append(QualityIssue.EXCESSIVE_PITCH)
    
    if abs(pose.roll) > max_angle:
        issues.append(QualityIssue.EXCESSIVE_ROLL)
    
    return len(issues) == 0, issues


# ============= BRIGHTNESS CALCULATIONS =============

def calculate_brightness_metrics(gray_image: np.ndarray) -> BrightnessMetrics:
    """
    Calculate brightness metrics from grayscale image
    
    Args:
        gray_image: Grayscale image as numpy array (0-255)
    
    Returns:
        BrightnessMetrics with mean, std, and percentiles
    """
    if gray_image.size == 0:
        return BrightnessMetrics(mean=0, std=0, p05=0, p95=0)
    
    # Flatten and calculate statistics
    pixels = gray_image.flatten()
    mean = float(np.mean(pixels))
    std = float(np.std(pixels))
    p05 = float(np.percentile(pixels, 5))
    p95 = float(np.percentile(pixels, 95))
    
    return BrightnessMetrics(mean=mean, std=std, p05=p05, p95=p95)


def evaluate_brightness(metrics: BrightnessMetrics,
                       mean_min: float = 60,
                       mean_max: float = 200,
                       p05_min: float = 20,
                       p95_max: float = 235) -> Tuple[bool, List[QualityIssue]]:
    """
    Evaluate if brightness is acceptable
    
    Args:
        metrics: Calculated brightness metrics
        mean_min: Minimum acceptable mean brightness
        mean_max: Maximum acceptable mean brightness
        p05_min: Minimum acceptable 5th percentile
        p95_max: Maximum acceptable 95th percentile
    
    Returns:
        Tuple of (is_acceptable, list_of_issues)
    """
    issues = []
    
    if metrics.mean < mean_min or metrics.p05 < p05_min:
        issues.append(QualityIssue.TOO_DARK)
    
    if metrics.mean > mean_max or metrics.p95 > p95_max:
        issues.append(QualityIssue.TOO_BRIGHT)
    
    # Check contrast
    if metrics.std < 20:  # Low standard deviation indicates low contrast
        issues.append(QualityIssue.LOW_CONTRAST)
    
    return len(issues) == 0, issues


# ============= SHARPNESS CALCULATIONS =============

def calculate_tenengrad_sharpness(gray_image: np.ndarray,
                                 target_width: int = 640) -> float:
    """
    Calculate Tenengrad sharpness score
    
    The Tenengrad metric uses Sobel operators to calculate gradient magnitude.
    Higher values indicate sharper images.
    
    Args:
        gray_image: Grayscale image as numpy array
        target_width: Normalize to this width for consistent scoring
    
    Returns:
        Sharpness score (higher is sharper)
    """
    if gray_image.size == 0:
        return 0.0
    
    # Resize factor for normalization
    height, width = gray_image.shape
    if width > 0:
        scale_factor = target_width / width
    else:
        scale_factor = 1.0
    
    # Sobel operators
    sobel_x = np.array([[-1, 0, 1], [-2, 0, 2], [-1, 0, 1]], dtype=np.float32)
    sobel_y = np.array([[-1, -2, -1], [0, 0, 0], [1, 2, 1]], dtype=np.float32)
    
    # Pad image for convolution
    padded = np.pad(gray_image.astype(np.float32), ((1, 1), (1, 1)), mode='edge')
    
    # Calculate gradients using convolution
    grad_x = np.zeros_like(gray_image, dtype=np.float32)
    grad_y = np.zeros_like(gray_image, dtype=np.float32)
    
    for i in range(height):
        for j in range(width):
            window = padded[i:i+3, j:j+3]
            grad_x[i, j] = np.sum(window * sobel_x)
            grad_y[i, j] = np.sum(window * sobel_y)
    
    # Calculate gradient magnitude
    gradient_magnitude = np.sqrt(grad_x**2 + grad_y**2)
    
    # Tenengrad score is sum of squared gradients
    score = float(np.sum(gradient_magnitude**2))
    
    # Normalize by image size and scale
    normalized_score = score / (height * width) * scale_factor
    
    return normalized_score


def evaluate_sharpness(sharpness_score: float,
                      min_score: float = 500) -> Tuple[bool, Optional[QualityIssue]]:
    """
    Evaluate if image sharpness is acceptable
    
    Args:
        sharpness_score: Calculated Tenengrad score
        min_score: Minimum acceptable score
    
    Returns:
        Tuple of (is_sharp, issue_if_any)
    """
    if sharpness_score < min_score:
        return False, QualityIssue.BLUR_DETECTED
    else:
        return True, None


# ============= STABILITY CALCULATIONS =============

@dataclass
class StabilityTracker:
    """Track face stability over time"""
    history: List[Tuple[float, BoundingBox]]  # (timestamp, bbox)
    max_history: int = 30
    
    def add_frame(self, timestamp: float, bbox: BoundingBox):
        """Add a frame to stability history"""
        self.history.append((timestamp, bbox))
        # Keep only recent history
        if len(self.history) > self.max_history:
            self.history = self.history[-self.max_history:]
    
    def calculate_stability(self, window_ms: float = 900) -> Tuple[bool, float]:
        """
        Calculate if face has been stable for required duration
        
        Args:
            window_ms: Required stability window in milliseconds
        
        Returns:
            Tuple of (is_stable, stable_duration_ms)
        """
        if len(self.history) < 2:
            return False, 0.0
        
        current_time = self.history[-1][0]
        current_bbox = self.history[-1][1]
        
        # Find how long the face has been stable
        stable_start_time = current_time
        
        for i in range(len(self.history) - 2, -1, -1):
            prev_time, prev_bbox = self.history[i]
            
            # Check if position is stable (within threshold)
            if not self._is_similar_position(current_bbox, prev_bbox):
                break
            
            stable_start_time = prev_time
            
            # Check if we've reached required duration
            if (current_time - stable_start_time) >= window_ms:
                return True, current_time - stable_start_time
        
        stable_duration = current_time - stable_start_time
        return stable_duration >= window_ms, stable_duration
    
    def _is_similar_position(self, bbox1: BoundingBox, bbox2: BoundingBox,
                            position_threshold: float = 0.05) -> bool:
        """Check if two bounding boxes are in similar positions"""
        # Calculate normalized distance
        dx = abs(bbox1.center_x - bbox2.center_x) / max(bbox1.width, bbox2.width)
        dy = abs(bbox1.center_y - bbox2.center_y) / max(bbox1.height, bbox2.height)
        
        # Calculate size difference
        size_diff = abs(bbox1.area - bbox2.area) / max(bbox1.area, bbox2.area)
        
        return dx < position_threshold and dy < position_threshold and size_diff < 0.1


# ============= COMPREHENSIVE ANALYSIS =============

def analyze_face_geometry(face_bbox: BoundingBox,
                         frame_width: int,
                         frame_height: int,
                         gray_face_region: np.ndarray,
                         landmarks: Optional[Dict[str, Tuple[float, float]]] = None,
                         thresholds: Optional[Dict[str, Any]] = None) -> GeometryResult:
    """
    Perform comprehensive face geometry analysis
    
    This is a pure function that analyzes all geometric properties of a face.
    
    Args:
        face_bbox: Face bounding box
        frame_width: Frame width in pixels
        frame_height: Frame height in pixels
        gray_face_region: Grayscale image of face region
        landmarks: Optional facial landmarks
        thresholds: Optional threshold overrides
    
    Returns:
        Complete geometry analysis result
    """
    # Use default thresholds if not provided
    if thresholds is None:
        thresholds = {
            'min_occupancy': 0.3,
            'max_occupancy': 0.8,
            'centering_tolerance': 0.15,
            'max_pose_angle': 30.0,
            'brightness_mean_min': 60,
            'brightness_mean_max': 200,
            'brightness_p05_min': 20,
            'brightness_p95_max': 235,
            'min_sharpness': 500
        }
    
    issues = []
    
    # Calculate occupancy
    occupancy_ratio = calculate_occupancy_ratio(face_bbox, frame_width, frame_height)
    occupancy_ok, occupancy_issue = evaluate_occupancy(
        occupancy_ratio,
        thresholds['min_occupancy'],
        thresholds['max_occupancy']
    )
    if occupancy_issue:
        issues.append(occupancy_issue)
    
    # Calculate centering
    centering_offset = calculate_centering_offset(face_bbox, frame_width, frame_height)
    centering_ok, centering_issue = evaluate_centering(
        centering_offset,
        thresholds['centering_tolerance']
    )
    if centering_issue:
        issues.append(centering_issue)
    
    # Calculate pose
    if landmarks:
        pose = calculate_pose_from_landmarks(landmarks)
    else:
        pose = PoseAngles(yaw=0.0, pitch=0.0, roll=0.0)
    
    pose_ok, pose_issues = evaluate_pose(pose, thresholds['max_pose_angle'])
    issues.extend(pose_issues)
    
    # Calculate brightness
    brightness = calculate_brightness_metrics(gray_face_region)
    brightness_ok, brightness_issues = evaluate_brightness(
        brightness,
        thresholds['brightness_mean_min'],
        thresholds['brightness_mean_max'],
        thresholds['brightness_p05_min'],
        thresholds['brightness_p95_max']
    )
    issues.extend(brightness_issues)
    
    # Calculate sharpness
    sharpness_score = calculate_tenengrad_sharpness(gray_face_region)
    sharpness_ok, sharpness_issue = evaluate_sharpness(
        sharpness_score,
        thresholds['min_sharpness']
    )
    if sharpness_issue:
        issues.append(sharpness_issue)
    
    # Calculate overall confidence
    checks_passed = sum([
        occupancy_ok,
        centering_ok,
        pose_ok,
        brightness_ok,
        sharpness_ok
    ])
    confidence = checks_passed / 5.0
    
    return GeometryResult(
        occupancy_ratio=occupancy_ratio,
        centering_offset=centering_offset,
        pose=pose,
        brightness=brightness,
        sharpness_score=sharpness_score,
        issues=issues,
        confidence=confidence
    )


def format_geometry_feedback(result: GeometryResult) -> Dict[str, Any]:
    """
    Format geometry analysis result as user feedback
    
    Args:
        result: Geometry analysis result
    
    Returns:
        Dictionary with formatted feedback
    """
    feedback = {
        'ok': len(result.issues) == 0,
        'confidence': result.confidence,
        'metrics': {
            'occupancy': round(result.occupancy_ratio, 3),
            'centering_x': round(result.centering_offset[0], 3),
            'centering_y': round(result.centering_offset[1], 3),
            'yaw': round(result.pose.yaw, 1),
            'pitch': round(result.pose.pitch, 1),
            'roll': round(result.pose.roll, 1),
            'brightness_mean': round(result.brightness.mean, 1),
            'sharpness': round(result.sharpness_score, 1)
        },
        'issues': [issue.value for issue in result.issues],
        'suggestions': []
    }
    
    # Generate suggestions based on issues
    for issue in result.issues:
        if issue == QualityIssue.FACE_TOO_SMALL:
            feedback['suggestions'].append("Move closer to the camera")
        elif issue == QualityIssue.FACE_TOO_LARGE:
            feedback['suggestions'].append("Move further from the camera")
        elif issue == QualityIssue.OFF_CENTER:
            feedback['suggestions'].append("Center your face in the frame")
        elif issue in [QualityIssue.EXCESSIVE_YAW, QualityIssue.EXCESSIVE_PITCH, QualityIssue.EXCESSIVE_ROLL]:
            feedback['suggestions'].append("Face the camera directly")
        elif issue == QualityIssue.TOO_DARK:
            feedback['suggestions'].append("Move to a brighter area")
        elif issue == QualityIssue.TOO_BRIGHT:
            feedback['suggestions'].append("Reduce lighting or move away from direct light")
        elif issue == QualityIssue.LOW_CONTRAST:
            feedback['suggestions'].append("Improve lighting conditions")
        elif issue == QualityIssue.BLUR_DETECTED:
            feedback['suggestions'].append("Hold the device steady")
    
    return feedback