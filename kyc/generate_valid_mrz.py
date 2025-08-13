from __future__ import annotations

from pathlib import Path
from typing import Tuple
import argparse
import json

from kyc.evidence_extraction import _mrz_checksum, validate_mrz_td3


def build_valid_td3() -> Tuple[str, str]:
    # Line 1 (issuer + names). Validator only checks length; pad to 44
    line1 = "P<UTOJOHN<<DOE<<<<<<<<<<<<<<<<<<<<<<<<<<"  # shorter than 44
    if len(line1) < 44:
        line1 = line1 + ("<" * (44 - len(line1)))
    else:
        line1 = line1[:44]

    # Line 2 fields per simplified validator expectations
    passport_number = "123456789"  # 9 chars
    pn_check = str(_mrz_checksum(passport_number))
    nationality = "UTO"            # positions 10..12
    birth_date = "800101"          # YYMMDD
    birth_check = str(_mrz_checksum(birth_date))
    sex = "M"                      # position 20
    expiry_date = "250101"         # YYMMDD
    expiry_check = str(_mrz_checksum(expiry_date))
    personal_number = "<<<<<<<<<<<<<<"  # 14 chars filler
    personal_check = str(_mrz_checksum(personal_number))

    # Assemble line2 up to final check (pos 43)
    # Index map:
    # 0..8: passport_number
    # 9:    pn_check
    # 10..12: nationality
    # 13..18: birth_date
    # 19:     birth_check
    # 20:     sex
    # 21..26: expiry_date
    # 27:     expiry_check
    # 28..41: personal_number (14)
    # 42:     personal_check
    # 43:     final_check (computed below)
    line2_core = (
        passport_number
        + pn_check
        + nationality
        + birth_date
        + birth_check
        + sex
        + expiry_date
        + expiry_check
        + personal_number
        + personal_check
    )
    # Compute final composite per validator implementation
    composite = (
        passport_number
        + pn_check
        + nationality
        + birth_date
        + birth_check
        + sex
        + expiry_date
        + expiry_check
        + personal_number
        + personal_check
    )
    final_check = str(_mrz_checksum(composite))
    line2 = line2_core + final_check
    assert len(line2) == 44, f"TD3 line2 must be 44 chars, got {len(line2)}"

    # Validate with our validator to ensure success
    res = validate_mrz_td3(line1, line2)
    assert res.get("ok"), f"Generated MRZ failed validation: {res}"
    return line1, line2


def main():
    parser = argparse.ArgumentParser(description="Generate a valid MRZ TD3 pair and optionally write to a file")
    parser.add_argument("--outfile", type=Path, default=None, help="Write two-line MRZ to this file")
    parser.add_argument("--json", action="store_true", help="Print JSON with line1,line2")
    args = parser.parse_args()

    line1, line2 = build_valid_td3()
    if args.outfile:
        args.outfile.write_text(f"{line1}\n{line2}\n", encoding="utf-8")
    if args.json:
        print(json.dumps({"line1": line1, "line2": line2}, indent=2))
    else:
        print(line1)
        print(line2)


if __name__ == "__main__":
    main()


