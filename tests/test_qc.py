"""Tests for quality control module."""

import pytest
import numpy as np
import pandas as pd

from ctd_processor.qc import (
    detect_spikes_mad,
    detect_density_inversions,
    calculate_qc_report
)


class TestSpikeDetection:
    """Test spike detection via MAD."""

    def test_detects_obvious_spike(self):
        """Test detection of obvious outlier."""
        data = pd.Series([1.0, 1.0, 1.0, 10.0, 1.0, 1.0])
        spikes = detect_spikes_mad(data, window=3, threshold=2.0)
        assert spikes[3] == True  # Index 3 is the spike

    def test_no_false_positives_clean_data(self):
        """Test no flags on clean data."""
        data = pd.Series(np.linspace(20, 5, 50) + np.random.normal(0, 0.1, 50))
        spikes = detect_spikes_mad(data, window=3, threshold=3.0)
        assert np.sum(spikes) < 3  # Expect few/no spikes

    def test_handles_empty_series(self):
        """Test graceful handling of short series."""
        data = pd.Series([1.0, 2.0])
        spikes = detect_spikes_mad(data, window=3, threshold=3.0)
        assert len(spikes) == len(data)


class TestDensityInversions:
    """Test density inversion detection."""

    def test_detects_stable_profile(self):
        """Test stable (increasing density with depth) profile."""
        pressure = np.array([0, 100, 500, 1000])
        temp = np.array([25.0, 15.0, 5.0, 4.0])
        sal = np.array([35.0, 35.2, 35.5, 35.6])

        inversions, max_inv = detect_density_inversions(pressure, sal, temp, threshold=0.1)
        # Stable profile should have few/no inversions
        assert np.sum(inversions) < 2

    def test_detects_inversion(self):
        """Test detection of unstable density."""
        pressure = np.array([0, 10, 20, 30])
        temp = np.array([20.0, 19.0, 15.0, 20.0])  # Temperature bump
        sal = np.array([35.0, 35.0, 35.0, 35.0])

        inversions, max_inv = detect_density_inversions(pressure, sal, temp, threshold=0.01)
        # Temperature increase at depth should cause inversion
        assert len(inversions) > 0


class TestQCReport:
    """Test QC report generation."""

    def test_generates_report(self):
        """Test basic report generation."""
        data = pd.DataFrame({
            "pressure": [0, 10, 20, 30],
            "temperature": [28.5, 28.3, 27.9, 25.2],
            "salinity": [35.0, 35.1, 35.2, 35.3]
        })
        qc_flags = {
            "pressure": np.array([1, 1, 1, 1]),
            "temperature": np.array([1, 1, 2, 1]),
            "salinity": np.array([1, 1, 1, 1])
        }

        report = calculate_qc_report("cast_001", data, qc_flags)

        assert report.cast_id == "cast_001"
        assert report.total_observations == 4
        assert report.suspicious_count["temperature"] == 1
        assert report.good_count["temperature"] == 3

    def test_report_structure(self):
        """Test report has required fields."""
        data = pd.DataFrame({"temp": [20.0, 19.0, 18.0]})
        qc_flags = {"temp": np.array([1, 1, 1])}

        report = calculate_qc_report("test", data, qc_flags)

        assert hasattr(report, "cast_id")
        assert hasattr(report, "total_observations")
        assert hasattr(report, "good_count")
        assert hasattr(report, "suspicious_count")
        assert hasattr(report, "bad_count")
        assert hasattr(report, "density_inversion_found")
