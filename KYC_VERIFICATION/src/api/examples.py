"""
API Usage Examples
Demonstrates how to use the KYC Verification API endpoints
"""

import json
import base64
import requests
from typing import Dict, Any
from pathlib import Path


class KYCAPIClient:
    """Simple client for KYC Verification API"""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        """Initialize API client"""
        self.base_url = base_url
        self.session = requests.Session()
        self.session.headers.update({
            "Content-Type": "application/json",
            "Accept": "application/json"
        })
    
    def validate_document(self, image_path: str) -> Dict[str, Any]:
        """
        Validate a document image
        
        Args:
            image_path: Path to document image file
            
        Returns:
            Validation response
        """
        # Read and encode image
        with open(image_path, "rb") as f:
            image_data = f.read()
        image_base64 = f"data:image/jpeg;base64,{base64.b64encode(image_data).decode()}"
        
        # Prepare request
        payload = {
            "image_base64": image_base64,
            "document_type": "PHILIPPINE_ID",
            "metadata": {"source": "example"}
        }
        
        # Send request
        response = self.session.post(
            f"{self.base_url}/validate",
            json=payload
        )
        response.raise_for_status()
        
        return response.json()
    
    def extract_data(self, image_path: str) -> Dict[str, Any]:
        """
        Extract data from document
        
        Args:
            image_path: Path to document image file
            
        Returns:
            Extraction response
        """
        # Read and encode image
        with open(image_path, "rb") as f:
            image_data = f.read()
        image_base64 = f"data:image/jpeg;base64,{base64.b64encode(image_data).decode()}"
        
        # Prepare request
        payload = {
            "image_base64": image_base64,
            "extract_face": True,
            "extract_mrz": True,
            "extract_barcode": True
        }
        
        # Send request
        response = self.session.post(
            f"{self.base_url}/extract",
            json=payload
        )
        response.raise_for_status()
        
        return response.json()
    
    def calculate_risk_score(self, extracted_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Calculate risk score
        
        Args:
            extracted_data: Data from extraction endpoint
            
        Returns:
            Scoring response
        """
        payload = {
            "document_data": extracted_data,
            "device_info": {
                "ip": "120.29.100.50",
                "user_agent": "Mozilla/5.0",
                "device_id": "dev_example"
            }
        }
        
        response = self.session.post(
            f"{self.base_url}/score",
            json=payload
        )
        response.raise_for_status()
        
        return response.json()
    
    def make_decision(self, risk_score: float, extracted_data: Dict, validation: Dict) -> Dict[str, Any]:
        """
        Make final decision
        
        Args:
            risk_score: Risk score from scoring
            extracted_data: Extracted document data
            validation: Validation results
            
        Returns:
            Decision response
        """
        payload = {
            "risk_score": risk_score,
            "extracted_data": extracted_data,
            "validation_result": validation
        }
        
        response = self.session.post(
            f"{self.base_url}/decide",
            json=payload
        )
        response.raise_for_status()
        
        return response.json()
    
    def verify_with_issuer(self, document_type: str, document_number: str, personal_info: Dict) -> Dict[str, Any]:
        """
        Verify document with issuer
        
        Args:
            document_type: Type of document
            document_number: Document ID number
            personal_info: Personal information to verify
            
        Returns:
            Issuer verification response
        """
        payload = {
            "document_type": document_type,
            "document_number": document_number,
            "personal_info": personal_info
        }
        
        response = self.session.post(
            f"{self.base_url}/issuer/verify",
            json=payload
        )
        response.raise_for_status()
        
        return response.json()
    
    def screen_aml(self, full_name: str, birth_date: str = None) -> Dict[str, Any]:
        """
        Screen for AML/sanctions
        
        Args:
            full_name: Full name to screen
            birth_date: Date of birth (optional)
            
        Returns:
            AML screening response
        """
        payload = {
            "full_name": full_name,
            "birth_date": birth_date,
            "nationality": "PH",
            "screening_level": "standard"
        }
        
        response = self.session.post(
            f"{self.base_url}/aml/screen",
            json=payload
        )
        response.raise_for_status()
        
        return response.json()
    
    def complete_kyc(self, image_path: str, selfie_path: str = None) -> Dict[str, Any]:
        """
        Complete KYC verification in one call
        
        Args:
            image_path: Path to document image
            selfie_path: Path to selfie image (optional)
            
        Returns:
            Complete KYC response
        """
        # Read and encode document image
        with open(image_path, "rb") as f:
            image_data = f.read()
        image_base64 = f"data:image/jpeg;base64,{base64.b64encode(image_data).decode()}"
        
        # Read and encode selfie if provided
        selfie_base64 = None
        if selfie_path:
            with open(selfie_path, "rb") as f:
                selfie_data = f.read()
            selfie_base64 = f"data:image/jpeg;base64,{base64.b64encode(selfie_data).decode()}"
        
        # Prepare request
        payload = {
            "image_base64": image_base64,
            "selfie_base64": selfie_base64,
            "document_type": "PHILIPPINE_ID",
            "personal_info": {
                "full_name": "JUAN DELA CRUZ",
                "birth_date": "1990-01-01"
            },
            "device_info": {
                "ip": "120.29.100.50",
                "user_agent": "Mozilla/5.0",
                "device_id": "dev_example"
            },
            "session_id": "sess_example_123"
        }
        
        response = self.session.post(
            f"{self.base_url}/complete",
            json=payload
        )
        response.raise_for_status()
        
        return response.json()
    
    def get_health(self) -> Dict[str, Any]:
        """Get service health status"""
        response = self.session.get(f"{self.base_url}/health")
        response.raise_for_status()
        return response.json()
    
    def get_ready(self) -> Dict[str, Any]:
        """Get service readiness status"""
        response = self.session.get(f"{self.base_url}/ready")
        response.raise_for_status()
        return response.json()
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get service metrics"""
        response = self.session.get(f"{self.base_url}/metrics")
        response.raise_for_status()
        return response.json()


def example_basic_flow():
    """Example: Basic KYC verification flow"""
    print("\n" + "="*60)
    print("EXAMPLE: Basic KYC Verification Flow")
    print("="*60 + "\n")
    
    # Initialize client
    client = KYCAPIClient()
    
    # Sample image path (would be actual document in production)
    image_path = "./sample_document.jpg"
    
    # Check if sample exists, create if not
    if not Path(image_path).exists():
        print("Creating sample document...")
        import sys
        sys.path.append("../..")
        from main import KYCVerificationSystem
        system = KYCVerificationSystem()
        system.generate_sample_image(image_path)
    
    try:
        # Step 1: Validate document
        print("1. Validating document...")
        validation = client.validate_document(image_path)
        print(f"   Valid: {validation['valid']}")
        print(f"   Quality Score: {validation['quality_score']:.2%}")
        print(f"   Document Type: {validation['document_type']}")
        
        # Step 2: Extract data
        print("\n2. Extracting data...")
        extraction = client.extract_data(image_path)
        print(f"   Success: {extraction['success']}")
        print(f"   OCR Fields: {list(extraction['extracted_data']['ocr_text'].keys())}")
        
        # Step 3: Calculate risk score
        print("\n3. Calculating risk score...")
        scoring = client.calculate_risk_score(extraction['extracted_data'])
        print(f"   Risk Score: {scoring['risk_score']}")
        print(f"   Risk Level: {scoring['risk_level']}")
        
        # Step 4: Make decision
        print("\n4. Making decision...")
        decision = client.make_decision(
            scoring['risk_score'],
            extraction['extracted_data'],
            validation
        )
        print(f"   Decision: {decision['decision']}")
        print(f"   Confidence: {decision['confidence']:.2%}")
        print(f"   Reasons: {', '.join(decision['reasons'])}")
        
        print("\n✅ Basic flow completed successfully!")
        
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")


def example_complete_flow():
    """Example: Complete KYC verification in one call"""
    print("\n" + "="*60)
    print("EXAMPLE: Complete KYC Verification (Single Call)")
    print("="*60 + "\n")
    
    # Initialize client
    client = KYCAPIClient()
    
    # Sample image path
    image_path = "./sample_document.jpg"
    
    # Check if sample exists
    if not Path(image_path).exists():
        print("Creating sample document...")
        import sys
        sys.path.append("../..")
        from main import KYCVerificationSystem
        system = KYCVerificationSystem()
        system.generate_sample_image(image_path)
    
    try:
        # Complete KYC in one call
        print("Performing complete KYC verification...")
        result = client.complete_kyc(image_path)
        
        print(f"\n📊 Results:")
        print(f"   Session ID: {result['session_id']}")
        print(f"   Decision: {result['decision']}")
        print(f"   Risk Score: {result['risk_score']}")
        print(f"   Risk Level: {result['risk_level']}")
        print(f"   Processing Time: {result['processing_time_ms']}ms")
        
        print("\n✅ Complete flow finished successfully!")
        
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")


def example_health_checks():
    """Example: Health and metrics endpoints"""
    print("\n" + "="*60)
    print("EXAMPLE: Health and Metrics Checks")
    print("="*60 + "\n")
    
    # Initialize client
    client = KYCAPIClient()
    
    try:
        # Health check
        print("1. Health Check:")
        health = client.get_health()
        print(f"   Status: {health['status']}")
        print(f"   Version: {health['version']}")
        print(f"   Uptime: {health['uptime_seconds']:.1f} seconds")
        
        # Readiness check
        print("\n2. Readiness Check:")
        ready = client.get_ready()
        print(f"   Ready: {ready['ready']}")
        print(f"   Dependencies:")
        for dep, status in ready['dependencies'].items():
            print(f"     - {dep}: {'✅' if status else '❌'}")
        
        # Metrics
        print("\n3. Metrics:")
        metrics = client.get_metrics()['metrics']
        print(f"   Requests Total: {metrics['requests_total']}")
        print(f"   Error Rate: {metrics['error_rate']:.3%}")
        print(f"   P95 Latency: {metrics['p95_latency_ms']}ms")
        
        print("\n✅ Health checks completed!")
        
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")


def main():
    """Run all examples"""
    print("\n" + "🚀 KYC VERIFICATION API EXAMPLES 🚀")
    
    # Note: Ensure API server is running before executing examples
    print("\nNote: Make sure the API server is running at http://localhost:8000")
    print("Run with: uvicorn src.api.app:app --reload")
    
    input("\nPress Enter to run examples...")
    
    # Run examples
    example_health_checks()
    example_basic_flow()
    example_complete_flow()
    
    print("\n" + "="*60)
    print("✅ All examples completed!")
    print("="*60)


if __name__ == "__main__":
    main()
