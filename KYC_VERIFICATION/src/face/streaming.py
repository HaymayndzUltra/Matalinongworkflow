"""
Real-time Streaming Implementation
Implements SSE streaming for multiple concurrent sessions (UX Requirement E)

This module provides real-time streaming functionality with support for
multiple concurrent sessions and progressive field updates.
"""

import asyncio
import json
import logging
import time
import uuid
from typing import Dict, List, Optional, Any, AsyncIterator, Set
from dataclasses import dataclass, field
from enum import Enum
from collections import deque
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class StreamEventType(Enum):
    """Types of streaming events"""
    # Connection events
    CONNECTED = "connected"
    HEARTBEAT = "heartbeat"
    DISCONNECTED = "disconnected"
    
    # State events
    STATE_CHANGE = "state_change"
    STATE_TRANSITION = "state_transition"
    
    # Quality events
    QUALITY_UPDATE = "quality_update"
    QUALITY_GATE_PASSED = "quality_gate_passed"
    QUALITY_GATE_FAILED = "quality_gate_failed"
    
    # Extraction events
    EXTRACTION_START = "extraction_start"
    EXTRACTION_FIELD = "extraction_field"
    EXTRACTION_PROGRESS = "extraction_progress"
    EXTRACTION_COMPLETE = "extraction_complete"
    
    # Capture events
    CAPTURE_START = "capture_start"
    CAPTURE_PROGRESS = "capture_progress"
    CAPTURE_COMPLETE = "capture_complete"
    
    # Error events
    ERROR = "error"
    WARNING = "warning"


@dataclass
class StreamEvent:
    """Individual streaming event"""
    event_id: str
    event_type: StreamEventType
    session_id: str
    timestamp: float
    sequence: int
    data: Dict[str, Any]
    retry_after: Optional[int] = None  # Milliseconds to retry
    
    def to_sse(self) -> str:
        """Convert to Server-Sent Event format"""
        lines = []
        
        # Event ID for reconnection
        lines.append(f"id: {self.event_id}")
        
        # Event type
        lines.append(f"event: {self.event_type.value}")
        
        # Retry hint if provided
        if self.retry_after:
            lines.append(f"retry: {self.retry_after}")
        
        # Event data
        event_data = {
            "session_id": self.session_id,
            "timestamp": self.timestamp,
            "sequence": self.sequence,
            "type": self.event_type.value,
            "data": self.data
        }
        lines.append(f"data: {json.dumps(event_data)}")
        
        # Double newline to end event
        return "\n".join(lines) + "\n\n"


@dataclass
class StreamConnection:
    """Represents a streaming connection"""
    connection_id: str
    session_id: str
    created_at: float
    last_event_id: Optional[str] = None
    last_sequence: int = 0
    event_queue: deque = field(default_factory=lambda: deque(maxlen=100))
    is_active: bool = True
    last_heartbeat: float = field(default_factory=time.time)
    
    def add_event(self, event: StreamEvent):
        """Add event to connection queue"""
        self.event_queue.append(event)
        self.last_event_id = event.event_id
        self.last_sequence = event.sequence
    
    def get_pending_events(self) -> List[StreamEvent]:
        """Get all pending events"""
        events = list(self.event_queue)
        self.event_queue.clear()
        return events
    
    def is_stale(self, timeout_seconds: int = 60) -> bool:
        """Check if connection is stale"""
        return time.time() - self.last_heartbeat > timeout_seconds


class StreamManager:
    """Manages streaming connections and event distribution"""
    
    def __init__(self, max_connections: int = 1000, max_events_per_session: int = 100):
        """
        Initialize stream manager
        
        Args:
            max_connections: Maximum concurrent connections
            max_events_per_session: Maximum events to buffer per session
        """
        self.connections: Dict[str, StreamConnection] = {}
        self.session_connections: Dict[str, Set[str]] = {}  # session_id -> connection_ids
        self.max_connections = max_connections
        self.max_events_per_session = max_events_per_session
        self.global_sequence = 0
        self._lock = asyncio.Lock()
        self._cleanup_task = None
        
    async def create_connection_async(self, session_id: str, last_event_id: Optional[str] = None) -> StreamConnection:
        """
        Create a new streaming connection
        
        Args:
            session_id: Session identifier
            last_event_id: Last event ID for reconnection
            
        Returns:
            StreamConnection instance
        """
        async with self._lock:
            # Check connection limit
            if len(self.connections) >= self.max_connections:
                # Remove oldest stale connection
                await self._cleanup_stale_connections()
                
                if len(self.connections) >= self.max_connections:
                    raise ValueError(f"Maximum connections ({self.max_connections}) reached")
            
            # Create new connection
            connection_id = str(uuid.uuid4())
            connection = StreamConnection(
                connection_id=connection_id,
                session_id=session_id,
                created_at=time.time(),
                last_event_id=last_event_id
            )
            
            # Register connection
            self.connections[connection_id] = connection
            
            # Track session connections
            if session_id not in self.session_connections:
                self.session_connections[session_id] = set()
            self.session_connections[session_id].add(connection_id)
            
            # Send connected event
            await self.send_event(
                session_id,
                StreamEventType.CONNECTED,
                {
                    "connection_id": connection_id,
                    "session_id": session_id,
                    "timestamp": time.time()
                }
            )
            
            logger.info(f"Created stream connection: {connection_id} for session: {session_id}")
            return connection

    # Backward-compatibility: synchronous facade for tests that don't await
    def create_connection(self, session_id: str, last_event_id: Optional[str] = None) -> StreamConnection:  # sync wrapper for tests
        loop = asyncio.new_event_loop()
        try:
            asyncio.set_event_loop(loop)
            return loop.run_until_complete(self.create_connection_async(session_id, last_event_id))
        finally:
            loop.close()
    
    async def close_connection(self, connection_id: str):
        """Close a streaming connection"""
        async with self._lock:
            if connection_id in self.connections:
                connection = self.connections[connection_id]
                session_id = connection.session_id
                
                # Send disconnected event
                await self.send_event(
                    session_id,
                    StreamEventType.DISCONNECTED,
                    {"connection_id": connection_id}
                )
                
                # Remove from session connections
                if session_id in self.session_connections:
                    self.session_connections[session_id].discard(connection_id)
                    if not self.session_connections[session_id]:
                        del self.session_connections[session_id]
                
                # Remove connection
                del self.connections[connection_id]
                
                logger.info(f"Closed stream connection: {connection_id}")
    
    async def send_event(self, 
                        session_id: str,
                        event_type: StreamEventType,
                        data: Dict[str, Any],
                        retry_after: Optional[int] = None):
        """
        Send event to all connections for a session (awaitable API)
        """
        async with self._lock:
            # Generate event
            self.global_sequence += 1
            event = StreamEvent(
                event_id=str(uuid.uuid4()),
                event_type=event_type,
                session_id=session_id,
                timestamp=time.time(),
                sequence=self.global_sequence,
                data=data,
                retry_after=retry_after
            )
            
            # Send to all session connections
            if session_id in self.session_connections:
                for connection_id in self.session_connections[session_id]:
                    if connection_id in self.connections:
                        self.connections[connection_id].add_event(event)
                        
                logger.debug(f"Sent {event_type.value} event to {len(self.session_connections[session_id])} connections")

    # Backward-compatibility: synchronous facade mirroring async send_event
    def send_event_sync(self, session_id: str, event: Dict[str, Any]):
        """Synchronous facade for tests: accepts a single event dictionary."""
        try:
            etype = event.get("type")
            # Map raw type string to StreamEventType if possible
            try:
                event_type = StreamEventType(etype) if isinstance(etype, str) else etype
            except Exception:
                event_type = StreamEventType.STATE_CHANGE
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self.send_event(session_id, event_type, event.get("data", {})))
        finally:
            try:
                loop.close()
            except Exception:
                pass
    
    async def stream_events(self, connection_id: str) -> AsyncIterator[str]:
        """
        Stream events for a connection (async generator)
        
        Args:
            connection_id: Connection identifier
            
        Yields:
            SSE formatted events
        """
        if connection_id not in self.connections:
            raise ValueError(f"Connection {connection_id} not found")
        
        connection = self.connections[connection_id]
        
        try:
            while connection.is_active:
                # Get pending events
                events = connection.get_pending_events()
                
                if events:
                    for event in events:
                        yield event.to_sse()
                else:
                    # Send heartbeat if no events
                    await asyncio.sleep(1)
                    
                    # Send heartbeat every 30 seconds
                    if time.time() - connection.last_heartbeat > 30:
                        heartbeat_event = StreamEvent(
                            event_id=str(uuid.uuid4()),
                            event_type=StreamEventType.HEARTBEAT,
                            session_id=connection.session_id,
                            timestamp=time.time(),
                            sequence=self.global_sequence,
                            data={"connection_id": connection_id}
                        )
                        connection.last_heartbeat = time.time()
                        yield heartbeat_event.to_sse()
                
        except asyncio.CancelledError:
            # Clean disconnection
            await self.close_connection(connection_id)
            raise
        except Exception as e:
            logger.error(f"Error streaming events: {e}")
            await self.close_connection(connection_id)
            raise
    
    async def broadcast_state_change(self,
                                    session_id: str,
                                    old_state: str,
                                    new_state: str,
                                    reason: Optional[str] = None):
        """Broadcast state change event"""
        await self.send_event(
            session_id,
            StreamEventType.STATE_CHANGE,
            {
                "old_state": old_state,
                "new_state": new_state,
                "reason": reason,
                "timestamp": time.time()
            }
        )
    
    async def broadcast_quality_update(self,
                                      session_id: str,
                                      quality_metrics: Dict[str, Any],
                                      passed: bool):
        """Broadcast quality update event"""
        event_type = StreamEventType.QUALITY_GATE_PASSED if passed else StreamEventType.QUALITY_GATE_FAILED
        await self.send_event(
            session_id,
            event_type,
            {
                "metrics": quality_metrics,
                "passed": passed,
                "timestamp": time.time()
            }
        )
    
    async def broadcast_extraction_field(self,
                                        session_id: str,
                                        field_name: str,
                                        field_value: str,
                                        confidence: float):
        """Broadcast extraction field event"""
        await self.send_event(
            session_id,
            StreamEventType.EXTRACTION_FIELD,
            {
                "field": field_name,
                "value": field_value,
                "confidence": confidence,
                "timestamp": time.time()
            }
        )
    
    async def broadcast_extraction_progress(self,
                                           session_id: str,
                                           progress: float,
                                           fields_extracted: int,
                                           total_fields: int):
        """Broadcast extraction progress event"""
        await self.send_event(
            session_id,
            StreamEventType.EXTRACTION_PROGRESS,
            {
                "progress": progress,
                "fields_extracted": fields_extracted,
                "total_fields": total_fields,
                "timestamp": time.time()
            }
        )
    
    async def _cleanup_stale_connections(self):
        """Remove stale connections"""
        stale_connections = []
        
        for conn_id, connection in self.connections.items():
            if connection.is_stale():
                stale_connections.append(conn_id)
        
        for conn_id in stale_connections:
            await self.close_connection(conn_id)
        
        if stale_connections:
            logger.info(f"Cleaned up {len(stale_connections)} stale connections")
    
    async def start_cleanup_task(self):
        """Start periodic cleanup task"""
        async def cleanup_loop():
            while True:
                try:
                    await asyncio.sleep(60)  # Cleanup every minute
                    async with self._lock:
                        await self._cleanup_stale_connections()
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error(f"Error in cleanup task: {e}")
        
        self._cleanup_task = asyncio.create_task(cleanup_loop())
    
    async def stop_cleanup_task(self):
        """Stop cleanup task"""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
    
    def get_connection_stats(self) -> Dict[str, Any]:
        """Get streaming statistics"""
        stats = {
            "total_connections": len(self.connections),
            "active_sessions": len(self.session_connections),
            "connections_per_session": {
                session_id: len(conn_ids)
                for session_id, conn_ids in self.session_connections.items()
            },
            "max_connections": self.max_connections,
            "global_sequence": self.global_sequence
        }
        # Backward-compatibility: expose old key expected by tests
        stats["active_connections"] = stats["total_connections"]
        return stats


# Global stream manager instance
_stream_manager = None


def get_stream_manager() -> StreamManager:
    """Get or create the global stream manager"""
    global _stream_manager
    if _stream_manager is None:
        _stream_manager = StreamManager()
    return _stream_manager


async def create_sse_stream(session_id: str, last_event_id: Optional[str] = None) -> AsyncIterator[str]:
    """
    Create an SSE stream for a session
    
    Args:
        session_id: Session identifier
        last_event_id: Last event ID for reconnection
        
    Yields:
        SSE formatted events
    """
    manager = get_stream_manager()
    
    # Create connection
    connection = await manager.create_connection(session_id, last_event_id)
    
    try:
        # Stream events
        async for event in manager.stream_events(connection.connection_id):
            yield event
    finally:
        # Cleanup on disconnect
        await manager.close_connection(connection.connection_id)