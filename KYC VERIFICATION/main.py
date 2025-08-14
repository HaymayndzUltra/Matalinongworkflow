#!/usr/bin/env python3
"""
KYC Identity Verification System - Main Entry Point
Demonstrates the complete KYC verification pipeline
"""

import sys
import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional
import numpy as np
import cv2
from datetime import datetime, timezone, timedelta

# Import our modules
from src.capture.quality_analyzer import CaptureQualityAnalyzer, QualityMetrics
from src.classification.document_classifier import DocumentClassifier, DocumentType

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class KYCVerificationSystem:
    """Main KYC verification system orchestrator"""
    
    def __init__(self, config_path: Optional[str] = None):
        """Initialize KYC system with all components"""
        logger.info("🚀 Initializing KYC Verification System...")
        
        # Load configuration
        self.config = self._load_config(config_path)
        
        # Initialize components
        self.quality_analyzer = CaptureQualityAnalyzer()
        self.document_classifier = DocumentClassifier()
        
        # Track processing metrics
        self.metrics = {
            "total_processed": 0,
            "approved": 0,
            "rejected": 0,
            "manual_review": 0,
            "avg_processing_time": 0
        }
        
        logger.info("✅ KYC Verification System initialized successfully")
    
    def _load_config(self, config_path: Optional[str]) -> Dict[str, Any]:
        """Load system configuration"""
        default_config = {
            "min_quality_score": 0.95,
            "min_confidence": 0.90,
            "enable_auto_correction": True,
            "save_results": True,
            "results_path": "./results"
        }
        
        if config_path and Path(config_path).exists():
            with open(config_path, 'r') as f:
                user_config = json.load(f)
                default_config.update(user_config)
        
        return default_config
    
    def process_document(self, image_path: str) -> Dict[str, Any]:
        """
        Process a single document through the KYC pipeline
        
        Args:
            image_path: Path to document image
            
        Returns:
            Processing results dictionary
        """
        logger.info(f"📄 Processing document: {image_path}")
        
        # Start timing
        start_time = datetime.now()
        
        # Initialize result
        result = {
            "status": "processing",
            "document_path": image_path,
            "timestamp": self._get_timestamp(),
            "phases": {}
        }
        
        try:
            # Load image
            image = cv2.imread(image_path)
            if image is None:
                raise ValueError(f"Failed to load image: {image_path}")
            
            # Phase 1: Capture Quality Analysis
            logger.info("🔍 Phase 1: Analyzing capture quality...")
            quality_result = self._analyze_quality(image)
            result["phases"]["quality"] = quality_result
            
            if not quality_result["passed"]:
                result["status"] = "rejected"
                result["reason"] = "Poor image quality"
                logger.warning(f"❌ Document rejected: {result['reason']}")
                return result
            
            # Auto-correct orientation if enabled
            if self.config["enable_auto_correction"] and quality_result["orientation_angle"] != 0:
                logger.info("🔄 Auto-correcting image orientation...")
                image = self.quality_analyzer.auto_correct_orientation(
                    image, -quality_result["orientation_angle"]
                )
            
            # Phase 2: Document Classification
            logger.info("🎯 Phase 2: Classifying document type...")
            classification_result = self._classify_document(image)
            result["phases"]["classification"] = classification_result
            
            if classification_result["document_type"] == "Unknown":
                result["status"] = "rejected"
                result["reason"] = "Unknown document type"
                logger.warning(f"❌ Document rejected: {result['reason']}")
                return result
            
            # Phase 3: Document Validation
            logger.info("✔️ Phase 3: Validating document...")
            validation_result = self._validate_document(image, classification_result)
            result["phases"]["validation"] = validation_result
            
            if not validation_result["valid"]:
                result["status"] = "manual_review"
                result["reason"] = "Document validation issues"
                logger.warning(f"⚠️ Document sent for manual review: {validation_result['errors']}")
            else:
                result["status"] = "approved"
                logger.info("✅ Document approved")
            
            # Calculate processing time
            end_time = datetime.now()
            processing_time = (end_time - start_time).total_seconds()
            result["processing_time_seconds"] = processing_time
            
            # Update metrics
            self._update_metrics(result)
            
            # Save results if configured
            if self.config["save_results"]:
                self._save_results(result)
            
            logger.info(f"✅ Document processing completed in {processing_time:.2f} seconds")
            
        except Exception as e:
            logger.error(f"❌ Error processing document: {str(e)}")
            result["status"] = "error"
            result["error"] = str(e)
        
        return result
    
    def _analyze_quality(self, image: np.ndarray) -> Dict[str, Any]:
        """Analyze image quality"""
        metrics, hints = self.quality_analyzer.analyze_frame(image)
        
        passed = metrics.overall_score >= self.config["min_quality_score"]
        
        return {
            "passed": passed,
            "overall_score": metrics.overall_score,
            "resolution": metrics.resolution,
            "blur_score": metrics.blur_score,
            "glare_score": metrics.glare_score,
            "brightness_score": metrics.brightness_score,
            "contrast_score": metrics.contrast_score,
            "orientation_angle": metrics.orientation_angle,
            "document_coverage": metrics.document_coverage,
            "hints": [
                {
                    "issue": hint.issue.value,
                    "severity": hint.severity,
                    "message": hint.message,
                    "suggestion": hint.suggestion
                }
                for hint in hints
            ]
        }
    
    def _classify_document(self, image: np.ndarray) -> Dict[str, Any]:
        """Classify document type"""
        classification = self.document_classifier.classify(image)
        
        return {
            "document_type": classification.document_type.value,
            "country": classification.country,
            "confidence": classification.confidence,
            "template_id": classification.template_id,
            "features_detected": classification.features_detected,
            "metadata": classification.metadata
        }
    
    def _validate_document(self, image: np.ndarray, classification: Dict[str, Any]) -> Dict[str, Any]:
        """Validate document against template"""
        # Create a mock ClassificationResult for validation
        from src.classification.document_classifier import ClassificationResult, DocumentType
        
        mock_classification = ClassificationResult(
            document_type=DocumentType(classification["document_type"]),
            country=classification["country"],
            confidence=classification["confidence"],
            probabilities={},
            features_detected=classification["features_detected"],
            template_id=classification["template_id"],
            metadata=classification["metadata"]
        )
        
        validation = self.document_classifier.validate_document(image, mock_classification)
        return validation
    
    def _update_metrics(self, result: Dict[str, Any]):
        """Update processing metrics"""
        self.metrics["total_processed"] += 1
        
        if result["status"] == "approved":
            self.metrics["approved"] += 1
        elif result["status"] == "rejected":
            self.metrics["rejected"] += 1
        elif result["status"] == "manual_review":
            self.metrics["manual_review"] += 1
        
        # Update average processing time
        if "processing_time_seconds" in result:
            n = self.metrics["total_processed"]
            avg = self.metrics["avg_processing_time"]
            self.metrics["avg_processing_time"] = (avg * (n-1) + result["processing_time_seconds"]) / n
    
    def _save_results(self, result: Dict[str, Any]):
        """Save processing results to file"""
        results_dir = Path(self.config["results_path"])
        results_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"kyc_result_{timestamp}.json"
        filepath = results_dir / filename
        
        with open(filepath, 'w') as f:
            json.dump(result, f, indent=2, default=str)
        
        logger.info(f"💾 Results saved to: {filepath}")
    
    def _get_timestamp(self) -> str:
        """Get ISO8601 timestamp with +08:00 timezone"""
        tz = timezone(timedelta(hours=8))
        return datetime.now(tz).isoformat()
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get processing metrics"""
        return self.metrics
    
    def generate_sample_image(self, output_path: str = "./sample_document.jpg"):
        """Generate a sample document image for testing"""
        logger.info("🎨 Generating sample document image...")
        
        # Create a sample ID card image
        width, height = 856, 540  # Standard ID card aspect ratio
        
        # Create white background
        image = np.ones((height, width, 3), dtype=np.uint8) * 255
        
        # Add blue header
        cv2.rectangle(image, (0, 0), (width, 100), (168, 56, 0), -1)
        
        # Add text
        font = cv2.FONT_HERSHEY_SIMPLEX
        cv2.putText(image, "REPUBLIC OF THE PHILIPPINES", (150, 40), 
                   font, 0.8, (255, 255, 255), 2)
        cv2.putText(image, "PHILIPPINE NATIONAL ID", (200, 75), 
                   font, 0.7, (255, 255, 255), 2)
        
        # Add sample fields
        cv2.putText(image, "PSN: 1234-5678-9012-3456", (50, 150), 
                   font, 0.6, (0, 0, 0), 1)
        cv2.putText(image, "NAME: JUAN DELA CRUZ", (50, 200), 
                   font, 0.6, (0, 0, 0), 1)
        cv2.putText(image, "DATE OF BIRTH: 01/01/1990", (50, 250), 
                   font, 0.6, (0, 0, 0), 1)
        cv2.putText(image, "SEX: M", (50, 300), 
                   font, 0.6, (0, 0, 0), 1)
        cv2.putText(image, "BLOOD TYPE: O+", (200, 300), 
                   font, 0.6, (0, 0, 0), 1)
        
        # Add a sample QR code placeholder
        qr_size = 100
        qr_x, qr_y = width - qr_size - 50, height - qr_size - 50
        cv2.rectangle(image, (qr_x, qr_y), (qr_x + qr_size, qr_y + qr_size), (0, 0, 0), 2)
        
        # Add some noise pattern for QR simulation
        for i in range(10):
            for j in range(10):
                if (i + j) % 2 == 0:
                    x1 = qr_x + i * 10
                    y1 = qr_y + j * 10
                    cv2.rectangle(image, (x1, y1), (x1 + 10, y1 + 10), (0, 0, 0), -1)
        
        # Save image
        cv2.imwrite(output_path, image)
        logger.info(f"✅ Sample document saved to: {output_path}")
        
        return output_path

def main():
    """Main execution function"""
    print("\n" + "="*60)
    print("🔐 KYC IDENTITY VERIFICATION SYSTEM")
    print("="*60 + "\n")
    
    # Initialize system
    kyc_system = KYCVerificationSystem()
    
    # Check for command line arguments
    if len(sys.argv) > 1:
        image_path = sys.argv[1]
        print(f"📂 Processing provided document: {image_path}")
    else:
        # Generate sample image for demonstration
        print("📝 No document provided. Generating sample for demonstration...")
        image_path = kyc_system.generate_sample_image()
    
    # Process document
    print("\n" + "-"*60)
    print("🔄 STARTING KYC VERIFICATION PROCESS")
    print("-"*60 + "\n")
    
    result = kyc_system.process_document(image_path)
    
    # Display results
    print("\n" + "="*60)
    print("📊 VERIFICATION RESULTS")
    print("="*60)
    
    print(f"\n📌 Status: {result['status'].upper()}")
    print(f"⏱️  Processing Time: {result.get('processing_time_seconds', 0):.2f} seconds")
    
    if "phases" in result:
        # Quality Analysis Results
        if "quality" in result["phases"]:
            quality = result["phases"]["quality"]
            print(f"\n📸 Image Quality:")
            print(f"   • Overall Score: {quality['overall_score']:.2%}")
            print(f"   • Resolution: {quality['resolution'][0]}x{quality['resolution'][1]}")
            print(f"   • Blur Score: {quality['blur_score']:.2f}")
            print(f"   • Glare Score: {quality['glare_score']:.2f}")
            
            if quality["hints"]:
                print(f"   • Issues Detected:")
                for hint in quality["hints"]:
                    print(f"     - {hint['message']}")
        
        # Classification Results
        if "classification" in result["phases"]:
            classification = result["phases"]["classification"]
            print(f"\n🎯 Document Classification:")
            print(f"   • Type: {classification['document_type']}")
            print(f"   • Country: {classification['country']}")
            print(f"   • Confidence: {classification['confidence']:.2%}")
            print(f"   • Features: {', '.join(classification['features_detected'])}")
        
        # Validation Results
        if "validation" in result["phases"]:
            validation = result["phases"]["validation"]
            print(f"\n✔️ Document Validation:")
            print(f"   • Valid: {validation['valid']}")
            if validation["errors"]:
                print(f"   • Errors: {', '.join(validation['errors'])}")
            if validation["warnings"]:
                print(f"   • Warnings: {', '.join(validation['warnings'])}")
    
    # Display metrics
    metrics = kyc_system.get_metrics()
    print(f"\n📈 System Metrics:")
    print(f"   • Total Processed: {metrics['total_processed']}")
    print(f"   • Approved: {metrics['approved']}")
    print(f"   • Rejected: {metrics['rejected']}")
    print(f"   • Manual Review: {metrics['manual_review']}")
    print(f"   • Avg Processing Time: {metrics['avg_processing_time']:.2f}s")
    
    print("\n" + "="*60)
    print("✅ KYC VERIFICATION COMPLETE")
    print("="*60 + "\n")

if __name__ == "__main__":
    main()