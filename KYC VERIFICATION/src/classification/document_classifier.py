"""
Document Classification Module
Phase 2: Multi-ID/country classifier for Philippine IDs
Supports: PhilID, UMID, Driver's License, Passport, PRC
"""

import cv2
import numpy as np
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass
from enum import Enum
import json
import logging
from pathlib import Path
import torch
import torch.nn as nn
import torchvision.transforms as transforms
from PIL import Image
import re

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DocumentType(Enum):
    """Supported Philippine document types"""
    PHIL_ID = "PhilID"  # Philippine National ID
    UMID = "UMID"  # Unified Multi-Purpose ID
    DRIVERS_LICENSE = "Driver License"
    PASSPORT = "Passport"
    PRC = "PRC"  # Professional Regulation Commission ID
    UNKNOWN = "Unknown"

@dataclass
class ClassificationResult:
    """Document classification result"""
    document_type: DocumentType
    country: str
    confidence: float
    probabilities: Dict[str, float]
    features_detected: List[str]
    template_id: str
    metadata: Dict[str, Any]

@dataclass
class DocumentTemplate:
    """Template for document type"""
    id: str
    type: DocumentType
    country: str
    issuer: str
    dimensions: Tuple[float, float]  # Standard dimensions in mm
    aspect_ratio: float
    key_features: List[str]
    text_patterns: Dict[str, str]  # Regex patterns for validation
    color_scheme: List[Tuple[int, int, int]]  # Dominant colors (RGB)
    security_features: List[str]
    mrz_format: Optional[str]  # MRZ format if applicable
    barcode_types: List[str]  # Supported barcode types

class DocumentClassifier:
    """Multi-document classifier for Philippine IDs"""
    
    def __init__(self, templates_path: Optional[str] = None, model_path: Optional[str] = None):
        """
        Initialize document classifier
        
        Args:
            templates_path: Path to document templates directory
            model_path: Path to pre-trained classification model
        """
        self.templates = self._load_templates(templates_path)
        self.model = self._load_model(model_path)
        self.transform = self._setup_transforms()
        self.feature_extractors = self._initialize_extractors()
        
    def _load_templates(self, templates_path: Optional[str]) -> Dict[str, DocumentTemplate]:
        """Load document templates from configuration"""
        templates = {}
        
        # Default Philippine ID templates
        default_templates = [
            DocumentTemplate(
                id="ph_philid_v1",
                type=DocumentType.PHIL_ID,
                country="PH",
                issuer="Philippine Statistics Authority",
                dimensions=(85.6, 53.98),  # ISO ID-1 standard
                aspect_ratio=1.586,
                key_features=["PSN", "Full Name", "Date of Birth", "Sex", "Blood Type", "Address"],
                text_patterns={
                    "psn": r"\d{4}-\d{4}-\d{4}-\d{4}",
                    "date": r"\d{2}/\d{2}/\d{4}",
                    "blood_type": r"[ABO][+-]"
                },
                color_scheme=[(0, 56, 168), (255, 255, 255), (255, 0, 0)],  # Blue, White, Red
                security_features=["Hologram", "UV Print", "Microprint", "Ghost Image"],
                mrz_format=None,
                barcode_types=["QR", "PDF417"]
            ),
            DocumentTemplate(
                id="ph_umid_v1",
                type=DocumentType.UMID,
                country="PH",
                issuer="Social Security System",
                dimensions=(85.6, 53.98),
                aspect_ratio=1.586,
                key_features=["CRN", "Given Name", "Middle Name", "Surname", "Date of Birth"],
                text_patterns={
                    "crn": r"\d{2}-\d{7}-\d{1}",
                    "sss": r"\d{2}-\d{7}-\d{1}",
                    "gsis": r"\d{11}",
                    "tin": r"\d{3}-\d{3}-\d{3}-\d{3}"
                },
                color_scheme=[(0, 123, 255), (255, 255, 255)],  # Blue, White
                security_features=["Hologram", "Embossed Text", "Security Thread"],
                mrz_format=None,
                barcode_types=["BARCODE_128", "QR"]
            ),
            DocumentTemplate(
                id="ph_drivers_license_v1",
                type=DocumentType.DRIVERS_LICENSE,
                country="PH",
                issuer="Land Transportation Office",
                dimensions=(85.6, 53.98),
                aspect_ratio=1.586,
                key_features=["License No", "Full Name", "Nationality", "Date of Birth", "Expiration Date"],
                text_patterns={
                    "license_no": r"[A-Z]\d{2}-\d{2}-\d{6}",
                    "expiry": r"\d{4}-\d{2}-\d{2}",
                    "restrictions": r"[1-8](,[1-8])*"
                },
                color_scheme=[(255, 255, 0), (0, 0, 139)],  # Yellow, Dark Blue
                security_features=["Hologram", "UV Features", "Raised Print"],
                mrz_format=None,
                barcode_types=["PDF417"]
            ),
            DocumentTemplate(
                id="ph_passport_v1",
                type=DocumentType.PASSPORT,
                country="PH",
                issuer="Department of Foreign Affairs",
                dimensions=(125, 88),  # Passport dimensions
                aspect_ratio=1.42,
                key_features=["Passport No", "Surname", "Given Names", "Date of Birth", "Date of Issue", "Date of Expiry"],
                text_patterns={
                    "passport_no": r"[A-Z][A-Z0-9]\d{7}",
                    "mrz_line1": r"P<PHL[A-Z<]+",
                    "mrz_line2": r"[A-Z0-9<]{44}"
                },
                color_scheme=[(139, 0, 0), (255, 215, 0)],  # Maroon, Gold
                security_features=["Watermark", "UV Features", "Security Thread", "Holographic Foil"],
                mrz_format="TD3",  # ICAO 9303 format
                barcode_types=[]
            ),
            DocumentTemplate(
                id="ph_prc_v1",
                type=DocumentType.PRC,
                country="PH",
                issuer="Professional Regulation Commission",
                dimensions=(85.6, 53.98),
                aspect_ratio=1.586,
                key_features=["Registration No", "Full Name", "Profession", "Date of Registration", "Expiry Date"],
                text_patterns={
                    "registration_no": r"\d{7}",
                    "expiry": r"\d{2}/\d{2}/\d{4}"
                },
                color_scheme=[(0, 100, 0), (255, 255, 255)],  # Green, White
                security_features=["Hologram", "Embossed Seal", "Security Pattern"],
                mrz_format=None,
                barcode_types=["QR"]
            )
        ]
        
        # Load templates
        for template in default_templates:
            templates[template.id] = template
        
        # Load custom templates if path provided
        if templates_path and Path(templates_path).exists():
            custom_templates = self._load_custom_templates(templates_path)
            templates.update(custom_templates)
        
        logger.info(f"Loaded {len(templates)} document templates")
        return templates
    
    def _load_custom_templates(self, templates_path: str) -> Dict[str, DocumentTemplate]:
        """Load custom templates from directory"""
        custom_templates = {}
        templates_dir = Path(templates_path)
        
        for template_file in templates_dir.glob("*.json"):
            try:
                with open(template_file, 'r') as f:
                    data = json.load(f)
                    template = DocumentTemplate(
                        id=data["id"],
                        type=DocumentType[data["type"]],
                        country=data["country"],
                        issuer=data["issuer"],
                        dimensions=tuple(data["dimensions"]),
                        aspect_ratio=data["aspect_ratio"],
                        key_features=data["key_features"],
                        text_patterns=data["text_patterns"],
                        color_scheme=[tuple(c) for c in data["color_scheme"]],
                        security_features=data["security_features"],
                        mrz_format=data.get("mrz_format"),
                        barcode_types=data.get("barcode_types", [])
                    )
                    custom_templates[template.id] = template
                    logger.info(f"Loaded custom template: {template.id}")
            except Exception as e:
                logger.error(f"Failed to load template {template_file}: {e}")
        
        return custom_templates
    
    def _load_model(self, model_path: Optional[str]) -> nn.Module:
        """Load or create classification model"""
        class DocumentCNN(nn.Module):
            """Simple CNN for document classification"""
            def __init__(self, num_classes=6):
                super(DocumentCNN, self).__init__()
                self.conv1 = nn.Conv2d(3, 32, kernel_size=3, padding=1)
                self.conv2 = nn.Conv2d(32, 64, kernel_size=3, padding=1)
                self.conv3 = nn.Conv2d(64, 128, kernel_size=3, padding=1)
                self.pool = nn.MaxPool2d(2, 2)
                self.fc1 = nn.Linear(128 * 28 * 28, 512)
                self.fc2 = nn.Linear(512, 256)
                self.fc3 = nn.Linear(256, num_classes)
                self.dropout = nn.Dropout(0.5)
                self.relu = nn.ReLU()
                
            def forward(self, x):
                x = self.pool(self.relu(self.conv1(x)))
                x = self.pool(self.relu(self.conv2(x)))
                x = self.pool(self.relu(self.conv3(x)))
                x = x.view(-1, 128 * 28 * 28)
                x = self.relu(self.fc1(x))
                x = self.dropout(x)
                x = self.relu(self.fc2(x))
                x = self.dropout(x)
                x = self.fc3(x)
                return x
        
        model = DocumentCNN(num_classes=len(DocumentType))
        
        # Load pre-trained weights if available
        if model_path and Path(model_path).exists():
            try:
                model.load_state_dict(torch.load(model_path, map_location='cpu'))
                model.eval()
                logger.info(f"Loaded pre-trained model from {model_path}")
            except Exception as e:
                logger.warning(f"Failed to load model weights: {e}")
        
        return model
    
    def _setup_transforms(self) -> transforms.Compose:
        """Setup image transforms for model input"""
        return transforms.Compose([
            transforms.Resize((224, 224)),
            transforms.ToTensor(),
            transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
        ])
    
    def _initialize_extractors(self) -> Dict[str, Any]:
        """Initialize feature extractors"""
        return {
            "text": self._extract_text_features,
            "color": self._extract_color_features,
            "shape": self._extract_shape_features,
            "pattern": self._extract_pattern_features
        }
    
    def classify(self, image: np.ndarray) -> ClassificationResult:
        """
        Classify document type
        
        Args:
            image: Input image (BGR format)
            
        Returns:
            Classification result with confidence scores
        """
        # Extract features
        features = self._extract_features(image)
        
        # Get model predictions
        predictions = self._get_model_predictions(image)
        
        # Match against templates
        template_scores = self._match_templates(features)
        
        # Combine predictions
        final_scores = self._combine_scores(predictions, template_scores)
        
        # Get top prediction
        doc_type, confidence = self._get_top_prediction(final_scores)
        
        # Find matching template
        template_id = self._find_best_template(doc_type, features)
        
        # Build result
        result = ClassificationResult(
            document_type=doc_type,
            country="PH",
            confidence=confidence,
            probabilities=final_scores,
            features_detected=features.get("detected_features", []),
            template_id=template_id,
            metadata={
                "aspect_ratio": features.get("aspect_ratio"),
                "dominant_colors": features.get("dominant_colors"),
                "has_mrz": features.get("has_mrz", False),
                "has_barcode": features.get("has_barcode", False)
            }
        )
        
        logger.info(f"Classified as {doc_type.value} with confidence {confidence:.2f}")
        
        return result
    
    def _extract_features(self, image: np.ndarray) -> Dict[str, Any]:
        """Extract various features from document image"""
        features = {}
        
        # Extract text features
        features.update(self._extract_text_features(image))
        
        # Extract color features
        features.update(self._extract_color_features(image))
        
        # Extract shape features
        features.update(self._extract_shape_features(image))
        
        # Extract pattern features
        features.update(self._extract_pattern_features(image))
        
        return features
    
    def _extract_text_features(self, image: np.ndarray) -> Dict[str, Any]:
        """Extract text-based features"""
        features = {
            "detected_features": [],
            "text_regions": []
        }
        
        # Convert to grayscale for text detection
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        
        # Detect text regions using morphological operations
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (20, 3))
        dilated = cv2.dilate(gray, kernel, iterations=1)
        contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        # Analyze text regions
        for contour in contours:
            area = cv2.contourArea(contour)
            if area > 500:  # Filter small regions
                x, y, w, h = cv2.boundingRect(contour)
                features["text_regions"].append({
                    "bbox": (x, y, w, h),
                    "area": area
                })
        
        # Check for MRZ pattern (bottom of document, specific aspect ratio)
        height, width = image.shape[:2]
        bottom_region = gray[int(height * 0.7):, :]
        
        # Simple MRZ detection based on pattern
        edges = cv2.Canny(bottom_region, 50, 150)
        horizontal_proj = np.sum(edges, axis=1)
        
        if np.max(horizontal_proj) > width * 0.3:  # Significant horizontal lines
            features["has_mrz"] = True
            features["detected_features"].append("MRZ")
        
        return features
    
    def _extract_color_features(self, image: np.ndarray) -> Dict[str, Any]:
        """Extract color-based features"""
        features = {}
        
        # Convert to RGB for color analysis
        rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        
        # Calculate dominant colors using k-means
        pixels = rgb.reshape(-1, 3)
        
        # Simple color quantization
        from sklearn.cluster import MiniBatchKMeans
        n_colors = 5
        kmeans = MiniBatchKMeans(n_clusters=n_colors, random_state=42, n_init=3)
        kmeans.fit(pixels)
        
        dominant_colors = kmeans.cluster_centers_.astype(int)
        features["dominant_colors"] = [tuple(color) for color in dominant_colors]
        
        # Calculate color histogram
        hist_r = cv2.calcHist([rgb], [0], None, [256], [0, 256])
        hist_g = cv2.calcHist([rgb], [1], None, [256], [0, 256])
        hist_b = cv2.calcHist([rgb], [2], None, [256], [0, 256])
        
        features["color_histogram"] = {
            "red": hist_r.flatten().tolist()[:50],  # Store only first 50 bins
            "green": hist_g.flatten().tolist()[:50],
            "blue": hist_b.flatten().tolist()[:50]
        }
        
        return features
    
    def _extract_shape_features(self, image: np.ndarray) -> Dict[str, Any]:
        """Extract shape-based features"""
        features = {}
        
        height, width = image.shape[:2]
        features["aspect_ratio"] = width / height
        features["dimensions"] = (width, height)
        
        # Detect document corners
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        corners = cv2.goodFeaturesToTrack(gray, 4, 0.01, 100)
        
        if corners is not None and len(corners) >= 4:
            features["has_clear_corners"] = True
            features["detected_features"] = features.get("detected_features", [])
            features["detected_features"].append("Clear Corners")
        
        return features
    
    def _extract_pattern_features(self, image: np.ndarray) -> Dict[str, Any]:
        """Extract pattern-based features (barcodes, QR codes, etc.)"""
        features = {}
        
        # Detect barcodes
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        
        # Simple barcode detection using gradients
        gradX = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=1)
        gradY = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=1)
        gradient = cv2.subtract(gradX, gradY)
        gradient = cv2.convertScaleAbs(gradient)
        
        # Threshold and find barcode-like regions
        blurred = cv2.blur(gradient, (9, 9))
        _, thresh = cv2.threshold(blurred, 225, 255, cv2.THRESH_BINARY)
        
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (21, 7))
        closed = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)
        
        contours, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        barcode_regions = []
        for contour in contours:
            area = cv2.contourArea(contour)
            if area > 1000:  # Filter small regions
                x, y, w, h = cv2.boundingRect(contour)
                aspect_ratio = w / h
                
                # Barcodes typically have specific aspect ratios
                if 1.5 < aspect_ratio < 5 or 0.2 < aspect_ratio < 0.67:
                    barcode_regions.append((x, y, w, h))
        
        if barcode_regions:
            features["has_barcode"] = True
            features["barcode_regions"] = barcode_regions
            features["detected_features"] = features.get("detected_features", [])
            features["detected_features"].append("Barcode/QR")
        
        return features
    
    def _get_model_predictions(self, image: np.ndarray) -> Dict[str, float]:
        """Get CNN model predictions"""
        # Convert to PIL Image
        pil_image = Image.fromarray(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))
        
        # Apply transforms
        input_tensor = self.transform(pil_image)
        input_batch = input_tensor.unsqueeze(0)
        
        # Get predictions
        with torch.no_grad():
            output = self.model(input_batch)
            probabilities = torch.nn.functional.softmax(output, dim=1)
        
        # Map to document types
        probs = probabilities[0].numpy()
        doc_types = list(DocumentType)
        
        predictions = {}
        for i, doc_type in enumerate(doc_types):
            if i < len(probs):
                predictions[doc_type.value] = float(probs[i])
        
        return predictions
    
    def _match_templates(self, features: Dict[str, Any]) -> Dict[str, float]:
        """Match features against templates"""
        scores = {}
        
        for template_id, template in self.templates.items():
            score = 0.0
            weight_sum = 0.0
            
            # Match aspect ratio
            if "aspect_ratio" in features:
                ar_diff = abs(features["aspect_ratio"] - template.aspect_ratio)
                ar_score = max(0, 1 - ar_diff * 2)
                score += ar_score * 0.3
                weight_sum += 0.3
            
            # Match color scheme
            if "dominant_colors" in features:
                color_score = self._compare_colors(
                    features["dominant_colors"],
                    template.color_scheme
                )
                score += color_score * 0.2
                weight_sum += 0.2
            
            # Match detected features
            if "detected_features" in features:
                feature_matches = sum(
                    1 for f in features["detected_features"]
                    if f in template.key_features
                )
                feature_score = feature_matches / max(len(template.key_features), 1)
                score += feature_score * 0.3
                weight_sum += 0.3
            
            # Match MRZ presence
            if template.mrz_format:
                if features.get("has_mrz", False):
                    score += 0.2
                weight_sum += 0.2
            
            # Normalize score
            if weight_sum > 0:
                scores[template.type.value] = score / weight_sum
            else:
                scores[template.type.value] = 0.0
        
        return scores
    
    def _compare_colors(self, colors1: List[Tuple], colors2: List[Tuple]) -> float:
        """Compare two sets of colors"""
        if not colors1 or not colors2:
            return 0.0
        
        max_score = 0.0
        
        for c1 in colors1:
            for c2 in colors2:
                # Calculate color distance
                dist = np.sqrt(sum((a - b) ** 2 for a, b in zip(c1, c2)))
                # Normalize to 0-1 (max distance is sqrt(3 * 255^2))
                similarity = 1 - (dist / 441.67)
                max_score = max(max_score, similarity)
        
        return max_score
    
    def _combine_scores(self, model_scores: Dict[str, float], 
                       template_scores: Dict[str, float]) -> Dict[str, float]:
        """Combine model and template matching scores"""
        combined = {}
        
        # Weight: 70% model, 30% template matching
        model_weight = 0.7
        template_weight = 0.3
        
        all_types = set(model_scores.keys()) | set(template_scores.keys())
        
        for doc_type in all_types:
            model_score = model_scores.get(doc_type, 0.0)
            template_score = template_scores.get(doc_type, 0.0)
            combined[doc_type] = (model_score * model_weight + 
                                 template_score * template_weight)
        
        return combined
    
    def _get_top_prediction(self, scores: Dict[str, float]) -> Tuple[DocumentType, float]:
        """Get top prediction from scores"""
        if not scores:
            return DocumentType.UNKNOWN, 0.0
        
        top_type = max(scores, key=scores.get)
        confidence = scores[top_type]
        
        # Map string to enum
        try:
            doc_type = DocumentType(top_type)
        except ValueError:
            doc_type = DocumentType.UNKNOWN
        
        return doc_type, confidence
    
    def _find_best_template(self, doc_type: DocumentType, 
                           features: Dict[str, Any]) -> str:
        """Find best matching template for document type"""
        best_template_id = None
        best_score = 0.0
        
        for template_id, template in self.templates.items():
            if template.type == doc_type:
                # Simple scoring based on feature matches
                score = 0.0
                
                if "aspect_ratio" in features:
                    ar_diff = abs(features["aspect_ratio"] - template.aspect_ratio)
                    score += max(0, 1 - ar_diff)
                
                if score > best_score:
                    best_score = score
                    best_template_id = template_id
        
        return best_template_id or "unknown"
    
    def get_template(self, template_id: str) -> Optional[DocumentTemplate]:
        """Get template by ID"""
        return self.templates.get(template_id)
    
    def validate_document(self, image: np.ndarray, 
                         classification: ClassificationResult) -> Dict[str, Any]:
        """
        Validate document against template requirements
        
        Args:
            image: Document image
            classification: Classification result
            
        Returns:
            Validation results
        """
        template = self.get_template(classification.template_id)
        if not template:
            return {"valid": False, "errors": ["Template not found"]}
        
        validation_results = {
            "valid": True,
            "errors": [],
            "warnings": [],
            "checks": {}
        }
        
        # Check aspect ratio
        height, width = image.shape[:2]
        aspect_ratio = width / height
        if abs(aspect_ratio - template.aspect_ratio) > 0.1:
            validation_results["warnings"].append(
                f"Aspect ratio mismatch: expected {template.aspect_ratio:.2f}, got {aspect_ratio:.2f}"
            )
        validation_results["checks"]["aspect_ratio"] = abs(aspect_ratio - template.aspect_ratio) <= 0.1
        
        # Check for required features
        features = self._extract_features(image)
        detected = set(features.get("detected_features", []))
        required = set(template.key_features[:3])  # Check top 3 key features
        
        missing = required - detected
        if missing:
            validation_results["errors"].append(
                f"Missing required features: {', '.join(missing)}"
            )
            validation_results["valid"] = False
        validation_results["checks"]["required_features"] = len(missing) == 0
        
        # Check confidence threshold
        if classification.confidence < 0.9:
            validation_results["warnings"].append(
                f"Low confidence score: {classification.confidence:.2f}"
            )
        validation_results["checks"]["confidence"] = classification.confidence >= 0.9
        
        return validation_results

# Export main components
__all__ = ["DocumentClassifier", "DocumentType", "ClassificationResult", "DocumentTemplate"]