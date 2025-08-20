"""
Forensics & Authenticity Verification Module
Phase 4: ELA/noise/resample/copy-move detection with ROI heatmaps
Implements texture/FFT checks and font/kerning scoring for tamper detection
"""

import cv2
import numpy as np
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass
from enum import Enum
import logging
from pathlib import Path
import json
from scipy import fftpack, signal, ndimage
from skimage import feature, transform, exposure
from PIL import Image
import io
import hashlib

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TamperType(Enum):
    """Types of tampering detected"""
    COPY_MOVE = "copy_move"
    SPLICING = "splicing"
    RESAMPLING = "resampling"
    COMPRESSION_ARTIFACTS = "compression_artifacts"
    DIGITAL_EDIT = "digital_edit"
    FONT_INCONSISTENCY = "font_inconsistency"
    TEXTURE_ANOMALY = "texture_anomaly"
    NOISE_INCONSISTENCY = "noise_inconsistency"
    LIGHTING_INCONSISTENCY = "lighting_inconsistency"

@dataclass
class ForensicFinding:
    """Individual forensic finding"""
    tamper_type: TamperType
    confidence: float
    location: Optional[Tuple[int, int, int, int]]  # x, y, width, height
    severity: str  # "low", "medium", "high", "critical"
    description: str
    evidence: Dict[str, Any]

@dataclass
class SecurityFeature:
    """Document security feature"""
    feature_type: str
    present: bool
    confidence: float
    location: Optional[Tuple[int, int, int, int]]
    validation_passed: bool

@dataclass
class ForensicResult:
    """Complete forensic analysis result"""
    is_authentic: bool
    authenticity_score: float  # 0-1, higher is more authentic
    findings: List[ForensicFinding]
    security_features: List[SecurityFeature]
    ela_heatmap: Optional[np.ndarray]
    noise_heatmap: Optional[np.ndarray]
    texture_heatmap: Optional[np.ndarray]
    metadata: Dict[str, Any]
    processing_time_ms: float

class AuthenticityVerifier:
    """Verifies document authenticity using forensic techniques"""
    
    def __init__(self, config_path: Optional[str] = None):
        """Initialize authenticity verifier"""
        self.config = self._load_config(config_path)
        self.tamper_threshold = self.config.get("tamper_threshold", 0.1)
        self.auc_target = self.config.get("auc_target", 0.90)
        
    def _load_config(self, config_path: Optional[str]) -> Dict:
        """Load forensics configuration"""
        default_config = {
            "tamper_threshold": 0.1,
            "auc_target": 0.90,
            "ela": {
                "quality": 95,
                "scale_factor": 10,
                "threshold": 20
            },
            "noise": {
                "block_size": 8,
                "threshold": 0.05
            },
            "copy_move": {
                "block_size": 16,
                "search_window": 64,
                "threshold": 0.9
            },
            "texture": {
                "gabor_frequencies": [0.1, 0.2, 0.3],
                "gabor_orientations": [0, 45, 90, 135]
            },
            "security_features": {
                "check_hologram": True,
                "check_microprint": True,
                "check_uv": False,  # Requires special hardware
                "check_watermark": True
            }
        }
        
        if config_path and Path(config_path).exists():
            with open(config_path, 'r') as f:
                user_config = json.load(f)
                default_config.update(user_config)
        
        return default_config
    
    def verify_authenticity(self, image: np.ndarray, 
                           document_type: Optional[str] = None) -> ForensicResult:
        """
        Perform complete forensic analysis
        
        Args:
            image: Input document image
            document_type: Optional document type for specific checks
            
        Returns:
            Complete forensic analysis result
        """
        import time
        start_time = time.time()
        
        findings = []
        
        # Perform Error Level Analysis
        logger.info("🔍 Performing Error Level Analysis...")
        ela_result, ela_heatmap = self.error_level_analysis(image)
        if ela_result:
            findings.extend(ela_result)
        
        # Perform noise analysis
        logger.info("📊 Analyzing noise patterns...")
        noise_result, noise_heatmap = self.noise_analysis(image)
        if noise_result:
            findings.extend(noise_result)
        
        # Check for resampling
        logger.info("🔄 Checking for resampling artifacts...")
        resample_result = self.detect_resampling(image)
        if resample_result:
            findings.extend(resample_result)
        
        # Detect copy-move forgery
        logger.info("📋 Detecting copy-move forgery...")
        copy_move_result = self.detect_copy_move(image)
        if copy_move_result:
            findings.extend(copy_move_result)
        
        # Analyze texture consistency
        logger.info("🎨 Analyzing texture consistency...")
        texture_result, texture_heatmap = self.texture_analysis(image)
        if texture_result:
            findings.extend(texture_result)
        
        # Check font consistency
        logger.info("🔤 Checking font consistency...")
        font_result = self.check_font_consistency(image)
        if font_result:
            findings.extend(font_result)
        
        # Verify security features
        logger.info("🛡️ Verifying security features...")
        security_features = self.verify_security_features(image, document_type)
        
        # Calculate overall authenticity score
        authenticity_score = self._calculate_authenticity_score(findings, security_features)
        is_authentic = authenticity_score >= (1 - self.tamper_threshold)
        
        # Calculate processing time
        processing_time_ms = (time.time() - start_time) * 1000
        
        logger.info(f"Forensic analysis complete: Score={authenticity_score:.2f}, Authentic={is_authentic}")
        
        return ForensicResult(
            is_authentic=is_authentic,
            authenticity_score=authenticity_score,
            findings=findings,
            security_features=security_features,
            ela_heatmap=ela_heatmap,
            noise_heatmap=noise_heatmap,
            texture_heatmap=texture_heatmap,
            metadata={
                "total_findings": len(findings),
                "critical_findings": sum(1 for f in findings if f.severity == "critical"),
                "security_features_verified": sum(1 for s in security_features if s.validation_passed)
            },
            processing_time_ms=processing_time_ms
        )
    
    def error_level_analysis(self, image: np.ndarray) -> Tuple[List[ForensicFinding], np.ndarray]:
        """
        Perform Error Level Analysis to detect digital manipulation
        
        Args:
            image: Input image
            
        Returns:
            Tuple of findings and ELA heatmap
        """
        findings = []
        
        # Save image at specific quality
        quality = self.config["ela"]["quality"]
        scale = self.config["ela"]["scale_factor"]
        
        # Convert to PIL Image
        pil_image = Image.fromarray(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))
        
        # Save and reload at specific JPEG quality
        buffer = io.BytesIO()
        pil_image.save(buffer, format='JPEG', quality=quality)
        buffer.seek(0)
        compressed = Image.open(buffer)
        compressed_array = np.array(compressed)
        
        # Calculate difference
        ela_diff = cv2.cvtColor(compressed_array, cv2.COLOR_RGB2BGR).astype(float) - image.astype(float)
        
        # Scale and normalize
        ela_scaled = np.abs(ela_diff) * scale
        ela_normalized = np.clip(ela_scaled, 0, 255).astype(np.uint8)
        
        # Convert to grayscale for analysis
        ela_gray = cv2.cvtColor(ela_normalized, cv2.COLOR_BGR2GRAY)
        
        # Create heatmap
        ela_heatmap = cv2.applyColorMap(ela_gray, cv2.COLORMAP_JET)
        
        # Find suspicious regions
        threshold = self.config["ela"]["threshold"]
        suspicious_mask = ela_gray > threshold
        
        # Find contours of suspicious regions
        contours, _ = cv2.findContours(suspicious_mask.astype(np.uint8), 
                                      cv2.RETR_EXTERNAL, 
                                      cv2.CHAIN_APPROX_SIMPLE)
        
        for contour in contours:
            area = cv2.contourArea(contour)
            if area > 100:  # Filter small regions
                x, y, w, h = cv2.boundingRect(contour)
                
                # Calculate local ELA score
                roi = ela_gray[y:y+h, x:x+w]
                local_score = np.mean(roi) / 255.0
                
                if local_score > 0.3:
                    findings.append(ForensicFinding(
                        tamper_type=TamperType.DIGITAL_EDIT,
                        confidence=min(1.0, local_score * 1.5),
                        location=(x, y, w, h),
                        severity="high" if local_score > 0.6 else "medium",
                        description=f"ELA detected potential manipulation in region",
                        evidence={"ela_score": float(local_score), "area": float(area)}
                    ))
        
        return findings, ela_heatmap
    
    def noise_analysis(self, image: np.ndarray) -> Tuple[List[ForensicFinding], np.ndarray]:
        """
        Analyze noise patterns to detect inconsistencies
        
        Args:
            image: Input image
            
        Returns:
            Tuple of findings and noise heatmap
        """
        findings = []
        
        # Convert to grayscale
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image
        
        # Calculate local noise using standard deviation
        block_size = self.config["noise"]["block_size"]
        h, w = gray.shape
        noise_map = np.zeros_like(gray, dtype=np.float32)
        
        for i in range(0, h - block_size, block_size):
            for j in range(0, w - block_size, block_size):
                block = gray[i:i+block_size, j:j+block_size]
                noise_map[i:i+block_size, j:j+block_size] = np.std(block)
        
        # Normalize noise map
        noise_normalized = cv2.normalize(noise_map, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
        
        # Create heatmap
        noise_heatmap = cv2.applyColorMap(noise_normalized, cv2.COLORMAP_HOT)
        
        # Detect anomalies
        mean_noise = np.mean(noise_map)
        std_noise = np.std(noise_map)
        threshold = mean_noise + 2 * std_noise
        
        anomaly_mask = noise_map > threshold
        
        # Find connected components
        labeled, num_features = ndimage.label(anomaly_mask)
        
        for i in range(1, num_features + 1):
            component = (labeled == i)
            if np.sum(component) > 50:  # Minimum size
                indices = np.where(component)
                y_min, y_max = indices[0].min(), indices[0].max()
                x_min, x_max = indices[1].min(), indices[1].max()
                
                local_noise = np.mean(noise_map[component])
                deviation = (local_noise - mean_noise) / std_noise
                
                if deviation > 2:
                    findings.append(ForensicFinding(
                        tamper_type=TamperType.NOISE_INCONSISTENCY,
                        confidence=min(1.0, deviation / 5),
                        location=(x_min, y_min, x_max - x_min, y_max - y_min),
                        severity="medium" if deviation < 3 else "high",
                        description="Noise pattern inconsistency detected",
                        evidence={"deviation": float(deviation), "local_noise": float(local_noise)}
                    ))
        
        return findings, noise_heatmap
    
    def detect_resampling(self, image: np.ndarray) -> List[ForensicFinding]:
        """
        Detect resampling artifacts using spectral analysis
        
        Args:
            image: Input image
            
        Returns:
            List of findings
        """
        findings = []
        
        # Convert to grayscale
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image
        
        # Apply FFT
        f_transform = fftpack.fft2(gray)
        f_shift = fftpack.fftshift(f_transform)
        magnitude_spectrum = np.abs(f_shift)
        
        # Look for periodic patterns in frequency domain
        # Resampling often creates periodic artifacts
        rows, cols = gray.shape
        crow, ccol = rows // 2, cols // 2
        
        # Analyze radial average
        Y, X = np.ogrid[:rows, :cols]
        r = np.sqrt((X - ccol)**2 + (Y - crow)**2)
        r = r.astype(int)
        
        # Calculate radial profile
        radial_prof = ndimage.mean(magnitude_spectrum, labels=r, index=np.arange(0, r.max()))
        
        # Detect peaks in radial profile (indicating resampling)
        peaks, properties = signal.find_peaks(radial_prof[10:], prominence=np.std(radial_prof))
        
        if len(peaks) > 2:  # Multiple periodic peaks suggest resampling
            confidence = min(1.0, len(peaks) / 10)
            findings.append(ForensicFinding(
                tamper_type=TamperType.RESAMPLING,
                confidence=confidence,
                location=None,  # Global finding
                severity="medium" if confidence < 0.7 else "high",
                description="Resampling artifacts detected in frequency domain",
                evidence={"num_peaks": len(peaks), "peak_locations": peaks.tolist()[:5]}
            ))
        
        return findings
    
    def detect_copy_move(self, image: np.ndarray) -> List[ForensicFinding]:
        """
        Detect copy-move forgery using block matching
        
        Args:
            image: Input image
            
        Returns:
            List of findings
        """
        findings = []
        
        # Convert to grayscale
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image
        
        # Parameters
        block_size = self.config["copy_move"]["block_size"]
        search_window = self.config["copy_move"]["search_window"]
        threshold = self.config["copy_move"]["threshold"]
        
        h, w = gray.shape
        
        # Divide image into blocks
        blocks = []
        positions = []
        
        for i in range(0, h - block_size, block_size // 2):
            for j in range(0, w - block_size, block_size // 2):
                block = gray[i:i+block_size, j:j+block_size]
                blocks.append(block.flatten())
                positions.append((i, j))
        
        blocks = np.array(blocks)
        
        # Find similar blocks using correlation
        matches = []
        
        for i in range(len(blocks)):
            for j in range(i + 1, min(i + search_window, len(blocks))):
                # Calculate correlation
                correlation = np.corrcoef(blocks[i], blocks[j])[0, 1]
                
                if correlation > threshold:
                    pos1 = positions[i]
                    pos2 = positions[j]
                    
                    # Check if blocks are not adjacent
                    dist = np.sqrt((pos1[0] - pos2[0])**2 + (pos1[1] - pos2[1])**2)
                    
                    if dist > block_size * 2:
                        matches.append({
                            "pos1": pos1,
                            "pos2": pos2,
                            "correlation": correlation,
                            "distance": dist
                        })
        
        # Group matches into regions
        if matches:
            # Simplified: Report the strongest match
            best_match = max(matches, key=lambda x: x["correlation"])
            
            findings.append(ForensicFinding(
                tamper_type=TamperType.COPY_MOVE,
                confidence=best_match["correlation"],
                location=(best_match["pos1"][1], best_match["pos1"][0], block_size, block_size),
                severity="critical" if best_match["correlation"] > 0.95 else "high",
                description="Copy-move forgery detected",
                evidence={
                    "correlation": float(best_match["correlation"]),
                    "distance": float(best_match["distance"]),
                    "source": best_match["pos1"],
                    "target": best_match["pos2"]
                }
            ))
        
        return findings
    
    def texture_analysis(self, image: np.ndarray) -> Tuple[List[ForensicFinding], np.ndarray]:
        """
        Analyze texture consistency using Gabor filters
        
        Args:
            image: Input image
            
        Returns:
            Tuple of findings and texture heatmap
        """
        findings = []
        
        # Convert to grayscale
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image
        
        # Apply Gabor filters
        frequencies = self.config["texture"]["gabor_frequencies"]
        orientations = [o * np.pi / 180 for o in self.config["texture"]["gabor_orientations"]]
        
        responses = []
        
        for freq in frequencies:
            for theta in orientations:
                # Create Gabor kernel
                kernel = cv2.getGaborKernel(
                    (31, 31), 4.0, theta, 10.0, freq, 0
                )
                
                # Apply filter
                filtered = cv2.filter2D(gray, cv2.CV_32F, kernel)
                responses.append(filtered)
        
        # Combine responses
        texture_map = np.mean(responses, axis=0)
        
        # Calculate local texture variance
        kernel_size = 15
        kernel = np.ones((kernel_size, kernel_size)) / (kernel_size ** 2)
        local_mean = cv2.filter2D(texture_map, cv2.CV_32F, kernel)
        local_var = cv2.filter2D(texture_map ** 2, cv2.CV_32F, kernel) - local_mean ** 2
        
        # Normalize variance map
        texture_normalized = cv2.normalize(local_var, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
        
        # Create heatmap
        texture_heatmap = cv2.applyColorMap(texture_normalized, cv2.COLORMAP_VIRIDIS)
        
        # Detect anomalies
        mean_texture = np.mean(local_var)
        std_texture = np.std(local_var)
        
        # Find regions with unusual texture
        anomaly_mask = np.abs(local_var - mean_texture) > 2 * std_texture
        
        contours, _ = cv2.findContours(anomaly_mask.astype(np.uint8), 
                                      cv2.RETR_EXTERNAL, 
                                      cv2.CHAIN_APPROX_SIMPLE)
        
        for contour in contours:
            area = cv2.contourArea(contour)
            if area > 500:
                x, y, w, h = cv2.boundingRect(contour)
                
                roi_texture = local_var[y:y+h, x:x+w]
                deviation = np.abs(np.mean(roi_texture) - mean_texture) / std_texture
                
                if deviation > 2:
                    findings.append(ForensicFinding(
                        tamper_type=TamperType.TEXTURE_ANOMALY,
                        confidence=min(1.0, deviation / 4),
                        location=(x, y, w, h),
                        severity="medium",
                        description="Texture inconsistency detected",
                        evidence={"deviation": float(deviation), "area": float(area)}
                    ))
        
        return findings, texture_heatmap
    
    def check_font_consistency(self, image: np.ndarray) -> List[ForensicFinding]:
        """
        Check for font and kerning inconsistencies
        
        Args:
            image: Input image
            
        Returns:
            List of findings
        """
        findings = []
        
        # This is a simplified implementation
        # In production, use OCR with font detection
        
        # Convert to grayscale
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image
        
        # Detect text regions
        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        
        # Find text contours
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (20, 3))
        dilated = cv2.dilate(binary, kernel, iterations=1)
        contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        # Analyze character spacing in text regions
        text_regions = []
        
        for contour in contours:
            area = cv2.contourArea(contour)
            if 500 < area < 50000:  # Text-sized regions
                x, y, w, h = cv2.boundingRect(contour)
                if w > h * 2:  # Horizontal text
                    text_regions.append((x, y, w, h))
        
        if len(text_regions) > 1:
            # Compare text characteristics
            heights = [h for _, _, _, h in text_regions]
            mean_height = np.mean(heights)
            std_height = np.std(heights)
            
            # Check for inconsistent text sizes
            for i, (x, y, w, h) in enumerate(text_regions):
                deviation = abs(h - mean_height) / (std_height + 1e-6)
                
                if deviation > 2 and std_height > 5:
                    findings.append(ForensicFinding(
                        tamper_type=TamperType.FONT_INCONSISTENCY,
                        confidence=min(1.0, deviation / 4),
                        location=(x, y, w, h),
                        severity="low" if deviation < 3 else "medium",
                        description="Font size inconsistency detected",
                        evidence={
                            "height": int(h),
                            "mean_height": float(mean_height),
                            "deviation": float(deviation)
                        }
                    ))
        
        return findings
    
    def verify_security_features(self, image: np.ndarray, 
                                document_type: Optional[str]) -> List[SecurityFeature]:
        """
        Verify document security features
        
        Args:
            image: Input image
            document_type: Type of document for specific features
            
        Returns:
            List of security features verification results
        """
        features = []
        
        # Check for hologram patterns (simplified)
        if self.config["security_features"]["check_hologram"]:
            hologram_present = self._check_hologram(image)
            features.append(SecurityFeature(
                feature_type="hologram",
                present=hologram_present,
                confidence=0.8 if hologram_present else 0.2,
                location=None,
                validation_passed=hologram_present
            ))
        
        # Check for microprint patterns
        if self.config["security_features"]["check_microprint"]:
            microprint_result = self._check_microprint(image)
            features.append(SecurityFeature(
                feature_type="microprint",
                present=microprint_result["present"],
                confidence=microprint_result["confidence"],
                location=microprint_result.get("location"),
                validation_passed=microprint_result["present"]
            ))
        
        # Check for watermark
        if self.config["security_features"]["check_watermark"]:
            watermark_result = self._check_watermark(image)
            features.append(SecurityFeature(
                feature_type="watermark",
                present=watermark_result["present"],
                confidence=watermark_result["confidence"],
                location=None,
                validation_passed=watermark_result["present"]
            ))
        
        return features
    
    def _check_hologram(self, image: np.ndarray) -> bool:
        """Check for holographic patterns"""
        # Convert to HSV for color analysis
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        
        # Holograms often have specific color properties
        # Look for iridescent/rainbow patterns
        h_channel = hsv[:, :, 0]
        
        # Calculate local hue variance
        kernel_size = 15
        kernel = np.ones((kernel_size, kernel_size)) / (kernel_size ** 2)
        local_mean = cv2.filter2D(h_channel.astype(np.float32), cv2.CV_32F, kernel)
        local_var = cv2.filter2D(h_channel.astype(np.float32) ** 2, cv2.CV_32F, kernel) - local_mean ** 2
        
        # High hue variance might indicate hologram
        max_var = np.max(local_var)
        
        return max_var > 500  # Threshold for hologram detection
    
    def _check_microprint(self, image: np.ndarray) -> Dict[str, Any]:
        """Check for microprint patterns"""
        # Convert to grayscale
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image
        
        # Apply high-pass filter to enhance fine details
        kernel = np.array([[-1, -1, -1],
                          [-1,  8, -1],
                          [-1, -1, -1]])
        enhanced = cv2.filter2D(gray, cv2.CV_32F, kernel)
        
        # Look for repetitive fine patterns
        # Apply FFT to detect periodic structures
        f_transform = fftpack.fft2(enhanced)
        f_shift = fftpack.fftshift(f_transform)
        magnitude = np.abs(f_shift)
        
        # Check for high-frequency components
        rows, cols = enhanced.shape
        crow, ccol = rows // 2, cols // 2
        
        # Analyze high-frequency region
        high_freq_region = magnitude[crow-50:crow+50, ccol-50:ccol+50]
        high_freq_energy = np.sum(high_freq_region)
        
        # Normalize by total energy
        total_energy = np.sum(magnitude)
        ratio = high_freq_energy / (total_energy + 1e-6)
        
        return {
            "present": ratio > 0.1,
            "confidence": min(1.0, ratio * 10),
            "location": None
        }
    
    def _check_watermark(self, image: np.ndarray) -> Dict[str, Any]:
        """Check for watermark presence"""
        # Convert to grayscale
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image
        
        # Apply adaptive histogram equalization
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(gray)
        
        # Look for semi-transparent patterns
        # Calculate local standard deviation
        kernel_size = 31
        kernel = np.ones((kernel_size, kernel_size)) / (kernel_size ** 2)
        local_mean = cv2.filter2D(enhanced.astype(np.float32), cv2.CV_32F, kernel)
        local_std = np.sqrt(cv2.filter2D(enhanced.astype(np.float32) ** 2, cv2.CV_32F, kernel) - local_mean ** 2)
        
        # Watermarks often have consistent but subtle patterns
        std_variance = np.var(local_std)
        
        # Check if there's a consistent pattern
        present = 10 < std_variance < 100
        
        return {
            "present": present,
            "confidence": 0.7 if present else 0.3
        }
    
    def _calculate_authenticity_score(self, findings: List[ForensicFinding], 
                                     security_features: List[SecurityFeature]) -> float:
        """Calculate overall authenticity score"""
        score = 1.0
        
        # Deduct points for tamper findings
        for finding in findings:
            if finding.severity == "critical":
                score -= 0.3 * finding.confidence
            elif finding.severity == "high":
                score -= 0.2 * finding.confidence
            elif finding.severity == "medium":
                score -= 0.1 * finding.confidence
            else:
                score -= 0.05 * finding.confidence
        
        # Add points for verified security features
        if security_features:
            verified_features = sum(1 for f in security_features if f.validation_passed)
            feature_bonus = (verified_features / len(security_features)) * 0.2
            score = min(1.0, score + feature_bonus)
        
        return max(0.0, score)

# Export main components
__all__ = [
    "AuthenticityVerifier",
    "ForensicResult",
    "ForensicFinding",
    "SecurityFeature",
    "TamperType"
]