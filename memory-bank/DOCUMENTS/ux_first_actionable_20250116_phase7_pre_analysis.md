# Phase 7 Pre-Analysis: FRONT/BACK CAPTURE FLOW
**Task ID:** ux_first_actionable_20250116  
**Phase:** 7  
**Date:** 2025-01-16  
**Status:** 🔄 Starting

## Objective
Implement front/back document capture flow for UX Requirement G, ensuring back-side capture guides users to capture the document (not selfie) with ≥95% completion rate.

## Prerequisites
✅ Phase 1: State machine (for front/back states)
✅ Phase 3: Messages (for guidance text)
✅ Phase 4: Extraction (for side-specific OCR)
✅ Phase 6: Quality gates (for per-side validation)

## Key Requirements (IMPORTANT NOTE)
"Back-side capture must guide users to capture document, not selfie. Completion rate for back step must be ≥95%."

## Implementation Plan

### 1. Front/Back State Flow
- FRONT states: SEARCHING → LOCKED → COUNTDOWN → CAPTURED → CONFIRM
- Transition: CONFIRM → FLIP_TO_BACK
- BACK states: BACK_SEARCHING → LOCKED → COUNTDOWN → CAPTURED → COMPLETE
- Clear state indicators per side

### 2. Back Capture Guidance
- "I-flip ang dokumento" (Flip the document)
- "Ipakita ang likod ng ID" (Show the back of ID)
- "Hindi selfie—likod ng dokumento" (Not selfie—back of document)
- Visual indicator for document flip
- Progress indicator (1/2, 2/2)

### 3. Side-Specific Processing
- Front: Extract personal details
- Back: Extract additional info
- Side-specific quality thresholds
- Different OCR fields per side

### 4. Completion Rate Optimization
- Clear flip instructions
- Auto-proceed after front confirm
- Visual flip animation guidance
- Progress persistence
- Resume support if interrupted

### 5. Session State Tracking
- front_captured flag
- back_captured flag
- current_side indicator
- Extraction per side
- Quality scores per side

## Risk Assessment

### Risks
1. **User Confusion**: May take selfie instead
2. **Abandonment**: May quit after front
3. **Quality Drop**: Back often lower quality
4. **State Loss**: Disconnection handling

### Mitigation
1. Explicit "NOT SELFIE" messaging
2. Auto-proceed with progress
3. Adjusted thresholds for back
4. State persistence

## Implementation Steps

1. **Create capture flow module** (`capture_flow.py`)
   - CaptureFlowManager class
   - Front/back orchestration
   - Progress tracking

2. **Enhance messages**
   - Back-specific guidance
   - Flip instructions
   - Progress indicators

3. **Update handlers**
   - Side-aware processing
   - Auto-transition logic
   - Progress persistence

4. **Add completion tracking**
   - Metrics per side
   - Abandonment detection
   - Success rate calculation

5. **Test both sides**
   - Full flow testing
   - Interruption recovery
   - Completion rate measurement

## Success Criteria
- ✅ Front capture working
- ✅ Back capture working
- ✅ Clear flip guidance
- ✅ ≥95% back completion rate
- ✅ Side-specific extraction
- ✅ Progress persistence
- ✅ Resume support

## Testing Strategy
- Full flow simulation
- Abandonment testing
- Message clarity testing
- State persistence testing
- Completion rate measurement

## Next Phase Dependencies
This phase enables:
- Phase 10: UX acceptance testing
- Phase 13: Biometric integration
- Phase 14: API consolidation