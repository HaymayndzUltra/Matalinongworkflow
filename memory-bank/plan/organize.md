Manifest OK: 19 requirements

[identity_capture]
 - IC1: Web/mobile guided capture; glare/blur/orientation checks; multi-frame burst (accept: >95% pass at 1000px width, orientation auto-correct, quality scores in [0..1])
 - IC2: Inputs: ID front/back, passport MRZ, selfie video for liveness (accept: MIME/type validated, size/duration limits enforced)

[evidence_extraction]
 - EE1: Document classifier (ID/passport/other) (accept: >=0.9 top1 confidence on test set)
 - EE2: OCR/MRZ/Barcode/NFC (accept: ICAO 9303 checksums pass, PDF417/QR parsed, NFC where available)
 - EE3: Face crops: ID and selfie (accept: face boxes returned, min size 112x112)

[authenticity_checks]
 - AU1: Security features: microprint/guilloché/UV (where feasible) (accept: thresholds documented per template)
 - AU2: Tamper detection: reprint/screenshot/composite (accept: AUC≥0.9 on benchmark; ELA/noise/lighting features)
 - AU3: Liveness: passive (texture/rPPG) + active (challenge) (accept: FNMR≤3%, FMR≤1% on eval)
 - AU4: Face match: ID vs selfie, multi-frame consensus (accept: TAR@FAR1% ≥ 98%)

[sanctions_aml]
 - SA1: Sanctions/PEP/adverse media; watchlists; IP/geo (accept: vendor API integrated, hit explainability present)

[risk_scoring]
 - RS1: Device fingerprint; proxy/VPN/TOR; geovelocity (accept: proxy/VPN detection enabled)
 - RS2: Doc validity/expiry; field consistency; issuer formats (accept: expiry/format validators implemented)
 - RS3: Aggregate score (rules + ML) → approve/review/deny (accept: calibrated thresholds; ROC/AUC reported)

[human_review]
 - HR1: Reviewer console with redaction, dual-control (accept: PII redaction toggle, two-person approval on high risk)

[compliance_security_privacy]
 - CP1: DPA/GDPR/CCPA; AML/KYC; NIST 800-63-3 alignment (accept: gaps documented and tracked)
 - CP2: Data minimization; encryption at rest; KMS/HSM; WORM audit logs; retention (accept: AES-256 at rest; TLS1.2+; append-only audit; retention policies applied)
 - CP3: DPIA/ROPA (accept: legal sign-off recorded)

[operations]
 - OP1: Observability: metrics, traces, risk distributions, FPR (accept: SLOs defined; oncall alerts wired)
 - OP2: AB tests; drift monitoring; periodic re-training; fairness checks (accept: drift alarms; bias audits scheduled)