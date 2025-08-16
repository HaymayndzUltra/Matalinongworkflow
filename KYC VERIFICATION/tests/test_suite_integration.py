#!/usr/bin/env python3
"""
Integration Tests - Testing how components work together
"""

import unittest
import sys
import os
from unittest.mock import Mock, patch
from datetime import datetime
import json
import asyncio

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../src'))

class TestFullCaptureFlow(unittest.TestCase):
    """Test complete document capture flow integration"""
    
    def setUp(self):
        from face.handlers import get_or_create_session
        from face.session_manager import CaptureState
        from face.quality_gates import get_quality_manager
        from face.capture_flow import get_capture_manager
        from face.messages import get_message_manager
        
        self.session = get_or_create_session("integration-test-123")
        self.quality_manager = get_quality_manager()
        self.capture_manager = get_capture_manager()
        self.message_manager = get_message_manager()
        self.CaptureState = CaptureState
    
    def test_front_capture_flow(self):
        """Test complete front capture flow"""
        # Start capture
        self.capture_manager.start_capture(self.session.session_id)
        
        # Simulate document detection
        self.session.transition_to(self.CaptureState.LOCKED)
        self.assertEqual(self.session.current_state, self.CaptureState.LOCKED)
        
        # Check quality gates
        metrics = {
            "focus": 8.5,
            "motion": 0.2,
            "glare": 0.02,
            "corners": 0.98,
            "fill_ratio": 0.75
        }
        quality_result = self.quality_manager.check_quality(metrics)
        self.assertIsNone(quality_result.cancel_reason)
        
        # Start countdown
        self.session.transition_to(self.CaptureState.COUNTDOWN)
        
        # Capture image
        self.session.transition_to(self.CaptureState.CAPTURED)
        
        # Get appropriate message
        message = self.message_manager.get_message("front_captured", self.session.language)
        self.assertIsNotNone(message)
        
        # Confirm capture
        self.session.transition_to(self.CaptureState.CONFIRM)
        
        # Advance capture flow
        self.capture_manager.advance_step(self.session.session_id)
        progress = self.capture_manager.get_progress(self.session.session_id)
        self.assertGreater(progress.steps_completed, 0)
    
    def test_back_capture_with_anti_selfie(self):
        """Test back capture flow with anti-selfie guidance"""
        # Set up for back capture
        self.session.current_side = "back"
        self.session.transition_to(self.CaptureState.FLIP_TO_BACK)
        
        # Get anti-selfie guidance
        guidance = self.capture_manager.get_guidance(
            self.session.session_id,
            "back_searching"
        )
        self.assertIn("warning", guidance)
        self.assertIn("selfie", guidance["warning"].lower())
        
        # Continue with back capture
        self.session.transition_to(self.CaptureState.BACK_SEARCHING)
        
        # Complete back capture
        self.session.transition_to(self.CaptureState.COMPLETE)
        self.assertEqual(self.session.current_state, self.CaptureState.COMPLETE)
        
        # Check completion metrics
        metrics = self.capture_manager.get_metrics(self.session.session_id)
        self.assertIsNotNone(metrics.back_time_ms)
    
    def test_cancel_on_jitter_integration(self):
        """Test cancel-on-jitter during countdown"""
        # Get to countdown state
        self.session.transition_to(self.CaptureState.LOCKED)
        self.session.transition_to(self.CaptureState.COUNTDOWN)
        
        # Simulate high motion (jitter)
        metrics = {
            "focus": 8.5,
            "motion": 0.6,  # High motion
            "glare": 0.02,
            "corners": 0.98,
            "fill_ratio": 0.75
        }
        
        # Check quality gates
        quality_result = self.quality_manager.check_quality(metrics)
        self.assertIsNotNone(quality_result.cancel_reason)
        
        # State should rollback
        if quality_result.cancel_reason:
            self.session.transition_to(self.CaptureState.SEARCHING)
            self.assertEqual(self.session.current_state, self.CaptureState.SEARCHING)
        
        # Get error message
        error_msg = self.message_manager.get_message(
            "quality_motion",
            self.session.language
        )
        self.assertIsNotNone(error_msg)


class TestExtractionWithStreaming(unittest.TestCase):
    """Test extraction with real-time streaming integration"""
    
    def setUp(self):
        from face.extraction import ExtractionProcessor
        from face.streaming import get_stream_manager
        from face.session_manager import get_session_manager
        
        self.extraction = ExtractionProcessor()
        self.stream_manager = get_stream_manager()
        self.session = get_session_manager().create_session("extract-test")
    
    def test_extraction_with_streaming_updates(self):
        """Test extraction sends streaming updates"""
        # Create stream connection
        connection = self.stream_manager.create_connection(self.session.session_id)
        
        # Define streaming callback
        events_received = []
        def streaming_callback(event_type, data):
            events_received.append({
                "type": event_type,
                "data": data
            })
            # Simulate sending to stream
            self.stream_manager.send_event(
                self.session.session_id,
                {"type": event_type, "data": data}
            )
        
        # Start extraction with streaming
        mock_image = b"test_image_data"
        result = self.extraction.extract_document(
            mock_image,
            document_type="drivers_license",
            streaming_callback=streaming_callback
        )
        
        # Check extraction completed
        self.assertIsNotNone(result)
        self.assertIn("overall_confidence", result)
        
        # Check streaming events were sent
        self.assertGreater(len(events_received), 0)
        
        # Check event types
        event_types = [e["type"] for e in events_received]
        self.assertIn("EXTRACT_START", event_types)
        self.assertIn("EXTRACT_RESULT", event_types)
        
        # Check stream buffer has events
        self.assertGreater(len(connection.event_queue), 0)
    
    def test_extraction_field_by_field_updates(self):
        """Test field-by-field extraction updates"""
        events = []
        
        def callback(event_type, data):
            if event_type == "EXTRACT_FIELD":
                events.append(data)
        
        mock_image = b"test_image_data"
        result = self.extraction.extract_document(
            mock_image,
            streaming_callback=callback
        )
        
        # Check we got field updates
        self.assertGreater(len(events), 0)
        
        # Check each field update has required data
        for event in events:
            self.assertIn("field", event)
            self.assertIn("value", event)
            self.assertIn("confidence", event)


class TestBiometricWithQualityGates(unittest.TestCase):
    """Test biometric integration with quality gates"""
    
    def setUp(self):
        from face.biometric_integration import get_biometric_integration
        from face.quality_gates import get_quality_manager
        from face.session_manager import get_session_manager
        
        self.biometric = get_biometric_integration()
        self.quality_manager = get_quality_manager()
        self.session = get_session_manager().create_session("biometric-test")
    
    def test_biometric_affects_quality_score(self):
        """Test biometric results affect overall quality score"""
        # Initial quality check
        metrics = {
            "focus": 8.5,
            "motion": 0.2,
            "glare": 0.02,
            "corners": 0.98,
            "fill_ratio": 0.75
        }
        
        initial_result = self.quality_manager.check_quality(metrics)
        initial_score = initial_result.overall_score
        
        # Process biometrics
        biometric_result = self.biometric.process_biometrics(
            reference_image=b"ref",
            live_image=b"live",
            session=self.session
        )
        
        # Integrate with quality gates
        self.biometric.integrate_with_quality_gates(self.quality_manager)
        
        # Check quality again with biometric data
        enhanced_result = self.biometric.check_quality_with_biometrics(
            metrics,
            self.session
        )
        
        # Score should be different (weighted with biometric confidence)
        self.assertNotEqual(initial_score, enhanced_result.overall_score)
    
    def test_attack_detection_triggers_cancel(self):
        """Test PAD attack detection triggers quality cancel"""
        # Simulate attack detection
        self.session.biometric_results = [{
            "passed": False,
            "reason": "Presentation attack detected",
            "confidence": 0.3
        }]
        
        metrics = {
            "focus": 8.5,
            "motion": 0.2,
            "glare": 0.02,
            "corners": 0.98,
            "fill_ratio": 0.75
        }
        
        # Check with biometric integration
        result = self.biometric.check_quality_with_biometrics(
            metrics,
            self.session
        )
        
        # Should be cancelled due to attack
        self.assertIsNotNone(result.cancel_reason)
        self.assertIn("attack", result.english_message.lower())


class TestAccessibilityIntegration(unittest.TestCase):
    """Test accessibility integration with other components"""
    
    def setUp(self):
        from face.accessibility import get_accessibility_adapter
        from face.session_manager import get_session_manager
        from face.messages import get_message_manager
        
        self.adapter = get_accessibility_adapter()
        self.session = get_session_manager().create_session("a11y-test")
        self.message_manager = get_message_manager()
    
    def test_reduced_motion_affects_timing(self):
        """Test reduced motion mode affects animation timings"""
        # Set reduced motion preference
        settings = self.adapter.detect_settings(
            headers={"Prefer": "reduced-motion"}
        )
        self.assertTrue(settings.reduced_motion)
        
        # Create normal response
        response = {
            "state": "locked",
            "timing": {
                "animation_flash_check_ms": 180,
                "animation_card_flip_ms": 400
            }
        }
        
        # Apply accessibility adaptations
        adapted = self.adapter.adapt_response(response, settings)
        
        # Animations should be instant
        self.assertEqual(adapted["timing"]["animation_flash_check_ms"], 0)
        self.assertEqual(adapted["timing"]["animation_card_flip_ms"], 0)
    
    def test_screen_reader_adds_aria_labels(self):
        """Test screen reader mode adds ARIA labels"""
        settings = self.adapter.detect_settings(
            headers={"X-Accessibility-Mode": "screen-reader"}
        )
        
        response = {
            "state": "searching",
            "message": "I-frame ang ID"
        }
        
        adapted = self.adapter.adapt_response(response, settings)
        
        # Should have screen reader content
        self.assertIn("accessibility", adapted)
        self.assertIn("aria_label", adapted["accessibility"])
        self.assertIn("screen_reader_text", adapted["accessibility"])
    
    def test_simplified_language_mode(self):
        """Test simplified language for cognitive accessibility"""
        settings = self.adapter.detect_settings(
            query_params={"simplified_language": "true"}
        )
        
        response = {
            "message": "Please ensure the document is clearly visible within the frame"
        }
        
        adapted = self.adapter.adapt_response(response, settings)
        
        # Should have simpler instructions
        self.assertIn("instructions", adapted)
        self.assertIn("simplified", adapted["instructions"])


class TestTelemetryIntegration(unittest.TestCase):
    """Test telemetry integration across components"""
    
    def setUp(self):
        from face.ux_telemetry import get_telemetry_manager
        from face.session_manager import get_session_manager
        from face.capture_flow import get_capture_manager
        
        self.telemetry = get_telemetry_manager()
        self.session = get_session_manager().create_session("telemetry-test")
        self.capture_manager = get_capture_manager()
    
    def test_state_transitions_tracked(self):
        """Test all state transitions are tracked in telemetry"""
        from face.session_manager import CaptureState
        
        # Clear existing events
        self.telemetry.clear_session_events(self.session.session_id)
        
        # Perform state transitions
        self.session.transition_to(CaptureState.LOCKED)
        self.session.transition_to(CaptureState.COUNTDOWN)
        self.session.transition_to(CaptureState.CAPTURED)
        
        # Get telemetry events
        events = self.telemetry.get_session_events(self.session.session_id)
        
        # Check state transitions were tracked
        event_types = [e.event_type for e in events]
        self.assertIn("state.searching_to_locked", event_types)
        self.assertIn("state.locked_to_countdown", event_types)
        self.assertIn("state.countdown_to_captured", event_types)
    
    def test_performance_metrics_calculated(self):
        """Test performance metrics are calculated correctly"""
        # Simulate capture flow
        self.capture_manager.start_capture(self.session.session_id)
        
        # Advance through steps
        for _ in range(7):  # Front capture steps
            self.capture_manager.advance_step(self.session.session_id)
        
        # Get performance metrics
        metrics = self.telemetry.get_performance_metrics(self.session.session_id)
        
        # Check metrics exist
        self.assertIn("time_to_lock_ms", metrics)
        self.assertIn("time_to_capture_ms", metrics)
        self.assertIn("total_time_ms", metrics)
        
        # Check overhead is minimal
        self.assertLess(metrics.get("telemetry_overhead_ms", 0), 1.0)


def run_integration_tests():
    """Run all integration tests"""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add all test classes
    suite.addTests(loader.loadTestsFromTestCase(TestFullCaptureFlow))
    suite.addTests(loader.loadTestsFromTestCase(TestExtractionWithStreaming))
    suite.addTests(loader.loadTestsFromTestCase(TestBiometricWithQualityGates))
    suite.addTests(loader.loadTestsFromTestCase(TestAccessibilityIntegration))
    suite.addTests(loader.loadTestsFromTestCase(TestTelemetryIntegration))
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_integration_tests()
    sys.exit(0 if success else 1)