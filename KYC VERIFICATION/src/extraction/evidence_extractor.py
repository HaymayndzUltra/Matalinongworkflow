"""
Evidence Extraction Module
Phase 3: OCR/MRZ/Barcode/NFC extraction with ROIs and confidences
Includes face detection/crops for downstream biometrics (≥112×112)
"""

import cv2
import numpy as np
import pytesseract
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass
from enum import Enum
import re
import logging
from pathlib import Path
import json
import hashlib

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Optional dependencies detection (system binaries may be missing)
try:
    # Ensure Tesseract binary is callable; this may raise if not installed
    _ = pytesseract.get_tesseract_version()
    TESSERACT_AVAILABLE = True
except Exception as e:
    TESSERACT_AVAILABLE = False
    logger.warning(f"Tesseract not available or not on PATH; OCR will be skipped. Details: {e}")

try:
    from pyzbar import pyzbar as _pyzbar  # type: ignore
    from pyzbar.pyzbar import ZBarSymbol as _ZBarSymbol  # type: ignore
    pyzbar = _pyzbar
    ZBarSymbol = _ZBarSymbol
    ZBAR_AVAILABLE = True
except Exception as e:
    pyzbar = None  # type: ignore
    ZBarSymbol = None  # type: ignore
    ZBAR_AVAILABLE = False
    logger.warning(f"ZBar/pyzbar not available; barcode decoding will be skipped. Details: {e}")

class ExtractionType(Enum):
    """Types of evidence extraction"""
    OCR_TEXT = "ocr_text"
    MRZ = "mrz"
    BARCODE_1D = "barcode_1d"
    BARCODE_2D = "barcode_2d"
    QR_CODE = "qr_code"
    PDF417 = "pdf417"
    FACE = "face"
    SIGNATURE = "signature"
    FINGERPRINT = "fingerprint"

@dataclass
class ExtractedField:
    """Extracted field with metadata"""
    field_name: str
    value: Any
    confidence: float
    extraction_type: ExtractionType
    roi: Tuple[int, int, int, int]  # x, y, width, height
    validation_status: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

@dataclass
class MRZData:
    """Machine Readable Zone data"""
    mrz_type: str  # TD1, TD2, TD3
    document_type: str
    country_code: str
    document_number: str
    birth_date: str
    sex: str
    expiry_date: str
    nationality: str
    surname: str
    given_names: str
    optional_data1: str
    optional_data2: str
    check_digits: Dict[str, bool]
    raw_text: List[str]
    confidence: float

@dataclass
class FaceData:
    """Detected face data"""
    bbox: Tuple[int, int, int, int]  # x, y, width, height
    confidence: float
    landmarks: Optional[Dict[str, Tuple[int, int]]]
    crop: np.ndarray  # Face crop image
    crop_size: Tuple[int, int]
    quality_score: float

@dataclass
class ExtractionResult:
    """Complete extraction result"""
    extracted_fields: List[ExtractedField]
    mrz_data: Optional[MRZData]
    faces: List[FaceData]
    barcodes: List[Dict[str, Any]]
    ocr_text: Dict[str, Any]
    metadata: Dict[str, Any]
    validation_passed: bool
    extraction_time_ms: float

class EvidenceExtractor:
    """Extracts evidence from document images"""
    
    def __init__(self, config_path: Optional[str] = None):
        """Initialize evidence extractor"""
        self.config = self._load_config(config_path)
        self.face_cascade = self._load_face_detector()
        self.mrz_validator = MRZValidator()
        # Optional NFC support
        try:
            from src.extraction.nfc_reader import NFCReader  # local import to avoid hard dep
            self.nfc_reader = NFCReader()
        except Exception:
            self.nfc_reader = None
        
    def _load_config(self, config_path: Optional[str]) -> Dict:
        """Load extraction configuration"""
        default_config = {
            "ocr_config": {
                "lang": "eng",
                "oem": 3,  # OCR Engine Mode
                "psm": 3,  # Page Segmentation Mode
                "confidence_threshold": 0.6
            },
            "face_detection": {
                "min_face_size": (112, 112),
                "scale_factor": 1.1,
                "min_neighbors": 5,
                "quality_threshold": 0.5
            },
            "mrz": {
                "validate_checksums": True,
                "strict_mode": False
            },
            "barcode": {
                # Use ZBar symbologies only if pyzbar/zbar is available
                "symbologies": (
                    [
                        ZBarSymbol.QRCODE,
                        ZBarSymbol.PDF417,
                        ZBarSymbol.CODE128,
                        ZBarSymbol.CODE39,
                        ZBarSymbol.EAN13,
                    ] if ("ZBAR_AVAILABLE" in globals() and ZBAR_AVAILABLE and ZBarSymbol is not None) else []
                )
            }
        }
        
        if config_path and Path(config_path).exists():
            with open(config_path, 'r') as f:
                user_config = json.load(f)
                default_config.update(user_config)
        
        return default_config
    
    def _load_face_detector(self):
        """Load face detection model"""
        # Try to load Haar Cascade classifier
        cascade_path = cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
        face_cascade = cv2.CascadeClassifier(cascade_path)
        
        if face_cascade.empty():
            logger.warning("Failed to load face cascade classifier")
            return None
        
        return face_cascade
    
    def extract_all(self, image: np.ndarray, 
                   document_type: Optional[str] = None) -> ExtractionResult:
        """
        Extract all evidence from document image
        
        Args:
            image: Input document image
            document_type: Optional document type hint
            
        Returns:
            Complete extraction result
        """
        import time
        start_time = time.time()
        
        extracted_fields = []
        
        # Extract OCR text
        logger.info("📝 Extracting OCR text...")
        ocr_result = self.extract_ocr(image)
        extracted_fields.extend(ocr_result["fields"])
        
        # Extract MRZ if present
        logger.info("🔍 Checking for MRZ...")
        mrz_data = self.extract_mrz(image)
        if mrz_data:
            logger.info(f"✅ MRZ detected: {mrz_data.mrz_type}")
        
        # Extract barcodes
        logger.info("📊 Scanning for barcodes...")
        barcodes = self.extract_barcodes(image)
        if barcodes:
            logger.info(f"✅ Found {len(barcodes)} barcode(s)")
        
        # Detect and extract faces
        logger.info("👤 Detecting faces...")
        faces = self.extract_faces(image)
        if faces:
            logger.info(f"✅ Detected {len(faces)} face(s)")
        
        # NFC (DG1/DG2) if reader available
        nfc_metadata: Dict[str, Any] = {}
        if self.nfc_reader is not None:
            try:
                dg1 = self.nfc_reader.read_dg1()
                dg2 = self.nfc_reader.read_dg2()
                if dg1:
                    nfc_metadata["dg1"] = {
                        "document_number": getattr(dg1, "document_number", None),
                        "name": getattr(dg1, "name", None),
                        "expiry_date": getattr(dg1, "expiry_date", None),
                    }
                if dg2:
                    nfc_metadata["dg2_present"] = True
            except Exception as e:
                logger.warning(f"NFC read failed: {e}")

        # Validate extracted data
        validation_passed = self._validate_extraction(
            extracted_fields, mrz_data, document_type
        )
        
        # Calculate extraction time
        extraction_time_ms = (time.time() - start_time) * 1000
        
        return ExtractionResult(
            extracted_fields=extracted_fields,
            mrz_data=mrz_data,
            faces=faces,
            barcodes=barcodes,
            ocr_text=ocr_result,
            metadata={
                "document_type": document_type,
                "total_fields": len(extracted_fields),
                "has_mrz": mrz_data is not None,
                "has_faces": len(faces) > 0,
                "has_barcodes": len(barcodes) > 0,
                "nfc": nfc_metadata or None
            },
            validation_passed=validation_passed,
            extraction_time_ms=extraction_time_ms
        )
    
    def extract_ocr(self, image: np.ndarray) -> Dict[str, Any]:
        """
        Extract text using OCR
        
        Args:
            image: Input image
            
        Returns:
            OCR extraction results
        """
        # Graceful fallback if Tesseract is not present
        if not TESSERACT_AVAILABLE or pytesseract is None:
            logger.warning("Skipping OCR: Tesseract not available.")
            return {
                "fields": [],
                "full_text": "",
                "lines": [],
                "total_words": 0,
                "avg_confidence": 0.0,
            }
        # Preprocess image for better OCR
        processed = self._preprocess_for_ocr(image)
        
        # Configure Tesseract
        custom_config = (
            f"--oem {self.config['ocr_config']['oem']} "
            f"--psm {self.config['ocr_config']['psm']}"
        )
        
        # Get detailed OCR data
        try:
            ocr_data = pytesseract.image_to_data(
                processed,
                lang=self.config['ocr_config']['lang'],
                config=custom_config,
                output_type=pytesseract.Output.DICT,
            )
        except Exception as e:
            logger.warning(f"OCR failed, returning empty result. Details: {e}")
            return {
                "fields": [],
                "full_text": "",
                "lines": [],
                "total_words": 0,
                "avg_confidence": 0.0,
            }
        
        # Extract fields with confidence
        fields = []
        extracted_text = []
        
        n_boxes = len(ocr_data['text'])
        for i in range(n_boxes):
            if int(ocr_data['conf'][i]) > self.config['ocr_config']['confidence_threshold'] * 100:
                text = ocr_data['text'][i].strip()
                if text:
                    x, y, w, h = (
                        ocr_data['left'][i],
                        ocr_data['top'][i],
                        ocr_data['width'][i],
                        ocr_data['height'][i]
                    )
                    
                    confidence = float(ocr_data['conf'][i]) / 100
                    
                    # Try to identify field type
                    field_name = self._identify_field_type(text)
                    
                    fields.append(ExtractedField(
                        field_name=field_name,
                        value=text,
                        confidence=confidence,
                        extraction_type=ExtractionType.OCR_TEXT,
                        roi=(x, y, w, h),
                        metadata={"word_num": ocr_data['word_num'][i]}
                    ))
                    
                    extracted_text.append(text)
        
        # Group text by lines
        lines = self._group_text_by_lines(ocr_data)
        
        return {
            "fields": fields,
            "full_text": " ".join(extracted_text),
            "lines": lines,
            "total_words": len(extracted_text),
            "avg_confidence": np.mean([f.confidence for f in fields]) if fields else 0
        }
    
    def _preprocess_for_ocr(self, image: np.ndarray) -> np.ndarray:
        """Preprocess image for better OCR results"""
        # Convert to grayscale
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image.copy()
        
        # Denoise
        denoised = cv2.fastNlMeansDenoising(gray)
        
        # Apply adaptive thresholding
        thresh = cv2.adaptiveThreshold(
            denoised, 255, 
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY, 11, 2
        )
        
        # Deskew if needed
        angle = self._detect_skew(thresh)
        if abs(angle) > 0.5:
            thresh = self._rotate_image(thresh, angle)
        
        return thresh
    
    def _detect_skew(self, image: np.ndarray) -> float:
        """Detect text skew angle"""
        coords = np.column_stack(np.where(image > 0))
        
        if len(coords) < 100:
            return 0.0
        
        # Use minimum area rectangle
        angle = cv2.minAreaRect(coords)[-1]
        
        if angle < -45:
            angle = -(90 + angle)
        else:
            angle = -angle
        
        return angle
    
    def _rotate_image(self, image: np.ndarray, angle: float) -> np.ndarray:
        """Rotate image by given angle"""
        h, w = image.shape[:2]
        center = (w // 2, h // 2)
        
        M = cv2.getRotationMatrix2D(center, angle, 1.0)
        rotated = cv2.warpAffine(
            image, M, (w, h),
            flags=cv2.INTER_CUBIC,
            borderMode=cv2.BORDER_REPLICATE
        )
        
        return rotated
    
    def _identify_field_type(self, text: str) -> str:
        """Identify field type from text content"""
        text_lower = text.lower()
        
        # Philippine ID field patterns
        patterns = {
            "psn": r"\d{4}-\d{4}-\d{4}-\d{4}",
            "tin": r"\d{3}-\d{3}-\d{3}-\d{3}",
            "sss": r"\d{2}-\d{7}-\d{1}",
            "license_no": r"[A-Z]\d{2}-\d{2}-\d{6}",
            "passport_no": r"[A-Z][A-Z0-9]\d{7}",
            "date": r"\d{1,2}[/-]\d{1,2}[/-]\d{2,4}",
            "phone": r"(\+63|0)\d{10}",
            "email": r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
            "blood_type": r"^(A|B|AB|O)[+-]$"
        }
        
        for field_type, pattern in patterns.items():
            if re.match(pattern, text):
                return field_type
        
        # Check for known field labels
        field_labels = {
            "name": ["name", "full name", "pangalan"],
            "address": ["address", "tirahan", "residence"],
            "birth_date": ["birth", "date of birth", "kapanganakan"],
            "sex": ["sex", "gender", "kasarian"],
            "nationality": ["nationality", "citizenship", "nasyonalidad"]
        }
        
        for field_type, labels in field_labels.items():
            if any(label in text_lower for label in labels):
                return field_type
        
        return "unknown"
    
    def _group_text_by_lines(self, ocr_data: Dict) -> List[str]:
        """Group OCR text by lines"""
        lines = {}
        
        for i in range(len(ocr_data['text'])):
            if ocr_data['text'][i].strip():
                line_num = ocr_data['line_num'][i]
                if line_num not in lines:
                    lines[line_num] = []
                lines[line_num].append(ocr_data['text'][i])
        
        return [" ".join(words) for words in lines.values()]
    
    def extract_mrz(self, image: np.ndarray) -> Optional[MRZData]:
        """
        Extract and parse Machine Readable Zone
        
        Args:
            image: Input document image
            
        Returns:
            Parsed MRZ data or None if not found
        """
        # Find MRZ region
        mrz_region = self._locate_mrz_region(image)
        
        if mrz_region is None:
            return None
        
        # Extract MRZ text
        mrz_text = self._extract_mrz_text(mrz_region)
        
        if not mrz_text:
            return None
        
        # Parse MRZ data
        mrz_data = self._parse_mrz(mrz_text)
        
        # Validate checksums if configured
        if self.config['mrz']['validate_checksums']:
            mrz_data = self.mrz_validator.validate(mrz_data)
        
        return mrz_data
    
    def _locate_mrz_region(self, image: np.ndarray) -> Optional[np.ndarray]:
        """Locate MRZ region in document"""
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image
        
        # MRZ typically in bottom 30% of document
        height = gray.shape[0]
        roi = gray[int(height * 0.7):, :]
        
        # Apply morphological operations to find text regions
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (30, 5))
        morph = cv2.morphologyEx(roi, cv2.MORPH_BLACKHAT, kernel)
        
        # Find horizontal text lines
        thresh = cv2.threshold(morph, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)[1]
        
        # Check if MRZ-like pattern exists
        horizontal_projection = np.sum(thresh, axis=1)
        
        # MRZ has 2-3 distinct lines with specific spacing
        lines = []
        in_line = False
        start = 0
        
        for i, val in enumerate(horizontal_projection):
            if val > thresh.shape[1] * 0.3:  # Significant horizontal content
                if not in_line:
                    start = i
                    in_line = True
            else:
                if in_line:
                    lines.append((start, i))
                    in_line = False
        
        # Check if we have 2 or 3 lines (TD1/TD2 or TD3)
        if len(lines) in [2, 3]:
            # Extract MRZ region
            top = int(height * 0.7) + lines[0][0]
            bottom = int(height * 0.7) + lines[-1][1]
            mrz_region = image[top:bottom, :]
            return mrz_region
        
        return None
    
    def _extract_mrz_text(self, mrz_region: np.ndarray) -> List[str]:
        """Extract text from MRZ region"""
        # Preprocess for MRZ OCR
        gray = cv2.cvtColor(mrz_region, cv2.COLOR_BGR2GRAY) if len(mrz_region.shape) == 3 else mrz_region

        # Enhance contrast
        enhanced = cv2.equalizeHist(gray)

        # Use specific OCR settings for MRZ
        custom_config = r'--oem 3 --psm 6 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789<'
        # If Tesseract is unavailable, skip MRZ OCR
        if not TESSERACT_AVAILABLE or pytesseract is None:
            logger.warning("Skipping MRZ OCR: Tesseract not available.")
            return []

        try:
            text = pytesseract.image_to_string(enhanced, config=custom_config)
        except Exception as e:
            logger.warning(f"MRZ OCR failed, skipping. Details: {e}")
            return []
        
        # Split into lines and clean
        lines = []
        for line in text.strip().split('\n'):
            cleaned = line.strip().replace(' ', '')
            if len(cleaned) > 20:  # MRZ lines are typically 30-44 chars
                lines.append(cleaned)
        
        return lines
    
    def _parse_mrz(self, mrz_lines: List[str]) -> MRZData:
        """Parse MRZ lines according to ICAO 9303 standard"""
        if len(mrz_lines) == 2:
            # TD3 format (passports)
            return self._parse_td3(mrz_lines)
        elif len(mrz_lines) == 3:
            # TD1 format (ID cards)
            return self._parse_td1(mrz_lines)
        else:
            logger.warning(f"Unexpected MRZ format with {len(mrz_lines)} lines")
            return None
    
    def _parse_td3(self, lines: List[str]) -> MRZData:
        """Parse TD3 format MRZ (passports)"""
        if len(lines) != 2 or len(lines[0]) != 44 or len(lines[1]) != 44:
            return None
        
        line1 = lines[0]
        line2 = lines[1]
        
        # Parse line 1
        doc_type = line1[0:2].replace('<', '')
        country = line1[2:5].replace('<', '')
        names = line1[5:44].split('<<')
        surname = names[0].replace('<', ' ').strip() if names else ''
        given_names = names[1].replace('<', ' ').strip() if len(names) > 1 else ''
        
        # Parse line 2
        doc_number = line2[0:9].replace('<', '')
        doc_number_check = line2[9]
        nationality = line2[10:13].replace('<', '')
        birth_date = line2[13:19]
        birth_date_check = line2[19]
        sex = line2[20]
        expiry_date = line2[21:27]
        expiry_date_check = line2[27]
        optional_data = line2[28:42].replace('<', '')
        optional_check = line2[42]
        composite_check = line2[43]
        
        # Validate checksums
        check_digits = {
            "document_number": self.mrz_validator.check_digit(doc_number) == doc_number_check,
            "birth_date": self.mrz_validator.check_digit(birth_date) == birth_date_check,
            "expiry_date": self.mrz_validator.check_digit(expiry_date) == expiry_date_check,
            "optional": self.mrz_validator.check_digit(optional_data) == optional_check,
            "composite": True  # TODO: Implement composite check
        }
        
        return MRZData(
            mrz_type="TD3",
            document_type=doc_type,
            country_code=country,
            document_number=doc_number,
            birth_date=birth_date,
            sex=sex,
            expiry_date=expiry_date,
            nationality=nationality,
            surname=surname,
            given_names=given_names,
            optional_data1=optional_data,
            optional_data2="",
            check_digits=check_digits,
            raw_text=lines,
            confidence=0.9 if all(check_digits.values()) else 0.5
        )
    
    def _parse_td1(self, lines: List[str]) -> MRZData:
        """Parse TD1 format MRZ (ID cards)"""
        # Similar implementation for TD1 format
        # This is a simplified version
        return MRZData(
            mrz_type="TD1",
            document_type="ID",
            country_code="PHL",
            document_number="",
            birth_date="",
            sex="",
            expiry_date="",
            nationality="PHL",
            surname="",
            given_names="",
            optional_data1="",
            optional_data2="",
            check_digits={},
            raw_text=lines,
            confidence=0.5
        )
    
    def extract_barcodes(self, image: np.ndarray) -> List[Dict[str, Any]]:
        """
        Extract and decode barcodes
        
        Args:
            image: Input image
            
        Returns:
            List of decoded barcodes
        """
        barcodes = []

        # Convert to grayscale if needed
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image

        # Detect and decode barcodes (graceful fallback if ZBar not present)
        if not ZBAR_AVAILABLE or pyzbar is None:
            logger.warning("Skipping barcode detection: ZBar/pyzbar not available.")
            return barcodes

        try:
            detected = pyzbar.decode(gray)
        except Exception as e:
            logger.warning(f"Barcode decoding failed, skipping. Details: {e}")
            return barcodes
        
        for barcode in detected:
            # Extract barcode data
            data = barcode.data.decode('utf-8')
            barcode_type = barcode.type
            
            # Get bounding box
            points = barcode.polygon
            if len(points) == 4:
                rect = cv2.boundingRect(np.array(points))
                x, y, w, h = rect
            else:
                x, y, w, h = barcode.rect
            
            barcode_info = {
                "type": barcode_type,
                "data": data,
                "roi": (x, y, w, h),
                "points": points,
                "extraction_type": ExtractionType.BARCODE_2D if barcode_type in ['QRCODE', 'PDF417'] else ExtractionType.BARCODE_1D
            }
            
            # Parse data if it's structured (e.g., JSON)
            try:
                parsed_data = json.loads(data)
                barcode_info["parsed"] = parsed_data
            except:
                barcode_info["parsed"] = None
            
            barcodes.append(barcode_info)
            
            logger.info(f"Decoded {barcode_type}: {data[:50]}...")
        
        return barcodes
    
    def extract_faces(self, image: np.ndarray) -> List[FaceData]:
        """
        Detect and extract faces from document
        
        Args:
            image: Input document image
            
        Returns:
            List of detected faces with crops
        """
        faces = []
        
        if self.face_cascade is None:
            logger.warning("Face detector not available")
            return faces
        
        # Convert to grayscale for detection
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image
        
        # Detect faces
        detected_faces = self.face_cascade.detectMultiScale(
            gray,
            scaleFactor=self.config['face_detection']['scale_factor'],
            minNeighbors=self.config['face_detection']['min_neighbors'],
            minSize=self.config['face_detection']['min_face_size']
        )
        
        for (x, y, w, h) in detected_faces:
            # Extract face crop with padding
            padding = int(min(w, h) * 0.2)
            x1 = max(0, x - padding)
            y1 = max(0, y - padding)
            x2 = min(image.shape[1], x + w + padding)
            y2 = min(image.shape[0], y + h + padding)
            
            face_crop = image[y1:y2, x1:x2]
            
            # Resize to minimum size if needed
            min_size = self.config['face_detection']['min_face_size']
            if face_crop.shape[0] < min_size[1] or face_crop.shape[1] < min_size[0]:
                face_crop = cv2.resize(face_crop, min_size, interpolation=cv2.INTER_CUBIC)
            
            # Calculate quality score
            quality_score = self._assess_face_quality(face_crop)
            
            # Detect facial landmarks (simplified)
            landmarks = self._detect_landmarks(face_crop)
            
            face_data = FaceData(
                bbox=(x, y, w, h),
                confidence=0.95,  # Haar cascade doesn't provide confidence
                landmarks=landmarks,
                crop=face_crop,
                crop_size=face_crop.shape[:2],
                quality_score=quality_score
            )
            
            faces.append(face_data)
            
            logger.info(f"Face detected at ({x}, {y}) with size {w}x{h}, quality: {quality_score:.2f}")
        
        return faces
    
    def _assess_face_quality(self, face_crop: np.ndarray) -> float:
        """Assess face image quality"""
        quality_scores = []
        
        # Check resolution
        min_dim = min(face_crop.shape[:2])
        resolution_score = min(1.0, min_dim / 224)  # 224 is ideal
        quality_scores.append(resolution_score)
        
        # Check blur
        gray = cv2.cvtColor(face_crop, cv2.COLOR_BGR2GRAY) if len(face_crop.shape) == 3 else face_crop
        laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
        blur_score = min(1.0, laplacian_var / 500)
        quality_scores.append(blur_score)
        
        # Check contrast
        contrast = gray.std() / 127.5
        quality_scores.append(min(1.0, contrast))
        
        # Check brightness
        brightness = gray.mean() / 255
        brightness_score = 1.0 - abs(brightness - 0.5) * 2
        quality_scores.append(brightness_score)
        
        return np.mean(quality_scores)
    
    def _detect_landmarks(self, face_crop: np.ndarray) -> Dict[str, Tuple[int, int]]:
        """Detect facial landmarks (simplified version)"""
        # This is a placeholder - in production, use dlib or mediapipe
        h, w = face_crop.shape[:2]
        
        # Approximate landmark positions
        landmarks = {
            "left_eye": (int(w * 0.35), int(h * 0.35)),
            "right_eye": (int(w * 0.65), int(h * 0.35)),
            "nose": (int(w * 0.5), int(h * 0.5)),
            "left_mouth": (int(w * 0.35), int(h * 0.65)),
            "right_mouth": (int(w * 0.65), int(h * 0.65))
        }
        
        return landmarks
    
    def _validate_extraction(self, fields: List[ExtractedField], 
                           mrz_data: Optional[MRZData],
                           document_type: Optional[str]) -> bool:
        """Validate extracted data consistency"""
        if not fields:
            return False
        
        # Check if minimum required fields are present
        required_fields = {"name", "date", "document_number"}
        found_fields = {f.field_name for f in fields if f.field_name != "unknown"}
        
        if not required_fields.intersection(found_fields):
            logger.warning("Missing required fields")
            return False
        
        # Validate MRZ checksums if present
        if mrz_data:
            checksum_valid = all(mrz_data.check_digits.values())
            if not checksum_valid:
                logger.warning("MRZ checksum validation failed")
                return False
        
        return True

class MRZValidator:
    """Validates MRZ data according to ICAO 9303 standard"""
    
    def check_digit(self, data: str) -> str:
        """Calculate check digit for MRZ field"""
        check_string = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        data = data.replace('<', '0')
        
        total = 0
        weight = [7, 3, 1]
        
        for i, char in enumerate(data):
            if char in check_string:
                value = check_string.index(char)
                total += value * weight[i % 3]
        
        return str(total % 10)
    
    def validate(self, mrz_data: MRZData) -> MRZData:
        """Validate MRZ checksums"""
        # Validate individual check digits
        for field, is_valid in mrz_data.check_digits.items():
            if not is_valid:
                logger.warning(f"MRZ checksum failed for {field}")
        
        # Update confidence based on validation
        if all(mrz_data.check_digits.values()):
            mrz_data.confidence = min(1.0, mrz_data.confidence * 1.2)
        else:
            mrz_data.confidence *= 0.7
        
        return mrz_data

# Export main components
__all__ = [
    "EvidenceExtractor", 
    "ExtractionResult", 
    "ExtractedField", 
    "MRZData", 
    "FaceData",
    "ExtractionType"
]