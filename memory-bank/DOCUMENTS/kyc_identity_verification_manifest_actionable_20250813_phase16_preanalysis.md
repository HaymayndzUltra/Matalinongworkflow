# Phase 16 Pre-Analysis: CONFIGS & ISSUER TEMPLATES (PH)

## Phase Overview
**Phase:** 16 - CONFIGS & ISSUER TEMPLATES (PH)
**Objective:** Ship configuration files and Philippine issuer templates

## IMPORTANT NOTE Restatement
**From Plan:** "Centralized thresholds in configs; templates define ROI boxes, fonts, tolerances, security features, and checksums."

This phase requires:
- policy_pack.yaml with decision thresholds
- vendors.yaml with vendor configurations
- Philippine issuer templates:
  - PhilID (Philippine National ID)
  - UMID (Unified Multi-Purpose ID)
  - Driver's License
  - Passport
  - PRC License (Professional Regulation Commission)
- Each template must include:
  - ROI (Region of Interest) boxes
  - Font specifications
  - Tolerance values
  - Security features (UV/hologram zones)
  - Checksum rules

## Prerequisites Check
✅ Phase 15 (Compliance Artifacts) completed
✅ All processing modules implemented
✅ Document classifier supports PH documents
✅ Template loading system exists

## Key Components to Implement
1. **Policy Configuration (policy_pack.yaml)**
   - Risk score thresholds
   - Decision rules
   - Auto-approve/deny limits
   - Review queue triggers
   - Policy versioning

2. **Vendor Configuration (vendors.yaml)**
   - Vendor endpoints
   - API credentials structure
   - Timeout/retry settings
   - Failover priorities
   - Cost/latency budgets

3. **Philippine ID Templates**
   - **PhilID Template**
     - PSN field location
     - Full name extraction
     - Birth date format
     - QR code position
     - Security features
   
   - **UMID Template**
     - CRN field location
     - Name fields
     - Employer info
     - Barcode specs
   
   - **Driver's License Template**
     - License number format
     - Expiry date location
     - Categories/restrictions
     - MRZ if present
   
   - **Passport Template**
     - MRZ location (2 lines)
     - Photo page layout
     - Signature location
     - Security features
   
   - **PRC License Template**
     - PRC number format
     - Profession field
     - Validity dates
     - Hologram location

4. **Template Structure**
   - Document dimensions
   - Field coordinates (x, y, width, height)
   - OCR zones configuration
   - Expected fonts and sizes
   - Validation rules
   - Checksum algorithms

5. **Security Features**
   - UV light patterns
   - Hologram locations
   - Watermark positions
   - Microprinting areas
   - Ghost image locations

## Implementation Components
1. **Config Loader**
   - YAML parsing
   - Schema validation
   - Default value handling
   - Environment variable substitution

2. **Template Registry**
   - Template loading
   - Version management
   - Fallback templates
   - Template validation

3. **ROI Extractor**
   - Coordinate mapping
   - Image cropping
   - Perspective correction
   - Scale normalization

4. **Validation Engine**
   - Field format validation
   - Checksum verification
   - Date range checks
   - Pattern matching

## Risk Considerations
1. **Template Accuracy**
   - Incorrect ROI coordinates
   - Missing security features
   - Wrong checksum algorithms

2. **Version Compatibility**
   - Old vs new ID formats
   - Template updates
   - Backward compatibility

3. **Security Risks**
   - Exposed thresholds
   - Hardcoded credentials
   - Template tampering

## Implementation Strategy
1. Create base configuration structure
2. Define policy thresholds and rules
3. Set up vendor configurations
4. Create PhilID template with all fields
5. Add other PH document templates
6. Implement ROI extraction logic
7. Add validation rules and checksums
8. Test with sample documents

## Success Criteria
- policy_pack.yaml with complete thresholds
- vendors.yaml with all vendor configs
- 5 Philippine issuer templates created
- ROI boxes accurately defined
- Security features documented
- Checksum validation working
- All configs centralized (no magic numbers)

## Rollback Plan
If configuration fails:
1. Use hardcoded defaults temporarily
2. Document missing configurations
3. Flag unsupported document types
4. Manual override capability

## Phase 16 Ready for Execution
All prerequisites met. Ready to implement configuration files and Philippine issuer templates.
