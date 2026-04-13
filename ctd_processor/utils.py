"""Utility functions for CTD processing."""

from datetime import datetime, timezone
from typing import Tuple
import numpy as np


def iso8601_timestamp() -> str:
    """Return current UTC timestamp in ISO 8601 format."""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def validate_pressure_range(pressure: np.ndarray, min_p: float = 0, max_p: float = 6000) -> Tuple[bool, str]:
    """
    Validate pressure values are within reasonable oceanographic range.

    Args:
        pressure: Pressure array (dbar)
        min_p: Minimum valid pressure
        max_p: Maximum valid pressure

    Returns:
        Tuple of (is_valid, message)
    """
    if len(pressure) == 0:
        return False, "Empty pressure array"

    if np.any(pressure < min_p) or np.any(pressure > max_p):
        return False, f"Pressure outside range [{min_p}, {max_p}] dbar"

    if not np.all(np.diff(pressure) >= 0):
        return False, "Pressure not monotonically increasing"

    return True, "Valid"


def validate_temperature_range(temp: np.ndarray, min_t: float = -2, max_t: float = 40) -> Tuple[bool, str]:
    """
    Validate temperature values are within reasonable oceanographic range.

    Args:
        temp: Temperature array (°C)
        min_t: Minimum valid temperature
        max_t: Maximum valid temperature

    Returns:
        Tuple of (is_valid, message)
    """
    if len(temp) == 0:
        return False, "Empty temperature array"

    if np.any(temp < min_t) or np.any(temp > max_t):
        return False, f"Temperature outside range [{min_t}, {max_t}]°C"

    return True, "Valid"


def validate_salinity_range(sal: np.ndarray, min_s: float = 0, max_s: float = 41) -> Tuple[bool, str]:
    """
    Validate salinity values are within reasonable oceanographic range.

    Args:
        sal: Salinity array (PSU)
        min_s: Minimum valid salinity
        max_s: Maximum valid salinity

    Returns:
        Tuple of (is_valid, message)
    """
    if len(sal) == 0:
        return False, "Empty salinity array"

    if np.any(sal < min_s) or np.any(sal > max_s):
        return False, f"Salinity outside range [{min_s}, {max_s}] PSU"

    return True, "Valid"
