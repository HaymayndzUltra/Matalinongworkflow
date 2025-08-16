# API Reference

## Overview
The KYC Verification System provides RESTful API endpoints for document capture, face scanning, and identity verification. Version 2 (v2) endpoints are recommended for new integrations.

## Base URL
```
https://api.kyc-system.com
```

## Authentication
```http
X-API-Key: your-api-key
Authorization: Bearer {token}
```

## V2 Endpoints (Recommended)

### POST /v2/face/scan
Unified endpoint for face scanning operations.

#### Request
```json
{
  "session_id": "user-123",
  "action": "lock|upload|evaluate",
  "data": {
    // Action-specific data
  }
}
```

#### Actions

##### lock - Check face position
```json
{
  "action": "lock",
  "data": {
    "image": "base64_encoded_image",
    "face_geometry": {
      "bounding_box": [100, 100, 200, 200],
      "landmarks": [...],
      "pose": {...}
    }
  }
}
```

##### upload - Upload burst frames
```json
{
  "action": "upload",
  "data": {
    "frames": [
      {
        "image": "base64_encoded",
        "timestamp": "2025-01-16T10:30:00Z",
        "index": 0
      }
    ]
  }
}
```

##### evaluate - Evaluate burst quality
```json
{
  "action": "evaluate",
  "data": {
    "burst_id": "burst-456",
    "force_decision": false
  }
}
```

#### Response
```json
{
  "success": true,
  "data": {
    "state": "locked",
    "quality_score": 0.95,
    "messages": {
      "tagalog": "Steady lang... kukunin na",
      "english": "Hold steady... capturing"
    },
    "timing": {
      "response_time_ms": 45,
      "animation_flash_check_ms": 180
    }
  },
  "metadata": {
    "session_id": "user-123",
    "timestamp": "2025-01-16T10:30:00Z",
    "version": "2.0.0"
  }
}
```

---

### POST /v2/face/biometric
Unified biometric verification endpoint.

#### Request
```json
{
  "session_id": "user-123",
  "check_type": "match|pad|both",
  "reference_image": "base64_encoded",
  "live_image": "base64_encoded"
}
```

#### Response
```json
{
  "success": true,
  "data": {
    "match_score": 0.92,
    "pad_score": 0.95,
    "passed": true,
    "confidence": 0.93
  },
  "metadata": {
    "processing_time_ms": 250
  }
}
```

---

### GET /v2/face/stream/{session_id}
Server-Sent Events stream for real-time updates.

#### Request
```http
GET /v2/face/stream/user-123
Accept: text/event-stream
```

#### Response (SSE)
```
event: state_change
data: {"state": "locked", "timestamp": "2025-01-16T10:30:00Z"}

event: quality_update
data: {"quality_score": 0.95, "issues": []}

event: extraction_progress
data: {"field": "name", "value": "Juan Dela Cruz", "confidence": 0.94}

event: extraction_result
data: {"overall_confidence": 0.91, "fields": [...]}
```

---

### GET /v2/telemetry/{session_id}
Retrieve telemetry data for a session.

#### Query Parameters
- `data_type`: events|performance|flow|quality (optional)
- `since`: ISO timestamp (optional)
- `limit`: Max events to return (default: 100)

#### Request
```http
GET /v2/telemetry/user-123?data_type=performance
```

#### Response
```json
{
  "success": true,
  "data": {
    "metrics": {
      "time_to_lock_ms": 1500,
      "time_to_capture_ms": 4200,
      "extraction_time_ms": 3800,
      "total_time_ms": 9500
    },
    "events": [...]
  }
}
```

---

### GET /v2/system/health
System health and status check.

#### Response
```json
{
  "success": true,
  "data": {
    "status": "healthy",
    "uptime_seconds": 86400,
    "version": "2.0.0",
    "services": {
      "api": "healthy",
      "database": "healthy",
      "redis": "healthy",
      "extraction": "healthy"
    },
    "metrics": {
      "requests_per_second": 150,
      "average_response_ms": 45,
      "error_rate": 0.001
    }
  }
}
```

---

### POST /v2/face/challenge
Liveness challenge generation and verification.

#### Request
```json
{
  "session_id": "user-123",
  "action": "generate|verify",
  "data": {
    // Action-specific data
  }
}
```

#### Generate Challenge
```json
{
  "action": "generate",
  "data": {
    "challenge_type": "motion|color|expression"
  }
}
```

#### Verify Challenge
```json
{
  "action": "verify",
  "data": {
    "challenge_id": "challenge-789",
    "response_frames": [...]
  }
}
```

---

### POST /v2/face/decision
Final KYC decision based on all checks.

#### Request
```json
{
  "session_id": "user-123",
  "force_decision": false
}
```

#### Response
```json
{
  "success": true,
  "data": {
    "decision": "approved|review|rejected",
    "risk_score": 0.15,
    "confidence": 0.94,
    "reasons": [],
    "checks": {
      "document": "passed",
      "biometric": "passed",
      "liveness": "passed",
      "quality": "passed"
    }
  }
}
```

---

### GET /v2/messages/catalog
Retrieve all available messages in supported languages.

#### Query Parameters
- `lang`: Language code (tl|en)
- `type`: Message type filter

#### Response
```json
{
  "success": true,
  "data": {
    "messages": {
      "lock_acquired": {
        "tagalog": "Steady lang... kukunin na",
        "english": "Hold steady... capturing"
      },
      "front_captured": {
        "tagalog": "Harap OK ✅",
        "english": "Front OK ✅"
      }
    }
  }
}
```

---

## Response Format

### Standard Response Structure
All v2 endpoints return responses in this format:

```json
{
  "success": true|false,
  "data": {
    // Response data
  },
  "metadata": {
    "session_id": "string",
    "timestamp": "ISO8601",
    "version": "string",
    "processing_time_ms": 0,
    "endpoint": "string",
    "method": "string",
    "request_id": "string"
  },
  "messages": {
    "tagalog": "string",
    "english": "string"
  },
  "error": {
    "code": "string",
    "message": "string",
    "status_code": 0,
    "details": {}
  }
}
```

### Success Response
```json
{
  "success": true,
  "data": {
    "result": "value"
  },
  "metadata": {
    "processing_time_ms": 45
  }
}
```

### Error Response
```json
{
  "success": false,
  "error": {
    "code": "INVALID_REQUEST",
    "message": "Session ID is required",
    "status_code": 400,
    "details": {
      "field": "session_id"
    }
  }
}
```

---

## Error Codes

| Code | Status | Description |
|------|--------|-------------|
| INVALID_REQUEST | 400 | Invalid request parameters |
| UNAUTHORIZED | 401 | Invalid or missing API key |
| FORBIDDEN | 403 | Access denied |
| NOT_FOUND | 404 | Resource not found |
| RATE_LIMITED | 429 | Too many requests |
| INTERNAL_ERROR | 500 | Server error |
| SERVICE_UNAVAILABLE | 503 | Service temporarily unavailable |

---

## Rate Limiting

### Limits
- **Standard**: 100 requests/minute
- **Burst**: 10 requests/second
- **Stream**: 5 concurrent connections

### Headers
```http
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1642339200
```

---

## Deprecation Notice

### V1 Endpoints (Deprecated)
The following v1 endpoints are deprecated and will be sunset on 2025-07-16:

| V1 Endpoint | V2 Replacement |
|------------|----------------|
| POST /face/lock/check | POST /v2/face/scan (action=lock) |
| POST /face/burst/upload | POST /v2/face/scan (action=upload) |
| POST /face/burst/eval | POST /v2/face/scan (action=evaluate) |
| GET /face/stream/{id} | GET /v2/face/stream/{id} |
| GET /telemetry/events/{id} | GET /v2/telemetry/{id} |
| POST /face/pad/check | POST /v2/face/biometric |
| POST /face/match/verify | POST /v2/face/biometric |

### Deprecation Headers
```http
X-API-Deprecated: true
X-API-Deprecated-Use: /v2/face/scan
X-API-Deprecated-Sunset: 2025-07-16
Warning: 299 - "Endpoint deprecated. Use /v2/face/scan"
```

---

## Webhooks

### Configuration
```json
{
  "url": "https://your-server.com/webhook",
  "events": ["capture.complete", "extraction.complete"],
  "secret": "webhook_secret"
}
```

### Event Format
```json
{
  "event": "capture.complete",
  "session_id": "user-123",
  "timestamp": "2025-01-16T10:30:00Z",
  "data": {
    // Event-specific data
  }
}
```

### Signature Verification
```http
X-Webhook-Signature: sha256=...
```

---

## SDKs

### JavaScript/TypeScript
```javascript
import { KYCClient } from '@kyc-system/sdk';

const client = new KYCClient({
  apiKey: 'your-api-key',
  baseUrl: 'https://api.kyc-system.com'
});

const result = await client.face.scan({
  sessionId: 'user-123',
  action: 'lock',
  data: {...}
});
```

### Python
```python
from kyc_system import KYCClient

client = KYCClient(
    api_key='your-api-key',
    base_url='https://api.kyc-system.com'
)

result = client.face.scan(
    session_id='user-123',
    action='lock',
    data={...}
)
```

---

## Testing

### Test Environment
```
https://test-api.kyc-system.com
```

### Test Credentials
```
API Key: test_key_123456789
```

### Test Session IDs
- `test-success`: Always returns success
- `test-failure`: Always returns failure
- `test-quality-poor`: Poor quality response
- `test-extraction-slow`: Slow extraction (6s)

---

## Support

### Contact
- Technical: tech-support@kyc-system.com
- Integration: integrations@kyc-system.com

### Resources
- [Postman Collection](https://postman.com/kyc-system)
- [OpenAPI Specification](https://api.kyc-system.com/openapi.json)
- [Status Page](https://status.kyc-system.com)