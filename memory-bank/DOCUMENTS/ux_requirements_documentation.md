# UX Requirements Documentation (A-H)
**Project:** KYC Face Scan System  
**Date:** 2025-01-16  
**Version:** 1.0

## Overview
This document outlines the eight core UX requirements (A-H) for the KYC face scan implementation, focusing on user experience, performance, and accessibility.

## Requirement A: State Machine Implementation
**Priority:** Critical  
**Category:** Core Infrastructure

### Description
Implement a comprehensive state machine to manage document capture flow with proper state transitions.

### States
- **SEARCHING**: Looking for document in frame
- **LOCKED**: Document detected and stable
- **COUNTDOWN**: Capture countdown in progress
- **CAPTURED**: Image captured successfully
- **CONFIRM**: User confirmation step
- **FLIP-TO-BACK**: Prompting user to flip document
- **BACK-SEARCHING**: Looking for back of document
- **COMPLETE**: Process finished

### Requirements
- Support both front and back document capture
- Track current_side (front/back)
- Maintain state history for telemetry
- Emit events on state transitions

## Requirement B: Timing & Animation Support
**Priority:** High  
**Category:** Performance & UX

### Timing Specifications
- **capture.flash_check**: 120-180ms flash + 250ms checkmark
- **transition.card_flip_y**: 350-450ms
- **stepper.advance_front_done**: 200ms
- **back.frame_pulse**: 3×300ms
- **countdown.ring**: 600ms
- **extraction.skeleton_fields**: <500ms
- **cancel-on-jitter response**: <50ms

### Requirements
- Return timing metadata in all API responses
- Support frontend animation synchronization
- Configurable timing thresholds

## Requirement C: Tagalog Microcopy Support
**Priority:** High  
**Category:** Localization

### Message Templates
- **LOCKED state**: "Steady lang… kukunin na"
- **Front captured**: "Harap OK ✅"
- **Flip prompt**: "Likod naman. I-frame ang barcode/QR kung meron"
- **Quality hints**: "Bawas glare / Ayusin sa loob ng frame / Hawak nang steady"
- **Cancel message**: "Gumalaw—subukan ulit"
- **Back captured**: "Likod OK ✅ — Tinitingnan ang detalye…"

### Requirements
- Tagalog as default language
- English fallback support
- Messages returned in API responses
- Support for message localization framework

## Requirement D: OCR Extraction with Confidence Scores
**Priority:** Critical  
**Category:** Data Processing

### Confidence Scoring
- **Green**: ≥0.9 (high confidence)
- **Amber**: 0.75-0.89 (medium confidence)
- **Red**: <0.75 (low confidence)

### Performance Targets
- **p50**: ≤4s from CAPTURED state
- **p95**: ≤6s from CAPTURED state

### Requirements
- Per-field confidence scores
- Color-coded confidence indicators
- Integration with burst_eval handler
- Support for streaming updates

## Requirement E: Real-time Streaming Implementation
**Priority:** High  
**Category:** Real-time Communication

### Endpoints
- **WebSocket**: `/ws/extraction/{session_id}`
- **SSE Fallback**: `/api/v1/kyc/extraction/stream/{session_id}`

### Requirements
- Field-by-field extraction updates
- Include confidence scores in streams
- Support multiple concurrent sessions
- Initial response <500ms
- Shimmer placeholder support

## Requirement F: Enhanced Quality Gates & Cancel-on-Jitter
**Priority:** Critical  
**Category:** Quality Control

### Quality Thresholds
- **Focus score**: <7.0 (cancel)
- **Motion score**: >0.4 (cancel)
- **Corners score**: <0.95 (cancel)
- **Glare percentage**: >3.5% (cancel)

### Error Conditions
- partial_document
- low_res
- blur_high

### Requirements
- Instant cancel response (<50ms)
- Clear Tagalog error messages
- Telemetry for cancel reasons
- Single-tap recapture support

## Requirement G: Front/Back Capture Flow
**Priority:** Critical  
**Category:** User Flow

### Front Capture Features
- "Harap OK" badge after capture
- Automatic stepper advance
- Transition to back capture

### Back Capture Features
- "I-frame ang barcode/QR" guidance
- Barcode/MRZ detection
- Countdown delay until decode_conf ≥0.95
- "Likod OK" confirmation

### Success Metrics
- Back-side completion rate ≥95%
- Clear distinction from selfie capture

## Requirement H: Telemetry for UX Events
**Priority:** High  
**Category:** Analytics & Monitoring

### Telemetry Events
- **capture.lock_open**: Lock achieved
- **countdown.start**: Countdown initiated
- **countdown.cancel_reason**: Why countdown was cancelled
- **capture.done_front**: Front capture completed
- **transition.front_to_back**: Flip transition
- **capture.done_back**: Back capture completed
- **extraction.fields_confidence_avg**: Average confidence
- **time_to_fields_ms**: Time to extract fields

### Requirements
- Precise timing data for all events
- State transition tracking
- Quality metrics inclusion
- Real-time tuning capability

## Additional Requirements

### Accessibility (Beyond H)
- Detect OS 'Reduce Motion' setting
- Alternative timing for reduced motion (200ms crossfade instead of flip)
- Disable haptic feedback when accessibility is on
- Text alternatives for all visual feedback
- Screen reader caption support
- ≥44×44 touch target sizing hints

### Acceptance Criteria
- Front→Back completion rate ≥95%
- Countdown visible ≥600ms
- Cancel-on-jitter <50ms response time
- Extraction latency p50≤4s, p95≤6s
- 9/10 users understand flow in comprehension test

### Parity Checklist
- ✅ Lock indicator with green corners
- ✅ Shutter flash animation
- ✅ Stepper advance animation
- ✅ Flip animation support
- ✅ Barcode assistance
- ✅ Real-time confidence display

## Implementation Priority Order
1. **Phase 0**: Setup & conflict resolution (current)
2. **Phase 1**: State machine (Requirement A)
3. **Phase 2**: Timing support (Requirement B)
4. **Phase 3**: Tagalog microcopy (Requirement C)
5. **Phase 4**: OCR extraction (Requirement D)
6. **Phase 5**: Streaming (Requirement E)
7. **Phase 6**: Quality gates (Requirement F)
8. **Phase 7**: Front/back flow (Requirement G)
9. **Phase 8**: Telemetry (Requirement H)
10. **Phase 9**: Accessibility
11. **Phase 10**: Acceptance testing

## Notes
- All requirements must be implemented in sequence
- Each phase builds upon the previous
- Testing required at each phase completion
- Documentation must be updated continuously