"""
Response Formatter Module for API v2 Standardization
Provides consistent response format across all endpoints

This module implements:
- Unified response structure
- Backward compatibility adapters
- Error formatting
- Metadata enrichment
- Deprecation warnings
"""

import time
import logging
from typing import Dict, Any, Optional, Union, List
from datetime import datetime, timezone, timedelta
from fastapi import Response, Request
from fastapi.responses import JSONResponse
import json

logger = logging.getLogger(__name__)

# Philippines timezone
PHT = timezone(timedelta(hours=8))

class ResponseFormatter:
    """
    Formats API responses according to v2 specification
    """
    
    def __init__(self, version: str = "2.0"):
        """
        Initialize response formatter
        
        Args:
            version: API version string
        """
        self.version = version
        self.start_times: Dict[str, float] = {}
    
    def start_timing(self, request_id: str):
        """
        Start timing for a request
        
        Args:
            request_id: Unique request identifier
        """
        self.start_times[request_id] = time.time()
    
    def format_response(self,
                       data: Any,
                       request: Optional[Request] = None,
                       session_id: Optional[str] = None,
                       messages: Optional[Dict[str, str]] = None,
                       error: Optional[Dict[str, Any]] = None,
                       success: Optional[bool] = None,
                       request_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Format response according to v2 specification
        
        Args:
            data: Response data
            request: Optional FastAPI request object
            session_id: Optional session identifier
            messages: Optional localized messages
            error: Optional error information
            success: Optional success flag (auto-detected if not provided)
            request_id: Optional request ID for timing
            
        Returns:
            Formatted response dictionary
        """
        # Auto-detect success if not provided
        if success is None:
            success = error is None
        
        # Calculate processing time
        processing_time_ms = 0.0
        if request_id and request_id in self.start_times:
            processing_time_ms = (time.time() - self.start_times[request_id]) * 1000
            del self.start_times[request_id]
        
        # Build metadata
        metadata = {
            "timestamp": datetime.now(PHT).isoformat(),
            "version": self.version,
            "processing_time_ms": round(processing_time_ms, 2)
        }
        
        if session_id:
            metadata["session_id"] = session_id
        
        if request:
            metadata["endpoint"] = str(request.url.path)
            metadata["method"] = request.method
        
        # Build response
        response = {
            "success": success,
            "data": data if success else None,
            "metadata": metadata,
            "error": error
        }
        
        # Add messages if provided
        if messages:
            response["messages"] = messages
        
        return response
    
    def format_error(self,
                    code: str,
                    message: str,
                    details: Optional[Dict[str, Any]] = None,
                    status_code: int = 400) -> Dict[str, Any]:
        """
        Format error response
        
        Args:
            code: Error code
            message: Error message
            details: Optional error details
            status_code: HTTP status code
            
        Returns:
            Formatted error dictionary
        """
        error = {
            "code": code,
            "message": message,
            "status_code": status_code
        }
        
        if details:
            error["details"] = details
        
        return error
    
    def add_deprecation_warning(self,
                               response: Union[Dict, Response],
                               deprecated_endpoint: str,
                               replacement_endpoint: str,
                               sunset_date: str) -> Union[Dict, Response]:
        """
        Add deprecation warning to response
        
        Args:
            response: Response object or dictionary
            deprecated_endpoint: The deprecated endpoint
            replacement_endpoint: The replacement endpoint
            sunset_date: ISO date when endpoint will be removed
            
        Returns:
            Response with deprecation headers
        """
        warning = f'299 - "{deprecated_endpoint} is deprecated. Use {replacement_endpoint}. Sunset: {sunset_date}"'
        
        if isinstance(response, dict):
            # Add to metadata
            if "metadata" not in response:
                response["metadata"] = {}
            response["metadata"]["deprecation"] = {
                "deprecated": deprecated_endpoint,
                "replacement": replacement_endpoint,
                "sunset": sunset_date
            }
            return response
        else:
            # Add HTTP headers
            response.headers["X-API-Deprecated"] = "true"
            response.headers["X-API-Deprecated-Endpoint"] = deprecated_endpoint
            response.headers["X-API-Deprecated-Use"] = replacement_endpoint
            response.headers["X-API-Deprecated-Sunset"] = sunset_date
            response.headers["Warning"] = warning
            return response

class V1ResponseAdapter:
    """
    Adapts v2 responses to v1 format for backward compatibility
    """
    
    @staticmethod
    def adapt_face_lock_response(v2_response: Dict[str, Any]) -> Dict[str, Any]:
        """
        Adapt v2 face lock response to v1 format
        
        Args:
            v2_response: V2 formatted response
            
        Returns:
            V1 formatted response
        """
        if not v2_response.get("success"):
            return {
                "ok": False,
                "error": v2_response.get("error", {}).get("message", "Unknown error")
            }
        
        data = v2_response.get("data", {})
        return {
            "ok": True,
            "sessionId": v2_response.get("metadata", {}).get("session_id"),
            "locked": data.get("locked", False),
            "lockToken": data.get("lock_token"),
            "padScore": data.get("pad_score"),
            "qualityScore": data.get("quality_score"),
            "message": v2_response.get("messages", {}).get("english", ""),
            "tagalogMessage": v2_response.get("messages", {}).get("tagalog", "")
        }
    
    @staticmethod
    def adapt_burst_eval_response(v2_response: Dict[str, Any]) -> Dict[str, Any]:
        """
        Adapt v2 burst eval response to v1 format
        
        Args:
            v2_response: V2 formatted response
            
        Returns:
            V1 formatted response
        """
        if not v2_response.get("success"):
            return {
                "ok": False,
                "error": v2_response.get("error", {}).get("message", "Unknown error")
            }
        
        data = v2_response.get("data", {})
        return {
            "ok": True,
            "session_id": v2_response.get("metadata", {}).get("session_id"),
            "burst_id": data.get("burst_id"),
            "consensus": data.get("consensus", {}),
            "frame_scores": data.get("frame_scores", []),
            "feedback": data.get("feedback", {}),
            "thresholds": data.get("thresholds", {})
        }
    
    @staticmethod
    def adapt_telemetry_response(v2_response: Dict[str, Any]) -> Dict[str, Any]:
        """
        Adapt v2 telemetry response to v1 format
        
        Args:
            v2_response: V2 formatted response
            
        Returns:
            V1 formatted response
        """
        data = v2_response.get("data", {})
        
        # V1 telemetry had flat structure
        return {
            "session_id": v2_response.get("metadata", {}).get("session_id"),
            "events": data.get("events", []),
            "metrics": data.get("metrics", {}),
            "timestamp": v2_response.get("metadata", {}).get("timestamp")
        }

def create_v2_endpoint_wrapper(handler_func, formatter: ResponseFormatter):
    """
    Create a wrapper that formats handler responses to v2 format
    
    Args:
        handler_func: Original handler function
        formatter: Response formatter instance
        
    Returns:
        Wrapped handler function
    """
    async def wrapper(request: Request, *args, **kwargs):
        # Generate request ID
        request_id = f"{request.client.host}_{time.time()}"
        formatter.start_timing(request_id)
        
        try:
            # Call original handler
            result = await handler_func(*args, **kwargs)
            
            # If already formatted, return as-is
            if isinstance(result, (Response, JSONResponse)):
                return result
            
            # Extract session_id if available
            session_id = None
            if "session_id" in kwargs:
                session_id = kwargs["session_id"]
            elif isinstance(result, dict) and "session_id" in result:
                session_id = result["session_id"]
            
            # Check for error in result
            error = None
            if isinstance(result, dict) and ("error" in result or not result.get("ok", True)):
                error = formatter.format_error(
                    code="HANDLER_ERROR",
                    message=result.get("error", "Unknown error")
                )
            
            # Format response
            formatted = formatter.format_response(
                data=result,
                request=request,
                session_id=session_id,
                error=error,
                request_id=request_id
            )
            
            return JSONResponse(content=formatted)
            
        except Exception as e:
            logger.error(f"Handler error: {e}")
            error = formatter.format_error(
                code="INTERNAL_ERROR",
                message=str(e),
                status_code=500
            )
            
            formatted = formatter.format_response(
                data=None,
                request=request,
                error=error,
                success=False,
                request_id=request_id
            )
            
            return JSONResponse(content=formatted, status_code=500)
    
    return wrapper

# Global formatter instance
_formatter = None

def get_response_formatter() -> ResponseFormatter:
    """Get or create response formatter instance"""
    global _formatter
    if _formatter is None:
        _formatter = ResponseFormatter()
    return _formatter

def standardize_response(data: Any,
                        session_id: Optional[str] = None,
                        messages: Optional[Dict[str, str]] = None,
                        error: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Convenience function to standardize responses
    
    Args:
        data: Response data
        session_id: Optional session ID
        messages: Optional messages
        error: Optional error
        
    Returns:
        Standardized response
    """
    formatter = get_response_formatter()
    return formatter.format_response(
        data=data,
        session_id=session_id,
        messages=messages,
        error=error
    )