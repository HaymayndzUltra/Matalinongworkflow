# Phase 2 Pre-Analysis — kyc_bank_grade_parity_actionable_20250814

## Phase Context
**Phase 2: NFC eMRTD Passive Authentication (PA)**

### Objectives
- Extend NFC path to read EF.SOD (Security Object Document)
- Verify DSC/CSCA certificate chain
- Validate DG (Data Group) hash integrity
- Emit kyc_nfc_pa_verified gauge metric
- Persist verification artifacts

## Current State Assessment

### Existing Capabilities
- Configuration framework ready (threshold manager)
- Metrics collection system operational (from Phase 1)
- Environment variables defined for NFC settings
- Audit trail infrastructure in place

### Gaps to Address
- No NFC reader interface implementation
- Missing eMRTD data structure parsing
- No certificate chain validation logic
- CSCA/DSC certificate storage not configured
- DG hash verification not implemented

## Technical Requirements

### ICAO 9303 Standards
- **Passive Authentication**: Verify document authenticity without chip interaction
- **Certificate Chain**: CSCA → DSC → Document
- **Data Groups**: DG1 (MRZ), DG2 (Face), DG3 (Fingerprints), etc.
- **Security Object**: EF.SOD containing hashes of all data groups

### Implementation Components
1. **NFC Interface Layer**
   - PC/SC reader support
   - ISO 14443 Type A/B communication
   - APDU command/response handling

2. **eMRTD Parser**
   - TLV (Tag-Length-Value) structure parsing
   - ASN.1 decoding for certificates
   - Data group extraction

3. **Cryptographic Validation**
   - X.509 certificate chain verification
   - RSA/ECDSA signature validation
   - SHA-256/SHA-512 hash verification

4. **Certificate Management**
   - CSCA master list management
   - DSC certificate caching
   - CRL/OCSP checking (optional)

## Risk Assessment

### Technical Risks
- **High**: Hardware dependency on NFC readers
- **Medium**: Certificate expiry and revocation handling
- **Medium**: Performance impact of cryptographic operations
- **Low**: Compatibility with different eMRTD implementations

### Mitigation Strategies
- Abstract NFC interface for multiple reader types
- Implement certificate caching and pre-validation
- Use hardware acceleration for crypto operations where available
- Graceful fallback for non-NFC documents

## Success Criteria

1. **Functional Requirements**
   - Successfully read EF.SOD from eMRTD
   - Validate complete certificate chain
   - Verify all DG hashes match SOD
   - Support Philippine passport and PhilID

2. **Performance Requirements**
   - NFC read completion < 5 seconds
   - Certificate validation < 1 second
   - Total PA process < 10 seconds

3. **Security Requirements**
   - Secure certificate storage
   - Audit trail for all PA operations
   - Clear failure reasons logging

## Dependencies

- Python NFC libraries (nfcpy, pyscard)
- Cryptography libraries (cryptography, pyasn1)
- Certificate storage infrastructure
- NFC reader hardware (ACR122U or similar)

## Deliverables

1. NFC interface module (`src/nfc/nfc_reader.py`)
2. eMRTD parser (`src/nfc/emrtd_parser.py`)
3. PA validator (`src/nfc/passive_auth.py`)
4. Certificate manager (`src/nfc/cert_manager.py`)
5. Integration tests
6. Compliance documentation

## Estimated Effort

- NFC interface: 1-2 days
- eMRTD parsing: 2 days
- PA implementation: 2 days
- Testing and integration: 2 days
- **Total: ~1 week**

## Next Steps

1. Set up NFC development environment
2. Implement basic NFC reader interface
3. Create eMRTD data structure parsers
4. Implement certificate chain validation
5. Add metrics and monitoring
6. Document compliance with ICAO 9303