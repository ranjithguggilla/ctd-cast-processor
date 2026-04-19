#!/usr/bin/env python3
"""
Generate realistic synthetic Seabird CTD .cnv files for testing.

Creates CTD profiles simulating:
- Gulf of Mexico surveys (GOMECC-style)
- Coastal upwelling regions
- Deep ocean profiles

Includes realistic sensor noise and occasional spikes for QC testing.
"""

import numpy as np
import pandas as pd
from pathlib import Path
from datetime import datetime, timedelta
import random

random.seed(42)
np.random.seed(42)

OUT_DIR = Path(__file__).parent / "raw"
OUT_DIR.mkdir(exist_ok=True)


def generate_gomecc_profile(cast_id: str, lat: float, lon: float, depth_max: float = 1000):
    """
    Generate Gulf of Mexico CTD profile (GOMECC-style).

    Temperature and salinity profiles typical of the Gulf with:
    - Warm surface mixed layer
    - Thermocline
    - Cold deep water
    - Realistic profiles for location

    Args:
        cast_id: Cast identifier
        lat: Latitude (°N)
        lon: Longitude (°W)
        depth_max: Maximum cast depth (m)
    """
    # Realistic pressure/depth profile
    pressures = np.linspace(0, depth_max, 150)

    # Temperature profile (Gulf of Mexico typical)
    surface_temp = 28.5 - (lat - 27) * 0.5 + np.random.normal(0, 0.3)
    temp_profile = np.array([
        surface_temp if p <= 50 else
        surface_temp - (p - 50) * 0.15 if p <= 200 else
        15.0 - (p - 200) * 0.01
        for p in pressures
    ])
    # Add realistic noise
    temp_profile += np.random.normal(0, 0.1, len(temp_profile))
    # Add occasional spikes for QC testing
    spike_idx = random.sample(range(20, len(temp_profile) - 20), 2)
    for idx in spike_idx:
        temp_profile[idx] += np.random.choice([-1, 1]) * random.uniform(2, 4)

    # Salinity profile
    sal_profile = np.array([
        35.0 + 0.3 * np.tanh((p - 50) / 50) + np.random.normal(0, 0.05)
        for p in pressures
    ])
    sal_profile = np.clip(sal_profile, 34.5, 36.5)

    # Conductivity from T, S relationship (UNESCO/TEOS-10 empirical, in mS/cm)
    # Reference: conductivity at 35 PSU, 15°C, 0 dbar = 42.914 mS/cm (Seabird standard)
    # Temperature coefficient: ~0.02 per °C
    # Salinity coefficient: linear with PSU
    # Pressure coefficient: ~0.45% per 1000 dbar
    C_ref = 42.914  # mS/cm at 35 PSU, 15°C, 0 dbar (standard Seabird reference)
    temp_coeff = 1 + 0.02 * (temp_profile - 15)
    sal_coeff = (sal_profile / 35.0)
    press_coeff = 1 + 0.00045 * (pressures / 100)  # pressure in dbar
    cond_profile = C_ref * sal_coeff * temp_coeff * press_coeff + np.random.normal(0, 0.1, len(sal_profile))

    # Dissolved oxygen (decreases with depth, minimum at intermediate depths)
    oxy_profile = np.array([
        7.5 - 0.05 * p if p <= 500 else
        3.0 + np.random.normal(0, 0.1)
        for p in pressures
    ])

    data = pd.DataFrame({
        "pressure": pressures,
        "temperature": temp_profile,
        "conductivity": cond_profile,
        "salinity": sal_profile,
        "oxygen": oxy_profile,
    })

    return data, {
        "cast_id": cast_id,
        "latitude": lat,
        "longitude": lon,
        "cruise": "GOMECC-4",
        "vessel": "R/V Ronald H. Brown",
        "date": datetime.now().isoformat(),
        "max_depth_m": depth_max,
    }


def write_cnv_file(filepath: str, data: pd.DataFrame, metadata: dict):
    """
    Write CTD data in Seabird .cnv format (simplified).

    Args:
        filepath: Output file path
        data: CTD observations
        metadata: Header metadata
    """
    filepath = Path(filepath)
    filepath.parent.mkdir(parents=True, exist_ok=True)

    with open(filepath, 'w') as f:
        # Header section
        f.write("* Sea-Bird SBE 9/11 CTD\n")
        f.write(f"* Cast ID: {metadata.get('cast_id', 'unknown')}\n")
        f.write(f"* Cruise: {metadata.get('cruise', 'UNKNOWN')}\n")
        f.write(f"* Vessel: {metadata.get('vessel', 'UNKNOWN')}\n")
        f.write(f"* Latitude: {metadata.get('latitude', 0)}\n")
        f.write(f"* Longitude: {metadata.get('longitude', 0)}\n")
        f.write(f"* Start time: {metadata.get('date', datetime.now().isoformat())}\n")
        f.write("*\n")
        f.write("* Sensor Information:\n")
        f.write("* SBE 9/11 Serial Number: 0001\n")
        f.write("* Temperature sensor: SBE 3 SN 12345\n")
        f.write("* Conductivity sensor: SBE 4 SN 67890\n")
        f.write("*END*\n")

        # Data section
        for idx, row in data.iterrows():
            # Write in Seabird format: Pressure, Temperature, Conductivity, Salinity, Oxygen
            line = f"{row['pressure']:.1f} {row['temperature']:.4f} {row['conductivity']:.4f} {row['salinity']:.4f} {row['oxygen']:.2f}\n"
            f.write(line)


# Generate sample casts
casts = [
    ("cast_001", 27.50, -96.50, 800),   # Corpus Christi Shelf
    ("cast_002", 27.75, -95.80, 1000),  # Matagorda Slope
    ("cast_003", 28.10, -94.50, 500),   # Galveston Approach
    ("cast_004", 26.80, -92.00, 1500),  # De Soto Canyon
]

print("Generating synthetic Seabird .cnv files...")
for cast_id, lat, lon, depth in casts:
    data, meta = generate_gomecc_profile(cast_id, lat, lon, depth)
    cnv_path = OUT_DIR / f"{cast_id}.cnv"
    write_cnv_file(str(cnv_path), data, meta)
    print(f"  ✓ {cnv_path.name} ({len(data)} samples, {depth}m depth)")

print(f"\nGenerated {len(casts)} sample CTD casts in {OUT_DIR}/")
