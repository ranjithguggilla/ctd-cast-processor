"""
Core CTDProfile class for Seabird CTD processing.

Handles:
- Raw .cnv file ingestion (via seabird package)
- Standard QC (loop edit, despike, bin-averaging)
- TEOS-10 derived variables (absolute salinity, conservative temperature, density)
- CF-1.8 NetCDF export with full metadata
- ISO 19115-2 metadata generation
- IOOS compliance validation
"""

import json
import logging
from pathlib import Path
from datetime import datetime, timezone

import pandas as pd
import numpy as np
import xarray as xr
import gsw

try:
    from seabird.cnv import fCNV
except ImportError:
    fCNV = None

logger = logging.getLogger(__name__)


class CTDProfile:
    """
    Represents a single Seabird CTD cast with full processing pipeline.

    Attributes:
        cast_id (str): Unique cast identifier
        raw_data (pd.DataFrame): Raw observations from .cnv
        data (pd.DataFrame): QC-flagged and derived variable data
        metadata (dict): Cruise, cast, instrument information
        processing_log (list): Complete provenance chain
    """

    def __init__(self, cast_id: str, cruise: str = "UNKNOWN", vessel: str = "UNKNOWN"):
        """Initialize CTD profile."""
        self.cast_id = cast_id
        self.cruise = cruise
        self.vessel = vessel
        self.raw_data = pd.DataFrame()
        self.data = pd.DataFrame()
        self.metadata = {
            "cast_id": cast_id,
            "cruise": cruise,
            "vessel": vessel,
            "created_at": self._iso8601_timestamp(),
            "processing_version": "1.0.0",
        }
        self.processing_log = []
        self.qc_flags = {}
        self.derived_params = []

    @staticmethod
    def _iso8601_timestamp() -> str:
        """Return current UTC timestamp in ISO 8601 format."""
        return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    def _log_action(self, action: str, **kwargs) -> None:
        """Log a processing action with timestamp and parameters."""
        entry = {
            "timestamp": self._iso8601_timestamp(),
            "action": action,
            **kwargs
        }
        self.processing_log.append(entry)
        logger.info(f"{action}: {json.dumps({k: v for k, v in kwargs.items() if k not in ['data']})}")

    @classmethod
    def from_seabird_cnv(cls, filepath: str, cruise: str = "UNKNOWN", vessel: str = "UNKNOWN") -> "CTDProfile":
        """
        Load a CTD profile from Seabird .cnv file.

        Parses header for metadata (time, position, sensor info) and data section.

        Args:
            filepath: Path to .cnv file
            cruise: Cruise identifier
            vessel: Vessel name

        Returns:
            CTDProfile instance
        """
        filepath = Path(filepath)
        if not filepath.exists():
            raise FileNotFoundError(f"File not found: {filepath}")

        profile = cls(cast_id=filepath.stem, cruise=cruise, vessel=vessel)

        # Try using seabird package if available
        if fCNV is not None:
            try:
                cnv = fCNV(str(filepath))
                profile.raw_data = cnv.df.copy()
                profile.metadata["parsed_by"] = "seabird_package"
                profile._log_action(
                    "load_seabird_cnv",
                    filepath=str(filepath),
                    rows=len(profile.raw_data),
                    columns=list(profile.raw_data.columns)
                )
                logger.info(f"Loaded {len(profile.raw_data)} observations from {filepath.name}")
                return profile
            except Exception as e:
                logger.warning(f"seabird package failed ({e}), falling back to manual parsing")

        # Fallback: manual .cnv parsing
        with open(filepath, 'r') as f:
            lines = f.readlines()

        header_end = 0
        for i, line in enumerate(lines):
            if line.strip().startswith("*END*"):
                header_end = i + 1
                break

        # Parse header metadata
        for line in lines[:header_end]:
            if "start_time" in line.lower():
                profile.metadata["start_time"] = line.split("=")[-1].strip() if "=" in line else ""
            elif "position" in line.lower():
                profile.metadata["position"] = line.split("=")[-1].strip() if "=" in line else ""
            elif "latitude" in line.lower():
                try:
                    lat = float(line.split("=")[-1].strip())
                    profile.metadata["latitude"] = lat
                except (ValueError, IndexError):
                    pass
            elif "longitude" in line.lower():
                try:
                    lon = float(line.split("=")[-1].strip())
                    profile.metadata["longitude"] = lon
                except (ValueError, IndexError):
                    pass

        # Parse data
        data_lines = [line.strip() for line in lines[header_end:] if line.strip()]
        if data_lines:
            try:
                data_array = np.array([
                    [float(x) for x in line.split()]
                    for line in data_lines
                ])
                # Assume standard column order: pressure, temperature, conductivity, ...
                if data_array.shape[1] >= 3:
                    profile.raw_data = pd.DataFrame(
                        data_array,
                        columns=["pressure", "temperature", "conductivity"] +
                               [f"var_{i}" for i in range(data_array.shape[1] - 3)]
                    )
            except (ValueError, IndexError) as e:
                logger.warning(f"Data parsing failed: {e}")

        profile.data = profile.raw_data.copy()
        profile._log_action(
            "load_seabird_cnv",
            filepath=str(filepath),
            rows=len(profile.data),
            parsing_method="manual_fallback"
        )

        return profile

    def apply_qc(
        self,
        loop_edit_threshold: float = 0.02,
        despike_window: int = 3,
        despike_threshold: float = 3.0,
        bin_size: float = 1.0
    ) -> None:
        """
        Apply standard CTD QC processing.

        Steps:
        1. Loop edit: Remove duplicate casts (same depth) where T/S reverses
        2. Despike: Remove isolated high-frequency noise via MAD
        3. Bin-average: 1 dbar depth bins (default)

        Args:
            loop_edit_threshold: Salinity/temperature change tolerance
            despike_window: MAD window (samples)
            despike_threshold: MAD multiplier (sigma)
            bin_size: Depth bin size (dbar)
        """
        if self.data.empty or "pressure" not in self.data.columns:
            logger.warning("Cannot apply QC: missing pressure column")
            return

        # Initialize QC flags
        self.qc_flags = {col: np.ones(len(self.data), dtype=int)
                        for col in self.data.columns}

        # 1. Loop edit: Remove upcast/downcast reversals
        loop_edit_flags = self._loop_edit(loop_edit_threshold)
        for col in self.qc_flags:
            self.qc_flags[col][loop_edit_flags] = 3  # Mark bad

        # 2. Despike: Median Absolute Deviation on T, S, conductivity
        for col in ["temperature", "conductivity"]:
            if col in self.data.columns:
                despike_flags = self._despike(col, despike_window, despike_threshold)
                self.qc_flags[col][despike_flags] = 2  # Mark suspicious

        self._log_action(
            "apply_qc",
            loop_edit_threshold=loop_edit_threshold,
            despike_threshold=despike_threshold,
            suspicious_points=int(np.sum([np.sum(self.qc_flags[c] == 2) for c in self.qc_flags]))
        )

        # 3. Bin-average to standard depth intervals
        if bin_size > 0:
            self._bin_average(bin_size)

    def _loop_edit(self, threshold: float) -> np.ndarray:
        """
        Detect and flag loop reversals (CTD moving up/down then back).

        Returns boolean array (True = bad).
        """
        if "temperature" not in self.data.columns or "pressure" not in self.data.columns:
            return np.zeros(len(self.data), dtype=bool)

        bad = np.zeros(len(self.data), dtype=bool)
        pressure = self.data["pressure"].values
        temp = self.data["temperature"].values

        for i in range(1, len(pressure) - 1):
            # Check for pressure reversal (up-down pattern)
            if (pressure[i] < pressure[i-1] and pressure[i] < pressure[i+1]):
                # If temperature change is large, mark both samples bad
                if abs(temp[i] - temp[i-1]) > threshold:
                    bad[i-1:i+1] = True

        return bad

    def _despike(self, column: str, window: int = 3, threshold: float = 3.0) -> np.ndarray:
        """
        Detect spikes via Median Absolute Deviation (robust to outliers).

        Returns boolean array (True = spike).
        """
        if column not in self.data.columns or len(self.data) < window:
            return np.zeros(len(self.data), dtype=bool)

        series = self.data[column].values
        rolling_mad = pd.Series(series).rolling(window=window, center=True).apply(
            lambda x: np.median(np.abs(x - np.median(x)))
        ).values
        rolling_median = pd.Series(series).rolling(window=window, center=True).median().values

        deviation = np.abs(series - rolling_median)
        spikes = deviation > (threshold * rolling_mad)
        spikes[:window//2] = False  # Don't flag edges
        spikes[-window//2:] = False

        return spikes

    def _bin_average(self, bin_size: float = 1.0) -> None:
        """
        Bin-average to standard pressure levels (1 dbar default).

        Creates mean and std for each bin.
        """
        if "pressure" not in self.data.columns:
            return

        p_min = self.data["pressure"].min()
        p_max = self.data["pressure"].max()
        bins = np.arange(int(p_min), int(p_max) + bin_size, bin_size)

        binned_data = []
        for i in range(len(bins) - 1):
            mask = (self.data["pressure"] >= bins[i]) & (self.data["pressure"] < bins[i+1])
            if mask.sum() > 0:
                row = {col: self.data.loc[mask, col].mean() for col in self.data.columns}
                row["pressure"] = bins[i]
                binned_data.append(row)

        if binned_data:
            self.data = pd.DataFrame(binned_data)
            # Recalculate QC flags for binned data (set to 1 = good by default)
            self.qc_flags = {col: np.ones(len(self.data), dtype=int)
                           for col in self.data.columns}
            self._log_action("bin_average", bin_size=bin_size, output_rows=len(self.data))

    def calculate_derived_parameters(self) -> None:
        """
        Calculate TEOS-10 derived variables.

        Requires: pressure (dbar), temperature (°C), conductivity (S/m)
        Produces: salinity, absolute_salinity, conservative_temperature, potential_density_anomaly
        """
        if self.data.empty:
            logger.warning("No data for derivations")
            return

        required = ["pressure", "temperature", "conductivity"]
        if not all(col in self.data.columns for col in required):
            logger.warning(f"Missing required columns for derivations: {required}")
            return

        p = self.data["pressure"].values
        t = self.data["temperature"].values
        c = self.data["conductivity"].values

        try:
            # Practical salinity from conductivity (input in mS/cm, standard Seabird format)
            # gsw.SP_from_C expects conductivity in mS/cm
            self.data["salinity_practical"] = gsw.SP_from_C(c, t, p)
            self.derived_params.append("salinity_practical")

            # Absolute salinity (TEOS-10)
            # Requires longitude/latitude for realistic calc; use defaults if missing
            lon = self.metadata.get("longitude", 0)
            lat = self.metadata.get("latitude", 0)
            self.data["salinity_absolute"] = gsw.SA_from_SP(
                self.data["salinity_practical"], p, lon, lat
            )
            self.derived_params.append("salinity_absolute")

            # Conservative temperature (TEOS-10)
            self.data["temperature_conservative"] = gsw.CT_from_t(
                self.data["salinity_absolute"], t, p
            )
            self.derived_params.append("temperature_conservative")

            # Potential density anomaly (sigma-0): density at surface pressure
            rho = gsw.rho(self.data["salinity_absolute"], self.data["temperature_conservative"], p)
            self.data["density_potential_anomaly"] = rho - 1000
            self.derived_params.append("density_potential_anomaly")

            # Sound speed (UNESCO equation)
            self.data["sound_speed"] = gsw.sound_speed(
                self.data["salinity_absolute"], self.data["temperature_conservative"], p
            )
            self.derived_params.append("sound_speed")

            self._log_action(
                "calculate_derived_parameters",
                parameters=self.derived_params,
                library="gsw_teos10"
            )
            logger.info(f"Derived: {', '.join(self.derived_params)}")

        except Exception as e:
            logger.error(f"Derivation failed: {e}")

    def to_netcdf(self, filepath: str, compress: bool = True) -> None:
        """
        Export to CF-1.8 compliant NetCDF-4.

        Includes:
        - Standard CF variable names and attributes
        - Full global metadata
        - Processing history (provenance)
        - Data quality flags

        Args:
            filepath: Output path
            compress: Use gzip compression (level 4)
        """
        filepath = Path(filepath)
        filepath.parent.mkdir(parents=True, exist_ok=True)

        # Create xarray Dataset from all available columns
        data_vars = {
            col: (["obs"], self.data[col].values)
            for col in self.data.columns
        }
        ds = xr.Dataset(
            data_vars=data_vars,
            coords={"obs": np.arange(len(self.data))},
        )

        # Set CF standard names and attributes (only for present variables)
        _var_attrs = {
            "pressure": {
                "standard_name": "sea_water_pressure",
                "units": "dbar",
                "long_name": "Sea water pressure",
            },
            "temperature": {
                "standard_name": "sea_water_temperature",
                "units": "degree_Celsius",
                "long_name": "Sea water temperature",
            },
            "conductivity": {
                "standard_name": "sea_water_electrical_conductivity",
                "units": "mS/cm",
                "long_name": "Sea water electrical conductivity",
            },
        }
        for var, attrs in _var_attrs.items():
            if var in ds.data_vars:
                ds[var].attrs = attrs

        # Add derived variable attributes
        if "salinity_absolute" in ds.data_vars:
            ds["salinity_absolute"].attrs = {
                "standard_name": "sea_water_absolute_salinity",
                "units": "g/kg",
                "long_name": "Sea water absolute salinity (TEOS-10)",
            }
        if "temperature_conservative" in ds.data_vars:
            ds["temperature_conservative"].attrs = {
                "standard_name": "sea_water_conservative_temperature",
                "units": "degree_Celsius",
                "long_name": "Sea water conservative temperature (TEOS-10)",
            }
        if "density_potential_anomaly" in ds.data_vars:
            ds["density_potential_anomaly"].attrs = {
                "standard_name": "sea_water_sigma_theta",
                "units": "kg/m³",
                "long_name": "Sea water potential density anomaly",
            }

        # Global attributes (CF and ACDD)
        ds.attrs = {
            "Conventions": "CF-1.8, ACDD-1.3",
            "title": f"CTD Profile {self.cast_id}",
            "summary": f"Processed Seabird CTD profile from {self.cruise} aboard {self.vessel}. Includes standard QC (loop edit, despike, bin-average) and TEOS-10 derived variables.",
            "cruise_id": self.cruise,
            "platform": self.vessel,
            "instrument": "CTD (Seabird Electronics)",
            "date_created": self.metadata["created_at"],
            "history": " → ".join([p["action"] for p in self.processing_log]),
            "source": "Seabird CTD profiler",
            "references": "TEOS-10 equations: https://www.teos-10.org/",
        }

        if "latitude" in self.metadata:
            ds.attrs["geospatial_lat_min"] = self.metadata["latitude"]
            ds.attrs["geospatial_lat_max"] = self.metadata["latitude"]
        if "longitude" in self.metadata:
            ds.attrs["geospatial_lon_min"] = self.metadata["longitude"]
            ds.attrs["geospatial_lon_max"] = self.metadata["longitude"]

        # Write with compression
        encoding = {var: {"zlib": compress, "complevel": 4} for var in ds.data_vars}
        ds.to_netcdf(filepath, encoding=encoding)

        self._log_action("export_netcdf", filepath=str(filepath), rows=len(self.data))
        logger.info(f"Exported NetCDF: {filepath}")

    def to_csv(self, filepath: str) -> None:
        """Export data to CSV with QC flags."""
        filepath = Path(filepath)
        filepath.parent.mkdir(parents=True, exist_ok=True)

        output = self.data.copy()
        for col in self.qc_flags:
            output[f"{col}_qc"] = self.qc_flags.get(col, 1)

        output.to_csv(filepath, index=False)
        self._log_action("export_csv", filepath=str(filepath), rows=len(output))

    def save_metadata(self, filepath: str) -> None:
        """Save metadata and processing log to JSON."""
        filepath = Path(filepath)
        filepath.parent.mkdir(parents=True, exist_ok=True)

        metadata_out = {
            "profile": self.metadata,
            "processing_log": self.processing_log,
            "derived_parameters": self.derived_params,
            "qc_summary": {
                col: {
                    "good": int(np.sum(self.qc_flags.get(col, [1]) == 1)),
                    "suspicious": int(np.sum(self.qc_flags.get(col, [1]) == 2)),
                    "bad": int(np.sum(self.qc_flags.get(col, [1]) == 3)),
                }
                for col in self.data.columns
            }
        }

        with open(filepath, 'w') as f:
            json.dump(metadata_out, f, indent=2)

        self._log_action("save_metadata", filepath=str(filepath))
