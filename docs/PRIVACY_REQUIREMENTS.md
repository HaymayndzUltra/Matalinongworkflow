# Privacy Requirements Document
## Face Scan Implementation - Data Protection Guidelines

### Document Control
- **Version:** 1.0.0
- **Date:** 2025-01-16
- **Classification:** Confidential
- **Compliance:** GDPR, CCPA, ISO 27001

---

## 1. EXECUTIVE SUMMARY

This document defines mandatory privacy requirements for the backend-only face scan implementation. All developers, reviewers, and stakeholders must ensure strict compliance with these requirements to protect user biometric data and maintain regulatory compliance.

---

## 2. DATA CLASSIFICATION

### 2.1 Biometric Data (HIGHLY SENSITIVE)
- **Definition:** Facial images, facial features, biometric templates
- **Classification:** PII - Personally Identifiable Information
- **Sensitivity:** CRITICAL
- **Special Category:** Yes (GDPR Article 9)

### 2.2 Metadata (SENSITIVE)
- **Definition:** Timestamps, session IDs, device information
- **Classification:** Indirect PII
- **Sensitivity:** HIGH
- **Special Category:** No

### 2.3 Metrics (INTERNAL)
- **Definition:** Aggregated statistics, performance metrics
- **Classification:** Non-PII
- **Sensitivity:** LOW
- **Special Category:** No

---

## 3. DATA HANDLING REQUIREMENTS

### 3.1 Collection Principles
**MANDATORY COMPLIANCE:**

#### Minimization
- Collect ONLY data necessary for face verification
- No collection of unnecessary metadata
- No collection for secondary purposes

#### Purpose Limitation
- Data used ONLY for identity verification
- No repurposing without explicit consent
- No training of ML models without anonymization

#### Transparency
- Clear indication when face scan is active
- Explicit consent before biometric processing
- User awareness of data usage

### 3.2 Processing Rules

#### Transient Processing Only
```python
# CORRECT: Transient processing
def process_face_image(image_data):
    # Process in memory
    result = analyze_face(image_data)
    # Clear immediately
    del image_data
    gc.collect()
    return result

# INCORRECT: Persistent storage
def process_face_image(image_data):
    # NEVER DO THIS
    save_to_disk(image_data)  # VIOLATION
    result = analyze_face(image_data)
    return result
```

#### No Persistent Storage
- **RAM/tmpfs ONLY:** Use memory or temporary filesystem
- **Auto-cleanup:** Implement automatic deletion
- **Error Handling:** Clean up even on exceptions

```python
# CORRECT: With cleanup
import tempfile
import os

def process_burst(frames):
    temp_dir = None
    try:
        # Use tmpfs if needed
        temp_dir = tempfile.mkdtemp(dir='/dev/shm')
        # Process frames
        result = process_frames(frames, temp_dir)
        return result
    finally:
        # Always cleanup
        if temp_dir and os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
```

### 3.3 Logging Restrictions

#### Production Logging
```python
# CORRECT: Anonymized logging
logger.info(f"Face scan completed: session={session_id}, result={decision}")

# INCORRECT: PII in logs
logger.info(f"Face scan for user {user_email}: {face_image_data}")  # VIOLATION
```

#### Debug Mode
```python
import os

DEBUG_MODE = os.getenv('DEBUG_FACE_SCAN', 'false').lower() == 'true'

def log_face_data(data):
    if DEBUG_MODE:
        # Only in explicit debug mode
        logger.debug(f"Face data shape: {data.shape}")
    else:
        # Production: no data logging
        logger.info("Face processing completed")
```

---

## 4. SECURITY MEASURES

### 4.1 Encryption Requirements

#### In Transit
- **Protocol:** HTTPS/TLS 1.3 minimum
- **Certificate:** Valid SSL certificate required
- **HSTS:** Enable HTTP Strict Transport Security

#### In Processing
- **Memory:** Use secure memory allocation where available
- **Cleanup:** Overwrite memory after use
- **Swap:** Disable swap for sensitive processes

### 4.2 Access Control

#### API Authentication
- **Required:** Bearer token or API key
- **Session:** Limited duration (max 30 minutes)
- **Rate Limiting:** Prevent abuse

```python
from functools import wraps
from flask import request, abort

def require_auth(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        auth = request.headers.get('Authorization')
        if not validate_token(auth):
            abort(401)
        return f(*args, **kwargs)
    return decorated_function

@app.route('/face/lock/check')
@require_auth
@rate_limit(calls=10, period=60)  # 10 calls per minute
def check_face_lock():
    # Implementation
    pass
```

### 4.3 EXIF Data Stripping

**MANDATORY: Remove all metadata from images**

```python
from PIL import Image
import io

def strip_exif(image_bytes):
    """Remove all EXIF data from image"""
    img = Image.open(io.BytesIO(image_bytes))
    
    # Create new image without EXIF
    data = list(img.getdata())
    image_without_exif = Image.new(img.mode, img.size)
    image_without_exif.putdata(data)
    
    # Return clean bytes
    clean_bytes = io.BytesIO()
    image_without_exif.save(clean_bytes, format='JPEG')
    return clean_bytes.getvalue()
```

---

## 5. AUDIT & COMPLIANCE

### 5.1 Audit Log Requirements

#### What to Log
```json
{
  "timestamp": "2025-01-16T14:30:00+08:00",
  "event": "face_verification_completed",
  "session_id": "sess_abc123",
  "result": "approved",
  "confidence": 0.95,
  "processing_time_ms": 1250,
  "policy_version": "1.0.0"
}
```

#### What NOT to Log
- Actual face images
- Biometric templates
- User identifying information
- Raw similarity scores with PII

### 5.2 WORM Audit Trail

```python
import hashlib
import json
from datetime import datetime

class WORMAuditLog:
    def __init__(self):
        self.entries = []
    
    def add_entry(self, session_id, decision, metrics):
        entry = {
            'timestamp': datetime.utcnow().isoformat(),
            'session_id': session_id,
            'decision': decision,
            'metrics': metrics,
            'hash': None
        }
        
        # Chain entries with hash
        if self.entries:
            prev_hash = self.entries[-1]['hash']
            entry['prev_hash'] = prev_hash
        
        # Calculate entry hash
        entry_str = json.dumps(entry, sort_keys=True)
        entry['hash'] = hashlib.sha256(entry_str.encode()).hexdigest()
        
        # Write-once
        self.entries.append(entry)
        self._persist_entry(entry)
    
    def _persist_entry(self, entry):
        # Write to append-only log
        with open('/var/log/face_audit.log', 'a') as f:
            f.write(json.dumps(entry) + '\n')
```

---

## 6. DATA RETENTION & DELETION

### 6.1 Retention Periods

| Data Type | Retention Period | Deletion Method |
|-----------|-----------------|-----------------|
| Face Images | 0 seconds (transient only) | Immediate memory clear |
| Session Data | 30 minutes | Automatic expiry |
| Audit Logs | 7 years | Archived after 1 year |
| Metrics | 90 days | Aggregated and anonymized |

### 6.2 Deletion Procedures

```python
import gc
import ctypes
import sys

def secure_delete(data):
    """Securely delete sensitive data from memory"""
    if isinstance(data, bytes):
        # Overwrite bytes
        mutable = ctypes.create_string_buffer(len(data))
        ctypes.memmove(mutable, data, len(data))
        ctypes.memset(mutable, 0, len(data))
    
    # Remove references
    del data
    
    # Force garbage collection
    gc.collect()
```

---

## 7. CONSENT MANAGEMENT

### 7.1 Consent Requirements
- **Explicit:** User must actively consent
- **Informed:** Clear explanation of processing
- **Withdrawable:** User can revoke consent
- **Documented:** Consent records maintained

### 7.2 Consent API

```python
@app.route('/face/consent', methods=['POST'])
def record_consent():
    consent_data = {
        'session_id': request.json['session_id'],
        'timestamp': datetime.utcnow().isoformat(),
        'purpose': 'identity_verification',
        'version': '1.0',
        'granted': True
    }
    # Store consent record (not face data)
    store_consent(consent_data)
    return jsonify({'status': 'consent_recorded'})
```

---

## 8. INCIDENT RESPONSE

### 8.1 Data Breach Protocol
1. **Immediate:** Stop affected service
2. **Within 1 hour:** Notify security team
3. **Within 72 hours:** Notify authorities (GDPR requirement)
4. **Document:** Record all actions taken

### 8.2 Privacy Violations
- Immediate investigation
- Root cause analysis
- Corrective actions
- Update procedures

---

## 9. COMPLIANCE CHECKLIST

### Development Phase
- [ ] No hardcoded PII in source code
- [ ] EXIF stripping implemented
- [ ] Transient storage only
- [ ] Secure memory handling
- [ ] Audit logging without PII

### Testing Phase
- [ ] Use synthetic test data
- [ ] No production data in test
- [ ] Security scan completed
- [ ] Privacy impact assessment

### Deployment Phase
- [ ] HTTPS/TLS configured
- [ ] Rate limiting enabled
- [ ] Monitoring configured
- [ ] Incident response ready

---

## 10. ENFORCEMENT

### 10.1 Violations
Any violation of these privacy requirements will result in:
1. Immediate code rollback
2. Security review
3. Retraining requirement
4. Potential disciplinary action

### 10.2 Exceptions
No exceptions permitted without:
- Written justification
- Risk assessment
- Legal review
- Executive approval

---

## APPENDIX: REGULATORY REFERENCES

### GDPR (General Data Protection Regulation)
- Article 9: Processing of special categories
- Article 32: Security of processing
- Article 33: Breach notification
- Article 35: Privacy impact assessment

### CCPA (California Consumer Privacy Act)
- Section 1798.100: Consumer rights
- Section 1798.150: Data breach liability

### ISO 27001
- A.8: Asset management
- A.12: Operations security
- A.18: Compliance

---

*END OF PRIVACY REQUIREMENTS DOCUMENT*