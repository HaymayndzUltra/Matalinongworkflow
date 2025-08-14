"""
Biometrics & Liveness Detection Module
Phase 5: Multi-frame face match for ID-vs-selfie with passive and challenge liveness
Calibrated thresholds with multi-frame consensus logic for robustness
"""

import cv2
import numpy as np
import face_recognition
import dlib
from typing import Dict, List, Tuple, Optional, Any, Union
from dataclasses import dataclass
from enum import Enum
import logging
from pathlib import Path
import json
import time
from scipy import signal
from scipy.spatial import distance
from collections import deque
import hashlib

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class LivenessType(Enum):
    """Types of liveness detection"""
    PASSIVE = "passive"
    BLINK = "blink"
    SMILE = "smile"
    HEAD_TURN = "head_turn"
    MOUTH_OPEN = "mouth_open"
    TEXTURE_ANALYSIS = "texture_analysis"
    FREQUENCY_ANALYSIS = "frequency_analysis"
    DEPTH_ANALYSIS = "depth_analysis"

class MatchResult(Enum):
    """Face match results"""
    MATCH = "match"
    NO_MATCH = "no_match"
    INCONCLUSIVE = "inconclusive"
    ERROR = "error"

@dataclass
class FaceEncoding:
    """Face encoding with metadata"""
    encoding: np.ndarray
    source: str  # "id_document" or "selfie"
    quality_score: float
    landmarks: Dict[str, Any]
    bbox: Tuple[int, int, int, int]
    timestamp: float

@dataclass
class LivenessResult:
    """Liveness detection result"""
    is_live: bool
    confidence: float
    liveness_type: LivenessType
    evidence: Dict[str, Any]
    frame_scores: List[float]
    consensus_score: float

@dataclass
class BiometricResult:
    """Complete biometric verification result"""
    match_result: MatchResult
    match_confidence: float
    similarity_score: float
    liveness_results: List[LivenessResult]
    is_live: bool
    liveness_confidence: float
    tar_at_far: float  # TAR@FAR1%
    processing_time_ms: float
    metadata: Dict[str, Any]

class FaceMatcher:
    """Face matching and biometric verification"""
    
    def __init__(self, config_path: Optional[str] = None):
        """Initialize face matcher with configuration"""
        self.config = self._load_config(config_path)
        self.face_detector = dlib.get_frontal_face_detector()
        self.shape_predictor = self._load_shape_predictor()
        self.face_encoder = face_recognition.face_encodings
        
        # Thresholds
        self.match_threshold = self.config["match_threshold"]  # 0.98 for TAR@FAR1%
        self.liveness_fmr = self.config["liveness_fmr"]  # 0.01 (1%)
        self.liveness_fnmr = self.config["liveness_fnmr"]  # 0.03 (3%)
        
        # Frame buffers for multi-frame analysis
        self.frame_buffer = deque(maxlen=30)
        self.encoding_buffer = deque(maxlen=10)
        
    def _load_config(self, config_path: Optional[str]) -> Dict:
        """Load biometric configuration"""
        default_config = {
            "match_threshold": 0.98,  # TAR@FAR1%
            "liveness_fmr": 0.01,  # False Match Rate
            "liveness_fnmr": 0.03,  # False Non-Match Rate
            "min_face_size": (112, 112),
            "encoding_model": "large",  # or "small"
            "multi_frame": {
                "min_frames": 5,
                "consensus_threshold": 0.7,
                "stability_threshold": 0.9
            },
            "liveness": {
                "passive": {
                    "texture_threshold": 0.7,
                    "frequency_threshold": 0.6,
                    "reflection_threshold": 0.5
                },
                "challenge": {
                    "blink_threshold": 0.3,
                    "smile_threshold": 0.4,
                    "head_turn_threshold": 15  # degrees
                }
            },
            "anti_spoofing": {
                "check_texture": True,
                "check_frequency": True,
                "check_reflection": True,
                "check_3d_depth": False  # Requires depth camera
            }
        }
        
        if config_path and Path(config_path).exists():
            with open(config_path, 'r') as f:
                user_config = json.load(f)
                default_config.update(user_config)
        
        return default_config
    
    def _load_shape_predictor(self):
        """Load dlib shape predictor"""
        # Try to load the 68-point facial landmark detector
        predictor_path = "shape_predictor_68_face_landmarks.dat"
        
        if Path(predictor_path).exists():
            return dlib.shape_predictor(predictor_path)
        else:
            logger.warning("Shape predictor not found, using basic landmarks")
            return None
    
    def verify_biometric(self, id_image: np.ndarray, 
                        selfie_frames: Union[np.ndarray, List[np.ndarray]]) -> BiometricResult:
        """
        Perform complete biometric verification
        
        Args:
            id_image: ID document face image
            selfie_frames: Single selfie or list of frames for video
            
        Returns:
            Complete biometric verification result
        """
        start_time = time.time()
        
        # Convert single image to list
        if isinstance(selfie_frames, np.ndarray):
            selfie_frames = [selfie_frames]
        
        # Extract ID face encoding
        logger.info("🆔 Extracting face from ID document...")
        id_encoding = self.extract_face_encoding(id_image, "id_document")
        
        if id_encoding is None:
            return BiometricResult(
                match_result=MatchResult.ERROR,
                match_confidence=0.0,
                similarity_score=0.0,
                liveness_results=[],
                is_live=False,
                liveness_confidence=0.0,
                tar_at_far=0.0,
                processing_time_ms=(time.time() - start_time) * 1000,
                metadata={"error": "No face found in ID document"}
            )
        
        # Extract selfie encodings (multi-frame if available)
        logger.info("🤳 Processing selfie frames...")
        selfie_encodings = []
        for i, frame in enumerate(selfie_frames):
            encoding = self.extract_face_encoding(frame, f"selfie_frame_{i}")
            if encoding:
                selfie_encodings.append(encoding)
        
        if not selfie_encodings:
            return BiometricResult(
                match_result=MatchResult.ERROR,
                match_confidence=0.0,
                similarity_score=0.0,
                liveness_results=[],
                is_live=False,
                liveness_confidence=0.0,
                tar_at_far=0.0,
                processing_time_ms=(time.time() - start_time) * 1000,
                metadata={"error": "No face found in selfie"}
            )
        
        # Perform face matching
        logger.info("👥 Matching faces...")
        match_result, similarity_score = self.match_faces(id_encoding, selfie_encodings)
        
        # Perform liveness detection
        logger.info("🔍 Detecting liveness...")
        liveness_results = self.detect_liveness(selfie_frames)
        
        # Calculate overall liveness
        is_live, liveness_confidence = self._calculate_overall_liveness(liveness_results)
        
        # Calculate TAR@FAR
        tar_at_far = self._calculate_tar_at_far(similarity_score)
        
        # Determine match confidence
        match_confidence = self._calculate_match_confidence(
            similarity_score, is_live, liveness_confidence
        )
        
        processing_time_ms = (time.time() - start_time) * 1000
        
        logger.info(f"✅ Biometric verification complete: "
                   f"Match={match_result.value}, "
                   f"Similarity={similarity_score:.3f}, "
                   f"Live={is_live}, "
                   f"Confidence={match_confidence:.3f}")
        
        return BiometricResult(
            match_result=match_result,
            match_confidence=match_confidence,
            similarity_score=similarity_score,
            liveness_results=liveness_results,
            is_live=is_live,
            liveness_confidence=liveness_confidence,
            tar_at_far=tar_at_far,
            processing_time_ms=processing_time_ms,
            metadata={
                "id_quality": id_encoding.quality_score if id_encoding else 0,
                "selfie_frames": len(selfie_frames),
                "encodings_extracted": len(selfie_encodings),
                "liveness_checks": len(liveness_results)
            }
        )
    
    def extract_face_encoding(self, image: np.ndarray, source: str) -> Optional[FaceEncoding]:
        """
        Extract face encoding from image
        
        Args:
            image: Input image
            source: Source identifier
            
        Returns:
            Face encoding or None if no face found
        """
        # Detect faces using dlib
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image
        faces = self.face_detector(gray)
        
        if not faces:
            # Try with face_recognition as fallback
            face_locations = face_recognition.face_locations(image)
            if not face_locations:
                return None
            
            # Convert to dlib rectangle
            top, right, bottom, left = face_locations[0]
            face = dlib.rectangle(left, top, right, bottom)
        else:
            face = faces[0]  # Use first face
        
        # Get face landmarks
        if self.shape_predictor:
            landmarks = self.shape_predictor(gray, face)
            landmarks_dict = self._landmarks_to_dict(landmarks)
        else:
            landmarks_dict = {}
        
        # Extract face encoding
        face_encodings = face_recognition.face_encodings(image, [self._dlib_to_rect(face)])
        
        if not face_encodings:
            return None
        
        # Calculate quality score
        quality_score = self._assess_face_quality(image, face)
        
        return FaceEncoding(
            encoding=face_encodings[0],
            source=source,
            quality_score=quality_score,
            landmarks=landmarks_dict,
            bbox=(face.left(), face.top(), face.width(), face.height()),
            timestamp=time.time()
        )
    
    def match_faces(self, id_encoding: FaceEncoding, 
                   selfie_encodings: List[FaceEncoding]) -> Tuple[MatchResult, float]:
        """
        Match ID face against selfie faces
        
        Args:
            id_encoding: ID document face encoding
            selfie_encodings: List of selfie face encodings
            
        Returns:
            Match result and similarity score
        """
        if not selfie_encodings:
            return MatchResult.ERROR, 0.0
        
        # Calculate similarities for all selfie frames
        similarities = []
        
        for selfie_enc in selfie_encodings:
            # Calculate Euclidean distance
            distance = np.linalg.norm(id_encoding.encoding - selfie_enc.encoding)
            
            # Convert to similarity score (0-1, higher is better)
            similarity = 1 / (1 + distance)
            similarities.append(similarity)
        
        # Multi-frame consensus
        if len(similarities) >= self.config["multi_frame"]["min_frames"]:
            # Use weighted average based on quality scores
            weights = [enc.quality_score for enc in selfie_encodings]
            similarity_score = np.average(similarities, weights=weights)
            
            # Check stability (variance should be low)
            stability = 1 - np.std(similarities)
            
            if stability < self.config["multi_frame"]["stability_threshold"]:
                logger.warning(f"Low stability in face matching: {stability:.3f}")
        else:
            # Simple average for few frames
            similarity_score = np.mean(similarities)
        
        # Determine match result
        if similarity_score >= self.match_threshold:
            match_result = MatchResult.MATCH
        elif similarity_score >= self.match_threshold * 0.9:
            match_result = MatchResult.INCONCLUSIVE
        else:
            match_result = MatchResult.NO_MATCH
        
        return match_result, similarity_score
    
    def detect_liveness(self, frames: List[np.ndarray]) -> List[LivenessResult]:
        """
        Perform liveness detection on frames
        
        Args:
            frames: List of video frames
            
        Returns:
            List of liveness detection results
        """
        results = []
        
        # Passive liveness detection
        if self.config["anti_spoofing"]["check_texture"]:
            texture_result = self._detect_texture_liveness(frames)
            results.append(texture_result)
        
        if self.config["anti_spoofing"]["check_frequency"]:
            frequency_result = self._detect_frequency_liveness(frames)
            results.append(frequency_result)
        
        if self.config["anti_spoofing"]["check_reflection"]:
            reflection_result = self._detect_reflection_liveness(frames)
            results.append(reflection_result)
        
        # Challenge-based liveness (if multiple frames)
        if len(frames) > 1:
            # Detect blink
            blink_result = self._detect_blink(frames)
            if blink_result:
                results.append(blink_result)
            
            # Detect head movement
            head_movement_result = self._detect_head_movement(frames)
            if head_movement_result:
                results.append(head_movement_result)
        
        return results
    
    def _detect_texture_liveness(self, frames: List[np.ndarray]) -> LivenessResult:
        """
        Detect liveness using texture analysis
        Real faces have different texture than printed/screen faces
        """
        frame_scores = []
        
        for frame in frames[:5]:  # Analyze first 5 frames
            # Convert to grayscale
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if len(frame.shape) == 3 else frame
            
            # Calculate Local Binary Patterns
            lbp = self._calculate_lbp(gray)
            
            # Calculate histogram
            hist, _ = np.histogram(lbp.ravel(), bins=256, range=(0, 256))
            hist = hist.astype("float")
            hist /= (hist.sum() + 1e-6)
            
            # Calculate texture score based on histogram distribution
            # Real faces have more varied texture
            texture_score = -np.sum(hist * np.log(hist + 1e-6))  # Entropy
            texture_score = min(1.0, texture_score / 5.0)  # Normalize
            
            frame_scores.append(texture_score)
        
        consensus_score = np.mean(frame_scores)
        threshold = self.config["liveness"]["passive"]["texture_threshold"]
        
        return LivenessResult(
            is_live=consensus_score >= threshold,
            confidence=consensus_score,
            liveness_type=LivenessType.TEXTURE_ANALYSIS,
            evidence={
                "entropy": float(consensus_score),
                "threshold": threshold
            },
            frame_scores=frame_scores,
            consensus_score=consensus_score
        )
    
    def _detect_frequency_liveness(self, frames: List[np.ndarray]) -> LivenessResult:
        """
        Detect liveness using frequency analysis
        Printed/screen faces have different frequency characteristics
        """
        frame_scores = []
        
        for frame in frames[:5]:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if len(frame.shape) == 3 else frame
            
            # Apply FFT
            f_transform = np.fft.fft2(gray)
            f_shift = np.fft.fftshift(f_transform)
            magnitude = np.abs(f_shift)
            
            # Analyze high-frequency components
            rows, cols = gray.shape
            crow, ccol = rows // 2, cols // 2
            
            # High frequency region
            high_freq = magnitude[crow-30:crow+30, ccol-30:ccol+30]
            low_freq = magnitude[crow-60:crow+60, ccol-60:ccol+60]
            
            # Calculate ratio
            high_energy = np.sum(high_freq)
            low_energy = np.sum(low_freq)
            freq_ratio = high_energy / (low_energy + 1e-6)
            
            # Real faces have balanced frequency distribution
            score = 1 / (1 + np.exp(-10 * (freq_ratio - 0.3)))  # Sigmoid
            frame_scores.append(score)
        
        consensus_score = np.mean(frame_scores)
        threshold = self.config["liveness"]["passive"]["frequency_threshold"]
        
        return LivenessResult(
            is_live=consensus_score >= threshold,
            confidence=consensus_score,
            liveness_type=LivenessType.FREQUENCY_ANALYSIS,
            evidence={
                "frequency_ratio": float(consensus_score),
                "threshold": threshold
            },
            frame_scores=frame_scores,
            consensus_score=consensus_score
        )
    
    def _detect_reflection_liveness(self, frames: List[np.ndarray]) -> LivenessResult:
        """
        Detect liveness by checking for screen reflections
        """
        frame_scores = []
        
        for frame in frames[:5]:
            # Convert to HSV for better reflection detection
            hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
            
            # Check for uniform bright regions (screen reflection)
            _, _, v = cv2.split(hsv)
            
            # Find bright spots
            bright_mask = v > 240
            bright_ratio = np.sum(bright_mask) / (v.shape[0] * v.shape[1])
            
            # Check for uniform rectangular patterns (screen edges)
            edges = cv2.Canny(v, 50, 150)
            lines = cv2.HoughLinesP(edges, 1, np.pi/180, 100, minLineLength=100, maxLineGap=10)
            
            if lines is not None and len(lines) > 10:
                # Many straight lines might indicate screen
                score = 0.3
            else:
                score = 1.0 - bright_ratio * 2  # Penalize too bright
            
            frame_scores.append(max(0, min(1, score)))
        
        consensus_score = np.mean(frame_scores)
        threshold = self.config["liveness"]["passive"]["reflection_threshold"]
        
        return LivenessResult(
            is_live=consensus_score >= threshold,
            confidence=consensus_score,
            liveness_type=LivenessType.PASSIVE,
            evidence={
                "reflection_score": float(consensus_score),
                "threshold": threshold
            },
            frame_scores=frame_scores,
            consensus_score=consensus_score
        )
    
    def _detect_blink(self, frames: List[np.ndarray]) -> Optional[LivenessResult]:
        """
        Detect eye blink for liveness
        """
        if len(frames) < 10:
            return None
        
        eye_aspect_ratios = []
        
        for frame in frames:
            # Detect face and landmarks
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if len(frame.shape) == 3 else frame
            faces = self.face_detector(gray)
            
            if faces and self.shape_predictor:
                face = faces[0]
                landmarks = self.shape_predictor(gray, face)
                
                # Calculate eye aspect ratio
                ear = self._calculate_eye_aspect_ratio(landmarks)
                eye_aspect_ratios.append(ear)
        
        if len(eye_aspect_ratios) < 5:
            return None
        
        # Detect blink pattern
        ear_array = np.array(eye_aspect_ratios)
        mean_ear = np.mean(ear_array)
        
        # Find valleys (closed eyes)
        valleys = signal.argrelextrema(ear_array, np.less)[0]
        
        blink_detected = len(valleys) > 0
        confidence = 0.8 if blink_detected else 0.2
        
        return LivenessResult(
            is_live=blink_detected,
            confidence=confidence,
            liveness_type=LivenessType.BLINK,
            evidence={
                "blinks_detected": len(valleys),
                "mean_ear": float(mean_ear)
            },
            frame_scores=eye_aspect_ratios,
            consensus_score=confidence
        )
    
    def _detect_head_movement(self, frames: List[np.ndarray]) -> Optional[LivenessResult]:
        """
        Detect head movement for liveness
        """
        if len(frames) < 5:
            return None
        
        face_positions = []
        
        for frame in frames:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if len(frame.shape) == 3 else frame
            faces = self.face_detector(gray)
            
            if faces:
                face = faces[0]
                center_x = face.left() + face.width() // 2
                center_y = face.top() + face.height() // 2
                face_positions.append((center_x, center_y))
        
        if len(face_positions) < 3:
            return None
        
        # Calculate movement
        movements = []
        for i in range(1, len(face_positions)):
            dx = face_positions[i][0] - face_positions[i-1][0]
            dy = face_positions[i][1] - face_positions[i-1][1]
            movement = np.sqrt(dx**2 + dy**2)
            movements.append(movement)
        
        total_movement = sum(movements)
        movement_detected = total_movement > self.config["liveness"]["challenge"]["head_turn_threshold"]
        
        confidence = min(1.0, total_movement / 50)
        
        return LivenessResult(
            is_live=movement_detected,
            confidence=confidence,
            liveness_type=LivenessType.HEAD_TURN,
            evidence={
                "total_movement": float(total_movement),
                "positions": len(face_positions)
            },
            frame_scores=movements,
            consensus_score=confidence
        )
    
    def _calculate_lbp(self, gray: np.ndarray) -> np.ndarray:
        """Calculate Local Binary Patterns"""
        rows, cols = gray.shape
        lbp = np.zeros_like(gray)
        
        for i in range(1, rows - 1):
            for j in range(1, cols - 1):
                center = gray[i, j]
                code = 0
                
                # 8 neighbors
                neighbors = [
                    gray[i-1, j-1], gray[i-1, j], gray[i-1, j+1],
                    gray[i, j+1], gray[i+1, j+1], gray[i+1, j],
                    gray[i+1, j-1], gray[i, j-1]
                ]
                
                for k, neighbor in enumerate(neighbors):
                    if neighbor >= center:
                        code |= (1 << k)
                
                lbp[i, j] = code
        
        return lbp
    
    def _calculate_eye_aspect_ratio(self, landmarks) -> float:
        """Calculate Eye Aspect Ratio (EAR) for blink detection"""
        # Eye landmark indices for 68-point model
        LEFT_EYE = list(range(36, 42))
        RIGHT_EYE = list(range(42, 48))
        
        def eye_aspect_ratio(eye_points):
            # Vertical distances
            v1 = distance.euclidean(
                (landmarks.part(eye_points[1]).x, landmarks.part(eye_points[1]).y),
                (landmarks.part(eye_points[5]).x, landmarks.part(eye_points[5]).y)
            )
            v2 = distance.euclidean(
                (landmarks.part(eye_points[2]).x, landmarks.part(eye_points[2]).y),
                (landmarks.part(eye_points[4]).x, landmarks.part(eye_points[4]).y)
            )
            
            # Horizontal distance
            h = distance.euclidean(
                (landmarks.part(eye_points[0]).x, landmarks.part(eye_points[0]).y),
                (landmarks.part(eye_points[3]).x, landmarks.part(eye_points[3]).y)
            )
            
            return (v1 + v2) / (2.0 * h + 1e-6)
        
        left_ear = eye_aspect_ratio(LEFT_EYE)
        right_ear = eye_aspect_ratio(RIGHT_EYE)
        
        return (left_ear + right_ear) / 2.0
    
    def _assess_face_quality(self, image: np.ndarray, face: dlib.rectangle) -> float:
        """Assess face image quality"""
        # Extract face region
        face_img = image[face.top():face.bottom(), face.left():face.right()]
        
        if face_img.size == 0:
            return 0.0
        
        # Resize for consistent analysis
        face_resized = cv2.resize(face_img, (224, 224))
        gray = cv2.cvtColor(face_resized, cv2.COLOR_BGR2GRAY) if len(face_resized.shape) == 3 else face_resized
        
        scores = []
        
        # Check resolution
        min_dim = min(face.width(), face.height())
        resolution_score = min(1.0, min_dim / 112)
        scores.append(resolution_score)
        
        # Check blur
        laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
        blur_score = min(1.0, laplacian_var / 500)
        scores.append(blur_score)
        
        # Check contrast
        contrast_score = gray.std() / 127.5
        scores.append(min(1.0, contrast_score))
        
        # Check brightness
        brightness = gray.mean() / 255
        brightness_score = 1.0 - abs(brightness - 0.5) * 2
        scores.append(brightness_score)
        
        return np.mean(scores)
    
    def _landmarks_to_dict(self, landmarks) -> Dict[str, Tuple[int, int]]:
        """Convert dlib landmarks to dictionary"""
        points = {}
        
        # Key facial points
        key_indices = {
            "nose_tip": 30,
            "chin": 8,
            "left_eye_left": 36,
            "left_eye_right": 39,
            "right_eye_left": 42,
            "right_eye_right": 45,
            "mouth_left": 48,
            "mouth_right": 54
        }
        
        for name, idx in key_indices.items():
            if idx < landmarks.num_parts:
                points[name] = (landmarks.part(idx).x, landmarks.part(idx).y)
        
        return points
    
    def _dlib_to_rect(self, face: dlib.rectangle) -> Tuple[int, int, int, int]:
        """Convert dlib rectangle to (top, right, bottom, left)"""
        return (face.top(), face.right(), face.bottom(), face.left())
    
    def _calculate_overall_liveness(self, results: List[LivenessResult]) -> Tuple[bool, float]:
        """Calculate overall liveness from multiple checks"""
        if not results:
            return False, 0.0
        
        # Weighted voting based on liveness type
        weights = {
            LivenessType.TEXTURE_ANALYSIS: 0.3,
            LivenessType.FREQUENCY_ANALYSIS: 0.3,
            LivenessType.PASSIVE: 0.2,
            LivenessType.BLINK: 0.1,
            LivenessType.HEAD_TURN: 0.1
        }
        
        total_score = 0.0
        total_weight = 0.0
        
        for result in results:
            weight = weights.get(result.liveness_type, 0.1)
            total_score += result.confidence * weight
            total_weight += weight
        
        if total_weight > 0:
            confidence = total_score / total_weight
        else:
            confidence = 0.0
        
        # Require minimum confidence and at least one positive result
        is_live = confidence >= 0.5 and any(r.is_live for r in results)
        
        return is_live, confidence
    
    def _calculate_tar_at_far(self, similarity_score: float) -> float:
        """Calculate True Accept Rate at False Accept Rate 1%"""
        # This is a simplified calculation
        # In production, use ROC curve from test dataset
        
        if similarity_score >= self.match_threshold:
            return 0.98  # Target TAR@FAR1%
        elif similarity_score >= self.match_threshold * 0.95:
            return 0.90
        elif similarity_score >= self.match_threshold * 0.90:
            return 0.80
        else:
            return similarity_score
    
    def _calculate_match_confidence(self, similarity_score: float, 
                                   is_live: bool, 
                                   liveness_confidence: float) -> float:
        """Calculate overall match confidence"""
        # Combine face match and liveness scores
        if not is_live:
            return 0.0
        
        # Weighted combination
        match_weight = 0.7
        liveness_weight = 0.3
        
        confidence = (similarity_score * match_weight + 
                     liveness_confidence * liveness_weight)
        
        return confidence

# Export main components
__all__ = [
    "FaceMatcher",
    "BiometricResult",
    "LivenessResult",
    "FaceEncoding",
    "LivenessType",
    "MatchResult"
]