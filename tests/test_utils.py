"""Tests for utility functions."""

import pytest
import numpy as np

from ctd_processor.utils import (
    iso8601_timestamp,
    validate_pressure_range,
    validate_temperature_range,
    validate_salinity_range
)


class TestTimestamps:
    """Test timestamp generation."""

    def test_iso8601_format(self):
        """Test ISO 8601 timestamp format."""
        ts = iso8601_timestamp()
        assert "T" in ts
        assert "Z" in ts or "+" in ts
        assert len(ts) > 10


class TestPressureValidation:
    """Test pressure range validation."""

    def test_valid_pressure(self):
        """Test valid pressure range."""
        pressure = np.array([0, 100, 500, 1000])
        is_valid, msg = validate_pressure_range(pressure)
        assert is_valid == True

    def test_invalid_pressure_out_of_range(self):
        """Test out-of-range pressure."""
        pressure = np.array([0, 100, 10000])
        is_valid, msg = validate_pressure_range(pressure)
        assert is_valid == False

    def test_invalid_pressure_not_increasing(self):
        """Test non-monotonic pressure."""
        pressure = np.array([0, 100, 50, 150])
        is_valid, msg = validate_pressure_range(pressure)
        assert is_valid == False

    def test_empty_pressure(self):
        """Test empty pressure array."""
        pressure = np.array([])
        is_valid, msg = validate_pressure_range(pressure)
        assert is_valid == False


class TestTemperatureValidation:
    """Test temperature range validation."""

    def test_valid_temperature(self):
        """Test valid temperature range."""
        temp = np.array([25.0, 20.0, 15.0, 10.0, 5.0])
        is_valid, msg = validate_temperature_range(temp)
        assert is_valid == True

    def test_invalid_temperature_out_of_range(self):
        """Test out-of-range temperature."""
        temp = np.array([25.0, 50.0, 20.0])
        is_valid, msg = validate_temperature_range(temp)
        assert is_valid == False


class TestSalinityValidation:
    """Test salinity range validation."""

    def test_valid_salinity(self):
        """Test valid salinity range."""
        sal = np.array([35.0, 35.1, 35.2, 35.3])
        is_valid, msg = validate_salinity_range(sal)
        assert is_valid == True

    def test_invalid_salinity_out_of_range(self):
        """Test out-of-range salinity."""
        sal = np.array([35.0, 50.0, 35.0])
        is_valid, msg = validate_salinity_range(sal)
        assert is_valid == False

    def test_empty_salinity(self):
        """Test empty salinity array."""
        sal = np.array([])
        is_valid, msg = validate_salinity_range(sal)
        assert is_valid == False
