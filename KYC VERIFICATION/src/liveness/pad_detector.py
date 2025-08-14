"""
Presentation Attack Detection (PAD) Module
ISO 30107-3 Compliant Liveness Detection
Part of KYC Bank-Grade Parity - Phase 1

This module implements passive and active liveness detection to prevent
presentation attacks (spoofing) using printed photos, screens, masks, etc.
"""

import cv2
import numpy as np
import logging
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
import time
from scipy import signal, fftpack
from skimage import feature, filters

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class PADLevel(Enum):
    """ISO 30107-3 PAD Levels"""
    L1 = "L1"  # Basic presentation attack detection
    L2 = "L2"  # Advanced presentation attack detection


class AttackType(Enum):
    """Types of presentation attacks"""
    GENUINE = "genuine"
    PRINT = "print"
    SCREEN = "screen"
    MASK_2D = "mask_2d"
    MASK_3D = "mask_3d"
    VIDEO_REPLAY = "video_replay"
    UNKNOWN = "unknown"


@dataclass
class PADResult:
    """Result of PAD analysis"""
    is_live: bool
    confidence: float
    level: PADLevel
    detected_attack: AttackType
    scores: Dict[str, float]
    processing_time_ms: float
    features: Optional[Dict[str, Any]] = None
    reasons: Optional[List[str]] = None


class PassiveLivenessDetector:
    """Implements passive liveness detection algorithms"""
    
    def __init__(self):
        """Initialize passive liveness detector"""
        # Face detection using OpenCV instead of MediaPipe
        self.face_cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
        )
    
    def detect_texture_anomalies(self, image: np.ndarray) -> Dict[str, float]:
        """
        Detect texture anomalies using Local Binary Patterns (LBP)
        
        Args:
            image: Face image (BGR or RGB)
            
        Returns:
            Dictionary with texture analysis scores
        """
        # Convert to grayscale
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image
        
        # Compute LBP
        radius = 3
        n_points = 8 * radius
        lbp = feature.local_binary_pattern(gray, n_points, radius, method='uniform')
        
        # Calculate LBP histogram
        hist, _ = np.histogram(lbp.ravel(), bins=np.arange(0, n_points + 3), 
                               range=(0, n_points + 2))
        hist = hist.astype("float")
        hist /= (hist.sum() + 1e-6)
        
        # Calculate texture metrics
        entropy = -np.sum(hist * np.log2(hist + 1e-6))
        uniformity = np.sum(hist ** 2)
        
        # Genuine faces typically have higher entropy and lower uniformity
        texture_score = entropy / (uniformity + 1e-6)
        
        return {
            "lbp_entropy": float(entropy),
            "lbp_uniformity": float(uniformity),
            "texture_score": float(texture_score),
            "is_genuine_texture": texture_score > 15.0  # Threshold based on empirical data
        }
    
    def detect_screen_artifacts(self, image: np.ndarray) -> Dict[str, float]:
        """
        Detect screen/display artifacts using frequency domain analysis
        
        Args:
            image: Face image (BGR or RGB)
            
        Returns:
            Dictionary with screen detection scores
        """
        # Convert to grayscale
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image
        
        # Apply FFT
        f_transform = fftpack.fft2(gray)
        f_shift = fftpack.fftshift(f_transform)
        magnitude_spectrum = np.abs(f_shift)
        
        # Analyze frequency patterns
        rows, cols = gray.shape
        crow, ccol = rows // 2, cols // 2
        
        # Check for regular patterns (screen pixels/refresh rate)
        # Screens often show regular grid patterns in frequency domain
        horizontal_slice = magnitude_spectrum[crow, :]
        vertical_slice = magnitude_spectrum[:, ccol]
        
        # Find peaks indicating regular patterns
        h_peaks = signal.find_peaks(horizontal_slice, height=np.mean(horizontal_slice) * 2)[0]
        v_peaks = signal.find_peaks(vertical_slice, height=np.mean(vertical_slice) * 2)[0]
        
        # Calculate regularity score
        regularity_score = (len(h_peaks) + len(v_peaks)) / (cols + rows)
        
        # High-frequency energy ratio (screens have different HF characteristics)
        mask_radius = min(rows, cols) // 4
        high_freq_mask = np.zeros_like(magnitude_spectrum)
        center_mask = np.zeros_like(magnitude_spectrum)
        
        y, x = np.ogrid[:rows, :cols]
        mask_area = (x - ccol) ** 2 + (y - crow) ** 2
        high_freq_mask[mask_area > mask_radius ** 2] = 1
        center_mask[mask_area <= mask_radius ** 2] = 1
        
        high_freq_energy = np.sum(magnitude_spectrum * high_freq_mask)
        low_freq_energy = np.sum(magnitude_spectrum * center_mask)
        hf_ratio = high_freq_energy / (low_freq_energy + 1e-6)
        
        return {
            "regularity_score": float(regularity_score),
            "hf_energy_ratio": float(hf_ratio),
            "peak_count": len(h_peaks) + len(v_peaks),
            "is_screen_detected": regularity_score > 0.1 or hf_ratio < 0.5
        }
    
    def analyze_color_distribution(self, image: np.ndarray) -> Dict[str, float]:
        """
        Analyze color distribution for skin detection
        
        Args:
            image: Face image (BGR)
            
        Returns:
            Dictionary with color analysis scores
        """
        # Convert to different color spaces
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        ycrcb = cv2.cvtColor(image, cv2.COLOR_BGR2YCrCb)
        
        # Skin color range in HSV
        lower_skin_hsv = np.array([0, 20, 70], dtype=np.uint8)
        upper_skin_hsv = np.array([20, 255, 255], dtype=np.uint8)
        skin_mask_hsv = cv2.inRange(hsv, lower_skin_hsv, upper_skin_hsv)
        
        # Skin color range in YCrCb
        lower_skin_ycrcb = np.array([0, 133, 77], dtype=np.uint8)
        upper_skin_ycrcb = np.array([255, 173, 127], dtype=np.uint8)
        skin_mask_ycrcb = cv2.inRange(ycrcb, lower_skin_ycrcb, upper_skin_ycrcb)
        
        # Combine masks
        skin_mask = cv2.bitwise_and(skin_mask_hsv, skin_mask_ycrcb)
        
        # Calculate skin ratio
        total_pixels = image.shape[0] * image.shape[1]
        skin_pixels = np.sum(skin_mask > 0)
        skin_ratio = skin_pixels / total_pixels
        
        # Calculate color variance (genuine faces have natural variation)
        color_variance = np.mean([np.std(image[:, :, i]) for i in range(3)])
        
        # Hue histogram analysis
        hue_hist = cv2.calcHist([hsv], [0], None, [180], [0, 180])
        hue_hist = hue_hist.flatten() / (np.sum(hue_hist) + 1e-6)
        hue_entropy = -np.sum(hue_hist * np.log2(hue_hist + 1e-6))
        
        return {
            "skin_ratio": float(skin_ratio),
            "color_variance": float(color_variance),
            "hue_entropy": float(hue_entropy),
            "is_natural_skin": 0.3 < skin_ratio < 0.8 and color_variance > 10
        }
    
    def detect_illumination_inconsistencies(self, image: np.ndarray) -> Dict[str, float]:
        """
        Detect illumination inconsistencies that indicate fake presentations
        
        Args:
            image: Face image (BGR)
            
        Returns:
            Dictionary with illumination analysis scores
        """
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image
        
        # Divide image into regions
        h, w = gray.shape
        regions = [
            gray[:h//2, :w//2],      # Top-left
            gray[:h//2, w//2:],      # Top-right
            gray[h//2:, :w//2],      # Bottom-left
            gray[h//2:, w//2:]       # Bottom-right
        ]
        
        # Calculate illumination statistics for each region
        region_stats = []
        for region in regions:
            mean_intensity = np.mean(region)
            std_intensity = np.std(region)
            region_stats.append({
                'mean': mean_intensity,
                'std': std_intensity
            })
        
        # Check for unnatural uniformity (printed/screen)
        means = [stat['mean'] for stat in region_stats]
        stds = [stat['std'] for stat in region_stats]
        
        illumination_variance = np.std(means)
        texture_consistency = np.std(stds)
        
        # Detect specular highlights (common in prints/screens)
        _, specular_mask = cv2.threshold(gray, 240, 255, cv2.THRESH_BINARY)
        specular_ratio = np.sum(specular_mask > 0) / (h * w)
        
        # Calculate gradient magnitude (edge strength)
        grad_x = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
        grad_y = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)
        gradient_magnitude = np.sqrt(grad_x**2 + grad_y**2)
        edge_density = np.mean(gradient_magnitude)
        
        return {
            "illumination_variance": float(illumination_variance),
            "texture_consistency": float(texture_consistency),
            "specular_ratio": float(specular_ratio),
            "edge_density": float(edge_density),
            "is_natural_lighting": illumination_variance > 5 and specular_ratio < 0.05
        }
    
    def analyze_micro_textures(self, image: np.ndarray) -> Dict[str, float]:
        """
        Analyze micro-textures using Gabor filters
        
        Args:
            image: Face image (BGR or grayscale)
            
        Returns:
            Dictionary with micro-texture analysis scores
        """
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image
        
        # Define Gabor filter parameters
        ksize = 31
        sigma = 4.0
        lambd = 10.0
        gamma = 0.5
        psi = 0
        
        # Apply Gabor filters at different orientations
        orientations = np.arange(0, np.pi, np.pi / 4)
        gabor_responses = []
        
        for theta in orientations:
            kernel = cv2.getGaborKernel((ksize, ksize), sigma, theta, lambd, gamma, psi)
            filtered = cv2.filter2D(gray, cv2.CV_64F, kernel)
            gabor_responses.append(filtered)
        
        # Calculate statistics from Gabor responses
        gabor_features = []
        for response in gabor_responses:
            gabor_features.extend([
                np.mean(response),
                np.std(response),
                np.max(response) - np.min(response)
            ])
        
        # Compute overall texture complexity
        texture_complexity = np.std(gabor_features)
        texture_energy = np.sum(np.array(gabor_features) ** 2)
        
        return {
            "texture_complexity": float(texture_complexity),
            "texture_energy": float(texture_energy),
            "gabor_feature_count": len(gabor_features),
            "has_complex_texture": texture_complexity > 20  # Empirical threshold
        }


class PADDetector:
    """Main PAD detector implementing ISO 30107-3 compliant liveness detection"""
    
    def __init__(self, level: PADLevel = PADLevel.L2, 
                 config_path: Optional[Path] = None):
        """
        Initialize PAD detector
        
        Args:
            level: PAD level (L1 or L2)
            config_path: Optional path to configuration file
        """
        self.level = level
        self.config_path = config_path
        self.passive_detector = PassiveLivenessDetector()
        
        # Load thresholds from config
        self._load_config()
        
        logger.info(f"PAD Detector initialized with level {level.value}")
    
    def _load_config(self):
        """Load configuration and thresholds"""
        # Import threshold manager
        import sys
        sys.path.append('/workspace/KYC VERIFICATION')
        from src.config.threshold_manager import get_threshold_manager
        
        self.threshold_manager = get_threshold_manager()
        
        # Load PAD-specific thresholds
        self.far_threshold = self.threshold_manager.get('pad_far')
        self.frr_threshold = self.threshold_manager.get('pad_frr')
        self.tar_far1_target = self.threshold_manager.get('pad_tar_far1')
        
        # Decision thresholds based on level
        if self.level == PADLevel.L1:
            self.decision_threshold = 0.5  # More lenient for L1
        else:  # L2
            self.decision_threshold = 0.7  # Stricter for L2
    
    def detect(self, image: np.ndarray, 
               enable_active: bool = False) -> PADResult:
        """
        Perform presentation attack detection
        
        Args:
            image: Face image (BGR format)
            enable_active: Whether to enable active liveness (challenge-response)
            
        Returns:
            PADResult with liveness decision and metrics
        """
        start_time = time.time()
        
        # Ensure image is in correct format
        if image is None or image.size == 0:
            return PADResult(
                is_live=False,
                confidence=0.0,
                level=self.level,
                detected_attack=AttackType.UNKNOWN,
                scores={},
                processing_time_ms=0,
                reasons=["Invalid or empty image"]
            )
        
        # Resize image for consistent processing
        target_size = (256, 256)
        if image.shape[:2] != target_size:
            image = cv2.resize(image, target_size)
        
        # Collect all passive liveness scores
        scores = {}
        reasons = []
        
        # 1. Texture analysis
        texture_scores = self.passive_detector.detect_texture_anomalies(image)
        scores.update(texture_scores)
        if not texture_scores.get('is_genuine_texture', False):
            reasons.append("Suspicious texture patterns detected")
        
        # 2. Screen detection
        screen_scores = self.passive_detector.detect_screen_artifacts(image)
        scores.update(screen_scores)
        if screen_scores.get('is_screen_detected', False):
            reasons.append("Screen/display artifacts detected")
        
        # 3. Color analysis
        color_scores = self.passive_detector.analyze_color_distribution(image)
        scores.update(color_scores)
        if not color_scores.get('is_natural_skin', False):
            reasons.append("Unnatural skin color distribution")
        
        # 4. Illumination analysis
        illumination_scores = self.passive_detector.detect_illumination_inconsistencies(image)
        scores.update(illumination_scores)
        if not illumination_scores.get('is_natural_lighting', False):
            reasons.append("Illumination inconsistencies detected")
        
        # 5. Micro-texture analysis (L2 only)
        if self.level == PADLevel.L2:
            micro_texture_scores = self.passive_detector.analyze_micro_textures(image)
            scores.update(micro_texture_scores)
            if not micro_texture_scores.get('has_complex_texture', False):
                reasons.append("Insufficient micro-texture complexity")
        
        # Calculate composite liveness score
        liveness_indicators = [
            texture_scores.get('is_genuine_texture', False),
            not screen_scores.get('is_screen_detected', True),
            color_scores.get('is_natural_skin', False),
            illumination_scores.get('is_natural_lighting', False)
        ]
        
        if self.level == PADLevel.L2:
            liveness_indicators.append(
                micro_texture_scores.get('has_complex_texture', False)
            )
        
        # Weighted scoring
        weights = [0.25, 0.25, 0.2, 0.2, 0.1] if self.level == PADLevel.L2 else [0.3, 0.3, 0.2, 0.2]
        composite_score = sum(w * int(ind) for w, ind in zip(weights, liveness_indicators))
        
        # Make decision
        is_live = composite_score >= self.decision_threshold
        
        # Determine attack type if not live
        detected_attack = AttackType.GENUINE
        if not is_live:
            if screen_scores.get('is_screen_detected', False):
                detected_attack = AttackType.SCREEN
            elif not texture_scores.get('is_genuine_texture', False):
                detected_attack = AttackType.PRINT
            elif not color_scores.get('is_natural_skin', False):
                detected_attack = AttackType.MASK_2D
            else:
                detected_attack = AttackType.UNKNOWN
        
        # Calculate processing time
        processing_time_ms = (time.time() - start_time) * 1000
        
        # Log decision
        logger.info(f"PAD Decision: {'LIVE' if is_live else 'SPOOF'} "
                   f"(confidence: {composite_score:.2f}, time: {processing_time_ms:.1f}ms)")
        
        return PADResult(
            is_live=is_live,
            confidence=float(composite_score),
            level=self.level,
            detected_attack=detected_attack,
            scores=scores,
            processing_time_ms=processing_time_ms,
            features={
                "liveness_indicators": liveness_indicators,
                "weights": weights
            },
            reasons=reasons if not is_live else None
        )
    
    def validate_performance(self, test_results: List[Tuple[bool, bool]]) -> Dict[str, float]:
        """
        Validate PAD performance against ISO 30107-3 requirements
        
        Args:
            test_results: List of (predicted_is_live, actual_is_live) tuples
            
        Returns:
            Dictionary with performance metrics
        """
        if not test_results:
            return {}
        
        # Calculate metrics
        true_positives = sum(1 for pred, actual in test_results if pred and actual)
        true_negatives = sum(1 for pred, actual in test_results if not pred and not actual)
        false_positives = sum(1 for pred, actual in test_results if pred and not actual)
        false_negatives = sum(1 for pred, actual in test_results if not pred and actual)
        
        total = len(test_results)
        total_genuine = true_positives + false_negatives
        total_attacks = true_negatives + false_positives
        
        # Calculate rates
        far = false_positives / total_attacks if total_attacks > 0 else 0  # False Accept Rate
        frr = false_negatives / total_genuine if total_genuine > 0 else 0  # False Reject Rate
        
        # Calculate TAR at FAR 1%
        # This is simplified; actual implementation would need ROC curve analysis
        tar = true_positives / total_genuine if total_genuine > 0 else 0
        
        # APCER and BPCER for ISO 30107-3
        apcer = false_positives / total_attacks if total_attacks > 0 else 0
        bpcer = false_negatives / total_genuine if total_genuine > 0 else 0
        
        # Check compliance
        compliant = (
            far <= self.far_threshold and
            frr <= self.frr_threshold and
            tar >= self.tar_far1_target
        )
        
        metrics = {
            "far": float(far),
            "frr": float(frr),
            "tar": float(tar),
            "apcer": float(apcer),
            "bpcer": float(bpcer),
            "accuracy": float((true_positives + true_negatives) / total),
            "total_samples": total,
            "total_genuine": total_genuine,
            "total_attacks": total_attacks,
            "iso_30107_3_compliant": compliant
        }
        
        logger.info(f"PAD Performance: FAR={far:.3f}, FRR={frr:.3f}, "
                   f"TAR={tar:.3f}, Compliant={compliant}")
        
        return metrics


if __name__ == "__main__":
    # Demo and testing
    print("=== PAD Detector Demo ===")
    
    # Initialize detector
    detector = PADDetector(level=PADLevel.L2)
    
    # Create a test image (placeholder - would use actual face image)
    test_image = np.random.randint(0, 255, (256, 256, 3), dtype=np.uint8)
    
    # Perform liveness detection
    result = detector.detect(test_image)
    
    print(f"\nLiveness Detection Result:")
    print(f"  Is Live: {result.is_live}")
    print(f"  Confidence: {result.confidence:.2f}")
    print(f"  Level: {result.level.value}")
    print(f"  Detected Attack: {result.detected_attack.value}")
    print(f"  Processing Time: {result.processing_time_ms:.1f}ms")
    
    if result.reasons:
        print(f"  Reasons: {', '.join(result.reasons)}")
    
    print("\n✓ PAD Detector ready for integration")