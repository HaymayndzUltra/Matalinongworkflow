"""
PAD (Presentation Attack Detection) Passive Scorer
Phase 4: Passive liveness detection through multi-modal analysis

This module provides passive liveness detection using:
- Texture analysis (LBP, Haralick features)
- Frequency domain analysis (FFT patterns)
- Color space analysis (HSV, YCbCr distributions)
- Reflection and moire pattern detection
- Confidence scoring with configurable thresholds

All functions are pure with deterministic outputs.
"""

import math
import numpy as np
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass
from enum import Enum


class AttackType(Enum):
    """Types of presentation attacks that can be detected"""
    PRINT_ATTACK = "print_attack"
    SCREEN_REPLAY = "screen_replay"
    MASK_3D = "mask_3d"
    PAPER_MASK = "paper_mask"
    VIDEO_REPLAY = "video_replay"
    GENUINE = "genuine"
    UNKNOWN = "unknown"


class TextureFeature(Enum):
    """Types of texture features"""
    LBP_UNIFORM = "lbp_uniform"
    LBP_VARIANCE = "lbp_variance"
    HARALICK_CONTRAST = "haralick_contrast"
    HARALICK_HOMOGENEITY = "haralick_homogeneity"
    HARALICK_ENERGY = "haralick_energy"
    HARALICK_CORRELATION = "haralick_correlation"


@dataclass
class TextureAnalysis:
    """Results from texture analysis"""
    lbp_histogram: np.ndarray
    lbp_uniformity: float
    lbp_variance: float
    haralick_features: Dict[str, float]
    texture_score: float


@dataclass
class FrequencyAnalysis:
    """Results from frequency domain analysis"""
    high_freq_energy: float
    low_freq_energy: float
    freq_ratio: float
    peak_frequencies: List[float]
    aliasing_score: float
    frequency_score: float


@dataclass
class ColorAnalysis:
    """Results from color space analysis"""
    hsv_distribution: Dict[str, float]
    ycbcr_distribution: Dict[str, float]
    skin_tone_consistency: float
    color_variance: float
    illumination_uniformity: float
    color_score: float


@dataclass
class ReflectionAnalysis:
    """Results from reflection and pattern detection"""
    specular_highlights: int
    moire_pattern_strength: float
    screen_door_effect: float
    edge_sharpness_variance: float
    reflection_score: float


@dataclass
class PADResult:
    """Complete PAD analysis result"""
    texture: TextureAnalysis
    frequency: FrequencyAnalysis
    color: ColorAnalysis
    reflection: ReflectionAnalysis
    overall_score: float
    confidence: float
    attack_type_probabilities: Dict[AttackType, float]
    is_live: bool
    reasons: List[str]


# ============= TEXTURE ANALYSIS =============

def calculate_lbp(gray_image: np.ndarray, radius: int = 1, points: int = 8) -> np.ndarray:
    """
    Calculate Local Binary Pattern for texture analysis
    
    Args:
        gray_image: Grayscale image
        radius: Radius of the circular pattern
        points: Number of points to sample
    
    Returns:
        LBP image
    """
    if gray_image.size == 0:
        return np.array([])
    
    rows, cols = gray_image.shape
    lbp_image = np.zeros((rows, cols), dtype=np.uint8)
    
    for i in range(radius, rows - radius):
        for j in range(radius, cols - radius):
            center = gray_image[i, j]
            pattern = 0
            
            # Sample points in a circle
            for p in range(points):
                angle = 2 * math.pi * p / points
                x = int(round(i + radius * math.sin(angle)))
                y = int(round(j + radius * math.cos(angle)))
                
                if 0 <= x < rows and 0 <= y < cols:
                    if gray_image[x, y] >= center:
                        pattern |= (1 << p)
            
            lbp_image[i, j] = pattern
    
    return lbp_image


def calculate_lbp_histogram(lbp_image: np.ndarray, bins: int = 59) -> np.ndarray:
    """
    Calculate histogram of LBP uniform patterns
    
    Args:
        lbp_image: LBP transformed image
        bins: Number of histogram bins (59 for uniform LBP)
    
    Returns:
        Normalized histogram
    """
    if lbp_image.size == 0:
        return np.zeros(bins)
    
    # Count uniform patterns (at most 2 bitwise transitions)
    uniform_patterns = []
    for i in range(256):
        pattern = bin(i)[2:].zfill(8)
        transitions = sum(pattern[j] != pattern[j-1] for j in range(len(pattern)))
        if transitions <= 2:
            uniform_patterns.append(i)
    
    # Map to uniform patterns
    hist = np.zeros(bins)
    for val in lbp_image.flatten():
        if val in uniform_patterns[:bins-1]:
            hist[uniform_patterns.index(val)] += 1
        else:
            hist[-1] += 1  # Non-uniform patterns
    
    # Normalize
    if hist.sum() > 0:
        hist = hist / hist.sum()
    
    return hist


def calculate_haralick_features(gray_image: np.ndarray, distances: List[int] = [1]) -> Dict[str, float]:
    """
    Calculate Haralick texture features from co-occurrence matrix
    
    Args:
        gray_image: Grayscale image (quantized to fewer levels)
        distances: Pixel distances for co-occurrence
    
    Returns:
        Dictionary of Haralick features
    """
    if gray_image.size == 0:
        return {
            'contrast': 0.0,
            'homogeneity': 0.0,
            'energy': 0.0,
            'correlation': 0.0
        }
    
    # Quantize image to 8 levels for faster computation
    quantized = (gray_image / 32).astype(np.uint8)
    levels = 8
    
    # Create co-occurrence matrix
    glcm = np.zeros((levels, levels), dtype=np.float32)
    rows, cols = quantized.shape
    
    for d in distances:
        for i in range(rows):
            for j in range(cols - d):
                glcm[quantized[i, j], quantized[i, j + d]] += 1
                glcm[quantized[i, j + d], quantized[i, j]] += 1
    
    # Normalize
    if glcm.sum() > 0:
        glcm = glcm / glcm.sum()
    
    # Calculate features
    contrast = 0.0
    homogeneity = 0.0
    energy = 0.0
    correlation = 0.0
    
    # Means and stds for correlation
    pi = np.sum(glcm, axis=1)
    pj = np.sum(glcm, axis=0)
    mui = np.sum(pi * np.arange(levels))
    muj = np.sum(pj * np.arange(levels))
    stdi = np.sqrt(np.sum(pi * (np.arange(levels) - mui) ** 2))
    stdj = np.sqrt(np.sum(pj * (np.arange(levels) - muj) ** 2))
    
    for i in range(levels):
        for j in range(levels):
            if glcm[i, j] > 0:
                contrast += glcm[i, j] * (i - j) ** 2
                homogeneity += glcm[i, j] / (1 + abs(i - j))
                energy += glcm[i, j] ** 2
                if stdi > 0 and stdj > 0:
                    correlation += glcm[i, j] * (i - mui) * (j - muj) / (stdi * stdj)
    
    return {
        'contrast': float(contrast),
        'homogeneity': float(homogeneity),
        'energy': float(energy),
        'correlation': float(correlation)
    }


def analyze_texture(gray_image: np.ndarray) -> TextureAnalysis:
    """
    Perform comprehensive texture analysis
    
    Args:
        gray_image: Grayscale face image
    
    Returns:
        Complete texture analysis results
    """
    # Calculate LBP
    lbp_image = calculate_lbp(gray_image)
    lbp_hist = calculate_lbp_histogram(lbp_image)
    
    # LBP statistics
    lbp_uniformity = float(np.max(lbp_hist)) if lbp_hist.size > 0 else 0.0
    lbp_variance = float(np.var(lbp_hist)) if lbp_hist.size > 0 else 0.0
    
    # Haralick features
    haralick = calculate_haralick_features(gray_image)
    
    # Calculate texture score (higher for genuine faces)
    # Genuine faces have more texture complexity
    texture_score = (
        (1.0 - lbp_uniformity) * 0.3 +  # Less uniform is better
        min(lbp_variance * 100, 1.0) * 0.2 +  # Some variance is good
        min(haralick['contrast'] / 10, 1.0) * 0.2 +  # Moderate contrast
        haralick['homogeneity'] * 0.15 +  # Some homogeneity
        (1.0 - haralick['energy']) * 0.15  # Less energy (more random)
    )
    
    return TextureAnalysis(
        lbp_histogram=lbp_hist,
        lbp_uniformity=lbp_uniformity,
        lbp_variance=lbp_variance,
        haralick_features=haralick,
        texture_score=texture_score
    )


# ============= FREQUENCY ANALYSIS =============

def analyze_frequency_domain(gray_image: np.ndarray) -> FrequencyAnalysis:
    """
    Analyze frequency domain characteristics
    
    Args:
        gray_image: Grayscale face image
    
    Returns:
        Frequency analysis results
    """
    if gray_image.size == 0:
        return FrequencyAnalysis(
            high_freq_energy=0.0,
            low_freq_energy=0.0,
            freq_ratio=0.0,
            peak_frequencies=[],
            aliasing_score=0.0,
            frequency_score=0.0
        )
    
    # Apply FFT
    f_transform = np.fft.fft2(gray_image)
    f_shift = np.fft.fftshift(f_transform)
    magnitude = np.abs(f_shift)
    
    rows, cols = gray_image.shape
    crow, ccol = rows // 2, cols // 2
    
    # Define frequency bands
    low_freq_mask = np.zeros((rows, cols), dtype=bool)
    high_freq_mask = np.zeros((rows, cols), dtype=bool)
    
    for i in range(rows):
        for j in range(cols):
            dist = np.sqrt((i - crow) ** 2 + (j - ccol) ** 2)
            if dist < min(rows, cols) * 0.1:  # Low frequency
                low_freq_mask[i, j] = True
            elif dist > min(rows, cols) * 0.3:  # High frequency
                high_freq_mask[i, j] = True
    
    # Calculate energy in different bands
    total_energy = np.sum(magnitude ** 2)
    if total_energy > 0:
        low_freq_energy = np.sum(magnitude[low_freq_mask] ** 2) / total_energy
        high_freq_energy = np.sum(magnitude[high_freq_mask] ** 2) / total_energy
    else:
        low_freq_energy = 0.0
        high_freq_energy = 0.0
    
    # Frequency ratio (genuine faces have balanced distribution)
    if low_freq_energy > 0:
        freq_ratio = high_freq_energy / low_freq_energy
    else:
        freq_ratio = 0.0
    
    # Detect peak frequencies (potential aliasing/moire)
    # Flatten and sort magnitude spectrum
    mag_flat = magnitude.flatten()
    mag_sorted = np.sort(mag_flat)[::-1]
    
    # Find peaks (excluding DC component)
    peak_threshold = mag_sorted[10] if len(mag_sorted) > 10 else 0
    peaks = []
    for i in range(1, min(len(mag_sorted), 20)):
        if mag_sorted[i] > peak_threshold * 0.5:
            peaks.append(float(mag_sorted[i]))
    
    # Aliasing score (regular patterns indicate replay attacks)
    if len(peaks) > 1:
        peak_regularity = np.std(np.diff(peaks[:5]))
        aliasing_score = 1.0 / (1.0 + peak_regularity)
    else:
        aliasing_score = 0.0
    
    # Calculate frequency score
    # Genuine faces have balanced frequency distribution
    freq_balance = 1.0 - abs(0.5 - low_freq_energy)
    freq_diversity = min(len(peaks) / 10, 1.0)
    
    frequency_score = (
        freq_balance * 0.4 +
        (1.0 - aliasing_score) * 0.3 +
        freq_diversity * 0.3
    )
    
    return FrequencyAnalysis(
        high_freq_energy=float(high_freq_energy),
        low_freq_energy=float(low_freq_energy),
        freq_ratio=float(freq_ratio),
        peak_frequencies=peaks[:5],
        aliasing_score=float(aliasing_score),
        frequency_score=float(frequency_score)
    )


# ============= COLOR ANALYSIS =============

def rgb_to_hsv(rgb_image: np.ndarray) -> np.ndarray:
    """Convert RGB image to HSV color space"""
    if rgb_image.size == 0:
        return np.array([])
    
    rgb_norm = rgb_image.astype(np.float32) / 255.0
    hsv_image = np.zeros_like(rgb_norm)
    
    for i in range(rgb_norm.shape[0]):
        for j in range(rgb_norm.shape[1]):
            r, g, b = rgb_norm[i, j]
            
            max_val = max(r, g, b)
            min_val = min(r, g, b)
            diff = max_val - min_val
            
            # Value
            hsv_image[i, j, 2] = max_val
            
            # Saturation
            if max_val > 0:
                hsv_image[i, j, 1] = diff / max_val
            else:
                hsv_image[i, j, 1] = 0
            
            # Hue
            if diff == 0:
                hsv_image[i, j, 0] = 0
            elif max_val == r:
                hsv_image[i, j, 0] = (60 * ((g - b) / diff) + 360) % 360
            elif max_val == g:
                hsv_image[i, j, 0] = (60 * ((b - r) / diff) + 120) % 360
            else:
                hsv_image[i, j, 0] = (60 * ((r - g) / diff) + 240) % 360
    
    return hsv_image


def rgb_to_ycbcr(rgb_image: np.ndarray) -> np.ndarray:
    """Convert RGB image to YCbCr color space"""
    if rgb_image.size == 0:
        return np.array([])
    
    # Conversion matrix
    rgb_float = rgb_image.astype(np.float32)
    ycbcr = np.zeros_like(rgb_float)
    
    ycbcr[:, :, 0] = 0.299 * rgb_float[:, :, 0] + 0.587 * rgb_float[:, :, 1] + 0.114 * rgb_float[:, :, 2]
    ycbcr[:, :, 1] = 128 - 0.168736 * rgb_float[:, :, 0] - 0.331264 * rgb_float[:, :, 1] + 0.5 * rgb_float[:, :, 2]
    ycbcr[:, :, 2] = 128 + 0.5 * rgb_float[:, :, 0] - 0.418688 * rgb_float[:, :, 1] - 0.081312 * rgb_float[:, :, 2]
    
    return ycbcr.astype(np.uint8)


def analyze_color_distribution(rgb_image: np.ndarray) -> ColorAnalysis:
    """
    Analyze color distribution for liveness detection
    
    Args:
        rgb_image: RGB face image
    
    Returns:
        Color analysis results
    """
    if rgb_image.size == 0:
        return ColorAnalysis(
            hsv_distribution={},
            ycbcr_distribution={},
            skin_tone_consistency=0.0,
            color_variance=0.0,
            illumination_uniformity=0.0,
            color_score=0.0
        )
    
    # Convert to different color spaces
    hsv = rgb_to_hsv(rgb_image)
    ycbcr = rgb_to_ycbcr(rgb_image)
    
    # HSV distribution analysis
    hsv_dist = {}
    if hsv.size > 0:
        hsv_dist['hue_mean'] = float(np.mean(hsv[:, :, 0]))
        hsv_dist['hue_std'] = float(np.std(hsv[:, :, 0]))
        hsv_dist['sat_mean'] = float(np.mean(hsv[:, :, 1]))
        hsv_dist['sat_std'] = float(np.std(hsv[:, :, 1]))
        hsv_dist['val_mean'] = float(np.mean(hsv[:, :, 2]))
        hsv_dist['val_std'] = float(np.std(hsv[:, :, 2]))
    
    # YCbCr distribution analysis
    ycbcr_dist = {}
    if ycbcr.size > 0:
        ycbcr_dist['y_mean'] = float(np.mean(ycbcr[:, :, 0]))
        ycbcr_dist['cb_mean'] = float(np.mean(ycbcr[:, :, 1]))
        ycbcr_dist['cr_mean'] = float(np.mean(ycbcr[:, :, 2]))
        ycbcr_dist['cb_std'] = float(np.std(ycbcr[:, :, 1]))
        ycbcr_dist['cr_std'] = float(np.std(ycbcr[:, :, 2]))
    
    # Skin tone consistency (in YCbCr space)
    # Typical skin tone ranges: Cb [77, 127], Cr [133, 173]
    if ycbcr.size > 0:
        cb_values = ycbcr[:, :, 1].flatten()
        cr_values = ycbcr[:, :, 2].flatten()
        
        skin_mask = (cb_values >= 77) & (cb_values <= 127) & (cr_values >= 133) & (cr_values <= 173)
        skin_tone_consistency = float(np.sum(skin_mask) / len(skin_mask))
    else:
        skin_tone_consistency = 0.0
    
    # Color variance (genuine faces have natural color variation)
    color_variance = float(np.std(rgb_image))
    
    # Illumination uniformity (check for unnatural uniform lighting)
    if hsv.size > 0:
        illumination_uniformity = 1.0 - float(np.std(hsv[:, :, 2]))
    else:
        illumination_uniformity = 0.0
    
    # Calculate color score
    # Genuine faces have consistent skin tones but natural variation
    color_score = (
        skin_tone_consistency * 0.4 +
        min(color_variance / 50, 1.0) * 0.3 +  # Some variance is good
        (1.0 - illumination_uniformity) * 0.3  # Non-uniform lighting is natural
    )
    
    return ColorAnalysis(
        hsv_distribution=hsv_dist,
        ycbcr_distribution=ycbcr_dist,
        skin_tone_consistency=skin_tone_consistency,
        color_variance=color_variance,
        illumination_uniformity=illumination_uniformity,
        color_score=color_score
    )


# ============= REFLECTION ANALYSIS =============

def detect_specular_highlights(gray_image: np.ndarray, threshold: int = 250) -> int:
    """
    Detect specular highlights that may indicate screen/print
    
    Args:
        gray_image: Grayscale image
        threshold: Brightness threshold for highlights
    
    Returns:
        Number of specular highlight regions
    """
    if gray_image.size == 0:
        return 0
    
    # Find bright spots
    bright_mask = gray_image > threshold
    
    # Connected component analysis (simple version)
    visited = np.zeros_like(bright_mask, dtype=bool)
    num_highlights = 0
    
    for i in range(bright_mask.shape[0]):
        for j in range(bright_mask.shape[1]):
            if bright_mask[i, j] and not visited[i, j]:
                # Found a new highlight region
                num_highlights += 1
                # Mark connected region (simplified flood fill)
                stack = [(i, j)]
                while stack:
                    y, x = stack.pop()
                    if 0 <= y < bright_mask.shape[0] and 0 <= x < bright_mask.shape[1]:
                        if bright_mask[y, x] and not visited[y, x]:
                            visited[y, x] = True
                            stack.extend([(y+1, x), (y-1, x), (y, x+1), (y, x-1)])
    
    return num_highlights


def detect_moire_patterns(gray_image: np.ndarray) -> float:
    """
    Detect moire patterns from screen capture
    
    Args:
        gray_image: Grayscale image
    
    Returns:
        Moire pattern strength (0-1)
    """
    if gray_image.size == 0:
        return 0.0
    
    # Apply FFT to detect regular patterns
    f_transform = np.fft.fft2(gray_image)
    f_shift = np.fft.fftshift(f_transform)
    magnitude = np.abs(f_shift)
    
    rows, cols = gray_image.shape
    crow, ccol = rows // 2, cols // 2
    
    # Look for peaks in specific frequency bands (screen refresh patterns)
    moire_band_start = min(rows, cols) * 0.15
    moire_band_end = min(rows, cols) * 0.25
    
    moire_strength = 0.0
    peak_count = 0
    
    for i in range(rows):
        for j in range(cols):
            if i == crow and j == ccol:
                continue  # Skip DC component
            
            dist = np.sqrt((i - crow) ** 2 + (j - ccol) ** 2)
            if moire_band_start <= dist <= moire_band_end:
                if magnitude[i, j] > np.mean(magnitude) * 3:
                    peak_count += 1
                    moire_strength += magnitude[i, j]
    
    # Normalize
    if peak_count > 0:
        moire_strength = min(moire_strength / (np.max(magnitude) * peak_count), 1.0)
    
    return float(moire_strength)


def analyze_edge_sharpness(gray_image: np.ndarray) -> float:
    """
    Analyze edge sharpness variance (prints have uniform sharpness)
    
    Args:
        gray_image: Grayscale image
    
    Returns:
        Edge sharpness variance
    """
    if gray_image.size == 0:
        return 0.0
    
    # Simple edge detection using gradients
    dy, dx = np.gradient(gray_image.astype(np.float32))
    edge_magnitude = np.sqrt(dx ** 2 + dy ** 2)
    
    # Divide image into blocks and calculate sharpness variance
    block_size = 32
    rows, cols = gray_image.shape
    sharpness_values = []
    
    for i in range(0, rows - block_size, block_size):
        for j in range(0, cols - block_size, block_size):
            block = edge_magnitude[i:i+block_size, j:j+block_size]
            if block.size > 0:
                sharpness_values.append(np.mean(block))
    
    if sharpness_values:
        return float(np.std(sharpness_values))
    else:
        return 0.0


def analyze_reflections(gray_image: np.ndarray, rgb_image: np.ndarray) -> ReflectionAnalysis:
    """
    Analyze reflections and artifacts
    
    Args:
        gray_image: Grayscale face image
        rgb_image: RGB face image
    
    Returns:
        Reflection analysis results
    """
    # Detect specular highlights
    specular_highlights = detect_specular_highlights(gray_image)
    
    # Detect moire patterns
    moire_strength = detect_moire_patterns(gray_image)
    
    # Screen door effect (regular grid pattern)
    # Similar to moire but at different frequencies
    screen_door = moire_strength * 0.5  # Simplified
    
    # Edge sharpness variance
    edge_variance = analyze_edge_sharpness(gray_image)
    
    # Calculate reflection score
    # Lower score indicates more artifacts
    reflection_score = (
        max(0, 1.0 - specular_highlights / 10) * 0.3 +  # Few highlights
        (1.0 - moire_strength) * 0.3 +  # No moire
        (1.0 - screen_door) * 0.2 +  # No screen door
        min(edge_variance / 10, 1.0) * 0.2  # Natural edge variance
    )
    
    return ReflectionAnalysis(
        specular_highlights=specular_highlights,
        moire_pattern_strength=moire_strength,
        screen_door_effect=screen_door,
        edge_sharpness_variance=edge_variance,
        reflection_score=reflection_score
    )


# ============= COMPREHENSIVE PAD SCORING =============

def calculate_attack_probabilities(
    texture_score: float,
    frequency_score: float,
    color_score: float,
    reflection_score: float
) -> Dict[AttackType, float]:
    """
    Calculate probability of different attack types
    
    Args:
        texture_score: Texture analysis score
        frequency_score: Frequency domain score
        color_score: Color distribution score
        reflection_score: Reflection analysis score
    
    Returns:
        Probability distribution over attack types
    """
    # Define characteristic patterns for each attack type
    patterns = {
        AttackType.PRINT_ATTACK: {
            'texture': 0.3,  # Low texture
            'frequency': 0.4,  # Altered frequencies
            'color': 0.5,  # Moderate color
            'reflection': 0.3  # Paper reflections
        },
        AttackType.SCREEN_REPLAY: {
            'texture': 0.4,
            'frequency': 0.2,  # Moire patterns
            'color': 0.6,
            'reflection': 0.2  # Screen artifacts
        },
        AttackType.MASK_3D: {
            'texture': 0.6,  # Good texture
            'frequency': 0.7,
            'color': 0.4,  # Unnatural color
            'reflection': 0.6
        },
        AttackType.PAPER_MASK: {
            'texture': 0.2,  # Very low texture
            'frequency': 0.5,
            'color': 0.3,
            'reflection': 0.4
        },
        AttackType.VIDEO_REPLAY: {
            'texture': 0.5,
            'frequency': 0.3,  # Compression artifacts
            'color': 0.7,
            'reflection': 0.3
        },
        AttackType.GENUINE: {
            'texture': 0.8,  # High texture
            'frequency': 0.8,  # Natural frequencies
            'color': 0.8,  # Natural color
            'reflection': 0.9  # No artifacts
        }
    }
    
    scores = {
        'texture': texture_score,
        'frequency': frequency_score,
        'color': color_score,
        'reflection': reflection_score
    }
    
    # Calculate similarity to each pattern
    probabilities = {}
    for attack_type, pattern in patterns.items():
        similarity = 0.0
        for feature, expected in pattern.items():
            actual = scores[feature]
            # Gaussian-like similarity
            diff = abs(actual - expected)
            similarity += math.exp(-diff * diff * 5)
        
        probabilities[attack_type] = similarity / 4.0
    
    # Normalize probabilities
    total = sum(probabilities.values())
    if total > 0:
        for attack_type in probabilities:
            probabilities[attack_type] /= total
    
    return probabilities


def analyze_pad(
    gray_image: np.ndarray,
    rgb_image: np.ndarray,
    thresholds: Optional[Dict[str, float]] = None
) -> PADResult:
    """
    Perform comprehensive PAD analysis
    
    Args:
        gray_image: Grayscale face image
        rgb_image: RGB face image
        thresholds: Optional threshold overrides
    
    Returns:
        Complete PAD analysis result
    """
    # Default thresholds
    if thresholds is None:
        thresholds = {
            'pad_score_min': 0.7,
            'spoof_threshold': 0.3
        }
    
    # Perform analyses
    texture = analyze_texture(gray_image)
    frequency = analyze_frequency_domain(gray_image)
    color = analyze_color_distribution(rgb_image)
    reflection = analyze_reflections(gray_image, rgb_image)
    
    # Calculate overall score (weighted average)
    overall_score = (
        texture.texture_score * 0.3 +
        frequency.frequency_score * 0.25 +
        color.color_score * 0.25 +
        reflection.reflection_score * 0.2
    )
    
    # Calculate attack probabilities
    attack_probs = calculate_attack_probabilities(
        texture.texture_score,
        frequency.frequency_score,
        color.color_score,
        reflection.reflection_score
    )
    
    # Determine if live
    is_live = (
        overall_score >= thresholds['pad_score_min'] and
        attack_probs.get(AttackType.GENUINE, 0) > thresholds['spoof_threshold']
    )
    
    # Calculate confidence
    confidence = attack_probs.get(AttackType.GENUINE, 0)
    
    # Generate reasons
    reasons = []
    if texture.texture_score < 0.5:
        reasons.append("Low texture complexity detected")
    if frequency.aliasing_score > 0.5:
        reasons.append("Frequency aliasing patterns detected")
    if color.skin_tone_consistency < 0.3:
        reasons.append("Inconsistent skin tone distribution")
    if reflection.moire_pattern_strength > 0.3:
        reasons.append("Moire patterns detected")
    if reflection.specular_highlights > 5:
        reasons.append("Excessive specular highlights")
    
    if not reasons:
        if is_live:
            reasons.append("Face appears genuine with natural characteristics")
        else:
            reasons.append("Face characteristics indicate possible presentation attack")
    
    return PADResult(
        texture=texture,
        frequency=frequency,
        color=color,
        reflection=reflection,
        overall_score=overall_score,
        confidence=confidence,
        attack_type_probabilities=attack_probs,
        is_live=is_live,
        reasons=reasons
    )


def format_pad_feedback(result: PADResult) -> Dict[str, Any]:
    """
    Format PAD result as user-friendly feedback
    
    Args:
        result: PAD analysis result
    
    Returns:
        Formatted feedback dictionary
    """
    # Find most likely attack type
    max_prob = 0.0
    likely_attack = AttackType.GENUINE
    for attack_type, prob in result.attack_type_probabilities.items():
        if prob > max_prob:
            max_prob = prob
            likely_attack = attack_type
    
    feedback = {
        'is_live': result.is_live,
        'confidence': round(result.confidence * 100, 1),
        'overall_score': round(result.overall_score * 100, 1),
        'likely_attack': likely_attack.value if not result.is_live else None,
        'scores': {
            'texture': round(result.texture.texture_score * 100, 1),
            'frequency': round(result.frequency.frequency_score * 100, 1),
            'color': round(result.color.color_score * 100, 1),
            'reflection': round(result.reflection.reflection_score * 100, 1)
        },
        'details': {
            'lbp_uniformity': round(result.texture.lbp_uniformity, 3),
            'frequency_ratio': round(result.frequency.freq_ratio, 3),
            'skin_consistency': round(result.color.skin_tone_consistency, 3),
            'moire_strength': round(result.reflection.moire_pattern_strength, 3)
        },
        'reasons': result.reasons
    }
    
    # Add recommendations
    if not result.is_live:
        feedback['recommendation'] = "Please ensure you are presenting your actual face to the camera"
        if likely_attack == AttackType.PRINT_ATTACK:
            feedback['recommendation'] += " (no printed photos)"
        elif likely_attack == AttackType.SCREEN_REPLAY:
            feedback['recommendation'] += " (no screens or displays)"
    else:
        feedback['recommendation'] = "Liveness check passed"
    
    return feedback