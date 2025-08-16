# Phase 3 Pre-Analysis: TAGALOG MICROCOPY SUPPORT
**Task ID:** ux_first_actionable_20250116  
**Phase:** 3  
**Date:** 2025-01-16  
**Status:** Ready to Execute

## Phase 3 IMPORTANT NOTE (Restated)
"All user-facing messages must be in Tagalog by default with English fallback. Messages must be returned in API responses for frontend display."

## Phase Objectives
Implement all Tagalog-first microcopy in API responses:
- Add message templates:
  - "Steady lang… kukunin na" (LOCKED state)
  - "Harap OK ✅" (front captured)
  - "Likod naman. I-frame ang barcode/QR kung meron" (flip prompt)
  - "Bawas glare / Ayusin sa loob ng frame / Hawak nang steady" (quality hints)
  - "Gumalaw—subukan ulit" (cancel message)
  - "Likod OK ✅ — Tinitingnan ang detalye…" (back captured)
- Support message localization framework
- Include messages in API responses

## Prerequisites ✅
1. **State machine implemented** - Complete (Phase 1)
2. **Timing metadata working** - Complete (Phase 2)
3. **API response structure exists** - Confirmed
4. **State tracking operational** - Working

## Risks & Mitigations

### Risk 1: Character Encoding Issues
**Impact:** High  
**Mitigation:**
- Ensure UTF-8 encoding throughout
- Test with emoji (✅) support
- Validate JSON serialization

### Risk 2: Message Context Mismatch
**Impact:** Medium  
**Mitigation:**
- Map messages to specific states
- Include context hints
- Test all state transitions

### Risk 3: Localization Scalability
**Impact:** Low  
**Mitigation:**
- Design extensible structure
- Support language codes
- Plan for future languages

## Implementation Strategy

### Step 1: Create Message Templates
- Define message structure
- Map to states and conditions
- Include quality-specific hints

### Step 2: Implement Localization System
- Create message manager
- Support language selection
- Implement fallback logic

### Step 3: Integrate with Session State
- Add message tracking
- Update based on state
- Include quality feedback

### Step 4: Enhance API Responses
- Add `messages` section
- Include current message
- Provide hint messages

### Step 5: Testing
- Verify all messages display
- Test language fallback
- Validate emoji support

## Success Criteria
- ✅ All Tagalog messages implemented
- ✅ English fallback working
- ✅ Messages in API responses
- ✅ State-appropriate messaging
- ✅ Quality hints provided
- ✅ Emoji (✅) rendering correctly

## Files to Modify
1. Create `KYC VERIFICATION/src/face/messages.py` - Message templates
2. `KYC VERIFICATION/src/face/session_manager.py` - Message integration
3. `KYC VERIFICATION/src/face/handlers.py` - Response enhancement
4. `KYC VERIFICATION/src/config/threshold_manager.py` - Language config

## Rollback Plan
If messages cause issues:
1. Disable localization temporarily
2. Use English-only messages
3. Debug encoding issues
4. Re-enable incrementally

## Notes
- Consider message length for mobile UI
- Test with actual Tagalog speakers
- Ensure cultural appropriateness
- Document all message mappings