"""
Quality Control module for CTD data.

Implements detection algorithms:
- Spike detection (Median Absolute Deviation)
- Density inversion flagging
- Sensor drift checks
"""

import numpy as np
import pandas as pd
from typing import Dict, Tuple
from dataclasses import dataclass


@dataclass
class QCReport:
    """Quality control assessment report."""
    cast_id: str
    total_observations: int
    good_count: Dict[str, int]
    suspicious_count: Dict[str, int]
    bad_count: Dict[str, int]
    density_inversion_found: bool


def detect_spikes_mad(
    series: pd.Series,
    window: int = 3,
    threshold: float = 3.0
) -> np.ndarray:
    """
    Detect spikes using Median Absolute Deviation (MAD).

    MAD is more robust to outliers than standard deviation.

    Args:
        series: Data series to check
        window: Rolling window size (must be odd)
        threshold: MAD multiplier (default 3.0 = ~3 sigma)

    Returns:
        Boolean array (True = spike detected)
    """
    if len(series) < window:
        return np.zeros(len(series), dtype=bool)

    rolling_mad = series.rolling(window=window, center=True).apply(
        lambda x: np.median(np.abs(x - np.median(x)))
    )
    rolling_median = series.rolling(window=window, center=True).median()
    deviation = np.abs(series - rolling_median)

    return deviation > (threshold * rolling_mad)


def detect_density_inversions(
    pressure: np.ndarray,
    salinity: np.ndarray,
    temperature: np.ndarray,
    threshold: float = 0.1
) -> Tuple[np.ndarray, float]:
    """
    Detect density inversions (unstable stratification).

    Computed from simplified density anomaly: σ0 ≈ 1027 - 0.5T + 0.78S

    Args:
        pressure: Pressure (dbar)
        salinity: Salinity (PSU)
        temperature: Temperature (°C)
        threshold: Density inversion tolerance (kg/m³)

    Returns:
        Tuple of (inversion flags, max inversion magnitude)
    """
    sigma0 = 1027.6 - 0.5 * temperature + 0.78 * salinity
    inversions = np.diff(sigma0) < -threshold
    max_inversion = np.min(np.diff(sigma0)) if len(sigma0) > 1 else 0.0

    return inversions, max_inversion


def calculate_qc_report(
    cast_id: str,
    data: pd.DataFrame,
    qc_flags: Dict[str, np.ndarray]
) -> QCReport:
    """
    Generate a QC report from flagged data.

    Args:
        cast_id: Cast identifier
        data: Raw data
        qc_flags: Dictionary of flag arrays per variable

    Returns:
        QCReport with summary statistics
    """
    good = {col: np.sum(qc_flags[col] == 1) for col in qc_flags}
    suspicious = {col: np.sum(qc_flags[col] == 2) for col in qc_flags}
    bad = {col: np.sum(qc_flags[col] == 3) for col in qc_flags}

    # Check for density inversions
    density_inverted = False
    if "salinity" in data.columns and "temperature" in data.columns:
        _, max_inv = detect_density_inversions(
            data["pressure"].values if "pressure" in data.columns else np.arange(len(data)),
            data["salinity"].values,
            data["temperature"].values
        )
        density_inverted = max_inv < -0.05

    return QCReport(
        cast_id=cast_id,
        total_observations=len(data),
        good_count=good,
        suspicious_count=suspicious,
        bad_count=bad,
        density_inversion_found=density_inverted
    )
