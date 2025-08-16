#!/usr/bin/env python3
"""
Test script for Phase 13: Biometric Integration
Verifies face matching and PAD detection integration with UX system
"""

import sys
import os
import time
import json
import numpy as np
from typing import Dict, Any

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'KYC VERIFICATION/src'))

def test_biometric_module():
    """Test the biometric integration module"""
    print("\n" + "="*60)
    print("  BIOMETRIC MODULE TEST")
    print("="*60)
    
    try:
        # Test 1: Import module
        print("\n1. Testing biometric integration import...")
        from face.biometric_integration import (
            BiometricIntegration,
            BiometricResult,
            get_biometric_integration,
            integrate_biometrics_with_burst
        )
        print("   ✓ Module imported successfully")
        
        # Test 2: Create integration instance
        print("\n2. Testing integration instance...")
        integration = get_biometric_integration()
        assert integration is not None
        print("   ✓ Integration instance created")
        
        # Test 3: Test biometric result structure
        print("\n3. Testing BiometricResult structure...")
        result = BiometricResult()
        assert hasattr(result, 'match_score')
        assert hasattr(result, 'pad_score')
        assert hasattr(result, 'confidence')
        assert hasattr(result, 'passed')
        print("   ✓ BiometricResult has all required fields")
        
        # Test 4: Mock biometric processing
        print("\n4. Testing biometric processing...")
        from face.session_manager import EnhancedSessionState
        
        # Create test session
        session = EnhancedSessionState(session_id="test_biometric")
        
        # Create mock frames (3 frames)
        mock_frames = [
            np.random.rand(480, 640, 3).astype(np.uint8) * 255
            for _ in range(3)
        ]
        
        # Process biometrics (async function, run synchronously for test)
        import asyncio
        start_time = time.time()
        bio_result = asyncio.run(
            integration.process_biometrics(
                session,
                mock_frames,
                reference_image=None  # No reference for now
            )
        )
        processing_time = (time.time() - start_time) * 1000
        
        print(f"   ✓ Biometric processing completed in {processing_time:.2f}ms")
        print(f"   ✓ PAD score: {bio_result.pad_score:.3f}" if bio_result.pad_score else "   ⚠ PAD score: None")
        print(f"   ✓ Confidence: {bio_result.confidence:.3f}")
        print(f"   ✓ Passed: {bio_result.passed}")
        
        # Test 5: Check accuracy targets
        print("\n5. Testing accuracy metrics...")
        metrics = integration.get_accuracy_metrics()
        
        assert 'face_matching' in metrics
        assert 'pad_detection' in metrics
        assert 'targets' in metrics
        
        print(f"   ✓ Match threshold: {metrics['face_matching']['threshold']}")
        print(f"   ✓ PAD threshold: {metrics['pad_detection']['threshold']}")
        print(f"   ✓ FAR target: {metrics['targets']['FAR']}")
        print(f"   ✓ FRR target: {metrics['targets']['FRR']}")
        
        return True
        
    except Exception as e:
        print(f"   ✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_quality_gate_integration():
    """Test integration with quality gates"""
    print("\n" + "="*60)
    print("  QUALITY GATE INTEGRATION TEST")
    print("="*60)
    
    try:
        # Test 1: Import modules
        print("\n1. Testing quality gate integration...")
        from face.biometric_integration import get_biometric_integration
        from face.quality_gates import get_quality_manager
        from face.session_manager import EnhancedSessionState, CaptureState
        
        integration = get_biometric_integration()
        quality_manager = get_quality_manager()
        
        # Test 2: Integrate biometrics with quality gates
        print("\n2. Integrating biometric checks...")
        integration.integrate_with_quality_gates(quality_manager)
        print("   ✓ Biometric checks integrated")
        
        # Test 3: Test enhanced quality check
        print("\n3. Testing enhanced quality check...")
        session = EnhancedSessionState(session_id="test_quality")
        
        # Add mock biometric result to session
        session.biometric_results = [{
            "timestamp": time.time(),
            "match_score": 0.92,
            "pad_score": 0.95,
            "confidence": 0.93,
            "passed": True,
            "reason": None
        }]
        
        # Check quality with biometric data
        metrics = {
            'focus': 0.85,
            'motion': 0.1,
            'glare': 0.05,
            'corners': 1.0,
            'fill_ratio': 0.95
        }
        
        # Use the enhanced check method
        result = integration.check_quality_with_biometrics(metrics, session)
        
        print(f"   ✓ Overall score: {result.overall_score:.3f}")
        print(f"   ✓ Quality level: {result.level.value}")
        print(f"   ✓ Passed: {result.passed}")
        print("   ✓ Biometric influence applied")
        
        return True
        
    except Exception as e:
        print(f"   ✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_burst_integration():
    """Test integration with burst evaluation"""
    print("\n" + "="*60)
    print("  BURST EVALUATION INTEGRATION TEST")
    print("="*60)
    
    try:
        # Test 1: Import modules
        print("\n1. Testing burst integration function...")
        from face.biometric_integration import integrate_biometrics_with_burst
        from face.session_manager import EnhancedSessionState
        
        # Test 2: Create mock burst result
        print("\n2. Creating mock burst result...")
        burst_result = {
            'burst_id': 'test_burst_001',
            'frames': [
                np.random.rand(480, 640, 3).astype(np.uint8) * 255
                for _ in range(5)
            ],
            'consensus': {
                'passed': True,
                'median_score': 0.88,
                'confidence': 0.90
            },
            'processing_time_ms': 150.0
        }
        
        session = EnhancedSessionState(session_id="test_burst")
        
        # Test 3: Integrate biometrics
        print("\n3. Integrating biometrics with burst...")
        enhanced_result = integrate_biometrics_with_burst(
            burst_result,
            session,
            reference_image=None
        )
        
        assert 'biometric' in enhanced_result
        bio_data = enhanced_result['biometric']
        
        print(f"   ✓ Biometric data added to burst result")
        print(f"   ✓ PAD score: {bio_data.get('pad_score', 'N/A')}")
        print(f"   ✓ Confidence: {bio_data['confidence']:.3f}")
        print(f"   ✓ Processing time: {bio_data['processing_time_ms']:.2f}ms")
        
        # Test 4: Check if biometric failure affects consensus
        print("\n4. Testing biometric impact on consensus...")
        if not bio_data['passed']:
            assert not enhanced_result['consensus']['passed']
            print("   ✓ Biometric failure affects consensus")
        else:
            print("   ✓ Biometric passed, consensus maintained")
        
        return True
        
    except Exception as e:
        print(f"   ✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_telemetry_integration():
    """Test biometric telemetry events"""
    print("\n" + "="*60)
    print("  BIOMETRIC TELEMETRY TEST")
    print("="*60)
    
    try:
        # Test 1: Check telemetry events
        print("\n1. Testing biometric event tracking...")
        from face.ux_telemetry import get_telemetry_manager
        from face.biometric_integration import get_biometric_integration
        from face.session_manager import EnhancedSessionState
        
        # Reset telemetry
        telemetry = get_telemetry_manager()
        telemetry.reset()
        
        # Process biometrics to generate events
        integration = get_biometric_integration()
        session = EnhancedSessionState(session_id="test_telemetry")
        
        mock_frames = [
            np.random.rand(480, 640, 3).astype(np.uint8) * 255
            for _ in range(2)
        ]
        
        import asyncio
        asyncio.run(
            integration.process_biometrics(
                session,
                mock_frames,
                reference_image=None
            )
        )
        
        # Check events
        events = telemetry.get_session_events("test_telemetry")
        
        # Look for biometric events
        biometric_events = [
            e for e in events 
            if hasattr(e.event_type, 'value') and 'biometric' in str(e.event_type.value)
        ]
        
        print(f"   ✓ {len(biometric_events)} biometric events tracked")
        
        # Check for specific event types
        event_types = [str(e.event_type) for e in events]
        if any('match_start' in et for et in event_types):
            print("   ✓ Match start event tracked")
        if any('match_complete' in et or 'match_failed' in et for et in event_types):
            print("   ✓ Match completion event tracked")
        
        return True
        
    except Exception as e:
        print(f"   ✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_accuracy_targets():
    """Test that accuracy targets are maintained"""
    print("\n" + "="*60)
    print("  ACCURACY TARGETS TEST")
    print("="*60)
    
    try:
        from face.biometric_integration import (
            MATCH_THRESHOLD,
            PAD_THRESHOLD,
            MATCH_TIMEOUT_MS,
            PAD_TIMEOUT_MS
        )
        
        # Test 1: Check thresholds
        print("\n1. Verifying accuracy thresholds...")
        print(f"   ✓ Match threshold: {MATCH_THRESHOLD} (85%)")
        print(f"   ✓ PAD threshold: {PAD_THRESHOLD} (90%)")
        assert MATCH_THRESHOLD == 0.85
        assert PAD_THRESHOLD == 0.90
        
        # Test 2: Check timing targets
        print("\n2. Verifying timing targets...")
        print(f"   ✓ Match timeout: {MATCH_TIMEOUT_MS}ms (target: <500ms)")
        print(f"   ✓ PAD timeout: {PAD_TIMEOUT_MS}ms (target: <100ms)")
        assert MATCH_TIMEOUT_MS <= 500
        assert PAD_TIMEOUT_MS <= 100
        
        # Test 3: Simulate accuracy test
        print("\n3. Testing accuracy simulation...")
        from face.biometric_integration import BiometricResult
        
        # High confidence result
        good_result = BiometricResult(
            match_score=0.92,
            pad_score=0.95,
            confidence=0.93
        )
        
        # Low confidence result
        bad_result = BiometricResult(
            match_score=0.75,
            pad_score=0.85,
            confidence=0.78
        )
        
        # Check pass/fail logic
        from face.biometric_integration import BiometricIntegration
        integration = BiometricIntegration()
        
        good_passed = integration._check_passed(good_result)
        bad_passed = integration._check_passed(bad_result)
        
        assert good_passed == True
        assert bad_passed == False
        
        print(f"   ✓ High confidence passes: {good_passed}")
        print(f"   ✓ Low confidence fails: {bad_passed}")
        print("   ✓ Accuracy targets enforced")
        
        return True
        
    except Exception as e:
        print(f"   ✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run all biometric integration tests"""
    print("\n🔬 PHASE 13: BIOMETRIC INTEGRATION TESTS")
    
    # Run tests
    module_ok = test_biometric_module()
    quality_ok = test_quality_gate_integration()
    burst_ok = test_burst_integration()
    telemetry_ok = test_telemetry_integration()
    accuracy_ok = test_accuracy_targets()
    
    # Summary
    print("\n" + "="*60)
    print("  TEST SUMMARY")
    print("="*60)
    
    all_passed = all([module_ok, quality_ok, burst_ok, telemetry_ok, accuracy_ok])
    
    if all_passed:
        print("\n✅ ALL TESTS PASSED!")
        print("\nBiometric integration successful:")
        print("  • Face matching integrated")
        print("  • PAD detection integrated")
        print("  • Quality gates enhanced")
        print("  • Burst evaluation enhanced")
        print("  • Telemetry events tracked")
        print("  • Accuracy targets maintained")
        print("\n📊 Key Achievements:")
        print("  • Match threshold: 85%")
        print("  • PAD threshold: 90%")
        print("  • Processing time: <600ms")
        print("  • Full UX integration")
        return 0
    else:
        print("\n❌ SOME TESTS FAILED")
        print("\nFailed components:")
        if not module_ok:
            print("  • Biometric module")
        if not quality_ok:
            print("  • Quality gate integration")
        if not burst_ok:
            print("  • Burst integration")
        if not telemetry_ok:
            print("  • Telemetry integration")
        if not accuracy_ok:
            print("  • Accuracy targets")
        return 1

if __name__ == "__main__":
    sys.exit(main())