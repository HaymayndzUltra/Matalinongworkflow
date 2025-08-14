# Phase 1 Pre-Analysis — kyc_bank_grade_parity_actionable_20250814

## Phase Context
**Phase 1: PAD (Liveness) ISO 30107-3**

### Objectives
- Implement Presentation Attack Detection (PAD) Level 1/2 for anti-spoofing
- Deploy passive and/or challenge-response liveness detection
- Add metrics tracking (kyc_liveness_far, kyc_liveness_fnmr)
- Document evaluation and certification evidence
- Achieve performance targets: TAR@FAR1% ≥ 0.98, PAD FMR ≤ 1%, FNMR ≤ 3%

## Current State Assessment

### Existing Capabilities
- Face detection and extraction already implemented (≥112×112 resolution)
- Quality analysis framework in place
- Image forensics module can detect manipulation
- Threshold manager configured with PAD parameters

### Gaps to Address
- No active liveness detection (eye blink, head movement, etc.)
- No passive liveness analysis (texture, depth, reflection)
- Missing ISO 30107-3 compliance framework
- No PAD-specific metrics collection
- Certification evidence documentation needed

## Technical Requirements

### ISO 30107-3 Compliance
- **Level 1 (L1)**: Basic presentation attack detection
  - Print attacks
  - Screen replay attacks
  - Basic mask detection

- **Level 2 (L2)**: Advanced presentation attack detection  
  - 3D mask detection
  - Sophisticated replay attacks
  - Multi-modal spoofing attempts

### Performance Metrics
- **FAR (False Accept Rate)**: ≤ 1% - Rate of accepting spoofed attempts
- **FRR (False Reject Rate)**: ≤ 3% - Rate of rejecting genuine attempts  
- **TAR@FAR1%**: ≥ 0.98 - True Accept Rate when FAR is fixed at 1%
- **APCER (Attack Presentation Classification Error Rate)**: Target < 5%
- **BPCER (Bona Fide Presentation Classification Error Rate)**: Target < 7%

## Implementation Approach

### 1. Passive Liveness Detection
- Texture analysis using Local Binary Patterns (LBP)
- Frequency domain analysis (FFT for screen detection)
- Micro-texture analysis using Gabor wavelets
- Color space analysis (HSV, YCbCr for skin detection)
- Reflection and illumination consistency

### 2. Active Liveness Detection (Optional)
- Challenge-response mechanisms
- Random action requests (blink, smile, head turn)
- Motion analysis between frames
- 3D depth estimation from 2D images

### 3. Metrics Collection
- Real-time FAR/FRR calculation
- Prometheus metrics integration
- Performance dashboards in Grafana
- Audit trail for all liveness checks

## Risk Assessment

### Technical Risks
- **High**: Balancing security (low FAR) with user experience (low FRR)
- **Medium**: Processing latency impact on SLOs
- **Medium**: Integration with existing face detection pipeline

### Mitigation Strategies
- Implement configurable thresholds via ThresholdManager
- Use GPU acceleration where available
- Cache liveness models in memory
- Implement graceful degradation for system overload

## Success Criteria

1. **Functional Requirements**
   - PAD module integrated with face detection pipeline
   - Both passive and active liveness options available
   - Configurable L1/L2 operation modes

2. **Performance Requirements**
   - FAR ≤ 1% validated on test dataset
   - FRR ≤ 3% validated on test dataset
   - TAR@FAR1% ≥ 0.98 achieved
   - Processing time < 2 seconds per check

3. **Compliance Requirements**
   - ISO 30107-3 test methodology documented
   - Evaluation evidence collected and stored
   - Certification readiness documentation

## Deliverables

1. PAD implementation module (`src/liveness/pad_detector.py`)
2. Liveness metrics collector (`src/liveness/metrics.py`)
3. Test suite with spoofing samples
4. Performance evaluation report
5. ISO 30107-3 compliance documentation
6. Integration with existing KYC pipeline

## Dependencies

- OpenCV for image processing
- dlib or MediaPipe for facial landmarks
- scikit-learn for ML models
- NumPy/SciPy for numerical operations
- Prometheus client for metrics

## Estimated Effort

- Core PAD implementation: 2-3 days
- Metrics and monitoring: 1 day
- Testing and validation: 2 days
- Documentation and compliance: 1 day
- **Total: ~1 week**

## Next Steps

1. Set up PAD module structure
2. Implement passive liveness detection algorithms
3. Create test dataset with genuine and spoofed samples
4. Integrate with face detection pipeline
5. Validate performance metrics
6. Document compliance evidence