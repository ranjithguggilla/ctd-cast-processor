"""Tests for core CTDProfile functionality."""

import pytest
import tempfile
import pandas as pd
import numpy as np
from pathlib import Path

from ctd_processor import CTDProfile


class TestCTDProfileInit:
    """Test CTDProfile initialization."""

    def test_init_creates_profile(self):
        """Test basic profile creation."""
        profile = CTDProfile("cast_001", "GOMECC-4", "R/V Ronald H. Brown")
        assert profile.cast_id == "cast_001"
        assert profile.cruise == "GOMECC-4"
        assert profile.vessel == "R/V Ronald H. Brown"

    def test_init_empty_data(self):
        """Test profile starts with empty data."""
        profile = CTDProfile("cast_001", "GOMECC-4", "R/V Ronald H. Brown")
        assert profile.data.empty


class TestCTDProfileIOandExport:
    """Test data I/O and export."""

    def test_to_csv(self):
        """Test CSV export."""
        profile = CTDProfile("cast_001", "GOMECC-4", "R/V Ronald H. Brown")
        profile.data = pd.DataFrame({
            "pressure": [0, 10, 20, 30],
            "temperature": [28.5, 28.3, 27.9, 25.2],
            "conductivity": [4.2, 4.1, 4.0, 3.8]
        })
        profile.qc_flags = {
            "pressure": np.ones(4, dtype=int),
            "temperature": np.array([1, 1, 2, 1]),
            "conductivity": np.ones(4, dtype=int)
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            csv_path = Path(tmpdir) / "test.csv"
            profile.to_csv(str(csv_path))
            assert csv_path.exists()

            # Verify content
            result = pd.read_csv(csv_path)
            assert len(result) == 4
            assert "temperature_qc" in result.columns
            assert result["temperature_qc"].iloc[2] == 2  # Suspicious flag

    def test_to_netcdf(self):
        """Test NetCDF export."""
        profile = CTDProfile("cast_001", "GOMECC-4", "R/V Ronald H. Brown")
        profile.data = pd.DataFrame({
            "pressure": [0, 10, 20, 30],
            "temperature": [28.5, 28.3, 27.9, 25.2],
            "salinity": [35.1, 35.2, 35.3, 35.4]
        })

        with tempfile.TemporaryDirectory() as tmpdir:
            nc_path = Path(tmpdir) / "test.nc"
            profile.to_netcdf(str(nc_path))
            assert nc_path.exists()

            # Verify NetCDF structure
            import netCDF4 as nc
            ds = nc.Dataset(str(nc_path))
            assert ds.Conventions == "CF-1.8, ACDD-1.3"
            assert "temperature" in ds.variables
            assert "salinity" in ds.variables
            ds.close()


class TestCTDProfileProcessing:
    """Test processing functions."""

    def test_apply_qc(self):
        """Test QC flag application."""
        profile = CTDProfile("cast_001", "GOMECC-4", "R/V Ronald H. Brown")
        profile.data = pd.DataFrame({
            "pressure": [0, 10, 20, 30, 40],
            "temperature": [28.5, 28.4, 15.0, 28.2, 28.1],  # 15.0 is anomalous
            "conductivity": [4.2, 4.1, 3.9, 4.0, 4.1]
        })

        profile.apply_qc(despike_threshold=3.0)

        assert "temperature" in profile.qc_flags
        assert len(profile.qc_flags["temperature"]) > 0

    def test_calculate_derived_parameters(self):
        """Test derived parameter calculation."""
        profile = CTDProfile("cast_001", "GOMECC-4", "R/V Ronald H. Brown")
        profile.data = pd.DataFrame({
            "pressure": [0, 10, 20, 30],
            "temperature": [28.5, 28.3, 27.9, 25.2],
            "conductivity": [4.2, 4.1, 4.0, 3.8]
        })

        profile.calculate_derived_parameters()

        assert "salinity_practical" in profile.data.columns or "salinity_absolute" in profile.data.columns
        assert len(profile.derived_params) > 0

    def test_processing_log(self):
        """Test that processing log is maintained."""
        profile = CTDProfile("cast_001", "GOMECC-4", "R/V Ronald H. Brown")
        profile.data = pd.DataFrame({
            "pressure": [0, 10, 20],
            "temperature": [28.5, 28.3, 27.9]
        })

        profile.apply_qc()
        assert len(profile.processing_log) > 0
        assert any(e["action"] == "apply_qc" for e in profile.processing_log)
