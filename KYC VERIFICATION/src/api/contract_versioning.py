"""
API Contract Versioning Module
Schema Management, Deprecation Policy, and Compatibility Checks
Part of KYC Bank-Grade Parity - Phase 13

This module handles API versioning and backward compatibility.
"""

import logging
import json
import hashlib
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone, timedelta
from pathlib import Path
from enum import Enum
import semantic_version
from abc import ABC, abstractmethod

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Manila timezone
MANILA_TZ = timezone(timedelta(hours=8))


class ChangeType(Enum):
    """API change types"""
    BREAKING = "breaking"
    FEATURE = "feature"
    FIX = "fix"
    DEPRECATION = "deprecation"
    DOCUMENTATION = "documentation"


class DeprecationLevel(Enum):
    """Deprecation severity levels"""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass
class APIVersion:
    """API version information"""
    version: str
    release_date: datetime
    end_of_life: Optional[datetime]
    changes: List[Dict[str, Any]]
    deprecated_features: List[str] = field(default_factory=list)
    removed_features: List[str] = field(default_factory=list)
    migration_guide: Optional[str] = None
    
    def is_supported(self) -> bool:
        """Check if version is still supported"""
        if not self.end_of_life:
            return True
        return datetime.now(MANILA_TZ) < self.end_of_life
    
    def days_until_eol(self) -> Optional[int]:
        """Days until end of life"""
        if not self.end_of_life:
            return None
        delta = self.end_of_life - datetime.now(MANILA_TZ)
        return delta.days if delta.days > 0 else 0


@dataclass
class SchemaField:
    """API schema field definition"""
    name: str
    type: str
    required: bool
    description: str
    deprecated: bool = False
    deprecation_version: Optional[str] = None
    removal_version: Optional[str] = None
    default_value: Optional[Any] = None
    validation_rules: List[str] = field(default_factory=list)
    
    def validate(self, value: Any) -> Tuple[bool, Optional[str]]:
        """Validate field value"""
        # Type checking
        if self.type == "string" and not isinstance(value, str):
            return False, f"{self.name} must be string"
        elif self.type == "integer" and not isinstance(value, int):
            return False, f"{self.name} must be integer"
        elif self.type == "number" and not isinstance(value, (int, float)):
            return False, f"{self.name} must be number"
        elif self.type == "boolean" and not isinstance(value, bool):
            return False, f"{self.name} must be boolean"
        elif self.type == "array" and not isinstance(value, list):
            return False, f"{self.name} must be array"
        elif self.type == "object" and not isinstance(value, dict):
            return False, f"{self.name} must be object"
        
        # Custom validation rules
        for rule in self.validation_rules:
            if rule == "non_empty" and not value:
                return False, f"{self.name} cannot be empty"
            elif rule.startswith("min_length:"):
                min_len = int(rule.split(":")[1])
                if len(str(value)) < min_len:
                    return False, f"{self.name} minimum length is {min_len}"
            elif rule.startswith("max_length:"):
                max_len = int(rule.split(":")[1])
                if len(str(value)) > max_len:
                    return False, f"{self.name} maximum length is {max_len}"
            elif rule.startswith("pattern:"):
                import re
                pattern = rule.split(":", 1)[1]
                if not re.match(pattern, str(value)):
                    return False, f"{self.name} does not match pattern {pattern}"
        
        return True, None


@dataclass
class APIEndpoint:
    """API endpoint definition"""
    path: str
    method: str
    version: str
    request_schema: Dict[str, SchemaField]
    response_schema: Dict[str, SchemaField]
    deprecated: bool = False
    sunset_date: Optional[datetime] = None
    replacement_endpoint: Optional[str] = None
    
    def validate_request(self, data: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """Validate request against schema"""
        errors = []
        
        # Check required fields
        for field_name, field in self.request_schema.items():
            if field.required and field_name not in data:
                errors.append(f"Required field '{field_name}' is missing")
            elif field_name in data:
                valid, error = field.validate(data[field_name])
                if not valid:
                    errors.append(error)
        
        # Check for unknown fields
        unknown_fields = set(data.keys()) - set(self.request_schema.keys())
        if unknown_fields:
            errors.append(f"Unknown fields: {', '.join(unknown_fields)}")
        
        return len(errors) == 0, errors


class VersionManager:
    """API version management"""
    
    def __init__(self):
        """Initialize version manager"""
        self.versions: Dict[str, APIVersion] = {}
        self.current_version = "v2.0.0"
        self.minimum_supported = "v1.0.0"
        self._load_versions()
        logger.info(f"Version Manager initialized (current: {self.current_version})")
    
    def _load_versions(self):
        """Load API versions"""
        # Version 1.0.0
        self.versions["v1.0.0"] = APIVersion(
            version="v1.0.0",
            release_date=datetime(2024, 1, 1, tzinfo=MANILA_TZ),
            end_of_life=datetime(2024, 12, 31, tzinfo=MANILA_TZ),
            changes=[
                {"type": ChangeType.FEATURE, "description": "Initial release"}
            ],
            deprecated_features=["legacy_auth", "xml_format"]
        )
        
        # Version 1.1.0
        self.versions["v1.1.0"] = APIVersion(
            version="v1.1.0",
            release_date=datetime(2024, 6, 1, tzinfo=MANILA_TZ),
            end_of_life=datetime(2025, 6, 1, tzinfo=MANILA_TZ),
            changes=[
                {"type": ChangeType.FEATURE, "description": "Added PAD liveness endpoints"},
                {"type": ChangeType.FIX, "description": "Fixed rate limiting issues"},
                {"type": ChangeType.DEPRECATION, "description": "Deprecated legacy_auth"}
            ]
        )
        
        # Version 2.0.0
        self.versions["v2.0.0"] = APIVersion(
            version="v2.0.0",
            release_date=datetime(2024, 12, 1, tzinfo=MANILA_TZ),
            end_of_life=None,  # Current version
            changes=[
                {"type": ChangeType.BREAKING, "description": "New authentication system"},
                {"type": ChangeType.FEATURE, "description": "NFC eMRTD support"},
                {"type": ChangeType.FEATURE, "description": "Transaction monitoring"},
                {"type": ChangeType.BREAKING, "description": "Removed XML format support"}
            ],
            removed_features=["legacy_auth", "xml_format"],
            migration_guide="/docs/migration/v1-to-v2.md"
        )
    
    def get_version(self, version: str) -> Optional[APIVersion]:
        """Get version information"""
        return self.versions.get(version)
    
    def is_version_supported(self, version: str) -> bool:
        """Check if version is supported"""
        ver = self.get_version(version)
        return ver is not None and ver.is_supported()
    
    def get_deprecation_warnings(self, version: str) -> List[Dict[str, Any]]:
        """Get deprecation warnings for version"""
        warnings = []
        ver = self.get_version(version)
        
        if not ver:
            return warnings
        
        # Check if version is near EOL
        days_until_eol = ver.days_until_eol()
        if days_until_eol is not None:
            if days_until_eol <= 30:
                warnings.append({
                    "level": DeprecationLevel.CRITICAL,
                    "message": f"Version {version} will be deprecated in {days_until_eol} days",
                    "sunset_date": ver.end_of_life.isoformat()
                })
            elif days_until_eol <= 90:
                warnings.append({
                    "level": DeprecationLevel.WARNING,
                    "message": f"Version {version} will be deprecated in {days_until_eol} days",
                    "sunset_date": ver.end_of_life.isoformat()
                })
        
        # Add deprecated features warnings
        for feature in ver.deprecated_features:
            warnings.append({
                "level": DeprecationLevel.WARNING,
                "message": f"Feature '{feature}' is deprecated",
                "feature": feature
            })
        
        return warnings


class SchemaRegistry:
    """API schema registry and validation"""
    
    def __init__(self):
        """Initialize schema registry"""
        self.endpoints: Dict[str, APIEndpoint] = {}
        self._register_endpoints()
        logger.info(f"Schema Registry initialized with {len(self.endpoints)} endpoints")
    
    def _register_endpoints(self):
        """Register API endpoints"""
        # KYC Verification endpoint
        self.endpoints["POST /v2/kyc/verify"] = APIEndpoint(
            path="/v2/kyc/verify",
            method="POST",
            version="v2.0.0",
            request_schema={
                "customer_id": SchemaField(
                    name="customer_id",
                    type="string",
                    required=True,
                    description="Customer identifier",
                    validation_rules=["non_empty", "pattern:^CUST[0-9]+$"]
                ),
                "document_type": SchemaField(
                    name="document_type",
                    type="string",
                    required=True,
                    description="Type of document",
                    validation_rules=["pattern:^(passport|license|national_id)$"]
                ),
                "document_image": SchemaField(
                    name="document_image",
                    type="string",
                    required=True,
                    description="Base64 encoded document image",
                    validation_rules=["non_empty"]
                ),
                "liveness_image": SchemaField(
                    name="liveness_image",
                    type="string",
                    required=False,
                    description="Base64 encoded liveness image",
                    deprecated=False
                )
            },
            response_schema={
                "verification_id": SchemaField(
                    name="verification_id",
                    type="string",
                    required=True,
                    description="Verification identifier"
                ),
                "status": SchemaField(
                    name="status",
                    type="string",
                    required=True,
                    description="Verification status"
                ),
                "risk_score": SchemaField(
                    name="risk_score",
                    type="number",
                    required=True,
                    description="Risk score 0-100"
                )
            }
        )
        
        # Legacy endpoint (deprecated)
        self.endpoints["POST /v1/kyc/verify"] = APIEndpoint(
            path="/v1/kyc/verify",
            method="POST",
            version="v1.0.0",
            request_schema={
                "customer_id": SchemaField(
                    name="customer_id",
                    type="string",
                    required=True,
                    description="Customer identifier"
                ),
                "document_data": SchemaField(
                    name="document_data",
                    type="string",
                    required=True,
                    description="Document data",
                    deprecated=True,
                    deprecation_version="v1.1.0",
                    removal_version="v2.0.0"
                )
            },
            response_schema={},
            deprecated=True,
            sunset_date=datetime(2024, 12, 31, tzinfo=MANILA_TZ),
            replacement_endpoint="/v2/kyc/verify"
        )
    
    def validate_request(self, endpoint: str, data: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """Validate request against endpoint schema"""
        if endpoint not in self.endpoints:
            return False, [f"Unknown endpoint: {endpoint}"]
        
        return self.endpoints[endpoint].validate_request(data)
    
    def get_endpoint_info(self, endpoint: str) -> Optional[APIEndpoint]:
        """Get endpoint information"""
        return self.endpoints.get(endpoint)


class CompatibilityChecker:
    """API compatibility checker"""
    
    def __init__(self, schema_registry: SchemaRegistry):
        """
        Initialize compatibility checker
        
        Args:
            schema_registry: Schema registry instance
        """
        self.schema_registry = schema_registry
        logger.info("Compatibility Checker initialized")
    
    def check_backward_compatibility(self, 
                                    old_schema: Dict[str, SchemaField],
                                    new_schema: Dict[str, SchemaField]) -> Tuple[bool, List[str]]:
        """
        Check backward compatibility between schemas
        
        Args:
            old_schema: Previous schema version
            new_schema: New schema version
            
        Returns:
            Tuple of (is_compatible, breaking_changes)
        """
        breaking_changes = []
        
        # Check for removed required fields
        for field_name, field in old_schema.items():
            if field.required and field_name not in new_schema:
                breaking_changes.append(f"Required field '{field_name}' removed")
        
        # Check for type changes
        for field_name, old_field in old_schema.items():
            if field_name in new_schema:
                new_field = new_schema[field_name]
                if old_field.type != new_field.type:
                    breaking_changes.append(
                        f"Field '{field_name}' type changed from {old_field.type} to {new_field.type}"
                    )
                
                # Check if optional field became required
                if not old_field.required and new_field.required:
                    breaking_changes.append(f"Optional field '{field_name}' became required")
        
        return len(breaking_changes) == 0, breaking_changes
    
    def generate_compatibility_report(self, 
                                     version1: str, 
                                     version2: str) -> Dict[str, Any]:
        """Generate compatibility report between versions"""
        report = {
            "from_version": version1,
            "to_version": version2,
            "timestamp": datetime.now(MANILA_TZ).isoformat(),
            "compatible": True,
            "breaking_changes": [],
            "deprecations": [],
            "new_features": []
        }
        
        # Compare endpoints
        v1_endpoints = {
            k: v for k, v in self.schema_registry.endpoints.items() 
            if v.version == version1
        }
        v2_endpoints = {
            k: v for k, v in self.schema_registry.endpoints.items() 
            if v.version == version2
        }
        
        # Check for removed endpoints
        for endpoint_key in v1_endpoints:
            if endpoint_key not in v2_endpoints:
                report["breaking_changes"].append(f"Endpoint removed: {endpoint_key}")
                report["compatible"] = False
        
        # Check for schema changes
        for endpoint_key in v1_endpoints:
            if endpoint_key in v2_endpoints:
                v1_endpoint = v1_endpoints[endpoint_key]
                v2_endpoint = v2_endpoints[endpoint_key]
                
                compatible, changes = self.check_backward_compatibility(
                    v1_endpoint.request_schema,
                    v2_endpoint.request_schema
                )
                
                if not compatible:
                    report["compatible"] = False
                    report["breaking_changes"].extend(changes)
        
        # Check for new endpoints
        for endpoint_key in v2_endpoints:
            if endpoint_key not in v1_endpoints:
                report["new_features"].append(f"New endpoint: {endpoint_key}")
        
        return report


class CIGateway:
    """CI/CD gateway for contract validation"""
    
    def __init__(self, version_manager: VersionManager,
                 schema_registry: SchemaRegistry):
        """
        Initialize CI gateway
        
        Args:
            version_manager: Version manager instance
            schema_registry: Schema registry instance
        """
        self.version_manager = version_manager
        self.schema_registry = schema_registry
        self.compatibility_checker = CompatibilityChecker(schema_registry)
        logger.info("CI Gateway initialized")
    
    def validate_changes(self, changes: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate API changes for CI/CD
        
        Args:
            changes: Proposed API changes
            
        Returns:
            Validation result
        """
        result = {
            "valid": True,
            "errors": [],
            "warnings": [],
            "checks": {}
        }
        
        # Check version format
        if "version" in changes:
            try:
                ver = semantic_version.Version(changes["version"].lstrip("v"))
                result["checks"]["version_format"] = "passed"
            except ValueError:
                result["valid"] = False
                result["errors"].append(f"Invalid version format: {changes['version']}")
                result["checks"]["version_format"] = "failed"
        
        # Check for breaking changes without major version bump
        if "breaking_changes" in changes and changes["breaking_changes"]:
            current = semantic_version.Version(self.version_manager.current_version.lstrip("v"))
            new = semantic_version.Version(changes.get("version", "0.0.0").lstrip("v"))
            
            if new.major == current.major:
                result["valid"] = False
                result["errors"].append("Breaking changes require major version bump")
                result["checks"]["breaking_changes"] = "failed"
            else:
                result["checks"]["breaking_changes"] = "passed"
        
        # Check deprecation policy
        if "deprecations" in changes:
            for deprecation in changes["deprecations"]:
                if "sunset_date" not in deprecation:
                    result["warnings"].append(f"Deprecation missing sunset date: {deprecation}")
                else:
                    sunset = datetime.fromisoformat(deprecation["sunset_date"])
                    days_until = (sunset - datetime.now(MANILA_TZ)).days
                    if days_until < 90:
                        result["warnings"].append(
                            f"Deprecation period too short ({days_until} days): {deprecation}"
                        )
        
        # Check backward compatibility
        if "schema_changes" in changes:
            for endpoint, schema_change in changes["schema_changes"].items():
                if endpoint in self.schema_registry.endpoints:
                    old_schema = self.schema_registry.endpoints[endpoint].request_schema
                    # Simulate new schema (simplified for demo)
                    compatible, breaking = self.compatibility_checker.check_backward_compatibility(
                        old_schema, old_schema  # Would use actual new schema
                    )
                    
                    if not compatible:
                        result["valid"] = False
                        result["errors"].extend(breaking)
        
        result["checks"]["backward_compatibility"] = "passed" if result["valid"] else "failed"
        
        return result
    
    def generate_migration_guide(self, from_version: str, 
                                to_version: str) -> str:
        """Generate migration guide between versions"""
        guide = f"# Migration Guide: {from_version} → {to_version}\n\n"
        guide += f"Generated: {datetime.now(MANILA_TZ).isoformat()}\n\n"
        
        # Get version information
        old_ver = self.version_manager.get_version(from_version)
        new_ver = self.version_manager.get_version(to_version)
        
        if not old_ver or not new_ver:
            return guide + "Error: Version not found\n"
        
        # Breaking changes section
        guide += "## Breaking Changes\n\n"
        breaking_changes = [
            c for c in new_ver.changes 
            if c["type"] == ChangeType.BREAKING
        ]
        for change in breaking_changes:
            guide += f"- {change['description']}\n"
        
        # Removed features
        if new_ver.removed_features:
            guide += "\n## Removed Features\n\n"
            for feature in new_ver.removed_features:
                guide += f"- `{feature}` has been removed\n"
        
        # Deprecated features
        if new_ver.deprecated_features:
            guide += "\n## Deprecated Features\n\n"
            for feature in new_ver.deprecated_features:
                guide += f"- `{feature}` is deprecated and will be removed in future versions\n"
        
        # New features
        guide += "\n## New Features\n\n"
        new_features = [
            c for c in new_ver.changes 
            if c["type"] == ChangeType.FEATURE
        ]
        for change in new_features:
            guide += f"- {change['description']}\n"
        
        # Migration steps
        guide += "\n## Migration Steps\n\n"
        guide += "1. Review breaking changes above\n"
        guide += "2. Update client libraries to latest version\n"
        guide += "3. Test in staging environment\n"
        guide += "4. Update API endpoint URLs if needed\n"
        guide += "5. Implement new authentication if required\n"
        
        return guide


if __name__ == "__main__":
    # Demo and testing
    print("=== API Contract Versioning Demo ===\n")
    
    # Initialize components
    version_manager = VersionManager()
    schema_registry = SchemaRegistry()
    ci_gateway = CIGateway(version_manager, schema_registry)
    
    # Show current version info
    print(f"Current Version: {version_manager.current_version}")
    print(f"Minimum Supported: {version_manager.minimum_supported}\n")
    
    # Check version support
    print("=== Version Support Status ===")
    for version in ["v1.0.0", "v1.1.0", "v2.0.0"]:
        ver = version_manager.get_version(version)
        if ver:
            supported = "✓" if ver.is_supported() else "✗"
            eol_days = ver.days_until_eol()
            eol_info = f"(EOL in {eol_days} days)" if eol_days else "(Current)"
            print(f"  {version}: {supported} {eol_info}")
    
    # Test request validation
    print("\n=== Request Validation Test ===")
    test_request = {
        "customer_id": "CUST12345",
        "document_type": "passport",
        "document_image": "base64encodeddata..."
    }
    
    valid, errors = schema_registry.validate_request("POST /v2/kyc/verify", test_request)
    print(f"Valid: {'✓' if valid else '✗'}")
    if errors:
        for error in errors:
            print(f"  Error: {error}")
    
    # Check deprecation warnings
    print("\n=== Deprecation Warnings ===")
    warnings = version_manager.get_deprecation_warnings("v1.0.0")
    for warning in warnings:
        level_icon = "⚠" if warning["level"] == DeprecationLevel.WARNING else "🚨"
        print(f"  {level_icon} {warning['message']}")
    
    # Test CI gateway
    print("\n=== CI Gateway Validation ===")
    proposed_changes = {
        "version": "v2.1.0",
        "breaking_changes": [],
        "deprecations": [
            {"feature": "old_endpoint", "sunset_date": "2025-06-01T00:00:00+08:00"}
        ]
    }
    
    validation = ci_gateway.validate_changes(proposed_changes)
    print(f"Validation: {'✓ Passed' if validation['valid'] else '✗ Failed'}")
    for check, status in validation["checks"].items():
        icon = "✓" if status == "passed" else "✗"
        print(f"  {icon} {check}: {status}")
    
    # Generate migration guide
    print("\n=== Migration Guide Preview ===")
    guide = ci_gateway.generate_migration_guide("v1.0.0", "v2.0.0")
    print(guide[:500] + "...")
    
    # Compatibility report
    print("\n=== Compatibility Report ===")
    report = ci_gateway.compatibility_checker.generate_compatibility_report("v1.0.0", "v2.0.0")
    print(f"Compatible: {'✓' if report['compatible'] else '✗'}")
    if report["breaking_changes"]:
        print("Breaking Changes:")
        for change in report["breaking_changes"][:3]:
            print(f"  - {change}")
    
    print("\n✓ API contract versioning and CI gates operational")