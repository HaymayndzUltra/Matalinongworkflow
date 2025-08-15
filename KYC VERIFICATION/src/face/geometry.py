"""
Face Geometry & Gating Library - Pure functions for face validation
Phase 3: Deterministic geometry validation with reasoned failures
"""

import numpy as np
from typing import Dict, Any, List, Tuple, Optional
from dataclasses import dataclass
import cv2
import math


@dataclass
class ValidationResult:
    """Result of a validation check"""
    passed: bool
    value: Any
    threshold: Any
    reason: Optional[str] = None


@dataclass
class GeometryValidation:
    """Complete geometry validation result"""
    passed: bool
    failures: List[str]
    metrics: Dict[str, float]
    details: Dict[str, ValidationResult]


def calculate_bbox_fill(bbox: Tuple[int, int, int, int], 
                        frame_shape: Tuple[int, int]) -> float:
    """Calculate face bounding box fill ratio
    
    Args:
        bbox: Face bounding box (x, y, width, height)
        frame_shape: Frame dimensions (height, width)
    
    Returns:
        Fill ratio (0-1) representing fraction of frame occupied by face
    """
    x, y, w, h = bbox
    frame_h, frame_w = frame_shape
    
    if frame_h <= 0 or frame_w <= 0:
        return 0.0
    
    face_area = w * h
    frame_area = frame_h * frame_w
    
    return face_area / frame_area if frame_area > 0 else 0.0


def calculate_centering_offset(bbox: Tuple[int, int, int, int],
                              frame_shape: Tuple[int, int]) -> Tuple[float, float]:
    """Calculate face centering offset from frame center
    
    Args:
        bbox: Face bounding box (x, y, width, height)
        frame_shape: Frame dimensions (height, width)
    
    Returns:
        Tuple of (horizontal_offset, vertical_offset) as fractions (0-1)
    """
    x, y, w, h = bbox
    frame_h, frame_w = frame_shape
    
    if frame_h <= 0 or frame_w <= 0:
        return 1.0, 1.0
    
    # Calculate face center
    face_center_x = x + w / 2
    face_center_y = y + h / 2
    
    # Calculate frame center
    frame_center_x = frame_w / 2
    frame_center_y = frame_h / 2
    
    # Calculate offset as fraction of frame dimensions
    offset_x = abs(face_center_x - frame_center_x) / frame_w
    offset_y = abs(face_center_y - frame_center_y) / frame_h
    
    return offset_x, offset_y


def calculate_pose_angles(landmarks: np.ndarray) -> Dict[str, float]:
    """Calculate head pose angles from facial landmarks
    
    Args:
        landmarks: 68-point facial landmarks array
    
    Returns:
        Dictionary with yaw, pitch, and roll angles in degrees
    """
    if landmarks is None or len(landmarks) < 68:
        return {"yaw": 0.0, "pitch": 0.0, "roll": 0.0}
    
    # Define 3D model points for a generic face
    model_points = np.array([
        (0.0, 0.0, 0.0),             # Nose tip
        (0.0, -330.0, -65.0),        # Chin
        (-225.0, 170.0, -135.0),     # Left eye left corner
        (225.0, 170.0, -135.0),      # Right eye right corner
        (-150.0, -150.0, -125.0),    # Left mouth corner
        (150.0, -150.0, -125.0)      # Right mouth corner
    ])
    
    # Extract 2D image points from landmarks
    image_points = np.array([
        landmarks[30],  # Nose tip
        landmarks[8],   # Chin
        landmarks[36],  # Left eye left corner
        landmarks[45],  # Right eye right corner
        landmarks[48],  # Left mouth corner
        landmarks[54]   # Right mouth corner
    ], dtype="double")
    
    # Camera internals (assuming standard webcam)
    focal_length = 500
    center = (320, 240)  # Assuming 640x480 resolution
    camera_matrix = np.array([
        [focal_length, 0, center[0]],
        [0, focal_length, center[1]],
        [0, 0, 1]
    ], dtype="double")
    
    dist_coeffs = np.zeros((4, 1))
    
    # Solve PnP
    success, rotation_vector, translation_vector = cv2.solvePnP(
        model_points, image_points, camera_matrix, dist_coeffs
    )
    
    if not success:
        return {"yaw": 0.0, "pitch": 0.0, "roll": 0.0}
    
    # Convert rotation vector to rotation matrix
    rotation_matrix, _ = cv2.Rodrigues(rotation_vector)
    
    # Extract Euler angles
    sy = math.sqrt(rotation_matrix[0, 0] * rotation_matrix[0, 0] +
                   rotation_matrix[1, 0] * rotation_matrix[1, 0])
    
    singular = sy < 1e-6
    
    if not singular:
        x = math.atan2(rotation_matrix[2, 1], rotation_matrix[2, 2])
        y = math.atan2(-rotation_matrix[2, 0], sy)
        z = math.atan2(rotation_matrix[1, 0], rotation_matrix[0, 0])
    else:
        x = math.atan2(-rotation_matrix[1, 2], rotation_matrix[1, 1])
        y = math.atan2(-rotation_matrix[2, 0], sy)
        z = 0
    
    # Convert to degrees
    pitch = math.degrees(x)
    yaw = math.degrees(y)
    roll = math.degrees(z)
    
    return {"yaw": yaw, "pitch": pitch, "roll": roll}


def calculate_tenengrad_sharpness(image: np.ndarray, target_width: int = 640) -> float:
    """Calculate Tenengrad sharpness score
    
    Args:
        image: Grayscale or color image
        target_width: Target width for normalization
    
    Returns:
        Normalized sharpness score (0-1)
    """
    if image is None or image.size == 0:
        return 0.0
    
    # Convert to grayscale if needed
    if len(image.shape) == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image
    
    # Resize to target width for consistent scoring
    height, width = gray.shape
    if width != target_width:
        scale = target_width / width
        new_height = int(height * scale)
        gray = cv2.resize(gray, (target_width, new_height))
    
    # Calculate gradients using Sobel operator
    gx = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
    gy = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)
    
    # Calculate gradient magnitude
    gradient_magnitude = np.sqrt(gx**2 + gy**2)
    
    # Calculate Tenengrad score (sum of squared gradients)
    tenengrad = np.sum(gradient_magnitude**2)
    
    # Normalize by image size
    normalized_score = tenengrad / (gray.shape[0] * gray.shape[1])
    
    # Apply sigmoid-like normalization to get 0-1 range
    # Typical values range from 0 to 10000 for normalized score
    score = 1.0 / (1.0 + np.exp(-0.001 * (normalized_score - 2000)))
    
    return float(score)


def calculate_brightness_metrics(image: np.ndarray) -> Dict[str, float]:
    """Calculate brightness metrics for an image
    
    Args:
        image: Color or grayscale image
    
    Returns:
        Dictionary with mean, p05, and p95 brightness values
    """
    if image is None or image.size == 0:
        return {"mean": 0.0, "p05": 0.0, "p95": 0.0}
    
    # Convert to grayscale if needed
    if len(image.shape) == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image
    
    # Calculate percentiles
    mean_val = np.mean(gray)
    p05 = np.percentile(gray, 5)
    p95 = np.percentile(gray, 95)
    
    return {
        "mean": float(mean_val),
        "p05": float(p05),
        "p95": float(p95)
    }


def check_stability(timestamps_ms: List[int], pass_duration_ms: int) -> Tuple[bool, int]:
    """Check if face has been stable for required duration
    
    Args:
        timestamps_ms: List of timestamps when face passed checks
        pass_duration_ms: Required continuous pass duration
    
    Returns:
        Tuple of (is_stable, continuous_duration_ms)
    """
    if not timestamps_ms or len(timestamps_ms) < 2:
        return False, 0
    
    # Sort timestamps
    sorted_times = sorted(timestamps_ms)
    
    # Find longest continuous sequence
    max_duration = 0
    current_start = sorted_times[0]
    
    for i in range(1, len(sorted_times)):
        time_diff = sorted_times[i] - sorted_times[i-1]
        
        # Allow up to 100ms gap between frames
        if time_diff > 100:
            # Sequence broken, check duration
            duration = sorted_times[i-1] - current_start
            max_duration = max(max_duration, duration)
            current_start = sorted_times[i]
    
    # Check final sequence
    if len(sorted_times) > 0:
        final_duration = sorted_times[-1] - current_start
        max_duration = max(max_duration, final_duration)
    
    return max_duration >= pass_duration_ms, max_duration


def validate_face_geometry(frame_metadata: Dict[str, Any],
                          thresholds: Dict[str, Any]) -> GeometryValidation:
    """Validate face geometry against thresholds
    
    Args:
        frame_metadata: Dictionary containing bbox, pose, blur, brightness data
        thresholds: Threshold values for validation
    
    Returns:
        GeometryValidation result with pass/fail status and reasons
    """
    failures = []
    details = {}
    metrics = {}
    
    # Extract metadata
    bbox = frame_metadata.get("bbox", [0, 0, 0, 0])
    frame_shape = frame_metadata.get("frame_shape", (480, 640))
    pose = frame_metadata.get("pose", {})
    blur_score = frame_metadata.get("blur_score", 0.0)
    brightness = frame_metadata.get("brightness", {})
    
    # 1. Check bounding box fill
    fill_ratio = calculate_bbox_fill(bbox, frame_shape)
    metrics["bbox_fill"] = fill_ratio
    
    fill_min = thresholds.get("bbox_fill_min", 0.15)
    fill_max = thresholds.get("bbox_fill_max", 0.65)
    
    if fill_ratio < fill_min:
        failures.append(f"Face too small: {fill_ratio:.2f} < {fill_min}")
        details["bbox_fill"] = ValidationResult(False, fill_ratio, (fill_min, fill_max),
                                               "Face too far from camera")
    elif fill_ratio > fill_max:
        failures.append(f"Face too large: {fill_ratio:.2f} > {fill_max}")
        details["bbox_fill"] = ValidationResult(False, fill_ratio, (fill_min, fill_max),
                                               "Face too close to camera")
    else:
        details["bbox_fill"] = ValidationResult(True, fill_ratio, (fill_min, fill_max))
    
    # 2. Check centering
    offset_x, offset_y = calculate_centering_offset(bbox, frame_shape)
    max_offset = thresholds.get("centering_max_offset", 0.2)
    metrics["centering_offset_x"] = offset_x
    metrics["centering_offset_y"] = offset_y
    
    if offset_x > max_offset or offset_y > max_offset:
        failures.append(f"Face not centered: offset ({offset_x:.2f}, {offset_y:.2f}) > {max_offset}")
        details["centering"] = ValidationResult(False, (offset_x, offset_y), max_offset,
                                               "Please center your face in the frame")
    else:
        details["centering"] = ValidationResult(True, (offset_x, offset_y), max_offset)
    
    # 3. Check pose angles
    yaw = abs(pose.get("yaw", 0))
    pitch = abs(pose.get("pitch", 0))
    roll = abs(pose.get("roll", 0))
    
    pose_max = thresholds.get("pose_max_degrees", 15)
    metrics["pose_yaw"] = yaw
    metrics["pose_pitch"] = pitch
    metrics["pose_roll"] = roll
    
    if yaw > pose_max:
        failures.append(f"Head turned too much: yaw {yaw:.1f}° > {pose_max}°")
        details["pose_yaw"] = ValidationResult(False, yaw, pose_max,
                                              "Please face the camera directly")
    else:
        details["pose_yaw"] = ValidationResult(True, yaw, pose_max)
    
    if pitch > pose_max:
        failures.append(f"Head tilted too much: pitch {pitch:.1f}° > {pose_max}°")
        details["pose_pitch"] = ValidationResult(False, pitch, pose_max,
                                               "Please keep your head level")
    else:
        details["pose_pitch"] = ValidationResult(True, pitch, pose_max)
    
    if roll > pose_max * 0.67:  # Roll typically has tighter threshold
        failures.append(f"Head rotated too much: roll {roll:.1f}° > {pose_max * 0.67:.1f}°")
        details["pose_roll"] = ValidationResult(False, roll, pose_max * 0.67,
                                               "Please keep your head straight")
    else:
        details["pose_roll"] = ValidationResult(True, roll, pose_max * 0.67)
    
    # 4. Check blur/sharpness
    blur_min = thresholds.get("blur_min", 0.85)
    metrics["blur_score"] = blur_score
    
    if blur_score < blur_min:
        failures.append(f"Image too blurry: {blur_score:.2f} < {blur_min}")
        details["blur"] = ValidationResult(False, blur_score, blur_min,
                                          "Please hold the device steady")
    else:
        details["blur"] = ValidationResult(True, blur_score, blur_min)
    
    # 5. Check brightness
    brightness_mean = brightness.get("mean", 0)
    brightness_p05 = brightness.get("p05", 0)
    brightness_p95 = brightness.get("p95", 255)
    
    mean_range = thresholds.get("brightness_mean", [60, 200])
    p05_min = thresholds.get("brightness_p05_min", 20)
    p95_max = thresholds.get("brightness_p95_max", 235)
    
    metrics["brightness_mean"] = brightness_mean
    metrics["brightness_p05"] = brightness_p05
    metrics["brightness_p95"] = brightness_p95
    
    if brightness_mean < mean_range[0]:
        failures.append(f"Too dark: mean brightness {brightness_mean:.0f} < {mean_range[0]}")
        details["brightness_mean"] = ValidationResult(False, brightness_mean, mean_range,
                                                     "Please improve lighting")
    elif brightness_mean > mean_range[1]:
        failures.append(f"Too bright: mean brightness {brightness_mean:.0f} > {mean_range[1]}")
        details["brightness_mean"] = ValidationResult(False, brightness_mean, mean_range,
                                                     "Please reduce lighting")
    else:
        details["brightness_mean"] = ValidationResult(True, brightness_mean, mean_range)
    
    if brightness_p05 < p05_min:
        failures.append(f"Dark areas too dark: p05 {brightness_p05:.0f} < {p05_min}")
        details["brightness_p05"] = ValidationResult(False, brightness_p05, p05_min,
                                                    "Please avoid shadows on face")
    else:
        details["brightness_p05"] = ValidationResult(True, brightness_p05, p05_min)
    
    if brightness_p95 > p95_max:
        failures.append(f"Bright areas overexposed: p95 {brightness_p95:.0f} > {p95_max}")
        details["brightness_p95"] = ValidationResult(False, brightness_p95, p95_max,
                                                    "Please avoid direct light/glare")
    else:
        details["brightness_p95"] = ValidationResult(True, brightness_p95, p95_max)
    
    # Determine overall pass/fail
    passed = len(failures) == 0
    
    return GeometryValidation(
        passed=passed,
        failures=failures,
        metrics=metrics,
        details=details
    )


def calculate_face_quality_score(metrics: Dict[str, float]) -> float:
    """Calculate overall face quality score from metrics
    
    Args:
        metrics: Dictionary of face metrics
    
    Returns:
        Quality score (0-1)
    """
    scores = []
    
    # Bbox fill score (optimal around 0.3-0.4)
    fill = metrics.get("bbox_fill", 0)
    if 0.25 <= fill <= 0.45:
        scores.append(1.0)
    elif 0.15 <= fill <= 0.65:
        scores.append(0.7)
    else:
        scores.append(0.3)
    
    # Centering score
    offset_x = metrics.get("centering_offset_x", 1.0)
    offset_y = metrics.get("centering_offset_y", 1.0)
    max_offset = max(offset_x, offset_y)
    if max_offset <= 0.1:
        scores.append(1.0)
    elif max_offset <= 0.2:
        scores.append(0.8)
    else:
        scores.append(0.4)
    
    # Pose score
    yaw = metrics.get("pose_yaw", 90)
    pitch = metrics.get("pose_pitch", 90)
    roll = metrics.get("pose_roll", 90)
    max_angle = max(yaw, pitch, roll)
    if max_angle <= 5:
        scores.append(1.0)
    elif max_angle <= 15:
        scores.append(0.8)
    else:
        scores.append(0.3)
    
    # Blur score
    blur = metrics.get("blur_score", 0)
    scores.append(blur)
    
    # Brightness score
    brightness_mean = metrics.get("brightness_mean", 0)
    if 80 <= brightness_mean <= 180:
        scores.append(1.0)
    elif 60 <= brightness_mean <= 200:
        scores.append(0.7)
    else:
        scores.append(0.3)
    
    # Calculate weighted average
    if scores:
        return sum(scores) / len(scores)
    return 0.0