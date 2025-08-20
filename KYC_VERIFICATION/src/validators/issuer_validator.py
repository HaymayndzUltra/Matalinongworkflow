"""
Issuer Rules & Validators Module
Phase 6: Issuer-specific validators for expiry/format/name/DOB logic
All thresholds config-driven from templates, no magic numbers
"""

import re
import json
import logging
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from enum import Enum
from datetime import datetime, date, timedelta
from pathlib import Path
import hashlib
import difflib

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ValidationResult(Enum):
    """Validation result types"""
    VALID = "valid"
    INVALID = "invalid"
    WARNING = "warning"
    EXPIRED = "expired"
    NOT_YET_VALID = "not_yet_valid"

@dataclass
class FieldValidation:
    """Individual field validation result"""
    field_name: str
    value: Any
    result: ValidationResult
    confidence: float
    reason: Optional[str] = None
    expected_format: Optional[str] = None

@dataclass
class IssuerValidationResult:
    """Complete issuer validation result"""
    issuer: str
    document_type: str
    is_valid: bool
    overall_confidence: float
    field_validations: List[FieldValidation]
    expiry_status: ValidationResult
    checksum_valid: bool
    warnings: List[str]
    errors: List[str]
    metadata: Dict[str, Any]

class PhilippineIDValidator:
    """Base validator for Philippine IDs"""
    
    def __init__(self, config_path: Optional[str] = None):
        """Initialize validator with configuration"""
        self.config = self._load_config(config_path)
        self.templates = self._load_templates()
        
    def _load_config(self, config_path: Optional[str]) -> Dict:
        """Load validation configuration"""
        default_config = {
            "name_match_threshold": 0.85,
            "date_tolerance_days": 3,
            "expiry_warning_days": 30,
            "checksum_algorithms": ["luhn", "mod97", "custom"],
            "validation_rules": {
                "strict_mode": False,
                "allow_expired": False,
                "require_all_fields": False,
                "fuzzy_matching": True
            },
            "field_weights": {
                "id_number": 0.3,
                "name": 0.25,
                "date_of_birth": 0.2,
                "expiry": 0.15,
                "checksum": 0.1
            }
        }
        
        if config_path and Path(config_path).exists():
            with open(config_path, 'r') as f:
                user_config = json.load(f)
                default_config.update(user_config)
        
        return default_config
    
    def _load_templates(self) -> Dict[str, Dict]:
        """Load issuer-specific validation templates"""
        templates = {
            "PhilID": {
                "id_pattern": r"^\d{4}-\d{4}-\d{4}-\d{4}$",
                "name_format": "LASTNAME, FIRSTNAME MIDDLENAME",
                "date_format": "%m/%d/%Y",
                "expiry_years": 5,
                "required_fields": ["PSN", "Full Name", "Date of Birth", "Sex", "Blood Type"],
                "checksum_type": "mod97",
                "special_rules": {
                    "blood_type_values": ["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"],
                    "sex_values": ["M", "F"],
                    "min_age": 0,
                    "max_age": 150
                }
            },
            "UMID": {
                "id_pattern": r"^\d{2}-\d{7}-\d{1}$",
                "name_format": "FIRSTNAME MIDDLENAME LASTNAME",
                "date_format": "%m/%d/%Y",
                "expiry_years": 5,
                "required_fields": ["CRN", "SSS", "Given Name", "Surname", "Date of Birth"],
                "checksum_type": "luhn",
                "special_rules": {
                    "sss_pattern": r"^\d{2}-\d{7}-\d{1}$",
                    "tin_pattern": r"^\d{3}-\d{3}-\d{3}-\d{3}$",
                    "gsis_pattern": r"^\d{11}$"
                }
            },
            "Driver License": {
                "id_pattern": r"^[A-Z]\d{2}-\d{2}-\d{6}$",
                "name_format": "LASTNAME, FIRSTNAME MI",
                "date_format": "%Y-%m-%d",
                "expiry_years": 5,
                "required_fields": ["License No", "Full Name", "Date of Birth", "Expiration Date"],
                "checksum_type": "custom",
                "special_rules": {
                    "restriction_codes": ["1", "2", "3", "4", "5", "6", "7", "8"],
                    "min_age": 17,  # Minimum driving age for student permit
                    "nationality_required": True
                }
            },
            "Passport": {
                "id_pattern": r"^[A-Z][A-Z0-9]\d{7}$",
                "name_format": "SURNAME, GIVEN NAMES",
                "date_format": "%d %b %Y",
                "expiry_years": 10,
                "required_fields": ["Passport No", "Surname", "Given Names", "Date of Birth", "Date of Expiry"],
                "checksum_type": "icao9303",
                "special_rules": {
                    "mrz_required": True,
                    "issuing_authority": "DFA",
                    "place_of_birth_required": True
                }
            },
            "PRC": {
                "id_pattern": r"^\d{7}$",
                "name_format": "LASTNAME, FIRSTNAME MIDDLENAME",
                "date_format": "%m/%d/%Y",
                "expiry_years": 3,
                "required_fields": ["Registration No", "Full Name", "Profession", "Date of Registration", "Expiry Date"],
                "checksum_type": "mod11",
                "special_rules": {
                    "profession_required": True,
                    "prc_number_pattern": r"^\d{7}$",
                    "renewal_required": True
                }
            }
        }
        
        return templates
    
    def validate(self, document_type: str, extracted_data: Dict[str, Any]) -> IssuerValidationResult:
        """
        Validate document based on issuer rules
        
        Args:
            document_type: Type of document (PhilID, UMID, etc.)
            extracted_data: Extracted data from document
            
        Returns:
            Validation result
        """
        if document_type not in self.templates:
            return IssuerValidationResult(
                issuer="Unknown",
                document_type=document_type,
                is_valid=False,
                overall_confidence=0.0,
                field_validations=[],
                expiry_status=ValidationResult.INVALID,
                checksum_valid=False,
                warnings=["Unknown document type"],
                errors=["Document type not supported"],
                metadata={}
            )
        
        template = self.templates[document_type]
        field_validations = []
        errors = []
        warnings = []
        
        # Validate ID number format
        id_validation = self._validate_id_number(
            extracted_data.get("id_number", ""),
            template["id_pattern"],
            template.get("checksum_type")
        )
        field_validations.append(id_validation)
        
        # Validate name format
        name_validation = self._validate_name(
            extracted_data.get("name", ""),
            template["name_format"]
        )
        field_validations.append(name_validation)
        
        # Validate dates
        dob_validation = self._validate_date_of_birth(
            extracted_data.get("date_of_birth", ""),
            template["date_format"],
            template.get("special_rules", {})
        )
        field_validations.append(dob_validation)
        
        # Validate expiry
        expiry_validation = self._validate_expiry(
            extracted_data.get("expiry_date"),
            extracted_data.get("issue_date"),
            template["expiry_years"]
        )
        field_validations.append(expiry_validation)
        
        # Validate special rules
        special_validations = self._validate_special_rules(
            document_type,
            extracted_data,
            template.get("special_rules", {})
        )
        field_validations.extend(special_validations)
        
        # Check required fields
        missing_fields = self._check_required_fields(
            extracted_data,
            template["required_fields"]
        )
        if missing_fields:
            errors.extend([f"Missing required field: {field}" for field in missing_fields])
        
        # Calculate overall confidence
        overall_confidence = self._calculate_overall_confidence(field_validations)
        
        # Determine if valid
        critical_errors = [v for v in field_validations if v.result == ValidationResult.INVALID]
        is_valid = len(critical_errors) == 0 and len(errors) == 0
        
        # Check checksum
        checksum_valid = id_validation.result == ValidationResult.VALID if id_validation else False
        
        # Compile warnings and errors
        for validation in field_validations:
            if validation.result == ValidationResult.WARNING and validation.reason:
                warnings.append(validation.reason)
            elif validation.result == ValidationResult.INVALID and validation.reason:
                errors.append(validation.reason)
        
        return IssuerValidationResult(
            issuer=self._get_issuer_name(document_type),
            document_type=document_type,
            is_valid=is_valid,
            overall_confidence=overall_confidence,
            field_validations=field_validations,
            expiry_status=expiry_validation.result if expiry_validation else ValidationResult.VALID,
            checksum_valid=checksum_valid,
            warnings=warnings,
            errors=errors,
            metadata={
                "template_used": document_type,
                "validation_timestamp": datetime.now().isoformat(),
                "missing_fields": missing_fields
            }
        )
    
    def _validate_id_number(self, id_number: str, pattern: str, checksum_type: Optional[str]) -> FieldValidation:
        """Validate ID number format and checksum"""
        # Check format
        if not re.match(pattern, id_number):
            return FieldValidation(
                field_name="id_number",
                value=id_number,
                result=ValidationResult.INVALID,
                confidence=0.0,
                reason=f"ID format does not match expected pattern",
                expected_format=pattern
            )
        
        # Validate checksum if applicable
        if checksum_type:
            checksum_valid = self._validate_checksum(id_number, checksum_type)
            if not checksum_valid:
                return FieldValidation(
                    field_name="id_number",
                    value=id_number,
                    result=ValidationResult.WARNING,
                    confidence=0.7,
                    reason=f"Checksum validation failed for {checksum_type}",
                    expected_format=pattern
                )
        
        return FieldValidation(
            field_name="id_number",
            value=id_number,
            result=ValidationResult.VALID,
            confidence=1.0,
            expected_format=pattern
        )
    
    def _validate_checksum(self, value: str, checksum_type: str) -> bool:
        """Validate checksum based on algorithm type"""
        # Remove non-digits for calculation
        digits_only = re.sub(r'\D', '', value)
        
        if checksum_type == "luhn":
            return self._luhn_check(digits_only)
        elif checksum_type == "mod97":
            return self._mod97_check(digits_only)
        elif checksum_type == "mod11":
            return self._mod11_check(digits_only)
        elif checksum_type == "icao9303":
            return self._icao9303_check(value)
        else:
            # Custom or unknown checksum
            return True
    
    def _luhn_check(self, digits: str) -> bool:
        """Luhn algorithm checksum validation"""
        if not digits:
            return False
        
        def luhn_checksum(card_number):
            def digits_of(n):
                return [int(d) for d in str(n)]
            
            digits = digits_of(card_number)
            odd_digits = digits[-1::-2]
            even_digits = digits[-2::-2]
            
            checksum = sum(odd_digits)
            for d in even_digits:
                checksum += sum(digits_of(d*2))
            
            return checksum % 10
        
        return luhn_checksum(digits[:-1]) == int(digits[-1])
    
    def _mod97_check(self, digits: str) -> bool:
        """Mod 97 checksum validation"""
        if len(digits) < 2:
            return False
        
        check_digits = digits[-2:]
        main_part = digits[:-2]
        
        # Calculate mod 97
        calculated = 98 - (int(main_part) % 97)
        
        return str(calculated).zfill(2) == check_digits
    
    def _mod11_check(self, digits: str) -> bool:
        """Mod 11 checksum validation"""
        if not digits:
            return False
        
        weights = [2, 3, 4, 5, 6, 7, 2, 3, 4, 5, 6, 7]
        total = sum(int(d) * w for d, w in zip(digits[:-1], weights[:len(digits)-1]))
        
        remainder = total % 11
        check_digit = 0 if remainder == 0 else 11 - remainder
        
        return str(check_digit) == digits[-1]
    
    def _icao9303_check(self, value: str) -> bool:
        """ICAO 9303 checksum for passports"""
        # Simplified implementation
        check_string = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        value = value.replace('<', '0')
        
        total = 0
        weight = [7, 3, 1]
        
        for i, char in enumerate(value[:-1]):
            if char in check_string:
                val = check_string.index(char)
                total += val * weight[i % 3]
        
        return str(total % 10) == value[-1]
    
    def _validate_name(self, name: str, expected_format: str) -> FieldValidation:
        """Validate name format and structure"""
        if not name:
            return FieldValidation(
                field_name="name",
                value=name,
                result=ValidationResult.INVALID,
                confidence=0.0,
                reason="Name is missing",
                expected_format=expected_format
            )
        
        # Normalize name
        name_upper = name.upper().strip()
        
        # Check for basic format (has comma for lastname, firstname format)
        if "LASTNAME" in expected_format and "," not in name_upper:
            return FieldValidation(
                field_name="name",
                value=name,
                result=ValidationResult.WARNING,
                confidence=0.7,
                reason="Name format may be incorrect (missing comma)",
                expected_format=expected_format
            )
        
        # Check for suspicious patterns
        suspicious_patterns = [
            r'\d{3,}',  # Multiple digits
            r'[^A-Z\s,.\-ÑñáéíóúÁÉÍÓÚ]',  # Invalid characters (allowing Spanish/Filipino chars)
            r'(.)\1{4,}',  # Repeated characters
        ]
        
        for pattern in suspicious_patterns:
            if re.search(pattern, name_upper):
                return FieldValidation(
                    field_name="name",
                    value=name,
                    result=ValidationResult.WARNING,
                    confidence=0.5,
                    reason="Name contains suspicious patterns",
                    expected_format=expected_format
                )
        
        return FieldValidation(
            field_name="name",
            value=name,
            result=ValidationResult.VALID,
            confidence=0.95,
            expected_format=expected_format
        )
    
    def _validate_date_of_birth(self, dob_str: str, date_format: str, special_rules: Dict) -> FieldValidation:
        """Validate date of birth"""
        if not dob_str:
            return FieldValidation(
                field_name="date_of_birth",
                value=dob_str,
                result=ValidationResult.INVALID,
                confidence=0.0,
                reason="Date of birth is missing",
                expected_format=date_format
            )
        
        try:
            # Parse date
            dob = datetime.strptime(dob_str, date_format).date()
            
            # Check if date is in the future
            if dob > date.today():
                return FieldValidation(
                    field_name="date_of_birth",
                    value=dob_str,
                    result=ValidationResult.INVALID,
                    confidence=0.0,
                    reason="Date of birth is in the future",
                    expected_format=date_format
                )
            
            # Calculate age
            age = (date.today() - dob).days // 365
            
            # Check age limits
            min_age = special_rules.get("min_age", 0)
            max_age = special_rules.get("max_age", 150)
            
            if age < min_age:
                return FieldValidation(
                    field_name="date_of_birth",
                    value=dob_str,
                    result=ValidationResult.WARNING,
                    confidence=0.5,
                    reason=f"Age {age} is below minimum required age {min_age}",
                    expected_format=date_format
                )
            
            if age > max_age:
                return FieldValidation(
                    field_name="date_of_birth",
                    value=dob_str,
                    result=ValidationResult.WARNING,
                    confidence=0.3,
                    reason=f"Age {age} exceeds maximum expected age {max_age}",
                    expected_format=date_format
                )
            
            return FieldValidation(
                field_name="date_of_birth",
                value=dob_str,
                result=ValidationResult.VALID,
                confidence=1.0,
                expected_format=date_format
            )
            
        except ValueError:
            return FieldValidation(
                field_name="date_of_birth",
                value=dob_str,
                result=ValidationResult.INVALID,
                confidence=0.0,
                reason=f"Invalid date format, expected {date_format}",
                expected_format=date_format
            )
    
    def _validate_expiry(self, expiry_str: Optional[str], issue_str: Optional[str], 
                        expected_years: int) -> FieldValidation:
        """Validate expiry date"""
        if not expiry_str:
            # Some documents don't expire
            return FieldValidation(
                field_name="expiry_date",
                value=None,
                result=ValidationResult.VALID,
                confidence=1.0,
                reason="No expiry date required"
            )
        
        try:
            expiry_date = datetime.strptime(expiry_str, "%Y-%m-%d").date()
            today = date.today()
            
            # Check if expired
            if expiry_date < today:
                days_expired = (today - expiry_date).days
                return FieldValidation(
                    field_name="expiry_date",
                    value=expiry_str,
                    result=ValidationResult.EXPIRED,
                    confidence=1.0,
                    reason=f"Document expired {days_expired} days ago"
                )
            
            # Check if expiring soon
            days_until_expiry = (expiry_date - today).days
            warning_days = self.config.get("expiry_warning_days", 30)
            
            if days_until_expiry <= warning_days:
                return FieldValidation(
                    field_name="expiry_date",
                    value=expiry_str,
                    result=ValidationResult.WARNING,
                    confidence=0.9,
                    reason=f"Document expires in {days_until_expiry} days"
                )
            
            # Validate against issue date if available
            if issue_str:
                try:
                    issue_date = datetime.strptime(issue_str, "%Y-%m-%d").date()
                    validity_period = (expiry_date - issue_date).days / 365
                    
                    if abs(validity_period - expected_years) > 0.5:
                        return FieldValidation(
                            field_name="expiry_date",
                            value=expiry_str,
                            result=ValidationResult.WARNING,
                            confidence=0.7,
                            reason=f"Validity period {validity_period:.1f} years differs from expected {expected_years} years"
                        )
                except:
                    pass
            
            return FieldValidation(
                field_name="expiry_date",
                value=expiry_str,
                result=ValidationResult.VALID,
                confidence=1.0,
                reason=f"Valid for {days_until_expiry} days"
            )
            
        except ValueError:
            return FieldValidation(
                field_name="expiry_date",
                value=expiry_str,
                result=ValidationResult.INVALID,
                confidence=0.0,
                reason="Invalid expiry date format"
            )
    
    def _validate_special_rules(self, document_type: str, data: Dict[str, Any], 
                               special_rules: Dict) -> List[FieldValidation]:
        """Validate document-specific special rules"""
        validations = []
        
        if document_type == "PhilID":
            # Validate blood type
            blood_type = data.get("blood_type", "")
            valid_types = special_rules.get("blood_type_values", [])
            if blood_type and blood_type not in valid_types:
                validations.append(FieldValidation(
                    field_name="blood_type",
                    value=blood_type,
                    result=ValidationResult.WARNING,
                    confidence=0.5,
                    reason=f"Invalid blood type: {blood_type}"
                ))
            
            # Validate sex
            sex = data.get("sex", "")
            valid_sex = special_rules.get("sex_values", [])
            if sex and sex not in valid_sex:
                validations.append(FieldValidation(
                    field_name="sex",
                    value=sex,
                    result=ValidationResult.WARNING,
                    confidence=0.5,
                    reason=f"Invalid sex value: {sex}"
                ))
        
        elif document_type == "UMID":
            # Validate SSS number
            sss = data.get("sss", "")
            if sss and not re.match(special_rules.get("sss_pattern", ""), sss):
                validations.append(FieldValidation(
                    field_name="sss",
                    value=sss,
                    result=ValidationResult.WARNING,
                    confidence=0.6,
                    reason="Invalid SSS number format"
                ))
        
        elif document_type == "Driver License":
            # Validate restriction codes
            restrictions = data.get("restrictions", "")
            valid_codes = special_rules.get("restriction_codes", [])
            if restrictions:
                for code in restrictions.split(","):
                    if code.strip() not in valid_codes:
                        validations.append(FieldValidation(
                            field_name="restrictions",
                            value=restrictions,
                            result=ValidationResult.WARNING,
                            confidence=0.7,
                            reason=f"Invalid restriction code: {code}"
                        ))
                        break
        
        elif document_type == "Passport":
            # Check for MRZ
            if special_rules.get("mrz_required") and not data.get("mrz_data"):
                validations.append(FieldValidation(
                    field_name="mrz",
                    value=None,
                    result=ValidationResult.WARNING,
                    confidence=0.5,
                    reason="MRZ data not found or not readable"
                ))
        
        elif document_type == "PRC":
            # Validate profession
            profession = data.get("profession", "")
            if special_rules.get("profession_required") and not profession:
                validations.append(FieldValidation(
                    field_name="profession",
                    value=profession,
                    result=ValidationResult.INVALID,
                    confidence=0.0,
                    reason="Profession is required for PRC ID"
                ))
        
        return validations
    
    def _check_required_fields(self, data: Dict[str, Any], required_fields: List[str]) -> List[str]:
        """Check for missing required fields"""
        missing = []
        
        # Map common field names
        field_mapping = {
            "PSN": ["psn", "philsys_number", "national_id"],
            "Full Name": ["name", "full_name", "complete_name"],
            "Date of Birth": ["dob", "date_of_birth", "birth_date"],
            "CRN": ["crn", "common_reference_number"],
            "SSS": ["sss", "sss_number", "social_security"],
            "License No": ["license_no", "license_number", "dl_number"],
            "Passport No": ["passport_no", "passport_number"],
            "Registration No": ["registration_no", "prc_number", "license_number"]
        }
        
        for required_field in required_fields:
            found = False
            
            # Check direct match
            if required_field.lower().replace(" ", "_") in data:
                found = True
            else:
                # Check mapped fields
                possible_names = field_mapping.get(required_field, [])
                for name in possible_names:
                    if name in data:
                        found = True
                        break
            
            if not found:
                missing.append(required_field)
        
        return missing
    
    def _calculate_overall_confidence(self, validations: List[FieldValidation]) -> float:
        """Calculate weighted overall confidence score"""
        if not validations:
            return 0.0
        
        weights = self.config.get("field_weights", {})
        total_score = 0.0
        total_weight = 0.0
        
        for validation in validations:
            # Get weight for field type
            field_weight = weights.get(validation.field_name, 0.1)
            
            # Adjust confidence based on result
            if validation.result == ValidationResult.VALID:
                score = validation.confidence
            elif validation.result == ValidationResult.WARNING:
                score = validation.confidence * 0.7
            elif validation.result == ValidationResult.EXPIRED:
                score = 0.3
            else:
                score = 0.0
            
            total_score += score * field_weight
            total_weight += field_weight
        
        if total_weight > 0:
            return total_score / total_weight
        
        return 0.0
    
    def _get_issuer_name(self, document_type: str) -> str:
        """Get issuer name for document type"""
        issuer_map = {
            "PhilID": "Philippine Statistics Authority",
            "UMID": "Social Security System",
            "Driver License": "Land Transportation Office",
            "Passport": "Department of Foreign Affairs",
            "PRC": "Professional Regulation Commission"
        }
        
        return issuer_map.get(document_type, "Unknown Issuer")
    
    def compare_names(self, name1: str, name2: str) -> float:
        """
        Compare two names using fuzzy matching
        
        Args:
            name1: First name
            name2: Second name
            
        Returns:
            Similarity score (0-1)
        """
        if not name1 or not name2:
            return 0.0
        
        # Normalize names
        name1_normalized = re.sub(r'[^a-zA-Z\s]', '', name1.upper()).strip()
        name2_normalized = re.sub(r'[^a-zA-Z\s]', '', name2.upper()).strip()
        
        # Use SequenceMatcher for fuzzy matching
        similarity = difflib.SequenceMatcher(None, name1_normalized, name2_normalized).ratio()
        
        # Check for common variations
        if self._check_name_variations(name1_normalized, name2_normalized):
            similarity = max(similarity, 0.9)
        
        return similarity
    
    def _check_name_variations(self, name1: str, name2: str) -> bool:
        """Check for common name variations"""
        # Split into parts
        parts1 = name1.split()
        parts2 = name2.split()
        
        # Check if one is subset of the other (missing middle name, etc.)
        if set(parts1).issubset(set(parts2)) or set(parts2).issubset(set(parts1)):
            return True
        
        # Check for initials
        if len(parts1) == len(parts2):
            matches = 0
            for p1, p2 in zip(parts1, parts2):
                if p1 == p2 or (len(p1) == 1 and p1 == p2[0]) or (len(p2) == 1 and p2 == p1[0]):
                    matches += 1
            
            if matches >= len(parts1) - 1:  # Allow one mismatch
                return True
        
        return False

# Export main components
__all__ = [
    "PhilippineIDValidator",
    "IssuerValidationResult",
    "FieldValidation",
    "ValidationResult"
]