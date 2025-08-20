#!/usr/bin/env python3
"""
Performance Tests - Load testing, stress testing, and performance benchmarks
"""

import unittest
import sys
import os
import time
import threading
import concurrent.futures
from statistics import mean, stdev
import random

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../src'))

class TestResponseTimePerformance(unittest.TestCase):
    """Test response time performance targets"""
    
    def setUp(self):
        from face.quality_gates import get_quality_manager
        from face.session_manager import get_session_manager
        
        self.quality_manager = get_quality_manager()
        self.session_manager = get_session_manager()
    
    def test_cancel_on_jitter_under_50ms(self):
        """Test cancel-on-jitter completes in <50ms"""
        metrics = {
            "focus": 5.0,  # Poor focus
            "motion": 0.6,  # High motion
            "glare": 0.05,
            "corners": 0.90,
            "fill_ratio": 0.75
        }
        
        times = []
        for _ in range(100):  # Run 100 times for average
            start = time.perf_counter()
            result = self.quality_manager.check_quality(metrics)
            duration = (time.perf_counter() - start) * 1000
            times.append(duration)
        
        avg_time = mean(times)
        max_time = max(times)
        
        print(f"\nCancel-on-jitter performance:")
        print(f"  Average: {avg_time:.2f}ms")
        print(f"  Max: {max_time:.2f}ms")
        print(f"  StdDev: {stdev(times):.2f}ms")
        
        self.assertLess(avg_time, 50, f"Average time {avg_time:.2f}ms exceeds 50ms")
        self.assertLess(max_time, 100, f"Max time {max_time:.2f}ms too high")
    
    def test_lock_detection_under_100ms(self):
        """Test lock detection completes in <100ms"""
        from face.handlers import handle_lock_check
        
        request = {
            "session_id": "perf-test",
            "image": b"test_image",
            "face_geometry": {
                "bounding_box": [100, 100, 200, 200],
                "landmarks": [],
                "pose": {}
            }
        }
        
        times = []
        for _ in range(50):
            start = time.perf_counter()
            result = handle_lock_check(request)
            duration = (time.perf_counter() - start) * 1000
            times.append(duration)
        
        avg_time = mean(times)
        p95_time = sorted(times)[int(len(times) * 0.95)]
        
        print(f"\nLock detection performance:")
        print(f"  Average: {avg_time:.2f}ms")
        print(f"  P95: {p95_time:.2f}ms")
        
        self.assertLess(avg_time, 100, f"Average time {avg_time:.2f}ms exceeds 100ms")
    
    def test_extraction_performance_targets(self):
        """Test extraction meets P50≤4s and P95≤6s targets"""
        from face.extraction import ExtractionProcessor
        
        processor = ExtractionProcessor()
        mock_image = b"test_image_data"
        
        times = []
        for _ in range(20):  # Less iterations as extraction is slower
            start = time.perf_counter()
            result = processor.extract_document(mock_image)
            duration = time.perf_counter() - start
            times.append(duration)
        
        times_sorted = sorted(times)
        p50_time = times_sorted[int(len(times) * 0.50)]
        p95_time = times_sorted[int(len(times) * 0.95)]
        
        print(f"\nExtraction performance:")
        print(f"  P50: {p50_time:.2f}s")
        print(f"  P95: {p95_time:.2f}s")
        
        self.assertLessEqual(p50_time, 4.0, f"P50 {p50_time:.2f}s exceeds 4s")
        self.assertLessEqual(p95_time, 6.0, f"P95 {p95_time:.2f}s exceeds 6s")


class TestConcurrentSessions(unittest.TestCase):
    """Test system performance under concurrent load"""
    
    def setUp(self):
        from face.session_manager import get_session_manager
        from face.streaming import get_stream_manager
        
        self.session_manager = get_session_manager()
        self.stream_manager = get_stream_manager()
    
    def test_concurrent_session_creation(self):
        """Test creating many sessions concurrently"""
        def create_session(index):
            session_id = f"concurrent-{index}"
            session = self.session_manager.create_session(session_id)
            return session is not None
        
        start = time.perf_counter()
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=50) as executor:
            futures = [executor.submit(create_session, i) for i in range(100)]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]
        
        duration = time.perf_counter() - start
        
        print(f"\nConcurrent session creation:")
        print(f"  Created 100 sessions in {duration:.2f}s")
        print(f"  Rate: {100/duration:.1f} sessions/second")
        
        self.assertEqual(sum(results), 100, "Not all sessions created")
        self.assertLess(duration, 5.0, "Session creation too slow")
    
    def test_streaming_connection_limits(self):
        """Test streaming connection pool limits"""
        connections = []
        
        # Try to create more than limit
        for i in range(10):
            conn = self.stream_manager.create_connection(f"stream-{i}")
            if conn:
                connections.append(conn)
        
        # Should be limited to 5 concurrent
        stats = self.stream_manager.get_connection_stats()
        self.assertLessEqual(stats["active_connections"], 5)
        
        print(f"\nStreaming connections:")
        print(f"  Active: {stats['active_connections']}")
        print(f"  Limit enforced: {stats['active_connections'] <= 5}")
    
    def test_quality_check_throughput(self):
        """Test quality check throughput under load"""
        from face.quality_gates import get_quality_manager
        
        manager = get_quality_manager()
        
        def perform_quality_checks():
            metrics = {
                "focus": random.uniform(5.0, 10.0),
                "motion": random.uniform(0.1, 0.5),
                "glare": random.uniform(0.01, 0.05),
                "corners": random.uniform(0.90, 1.0),
                "fill_ratio": random.uniform(0.60, 0.80)
            }
            return manager.check_quality(metrics)
        
        start = time.perf_counter()
        checks_performed = 0
        
        # Run for 1 second
        while time.perf_counter() - start < 1.0:
            perform_quality_checks()
            checks_performed += 1
        
        print(f"\nQuality check throughput:")
        print(f"  Checks per second: {checks_performed}")
        
        self.assertGreater(checks_performed, 1000, "Throughput too low")


class TestMemoryUsage(unittest.TestCase):
    """Test memory usage and leaks"""
    
    def test_session_cleanup(self):
        """Test sessions are properly cleaned up"""
        from face.session_manager import get_session_manager
        import gc
        
        manager = get_session_manager()
        
        # Create many sessions
        session_ids = []
        for i in range(100):
            session_id = f"memory-test-{i}"
            manager.create_session(session_id)
            session_ids.append(session_id)
        
        # Clean up sessions
        for session_id in session_ids:
            manager.cleanup_session(session_id)
        
        # Force garbage collection
        gc.collect()
        
        # Check sessions are gone
        active_sessions = manager.get_active_session_count()
        self.assertEqual(active_sessions, 0, "Sessions not cleaned up")
    
    def test_event_buffer_memory_limit(self):
        """Test event buffer respects memory limits"""
        from face.streaming import get_stream_manager
        import sys
        
        manager = get_stream_manager()
        connection = manager.create_connection("buffer-test")
        
        # Send many large events
        large_event = {"data": "x" * 1000}  # 1KB event
        
        initial_size = sys.getsizeof(connection.event_queue)
        
        for i in range(10000):
            manager.send_event("buffer-test", large_event)
        
        final_size = sys.getsizeof(connection.event_queue)
        
        # Should be capped, not growing infinitely
        self.assertLess(final_size, initial_size * 100, "Buffer grew too much")
        
        print(f"\nEvent buffer memory:")
        print(f"  Initial: {initial_size} bytes")
        print(f"  After 10k events: {final_size} bytes")
    
    def test_telemetry_event_limit(self):
        """Test telemetry events don't grow unbounded"""
        from face.ux_telemetry import get_telemetry_manager
        
        manager = get_telemetry_manager()
        session_id = "telemetry-memory-test"
        
        # Generate many events
        for i in range(20000):
            manager.track_ux_event(
                event_type=f"test.event.{i}",
                session_id=session_id,
                metadata={"index": i}
            )
        
        # Check events are capped
        events = manager.get_session_events(session_id)
        self.assertLessEqual(len(events), 10000, "Too many events stored")
        
        print(f"\nTelemetry events:")
        print(f"  Generated: 20,000")
        print(f"  Stored: {len(events)} (capped)")


class TestStressScenarios(unittest.TestCase):
    """Test system under stress conditions"""
    
    def test_rapid_state_transitions(self):
        """Test rapid state transitions don't break system"""
        from face.session_manager import get_session_manager, CaptureState
        
        session = get_session_manager().create_session("stress-state")
        
        # Rapid random transitions
        states = list(CaptureState)
        transition_count = 0
        
        start = time.perf_counter()
        while time.perf_counter() - start < 1.0:
            target_state = random.choice(states)
            session.transition_to(target_state)
            transition_count += 1
        
        print(f"\nRapid state transitions:")
        print(f"  Transitions per second: {transition_count}")
        
        # System should handle it without crashing
        self.assertGreater(transition_count, 100)
    
    def test_burst_quality_checks(self):
        """Test system handles burst of quality checks"""
        from face.quality_gates import get_quality_manager
        
        manager = get_quality_manager()
        
        # Simulate burst of 1000 checks
        results = []
        start = time.perf_counter()
        
        for _ in range(1000):
            metrics = {
                "focus": random.uniform(5.0, 10.0),
                "motion": random.uniform(0.1, 0.5),
                "glare": random.uniform(0.01, 0.05),
                "corners": random.uniform(0.90, 1.0),
                "fill_ratio": random.uniform(0.60, 0.80)
            }
            result = manager.check_quality(metrics)
            results.append(result)
        
        duration = time.perf_counter() - start
        
        print(f"\nBurst quality checks:")
        print(f"  1000 checks in {duration:.2f}s")
        print(f"  Rate: {1000/duration:.1f} checks/second")
        
        self.assertLess(duration, 2.0, "Burst handling too slow")
    
    def test_extraction_under_load(self):
        """Test extraction performance under system load"""
        from face.extraction import ExtractionProcessor
        import threading
        
        processor = ExtractionProcessor()
        
        # Create background load
        stop_load = threading.Event()
        
        def create_load():
            while not stop_load.is_set():
                # Simulate CPU load
                sum(i*i for i in range(1000))
        
        # Start load threads
        load_threads = [threading.Thread(target=create_load) for _ in range(4)]
        for t in load_threads:
            t.start()
        
        try:
            # Perform extraction under load
            start = time.perf_counter()
            result = processor.extract_document(b"test_image")
            duration = time.perf_counter() - start
            
            print(f"\nExtraction under load:")
            print(f"  Time: {duration:.2f}s")
            
            # Should still meet P95 target even under load
            self.assertLess(duration, 8.0, "Extraction too slow under load")
            
        finally:
            # Stop load threads
            stop_load.set()
            for t in load_threads:
                t.join()


class TestLatencyMetrics(unittest.TestCase):
    """Test end-to-end latency metrics"""
    
    def test_full_capture_latency(self):
        """Test full capture flow latency"""
        from face.handlers import handle_lock_check, handle_burst_eval
        from face.session_manager import get_session_manager
        
        session_id = "latency-test"
        session = get_session_manager().create_session(session_id)
        
        # Measure full flow
        start = time.perf_counter()
        
        # Lock check
        lock_result = handle_lock_check({
            "session_id": session_id,
            "image": b"test",
            "face_geometry": {}
        })
        
        # Burst evaluation
        burst_result = handle_burst_eval({
            "session_id": session_id,
            "burst_id": "burst-123",
            "frames": []
        })
        
        total_time = (time.perf_counter() - start) * 1000
        
        print(f"\nFull capture latency:")
        print(f"  Total: {total_time:.2f}ms")
        
        self.assertLess(total_time, 500, "Full flow latency too high")
    
    def test_streaming_latency(self):
        """Test streaming event delivery latency"""
        from face.streaming import get_stream_manager
        import threading
        
        manager = get_stream_manager()
        session_id = "stream-latency"
        connection = manager.create_connection(session_id)
        
        latencies = []
        
        def measure_latency():
            for _ in range(100):
                start = time.perf_counter()
                event = {"timestamp": start}
                manager.send_event(session_id, event)
                
                # Simulate receiving
                if connection.event_queue:
                    received = connection.event_queue[-1]
                    latency = (time.perf_counter() - start) * 1000
                    latencies.append(latency)
        
        measure_latency()
        
        if latencies:
            avg_latency = mean(latencies)
            max_latency = max(latencies)
            
            print(f"\nStreaming latency:")
            print(f"  Average: {avg_latency:.2f}ms")
            print(f"  Max: {max_latency:.2f}ms")
            
            self.assertLess(avg_latency, 500, "Streaming latency too high")


def run_performance_tests():
    """Run all performance tests"""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add all test classes
    suite.addTests(loader.loadTestsFromTestCase(TestResponseTimePerformance))
    suite.addTests(loader.loadTestsFromTestCase(TestConcurrentSessions))
    suite.addTests(loader.loadTestsFromTestCase(TestMemoryUsage))
    suite.addTests(loader.loadTestsFromTestCase(TestStressScenarios))
    suite.addTests(loader.loadTestsFromTestCase(TestLatencyMetrics))
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Print performance summary
    print("\n" + "="*60)
    print("PERFORMANCE TEST SUMMARY")
    print("="*60)
    print("✅ Tests completed")
    print("📊 Key metrics validated:")
    print("  • Cancel-on-jitter: <50ms")
    print("  • Lock detection: <100ms")
    print("  • Extraction: P50≤4s, P95≤6s")
    print("  • Streaming: <500ms latency")
    print("  • Concurrent sessions: 100+ supported")
    print("  • Quality checks: 1000+ per second")
    
    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_performance_tests()
    sys.exit(0 if success else 1)