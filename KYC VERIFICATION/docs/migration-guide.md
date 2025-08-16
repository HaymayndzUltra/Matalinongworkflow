# Migration Guide: V1 to V2

## Overview
This guide helps you migrate from v1 to v2 API endpoints. Version 2 offers improved performance, standardized responses, and enhanced features.

## Timeline
- **Now**: V2 endpoints available
- **2025-04-16**: V1 deprecation warnings active
- **2025-07-16**: V1 endpoints sunset

## Key Changes

### 1. Endpoint Consolidation
V2 reduces 33 endpoints to 8 unified endpoints.

| V1 Endpoints | V2 Endpoint | Benefit |
|-------------|-------------|---------|
| /face/lock/check<br>/face/burst/upload<br>/face/burst/eval | /v2/face/scan | Single endpoint with actions |
| /face/pad/check<br>/face/match/verify | /v2/face/biometric | Unified biometric checks |
| /telemetry/events<br>/telemetry/performance<br>/telemetry/flow<br>/telemetry/quality | /v2/telemetry/{id} | Single telemetry endpoint |

### 2. Response Format Standardization

#### V1 Response (Inconsistent)
```json
{
  "ok": true,
  "sessionId": "user-123",
  "lockResult": {
    "quality": 0.95
  }
}
```

#### V2 Response (Standardized)
```json
{
  "success": true,
  "data": {
    "quality_score": 0.95
  },
  "metadata": {
    "session_id": "user-123",
    "processing_time_ms": 45
  }
}
```

### 3. Parameter Naming
- **V1**: camelCase (`sessionId`, `faceGeometry`)
- **V2**: snake_case (`session_id`, `face_geometry`)

## Migration Steps

### Step 1: Update Endpoints

#### Face Lock Check
**V1:**
```javascript
// OLD
POST /face/lock/check
{
  "sessionId": "user-123",
  "image": "base64...",
  "faceGeometry": {...}
}
```

**V2:**
```javascript
// NEW
POST /v2/face/scan
{
  "session_id": "user-123",
  "action": "lock",
  "data": {
    "image": "base64...",
    "face_geometry": {...}
  }
}
```

#### Burst Upload
**V1:**
```javascript
// OLD
POST /face/burst/upload
{
  "sessionId": "user-123",
  "frames": [...]
}
```

**V2:**
```javascript
// NEW
POST /v2/face/scan
{
  "session_id": "user-123",
  "action": "upload",
  "data": {
    "frames": [...]
  }
}
```

#### Burst Evaluation
**V1:**
```javascript
// OLD
POST /face/burst/eval
{
  "sessionId": "user-123",
  "burstId": "burst-456"
}
```

**V2:**
```javascript
// NEW
POST /v2/face/scan
{
  "session_id": "user-123",
  "action": "evaluate",
  "data": {
    "burst_id": "burst-456"
  }
}
```

### Step 2: Update Response Handling

#### JavaScript/TypeScript
```javascript
// V1 Response Handler
function handleV1Response(response) {
  if (response.ok) {
    const quality = response.lockResult.quality;
    const sessionId = response.sessionId;
    // Process...
  }
}

// V2 Response Handler
function handleV2Response(response) {
  if (response.success) {
    const quality = response.data.quality_score;
    const sessionId = response.metadata.session_id;
    // Process...
  }
}

// Adapter for backward compatibility
function v1ToV2Adapter(v1Response) {
  return {
    success: v1Response.ok,
    data: {
      quality_score: v1Response.lockResult?.quality
    },
    metadata: {
      session_id: v1Response.sessionId
    }
  };
}
```

#### Python
```python
# V1 Response Handler
def handle_v1_response(response):
    if response['ok']:
        quality = response['lockResult']['quality']
        session_id = response['sessionId']
        # Process...

# V2 Response Handler
def handle_v2_response(response):
    if response['success']:
        quality = response['data']['quality_score']
        session_id = response['metadata']['session_id']
        # Process...

# Adapter for backward compatibility
def v1_to_v2_adapter(v1_response):
    return {
        'success': v1_response.get('ok'),
        'data': {
            'quality_score': v1_response.get('lockResult', {}).get('quality')
        },
        'metadata': {
            'session_id': v1_response.get('sessionId')
        }
    }
```

### Step 3: Update Error Handling

#### V1 Error Response
```json
{
  "ok": false,
  "error": "Invalid session",
  "code": 400
}
```

#### V2 Error Response
```json
{
  "success": false,
  "error": {
    "code": "INVALID_SESSION",
    "message": "Session ID is invalid or expired",
    "status_code": 400,
    "details": {
      "session_id": "user-123"
    }
  }
}
```

#### Error Handler Update
```javascript
// V1 Error Handler
if (!response.ok) {
  console.error(`Error ${response.code}: ${response.error}`);
}

// V2 Error Handler
if (!response.success) {
  const error = response.error;
  console.error(`Error ${error.code} (${error.status_code}): ${error.message}`);
  if (error.details) {
    console.error('Details:', error.details);
  }
}
```

## Parallel Running Strategy

### Phase 1: Shadow Mode (Recommended)
Run both v1 and v2 in parallel, compare results.

```javascript
async function shadowMigration(request) {
  // Call both versions
  const [v1Result, v2Result] = await Promise.all([
    callV1Api(request),
    callV2Api(request)
  ]);
  
  // Log differences for monitoring
  if (JSON.stringify(v1Result) !== JSON.stringify(v2Result)) {
    logDifference(v1Result, v2Result);
  }
  
  // Use v1 result for now
  return v1Result;
}
```

### Phase 2: Gradual Rollout
```javascript
async function gradualRollout(request) {
  const useV2 = Math.random() < 0.1; // Start with 10%
  
  if (useV2) {
    return callV2Api(request);
  } else {
    return callV1Api(request);
  }
}
```

### Phase 3: Full Migration
```javascript
async function fullMigration(request) {
  try {
    return await callV2Api(request);
  } catch (error) {
    // Fallback to v1 if needed
    console.warn('V2 failed, falling back to v1:', error);
    return callV1Api(request);
  }
}
```

## Feature Mapping

### Tagalog Messages
- **V1**: English only or separate field
- **V2**: Integrated bilingual messages

```javascript
// V1
response.message = "Hold steady";

// V2
response.messages = {
  tagalog: "Steady lang... kukunin na",
  english: "Hold steady... capturing"
};
```

### Timing Metadata
- **V1**: Not available
- **V2**: Included in all responses

```javascript
// V2 Only
response.data.timing = {
  animation_flash_check_ms: 180,
  response_time_ms: 45
};
```

### Streaming
- **V1**: `/face/stream/{id}`
- **V2**: `/v2/face/stream/{id}` (enhanced)

```javascript
// V1 SSE
event: update
data: {"type": "state", "value": "locked"}

// V2 SSE (more structured)
event: state_change
data: {"state": "locked", "timestamp": "2025-01-16T10:30:00Z", "metadata": {...}}
```

## Testing Migration

### 1. Unit Tests
```javascript
describe('API Migration', () => {
  it('should handle v2 responses', async () => {
    const response = await apiClient.v2.face.scan({
      session_id: 'test-123',
      action: 'lock',
      data: {...}
    });
    
    expect(response.success).toBe(true);
    expect(response.data).toBeDefined();
    expect(response.metadata.session_id).toBe('test-123');
  });
  
  it('should adapt v1 to v2 format', () => {
    const v1Response = {
      ok: true,
      sessionId: 'test-123',
      lockResult: { quality: 0.95 }
    };
    
    const v2Format = v1ToV2Adapter(v1Response);
    expect(v2Format.success).toBe(true);
    expect(v2Format.data.quality_score).toBe(0.95);
  });
});
```

### 2. Integration Tests
```python
def test_parallel_apis():
    """Test both v1 and v2 return compatible results"""
    session_id = "test-123"
    
    # Call v1
    v1_response = requests.post(
        f"{BASE_URL}/face/lock/check",
        json={"sessionId": session_id, ...}
    )
    
    # Call v2
    v2_response = requests.post(
        f"{BASE_URL}/v2/face/scan",
        json={"session_id": session_id, "action": "lock", ...}
    )
    
    # Compare core functionality
    assert v1_response.json()["ok"] == v2_response.json()["success"]
```

### 3. Load Testing
```bash
# Test v2 performance
ab -n 1000 -c 10 -p request.json -T application/json \
  https://api.kyc-system.com/v2/face/scan

# Compare with v1
ab -n 1000 -c 10 -p request.json -T application/json \
  https://api.kyc-system.com/face/lock/check
```

## Rollback Plan

### Quick Rollback
```javascript
// Environment variable control
const API_VERSION = process.env.KYC_API_VERSION || 'v1';

function getApiEndpoint(action) {
  if (API_VERSION === 'v2') {
    return `/v2/face/scan`;
  }
  // V1 endpoints
  switch(action) {
    case 'lock': return '/face/lock/check';
    case 'upload': return '/face/burst/upload';
    case 'evaluate': return '/face/burst/eval';
  }
}
```

### Feature Flags
```javascript
const features = {
  useV2Api: false,  // Toggle this
  useTagalogMessages: true,
  useStreamingUpdates: true
};

async function callApi(request) {
  if (features.useV2Api) {
    return callV2(request);
  }
  return callV1(request);
}
```

## Common Issues

### Issue 1: Case Sensitivity
**Problem**: V2 uses snake_case, V1 uses camelCase.
**Solution**: Use a case converter.

```javascript
function camelToSnake(obj) {
  return Object.keys(obj).reduce((acc, key) => {
    const snakeKey = key.replace(/([A-Z])/g, '_$1').toLowerCase();
    acc[snakeKey] = obj[key];
    return acc;
  }, {});
}
```

### Issue 2: Missing Metadata
**Problem**: V2 expects metadata that V1 doesn't provide.
**Solution**: Add defaults.

```javascript
function ensureMetadata(response) {
  if (!response.metadata) {
    response.metadata = {
      timestamp: new Date().toISOString(),
      version: '2.0.0'
    };
  }
  return response;
}
```

### Issue 3: Deprecation Headers
**Problem**: V1 endpoints show deprecation warnings.
**Solution**: Monitor and plan migration.

```javascript
// Check for deprecation
if (response.headers['X-API-Deprecated']) {
  const sunset = response.headers['X-API-Deprecated-Sunset'];
  console.warn(`API deprecated, sunset: ${sunset}`);
  console.warn(`Use: ${response.headers['X-API-Deprecated-Use']}`);
}
```

## Support

### Migration Assistance
- Email: migration@kyc-system.com
- Slack: #api-migration
- Documentation: https://docs.kyc-system.com/migration

### Tools
- [Migration Script](https://github.com/kyc-system/migration-tools)
- [Response Adapter Library](https://npm.com/@kyc-system/v1-v2-adapter)
- [Testing Suite](https://github.com/kyc-system/migration-tests)

## Checklist

### Pre-Migration
- [ ] Review API changes
- [ ] Update dependencies
- [ ] Test in staging environment
- [ ] Update error handling
- [ ] Plan rollback strategy

### During Migration
- [ ] Enable monitoring
- [ ] Run in shadow mode
- [ ] Compare responses
- [ ] Monitor error rates
- [ ] Track performance

### Post-Migration
- [ ] Remove v1 code
- [ ] Update documentation
- [ ] Clean up adapters
- [ ] Performance review
- [ ] Success metrics

## Success Metrics

### Target Metrics
- **API Response Time**: ≤50ms (improved from v1)
- **Error Rate**: <0.1%
- **Migration Success**: 100% feature parity
- **No Breaking Changes**: 0 customer impacts

### Monitoring
```javascript
// Track migration metrics
const metrics = {
  v1Calls: 0,
  v2Calls: 0,
  errors: 0,
  avgResponseTime: 0
};

// Log to monitoring service
sendMetrics('api.migration', metrics);
```

---

**Migration Deadline: 2025-07-16**

For questions or assistance, contact the migration team.