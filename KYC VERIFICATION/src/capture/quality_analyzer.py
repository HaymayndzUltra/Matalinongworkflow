"""
KYC Capture Quality Analyzer
Implements glare/blur/orientation checks with quality scoring and coaching hints
Phase 1: Capture Quality & Coaching
"""

import cv2
import numpy as np
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass
from enum import Enum
import logging
from pathlib import Path
import json

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class QualityIssue(Enum):
    """Types of quality issues detected"""
    BLUR = "blur"
    GLARE = "glare"
    LOW_RESOLUTION = "low_resolution"
    POOR_LIGHTING = "poor_lighting"
    INCORRECT_ORIENTATION = "incorrect_orientation"
    PARTIAL_DOCUMENT = "partial_document"
    OBSTRUCTION = "obstruction"
    MULTIPLE_DOCUMENTS = "multiple_documents"
    NO_DOCUMENT = "no_document"

@dataclass
class QualityMetrics:
    """Quality metrics for captured image"""
    resolution: Tuple[int, int]
    blur_score: float  # 0-1, lower is better
    glare_score: float  # 0-1, lower is better
    brightness_score: float  # 0-1, optimal around 0.5
    contrast_score: float  # 0-1, higher is better
    orientation_angle: float  # degrees from correct orientation
    document_coverage: float  # 0-1, percentage of frame
    edge_clarity: float  # 0-1, higher is better
    overall_score: float  # 0-1, weighted average

@dataclass
class CoachingHint:
    """Coaching hint for user guidance"""
    issue: QualityIssue
    severity: str  # "critical", "warning", "info"
    message: str
    suggestion: str
    priority: int  # Lower number = higher priority

class CaptureQualityAnalyzer:
    """Analyzes capture quality and provides coaching hints"""
    
    def __init__(self, config_path: Optional[str] = None):
        """Initialize quality analyzer with configuration"""
        self.config = self._load_config(config_path)
        self.min_resolution = self.config.get("min_resolution", 1000)
        self.blur_threshold = self.config.get("blur_threshold", 0.3)
        self.glare_threshold = self.config.get("glare_threshold", 0.2)
        self.pass_threshold = self.config.get("pass_threshold", 0.95)
        
    def _load_config(self, config_path: Optional[str]) -> Dict:
        """Load configuration from file or use defaults"""
        default_config = {
            "min_resolution": 1000,
            "blur_threshold": 0.3,
            "glare_threshold": 0.2,
            "brightness_range": [0.3, 0.7],
            "contrast_threshold": 0.4,
            "pass_threshold": 0.95,
            "weights": {
                "blur": 0.25,
                "glare": 0.20,
                "brightness": 0.15,
                "contrast": 0.15,
                "resolution": 0.15,
                "orientation": 0.10
            }
        }
        
        if config_path and Path(config_path).exists():
            with open(config_path, 'r') as f:
                user_config = json.load(f)
                default_config.update(user_config)
        
        return default_config
    
    def analyze_frame(self, image: np.ndarray) -> Tuple[QualityMetrics, List[CoachingHint]]:
        """
        Analyze single frame for quality issues
        
        Args:
            image: Input image as numpy array (BGR format)
            
        Returns:
            Tuple of quality metrics and coaching hints
        """
        metrics = self._calculate_metrics(image)
        hints = self._generate_coaching_hints(metrics)
        
        # Log analysis results
        logger.info(f"Quality Score: {metrics.overall_score:.2f}")
        if hints:
            logger.warning(f"Issues detected: {[h.issue.value for h in hints]}")
        
        return metrics, hints
    
    def _calculate_metrics(self, image: np.ndarray) -> QualityMetrics:
        """Calculate all quality metrics for the image"""
        height, width = image.shape[:2]
        resolution = (width, height)
        
        # Convert to grayscale for analysis
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        
        # Calculate individual metrics
        blur_score = self._calculate_blur(gray)
        glare_score = self._detect_glare(image)
        brightness_score = self._calculate_brightness(gray)
        contrast_score = self._calculate_contrast(gray)
        orientation_angle = self._detect_orientation(gray)
        document_coverage = self._estimate_document_coverage(gray)
        edge_clarity = self._calculate_edge_clarity(gray)
        
        # Calculate weighted overall score
        weights = self.config["weights"]
        overall_score = (
            (1 - blur_score) * weights["blur"] +
            (1 - glare_score) * weights["glare"] +
            (1 - abs(brightness_score - 0.5) * 2) * weights["brightness"] +
            contrast_score * weights["contrast"] +
            min(1.0, min(resolution) / self.min_resolution) * weights["resolution"] +
            (1 - abs(orientation_angle) / 90) * weights["orientation"]
        )
        
        return QualityMetrics(
            resolution=resolution,
            blur_score=blur_score,
            glare_score=glare_score,
            brightness_score=brightness_score,
            contrast_score=contrast_score,
            orientation_angle=orientation_angle,
            document_coverage=document_coverage,
            edge_clarity=edge_clarity,
            overall_score=overall_score
        )
    
    def _calculate_blur(self, gray: np.ndarray) -> float:
        """
        Calculate blur score using Laplacian variance
        Lower variance indicates more blur
        """
        laplacian = cv2.Laplacian(gray, cv2.CV_64F)
        variance = laplacian.var()
        
        # Normalize to 0-1 range (inverse, as higher variance means less blur)
        # Typical variance ranges from 0 (very blurry) to 1000+ (very sharp)
        blur_score = 1 - min(1.0, variance / 500)
        
        return blur_score
    
    def _detect_glare(self, image: np.ndarray) -> float:
        """
        Detect glare/hotspots in the image
        Returns score 0-1, higher means more glare
        """
        # Convert to HSV for better brightness detection
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        _, _, v = cv2.split(hsv)
        
        # Find bright spots (potential glare)
        threshold = 250  # Very bright pixels
        glare_mask = v > threshold
        glare_pixels = np.sum(glare_mask)
        total_pixels = v.shape[0] * v.shape[1]
        
        # Calculate glare percentage
        glare_score = glare_pixels / total_pixels
        
        # Also check for large continuous bright regions
        kernel = np.ones((5, 5), np.uint8)
        glare_dilated = cv2.dilate(glare_mask.astype(np.uint8), kernel, iterations=2)
        contours, _ = cv2.findContours(glare_dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        if contours:
            max_area = max(cv2.contourArea(c) for c in contours)
            area_ratio = max_area / total_pixels
            glare_score = max(glare_score, area_ratio * 2)  # Weight large glare regions more
        
        return min(1.0, glare_score)
    
    def _calculate_brightness(self, gray: np.ndarray) -> float:
        """Calculate average brightness (0-1)"""
        return np.mean(gray) / 255.0
    
    def _calculate_contrast(self, gray: np.ndarray) -> float:
        """Calculate image contrast using standard deviation"""
        std_dev = np.std(gray)
        # Normalize to 0-1 range
        contrast_score = min(1.0, std_dev / 127.5)
        return contrast_score
    
    def _detect_orientation(self, gray: np.ndarray) -> float:
        """
        Detect document orientation angle
        Returns angle in degrees (-90 to 90)
        """
        # Detect edges
        edges = cv2.Canny(gray, 50, 150)
        
        # Detect lines using Hough transform
        lines = cv2.HoughLinesP(edges, 1, np.pi/180, 100, minLineLength=100, maxLineGap=10)
        
        if lines is None:
            return 0.0
        
        # Calculate angles of detected lines
        angles = []
        for line in lines:
            x1, y1, x2, y2 = line[0]
            angle = np.degrees(np.arctan2(y2 - y1, x2 - x1))
            # Normalize to -90 to 90 range
            if angle < -45:
                angle += 90
            elif angle > 45:
                angle -= 90
            angles.append(angle)
        
        if angles:
            # Use median angle to avoid outliers
            orientation_angle = np.median(angles)
        else:
            orientation_angle = 0.0
        
        return orientation_angle
    
    def _estimate_document_coverage(self, gray: np.ndarray) -> float:
        """
        Estimate how much of the frame is covered by the document
        Returns coverage ratio (0-1)
        """
        # Simple edge detection to find document boundaries
        edges = cv2.Canny(gray, 50, 150)
        
        # Find contours
        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        if not contours:
            return 0.0
        
        # Find largest contour (assumed to be document)
        largest_contour = max(contours, key=cv2.contourArea)
        doc_area = cv2.contourArea(largest_contour)
        total_area = gray.shape[0] * gray.shape[1]
        
        coverage = doc_area / total_area
        return min(1.0, coverage)
    
    def _calculate_edge_clarity(self, gray: np.ndarray) -> float:
        """
        Calculate edge clarity score
        Clear edges indicate good focus and quality
        """
        # Apply Sobel operator
        sobelx = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
        sobely = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)
        
        # Calculate gradient magnitude
        magnitude = np.sqrt(sobelx**2 + sobely**2)
        
        # Calculate edge clarity as mean of strong edges
        strong_edges = magnitude[magnitude > np.percentile(magnitude, 90)]
        
        if len(strong_edges) > 0:
            clarity = np.mean(strong_edges) / 255.0
        else:
            clarity = 0.0
        
        return min(1.0, clarity)
    
    def _generate_coaching_hints(self, metrics: QualityMetrics) -> List[CoachingHint]:
        """Generate coaching hints based on detected issues"""
        hints = []
        
        # Check resolution
        if min(metrics.resolution) < self.min_resolution:
            hints.append(CoachingHint(
                issue=QualityIssue.LOW_RESOLUTION,
                severity="critical",
                message=f"Image resolution too low: {metrics.resolution[0]}x{metrics.resolution[1]}",
                suggestion="Move closer to the document or use higher camera resolution",
                priority=1
            ))
        
        # Check blur
        if metrics.blur_score > self.blur_threshold:
            hints.append(CoachingHint(
                issue=QualityIssue.BLUR,
                severity="critical" if metrics.blur_score > 0.5 else "warning",
                message=f"Image is blurry (score: {metrics.blur_score:.2f})",
                suggestion="Hold the camera steady and ensure proper focus",
                priority=2
            ))
        
        # Check glare
        if metrics.glare_score > self.glare_threshold:
            hints.append(CoachingHint(
                issue=QualityIssue.GLARE,
                severity="critical" if metrics.glare_score > 0.4 else "warning",
                message=f"Glare detected (score: {metrics.glare_score:.2f})",
                suggestion="Adjust lighting or angle to reduce reflections",
                priority=3
            ))
        
        # Check brightness
        brightness_range = self.config["brightness_range"]
        if metrics.brightness_score < brightness_range[0]:
            hints.append(CoachingHint(
                issue=QualityIssue.POOR_LIGHTING,
                severity="warning",
                message="Image is too dark",
                suggestion="Improve lighting conditions or use camera flash",
                priority=4
            ))
        elif metrics.brightness_score > brightness_range[1]:
            hints.append(CoachingHint(
                issue=QualityIssue.POOR_LIGHTING,
                severity="warning",
                message="Image is overexposed",
                suggestion="Reduce lighting or disable camera flash",
                priority=4
            ))
        
        # Check orientation
        if abs(metrics.orientation_angle) > 5:
            hints.append(CoachingHint(
                issue=QualityIssue.INCORRECT_ORIENTATION,
                severity="warning" if abs(metrics.orientation_angle) < 15 else "critical",
                message=f"Document is tilted ({metrics.orientation_angle:.1f}°)",
                suggestion="Align document parallel to camera frame",
                priority=5
            ))
        
        # Check document coverage
        if metrics.document_coverage < 0.6:
            hints.append(CoachingHint(
                issue=QualityIssue.PARTIAL_DOCUMENT,
                severity="critical",
                message="Document doesn't fill the frame adequately",
                suggestion="Move closer to capture the entire document",
                priority=1
            ))
        
        # Sort by priority
        hints.sort(key=lambda h: h.priority)
        
        return hints
    
    def auto_correct_orientation(self, image: np.ndarray, angle: float) -> np.ndarray:
        """
        Auto-correct image orientation
        
        Args:
            image: Input image
            angle: Rotation angle in degrees
            
        Returns:
            Rotated image
        """
        if abs(angle) < 1:
            return image
        
        height, width = image.shape[:2]
        center = (width // 2, height // 2)
        
        # Get rotation matrix
        rotation_matrix = cv2.getRotationMatrix2D(center, angle, 1.0)
        
        # Calculate new dimensions
        cos = abs(rotation_matrix[0, 0])
        sin = abs(rotation_matrix[0, 1])
        new_width = int(height * sin + width * cos)
        new_height = int(height * cos + width * sin)
        
        # Adjust rotation matrix for new dimensions
        rotation_matrix[0, 2] += (new_width - width) / 2
        rotation_matrix[1, 2] += (new_height - height) / 2
        
        # Perform rotation
        rotated = cv2.warpAffine(image, rotation_matrix, (new_width, new_height),
                                flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT,
                                borderValue=(255, 255, 255))
        
        return rotated
    
    def validate_capture(self, image: np.ndarray) -> Tuple[bool, float, List[str]]:
        """
        Validate if capture meets quality standards
        
        Args:
            image: Input image
            
        Returns:
            Tuple of (passed, score, reasons)
        """
        metrics, hints = self.analyze_frame(image)
        
        passed = metrics.overall_score >= self.pass_threshold
        score = metrics.overall_score
        
        # Collect failure reasons
        reasons = []
        if not passed:
            for hint in hints:
                if hint.severity == "critical":
                    reasons.append(f"{hint.issue.value}: {hint.message}")
        
        return passed, score, reasons
    
    def process_multi_frame(self, frames: List[np.ndarray]) -> Dict[str, Any]:
        """
        Process multiple frames and return best one with consensus scoring
        
        Args:
            frames: List of image frames
            
        Returns:
            Dictionary with best frame index, metrics, and consensus data
        """
        frame_metrics = []
        
        for i, frame in enumerate(frames):
            metrics, hints = self.analyze_frame(frame)
            frame_metrics.append({
                "index": i,
                "metrics": metrics,
                "hints": hints,
                "score": metrics.overall_score
            })
        
        # Sort by overall score
        frame_metrics.sort(key=lambda x: x["score"], reverse=True)
        
        # Calculate consensus metrics
        scores = [fm["score"] for fm in frame_metrics]
        consensus = {
            "mean_score": np.mean(scores),
            "std_score": np.std(scores),
            "best_score": frame_metrics[0]["score"],
            "worst_score": frame_metrics[-1]["score"],
            "best_frame_index": frame_metrics[0]["index"],
            "frames_passing": sum(1 for s in scores if s >= self.pass_threshold),
            "total_frames": len(frames)
        }
        
        return {
            "best_frame": frame_metrics[0],
            "all_frames": frame_metrics,
            "consensus": consensus
        }

# Export main class
__all__ = ["CaptureQualityAnalyzer", "QualityMetrics", "CoachingHint", "QualityIssue"]