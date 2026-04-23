"""
IOOS Compliance checking for NetCDF files.

Validates against:
- CF-1.8 conventions
- ACDD-1.3 metadata
"""

import subprocess
import logging
from pathlib import Path
from typing import Dict, List, Tuple

logger = logging.getLogger(__name__)


class ComplianceChecker:
    """Validate NetCDF compliance."""

    @staticmethod
    def check_ioos_compliance(nc_filepath: str) -> Tuple[bool, Dict]:
        """
        Run IOOS Compliance Checker on NetCDF file.

        Args:
            nc_filepath: Path to NetCDF file

        Returns:
            Tuple of (is_compliant, results_dict)
        """
        filepath = Path(nc_filepath)
        if not filepath.exists():
            logger.error(f"File not found: {filepath}")
            return False, {"error": "File not found"}

        try:
            result = subprocess.run(
                ["compliance-checker", "--test", "cf:1.8", "--test", "acdd:1.3",
                 str(filepath), "--format", "json"],
                capture_output=True,
                text=True,
                timeout=30
            )

            # Parse JSON output (if available)
            if result.returncode == 0:
                logger.info(f"Compliance check PASSED for {filepath.name}")
                return True, {"status": "PASSED", "stdout": result.stdout}
            else:
                logger.warning(f"Compliance check FAILED for {filepath.name}")
                return False, {
                    "status": "FAILED",
                    "stdout": result.stdout,
                    "stderr": result.stderr
                }

        except FileNotFoundError:
            logger.warning("compliance-checker not installed. Install: pip install ioos-compliance-checker")
            return None, {"error": "compliance-checker not installed"}
        except subprocess.TimeoutExpired:
            logger.error("Compliance check timed out")
            return False, {"error": "Timeout"}

    @staticmethod
    def check_cf_conventions(nc_filepath: str) -> List[str]:
        """
        Check for CF convention compliance (manual checks).

        Returns:
            List of warnings/issues
        """
        issues = []

        try:
            import netCDF4 as nc
            ds = nc.Dataset(str(nc_filepath))

            # Check global conventions
            if "Conventions" not in ds.ncattrs():
                issues.append("Missing global 'Conventions' attribute")
            elif "CF" not in ds.getncattr("Conventions"):
                issues.append(f"Conventions missing CF: {ds.getncattr('Conventions')}")

            # Check for standard_name on primary variables
            required_vars = ["pressure", "temperature"]
            for var in required_vars:
                if var in ds.variables:
                    if "standard_name" not in ds.variables[var].ncattrs():
                        issues.append(f"{var}: missing standard_name")
                    if "units" not in ds.variables[var].ncattrs():
                        issues.append(f"{var}: missing units")

            ds.close()

        except Exception as e:
            issues.append(f"Check failed: {e}")

        return issues

    @staticmethod
    def check_acdd_metadata(nc_filepath: str) -> List[str]:
        """
        Check for ACDD (Attribute Convention for Data Discovery) compliance.

        Returns:
            List of missing/incomplete metadata
        """
        issues = []

        try:
            import netCDF4 as nc
            ds = nc.Dataset(str(nc_filepath))

            required_attrs = ["title", "summary", "date_created"]
            for attr in required_attrs:
                if attr not in ds.ncattrs():
                    issues.append(f"Missing ACDD attribute: {attr}")

            ds.close()

        except Exception as e:
            issues.append(f"Check failed: {e}")

        return issues
