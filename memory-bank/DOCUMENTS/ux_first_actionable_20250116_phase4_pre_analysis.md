# Phase 4 Pre-Analysis: OCR EXTRACTION WITH CONFIDENCE SCORES
**Task ID:** ux_first_actionable_20250116  
**Phase:** 4  
**Date:** 2025-01-16  
**Status:** 🔄 Starting

## Objective
Implement OCR extraction with confidence scores for UX Requirement D, ensuring all extracted fields include confidence metrics and support streaming updates.

## Prerequisites
✅ Phase 1: State machine (for CAPTURED state)
✅ Phase 2: Timing metadata (for extraction timing)
✅ Phase 3: Messages (for extraction feedback)

## Key Requirements (IMPORTANT NOTE)
"Extraction must include confidence scores for each field and support streaming updates via EXTRACT_START/RESULT events."

## Implementation Plan

### 1. Extraction Data Model
- Create `ExtractionResult` dataclass
- Include confidence scores (0.0-1.0)
- Support field-level confidence
- Add overall document confidence

### 2. Field Definitions
- First Name (confidence: 0.0-1.0)
- Middle Name (confidence: 0.0-1.0)
- Last Name (confidence: 0.0-1.0)
- Date of Birth (confidence: 0.0-1.0)
- Document Number (confidence: 0.0-1.0)
- Document Type (confidence: 0.0-1.0)
- Expiry Date (confidence: 0.0-1.0)
- Address (confidence: 0.0-1.0)

### 3. Streaming Events
- EXTRACT_START: Begin extraction
- EXTRACT_FIELD: Single field extracted
- EXTRACT_PROGRESS: Progress updates
- EXTRACT_RESULT: Complete results

### 4. Confidence Scoring System
- High confidence: > 0.85
- Medium confidence: 0.60-0.85
- Low confidence: < 0.60
- Color coding for UI (green/yellow/red)

### 5. API Response Enhancement
- Add `extraction` section to responses
- Include per-field confidence scores
- Overall extraction confidence
- Processing time metrics

## Risk Assessment

### Risks
1. **Performance Impact**: OCR processing may delay response
2. **Memory Usage**: Storing extraction results
3. **Confidence Accuracy**: Threshold tuning needed
4. **Streaming Complexity**: Event ordering issues

### Mitigation
1. Async processing with immediate response
2. Limit stored results per session
3. Configurable confidence thresholds
4. Event sequencing with timestamps

## Implementation Steps

1. **Create extraction models** (`extraction.py`)
   - ExtractionResult dataclass
   - FieldConfidence dataclass
   - ExtractionEvent enum

2. **Add extraction processor**
   - Mock OCR engine for testing
   - Confidence calculation logic
   - Field validation

3. **Integrate with session state**
   - Store extraction results
   - Track extraction progress
   - Handle streaming events

4. **Update API handlers**
   - Add extraction endpoint
   - Include in burst_eval response
   - Support streaming updates

5. **Add extraction messages**
   - Progress indicators
   - Confidence warnings
   - Field-specific feedback

## Success Criteria
- ✅ All fields have confidence scores
- ✅ Streaming events working
- ✅ Confidence thresholds configurable
- ✅ API responses include extraction
- ✅ Tests validate confidence scoring
- ✅ Performance < 500ms initial response

## Testing Strategy
- Unit tests for confidence calculation
- Integration tests for streaming
- Performance tests for extraction
- Validate against sample documents

## Next Phase Dependencies
This phase enables:
- Phase 5: Real-time streaming
- Phase 10: UX acceptance testing
- Phase 13: Biometric integration