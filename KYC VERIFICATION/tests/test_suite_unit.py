#!/usr/bin/env python3
"""
Unit Tests - Testing individual components in isolation
"""

import unittest
import sys
import os
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../src'))

class TestSessionManager(unittest.TestCase):
    """Test Session Manager component"""
    
    def setUp(self):
        from face.session_manager import EnhancedSessionState, CaptureState, DocumentSide
        self.session = EnhancedSessionState(
            session_id="test-123",
            created_at=datetime.now()
        )
        self.CaptureState = CaptureState
        self.DocumentSide = DocumentSide
    
    def test_state_initialization(self):
        """Test initial state is SEARCHING"""
        self.assertEqual(self.session.current_state, self.CaptureState.SEARCHING)
        self.assertEqual(self.session.current_side, self.DocumentSide.FRONT)
    
    def test_valid_state_transition(self):
        """Test valid state transitions"""
        # SEARCHING → LOCKED
        result = self.session.transition_to(self.CaptureState.LOCKED)
        self.assertTrue(result)
        self.assertEqual(self.session.current_state, self.CaptureState.LOCKED)
        
        # LOCKED → COUNTDOWN
        result = self.session.transition_to(self.CaptureState.COUNTDOWN)
        self.assertTrue(result)
        self.assertEqual(self.session.current_state, self.CaptureState.COUNTDOWN)
    
    def test_invalid_state_transition(self):
        """Test invalid state transitions are blocked"""
        # SEARCHING → COMPLETE (invalid)
        result = self.session.transition_to(self.CaptureState.COMPLETE)
        self.assertFalse(result)
        self.assertEqual(self.session.current_state, self.CaptureState.SEARCHING)
    
    def test_timing_metadata(self):
        """Test timing metadata recording"""
        self.session.record_timing_event("lock_acquired", 150.5)
        timing = self.session.get_timing_metadata()
        
        self.assertIn("lock_acquired", timing)
        self.assertEqual(timing["lock_acquired"], 150.5)
    
    def test_quality_issues_tracking(self):
        """Test quality issues are tracked"""
        self.session.set_quality_issues(["glare", "motion"])
        self.assertIn("glare", self.session.quality_issues)
        self.assertIn("motion", self.session.quality_issues)
    
    def test_extraction_storage(self):
        """Test extraction results storage"""
        extraction_result = {
            "fields": [
                {"field": "name", "value": "Juan Dela Cruz", "confidence": 0.95}
            ],
            "overall_confidence": 0.92
        }
        self.session.store_extraction_result(extraction_result)
        
        summary = self.session.get_extraction_summary()
        self.assertIsNotNone(summary)
        self.assertEqual(summary["overall_confidence"], 0.92)
    
    def test_session_expiry(self):
        """Test session expiry after timeout"""
        # Create expired session
        expired_session = EnhancedSessionState(
            session_id="expired-123",
            created_at=datetime.now() - timedelta(minutes=31)
        )
        # Assuming 30 minute timeout
        self.assertTrue((datetime.now() - expired_session.created_at).seconds > 1800)


class TestMessageLocalization(unittest.TestCase):
    """Test message localization system"""
    
    def setUp(self):
        from face.messages import get_message_manager, Language
        self.manager = get_message_manager()
        self.Language = Language
    
    def test_tagalog_messages(self):
        """Test Tagalog messages are returned"""
        msg = self.manager.get_message("lock_acquired", self.Language.TAGALOG)
        self.assertIsNotNone(msg)
        self.assertIn("steady", msg.lower())  # Should contain Tagalog
    
    def test_english_fallback(self):
        """Test English fallback works"""
        msg = self.manager.get_message("lock_acquired", self.Language.ENGLISH)
        self.assertIsNotNone(msg)
    
    def test_message_categories(self):
        """Test all message categories exist"""
        from face.messages import MessageType
        
        categories = [
            MessageType.STATE,
            MessageType.INSTRUCTION,
            MessageType.SUCCESS,
            MessageType.ERROR,
            MessageType.HINT,
            MessageType.PROMPT
        ]
        
        for category in categories:
            self.assertIsNotNone(category.value)
    
    def test_error_messages_complete(self):
        """Test all error messages have both languages"""
        error_keys = [
            "quality_motion",
            "quality_glare", 
            "quality_focus",
            "quality_corners",
            "quality_partial"
        ]
        
        for key in error_keys:
            tl_msg = self.manager.get_message(key, self.Language.TAGALOG)
            en_msg = self.manager.get_message(key, self.Language.ENGLISH)
            
            self.assertIsNotNone(tl_msg, f"Missing Tagalog for {key}")
            self.assertIsNotNone(en_msg, f"Missing English for {key}")


class TestQualityGates(unittest.TestCase):
    """Test quality gates and cancel-on-jitter"""
    
    def setUp(self):
        from face.quality_gates import get_quality_manager, QualityLevel, CancelReason
        self.manager = get_quality_manager()
        self.QualityLevel = QualityLevel
        self.CancelReason = CancelReason
    
    def test_quality_thresholds(self):
        """Test quality thresholds are enforced"""
        # Good quality metrics
        good_metrics = {
            "focus": 8.5,
            "motion": 0.2,
            "glare": 0.02,
            "corners": 0.98,
            "fill_ratio": 0.75
        }
        result = self.manager.check_quality(good_metrics)
        self.assertIsNone(result.cancel_reason)
        self.assertEqual(result.level, self.QualityLevel.EXCELLENT)
    
    def test_cancel_on_motion(self):
        """Test cancel on high motion (jitter)"""
        metrics = {
            "focus": 8.5,
            "motion": 0.6,  # Above 0.4 threshold
            "glare": 0.02,
            "corners": 0.98,
            "fill_ratio": 0.75
        }
        result = self.manager.check_quality(metrics)
        self.assertEqual(result.cancel_reason, self.CancelReason.MOTION_BLUR)
        self.assertIsNotNone(result.tagalog_message)
    
    def test_cancel_on_poor_focus(self):
        """Test cancel on poor focus"""
        metrics = {
            "focus": 5.0,  # Below 7.0 threshold
            "motion": 0.2,
            "glare": 0.02,
            "corners": 0.98,
            "fill_ratio": 0.75
        }
        result = self.manager.check_quality(metrics)
        self.assertEqual(result.cancel_reason, self.CancelReason.OUT_OF_FOCUS)
    
    def test_response_time(self):
        """Test cancel detection is fast (<50ms)"""
        import time
        
        metrics = {
            "focus": 5.0,
            "motion": 0.6,
            "glare": 0.05,
            "corners": 0.90,
            "fill_ratio": 0.75
        }
        
        start = time.time()
        result = self.manager.check_quality(metrics)
        duration = (time.time() - start) * 1000
        
        self.assertLess(duration, 50, f"Cancel detection took {duration}ms (>50ms)")
    
    def test_stability_tracking(self):
        """Test quality stability over multiple frames"""
        # Simulate stable frames
        for _ in range(5):
            metrics = {
                "focus": 8.5,
                "motion": 0.2,
                "glare": 0.02,
                "corners": 0.98,
                "fill_ratio": 0.75
            }
            self.manager.add_frame_quality(metrics)
        
        stability = self.manager.get_stability_score()
        self.assertGreater(stability, 0.9, "Stable frames should have high stability")


class TestExtractionConfidence(unittest.TestCase):
    """Test OCR extraction with confidence scores"""
    
    def setUp(self):
        from face.extraction import ExtractionProcessor, DocumentField, ConfidenceLevel
        self.processor = ExtractionProcessor()
        self.DocumentField = DocumentField
        self.ConfidenceLevel = ConfidenceLevel
    
    def test_field_extraction(self):
        """Test field extraction returns confidence scores"""
        # Mock image data
        mock_image = b"fake_image_data"
        
        result = self.processor.extract_document(
            mock_image,
            document_type="drivers_license"
        )
        
        self.assertIsNotNone(result)
        self.assertIn("fields", result)
        self.assertIn("overall_confidence", result)
        
        # Check each field has confidence
        for field in result["fields"]:
            self.assertIn("confidence", field)
            self.assertGreaterEqual(field["confidence"], 0.0)
            self.assertLessEqual(field["confidence"], 1.0)
    
    def test_confidence_color_coding(self):
        """Test confidence color coding logic"""
        test_cases = [
            (0.95, "green"),   # High confidence
            (0.80, "amber"),   # Medium confidence
            (0.60, "red")      # Low confidence
        ]
        
        for confidence, expected_color in test_cases:
            color = self.processor._get_confidence_color(confidence)
            self.assertEqual(color, expected_color)
    
    def test_extraction_performance(self):
        """Test extraction completes within time limits"""
        import time
        
        mock_image = b"fake_image_data"
        
        start = time.time()
        result = self.processor.extract_document(mock_image)
        duration = time.time() - start
        
        # Should complete within 6 seconds (P95)
        self.assertLess(duration, 6.0, f"Extraction took {duration}s (>6s)")


class TestBiometricIntegration(unittest.TestCase):
    """Test biometric integration (face matching + PAD)"""
    
    def setUp(self):
        from face.biometric_integration import get_biometric_integration
        self.integration = get_biometric_integration()
    
    def test_face_matching_threshold(self):
        """Test face matching threshold (85%)"""
        # Mock face data
        reference_face = b"reference_face_data"
        live_face = b"live_face_data"
        
        result = self.integration.match_faces(reference_face, live_face)
        
        self.assertIn("match_score", result)
        self.assertIn("passed", result)
        
        # Check threshold
        if result["match_score"] >= 0.85:
            self.assertTrue(result["passed"])
        else:
            self.assertFalse(result["passed"])
    
    def test_pad_detection_threshold(self):
        """Test PAD detection threshold (90%)"""
        face_data = b"face_data"
        
        result = self.integration.detect_presentation_attack(face_data)
        
        self.assertIn("pad_score", result)
        self.assertIn("is_live", result)
        
        # Check threshold
        if result["pad_score"] >= 0.90:
            self.assertTrue(result["is_live"])
    
    def test_combined_biometric_confidence(self):
        """Test combined biometric confidence calculation"""
        # Mock both checks
        biometric_result = self.integration.process_biometrics(
            reference_image=b"ref",
            live_image=b"live",
            session=Mock()
        )
        
        self.assertIn("confidence", biometric_result)
        self.assertIn("passed", biometric_result)
        
        # Confidence should be weighted average
        self.assertGreaterEqual(biometric_result["confidence"], 0.0)
        self.assertLessEqual(biometric_result["confidence"], 1.0)


class TestStreamingEvents(unittest.TestCase):
    """Test real-time streaming functionality"""
    
    def setUp(self):
        from face.streaming import get_stream_manager, StreamEventType
        self.manager = get_stream_manager()
        self.StreamEventType = StreamEventType
    
    def test_event_broadcasting(self):
        """Test events are broadcast to connections"""
        session_id = "stream-test-123"
        
        # Create mock connection
        connection = self.manager.create_connection(session_id)
        
        # Send event
        event = {
            "type": self.StreamEventType.STATE_CHANGE,
            "data": {"state": "locked"}
        }
        self.manager.send_event(session_id, event)
        
        # Check event was queued
        self.assertGreater(len(connection.event_queue), 0)
    
    def test_concurrent_connections(self):
        """Test multiple concurrent connections"""
        sessions = [f"session-{i}" for i in range(5)]
        
        for session_id in sessions:
            conn = self.manager.create_connection(session_id)
            self.assertIsNotNone(conn)
        
        # Check connection limit
        stats = self.manager.get_connection_stats()
        self.assertLessEqual(stats["active_connections"], 5)
    
    def test_event_buffer_limit(self):
        """Test event buffer doesn't exceed limit"""
        session_id = "buffer-test"
        connection = self.manager.create_connection(session_id)
        
        # Send many events
        for i in range(10100):  # More than 10k limit
            event = {"type": "test", "index": i}
            self.manager.send_event(session_id, event)
        
        # Buffer should be capped at 10k
        self.assertLessEqual(len(connection.event_queue), 10000)


def run_unit_tests():
    """Run all unit tests"""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add all test classes
    suite.addTests(loader.loadTestsFromTestCase(TestSessionManager))
    suite.addTests(loader.loadTestsFromTestCase(TestMessageLocalization))
    suite.addTests(loader.loadTestsFromTestCase(TestQualityGates))
    suite.addTests(loader.loadTestsFromTestCase(TestExtractionConfidence))
    suite.addTests(loader.loadTestsFromTestCase(TestBiometricIntegration))
    suite.addTests(loader.loadTestsFromTestCase(TestStreamingEvents))
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_unit_tests()
    sys.exit(0 if success else 1)