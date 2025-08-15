# Face Scan Implementation Protocol
## Backend-Only Implementation Guide

### Document Version
- **Version:** 1.0.0
- **Date:** 2025-01-16
- **Status:** Active
- **Phase:** 0 - Setup & Protocol

---

## 1. SCOPE & CONSTRAINTS

### 1.1 Implementation Boundaries
**STRICT ENFORCEMENT:**
- **Backend-Only Modifications:** All changes limited to backend services
- **Prohibited Files:** NO edits to `src/web/mobile_kyc.html` (AI-1 domain)
- **Allowed Modules:**
  - `src/api/app.py` - Main API application
  - `src/api/contracts.py` - API contracts and models
  - `src/config/threshold_manager.py` - Threshold configuration
  - `src/face/*` - All face-related modules (new)
- **Static Mount:** Optional `/web` path for static files (no UI modifications)

### 1.2 Technical Constraints
- **CORS/HTTPS:** Full exposure required for all endpoints
- **Feature Flags:** Allowed for progressive rollout
- **Phase Gates:** Mandatory validation between phases
- **Performance Targets:**
  - Lock detection: p50 ≤1.2s, p95 ≤2.5s
  - Endpoint response: ≤20ms typical
  - Challenge completion: ≤3.5s per action

---

## 2. PRIVACY & SECURITY REQUIREMENTS

### 2.1 Data Handling Policy
**MANDATORY COMPLIANCE:**

#### PII Protection
- **Logging:** NO raw PII/images in logs unless DEBUG explicitly enabled
- **Storage:** Transient only - RAM/tmpfs for temporary processing
- **Retention:** Auto-deletion post-evaluation (even on errors)
- **EXIF:** Strip all metadata from images

#### Image Processing
- **No Gallery Writes:** Images never persisted to gallery
- **No Long-term Storage:** All image data transient
- **Memory Cleanup:** Explicit clearing after processing
- **Audit Trail:** Store only anonymized metrics and decisions

### 2.2 Security Measures
- **Rate Limiting:** All endpoints must be rate-limit safe
- **Input Validation:** Strict bounds enforcement on all thresholds
- **Deterministic Outputs:** All functions must produce predictable results
- **Policy Snapshots:** Version and timestamp all decision policies

---

## 3. API ARCHITECTURE

### 3.1 Endpoint Structure
```
/face/
├── /lock/check          # Lock detection (no images)
├── /pad/pre             # Passive liveness pre-gate
├── /challenge/
│   ├── /script          # Generate challenge sequence
│   └── /verify          # Verify challenge completion
├── /burst/
│   ├── /upload          # Burst frame upload
│   └── /eval            # Consensus evaluation
├── /decision            # Final decision mapping
├── /telemetry           # Event tracking
└── /metrics             # Aggregated metrics
```

### 3.2 Response Standards
All endpoints must return:
- **Status:** HTTP status codes (200, 400, 401, 403, 429, 500)
- **Format:** JSON with consistent structure
- **Errors:** Human-readable reasons without PII
- **Versioning:** Include policy_version in responses

---

## 4. THRESHOLD MANAGEMENT

### 4.1 Required Thresholds
**All thresholds must use explicit names with validation:**

#### Geometry Thresholds
- `FACE_BBOX_FILL_MIN`: Minimum face bounding box fill ratio
- `FACE_CENTERING_TOLERANCE`: Maximum deviation from center
- `FACE_POSE_MAX_ANGLE`: Maximum allowed pose angles (yaw/pitch/roll)
- `FACE_TENENGRAD_MIN_640W`: Minimum sharpness at 640px width
- `FACE_BRIGHTNESS_MEAN_RANGE`: Acceptable brightness mean [min, max]
- `FACE_BRIGHTNESS_P05_MIN`: 5th percentile brightness minimum
- `FACE_BRIGHTNESS_P95_MAX`: 95th percentile brightness maximum
- `FACE_STABILITY_MIN_MS`: Minimum stable detection duration

#### PAD Thresholds
- `PAD_SCORE_MIN`: Minimum passive liveness score (0.70)
- `PAD_SPOOF_HIGH_THRESHOLD`: Spoof detection threshold
- `PAD_FMR_TARGET`: False Match Rate target (≤1%)
- `PAD_FNMR_TARGET`: False Non-Match Rate target (≤3%)

#### Burst & Consensus
- `BURST_MAX_FRAMES`: Maximum frames per burst (24)
- `BURST_MAX_DURATION_MS`: Maximum burst duration (3500ms)
- `CONSENSUS_TOP_K`: Number of top frames to consider (5)
- `CONSENSUS_MEDIAN_MIN`: Minimum median match score (0.62)
- `CONSENSUS_FRAME_MIN_COUNT`: Minimum frames above threshold (3)
- `CONSENSUS_FRAME_MIN_SCORE`: Per-frame minimum score (0.58)

#### Challenge Thresholds
- `CHALLENGE_ACTION_COUNT`: Number of actions per challenge (2)
- `CHALLENGE_TTL_MS`: Challenge time-to-live (7000ms)
- `CHALLENGE_ACTION_MAX_MS`: Maximum time per action (3500ms)
- `CHALLENGE_EAR_THRESHOLD`: Eye Aspect Ratio threshold
- `CHALLENGE_MAR_THRESHOLD`: Mouth Aspect Ratio threshold
- `CHALLENGE_YAW_THRESHOLD`: Yaw angle threshold

### 4.2 Configuration Management
- **Source:** Environment variables with defaults
- **Validation:** Bounds checking on all values
- **Override:** Document all override mechanisms
- **No Hardcoding:** Use ThresholdManager exclusively

---

## 5. TELEMETRY EVENTS

### 5.1 Required Events
Track the following events with timestamps:
- `FACE_SEARCHING` - User searching for face position
- `FACE_LOCK` - Face locked in position
- `COUNTDOWN_START` - UI countdown initiated
- `COUNTDOWN_STOP` - UI countdown completed/cancelled
- `BURST_START` - Burst capture initiated
- `BURST_END` - Burst capture completed
- `CHALLENGE_ISSUED` - Liveness challenge generated
- `CHALLENGE_PASSED` - Challenge successfully completed
- `CHALLENGE_FAILED` - Challenge failed
- `LIVENESS_PASS` - Overall liveness check passed
- `LIVENESS_FAIL` - Overall liveness check failed
- `MATCH_SCORE` - Biometric match score calculated
- `CONSENSUS_OK` - Consensus evaluation passed
- `FACE_DONE` - Face scan process completed

### 5.2 Metrics Aggregation
Expose via `/metrics` endpoint:
- `time_to_lock_ms` - Time to achieve face lock
- `cancel_rate` - Rate of cancelled sessions
- `challenge_success_rate` - Challenge completion rate
- `median_match_score` - Median biometric match score
- `passive_pad_fmr` - PAD False Match Rate
- `passive_pad_fnmr` - PAD False Non-Match Rate

---

## 6. WORM AUDIT REQUIREMENTS

### 6.1 Audit Entry Structure
Each decision must create an immutable audit entry:
```json
{
  "timestamp": "ISO-8601 with timezone",
  "session_id": "unique session identifier",
  "decision": "approve|review|deny",
  "policy_version": "policy snapshot version",
  "thresholds_used": {
    // All threshold values at decision time
  },
  "metrics": {
    // Anonymized performance metrics
  },
  "reasons": [
    // Human-readable decision factors
  ]
}
```

### 6.2 Retention Policy
- **Duration:** Define based on regulatory requirements
- **Storage:** Write-once, read-many system
- **Access:** Read-only after creation
- **Privacy:** No biometric data, only decisions

---

## 7. ACCEPTANCE CRITERIA

### 7.1 Performance Targets
**MANDATORY ACHIEVEMENT:**
- Lock Detection: p50 ≤1.2s, p95 ≤2.5s
- Countdown Duration: ≥600ms post-lock
- Cancel-on-jitter: <50ms response time
- Challenge Pass Rate: ≥95% (good lighting)
- TAR@FAR1%: ≥0.98 (evaluation set)
- PAD FMR: ≤1%
- PAD FNMR: ≤3%

### 7.2 Validation Requirements
- All thresholds configurable via ThresholdManager
- Metrics exposed and documented
- Performance report with gap analysis
- Threshold adjustment proposals if needed

---

## 8. PHASE GATE CHECKLIST

### Phase 0 Completion Requirements
- [x] Directory structure created (`src/api/`, `src/config/`, `src/face/`)
- [x] Protocol documentation created
- [ ] Privacy requirements documented
- [ ] CORS/HTTPS requirements documented
- [ ] Development environment configured
- [ ] Phase gates validation process defined

### Next Phase Prerequisites
Before proceeding to Phase 1:
1. All Phase 0 requirements completed
2. Documentation reviewed and approved
3. Development environment operational
4. Version control configured
5. CI/CD pipeline considerations documented

---

## APPENDIX A: GLOSSARY

- **PAD**: Presentation Attack Detection (anti-spoofing)
- **EAR**: Eye Aspect Ratio (eye openness metric)
- **MAR**: Mouth Aspect Ratio (mouth openness metric)
- **FAR**: False Accept Rate
- **FRR**: False Reject Rate
- **TAR**: True Accept Rate
- **WORM**: Write Once Read Many
- **Tenengrad**: Image sharpness metric

---

## APPENDIX B: REFERENCES

- ISO/IEC 19795-1: Biometric performance testing
- ISO/IEC 30107: Presentation attack detection
- NIST SP 800-63B: Digital Identity Guidelines
- GDPR Article 9: Processing of biometric data

---

*END OF PROTOCOL DOCUMENT*