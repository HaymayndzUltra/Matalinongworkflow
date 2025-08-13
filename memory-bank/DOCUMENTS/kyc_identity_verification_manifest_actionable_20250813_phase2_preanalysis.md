PHASE 2 Pre-Analysis — EVIDENCE EXTRACTION PIPELINE

Scope
- Document classifier, OCR/MRZ/Barcode/NFC ingestion, face crop extraction.

IMPORTANT NOTE (from plan)
- EE1: Document classifier top-1 ≥0.9 confidence on test set.
- EE2: ICAO 9303 MRZ checksums pass; PDF417/QR parsed; NFC where available.
- EE3: Face boxes returned; min crop size 112x112.

Risks & Prereqs
- Need labeled samples for classifier and MRZ/Barcode parsing.
- Integrate robust OCR/MRZ parsing libraries with checksum validation.
- Ensure deterministic face crop generation (min size ≥112x112) for downstream matching.

Next Steps
- Choose libraries for MRZ (ICAO 9303) and PDF417/QR; define API wrapper.
- Prepare a minimal classifier baseline or vendor integration and evaluation harness.
- Define face crop utility and IO schema for downstream phases.


