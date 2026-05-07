# Technical Methods — ctd-cast-processor

## 1. Input Format

Sea-Bird Electronics CNV ("converted") files are the standard output of
SBE Data Processing software. They consist of:

- A **header block** where every line starts with `*`, encoding metadata such
  as file name, start time, sensor serial numbers, variable names, and position.
- A sentinel line `*END*` marking the end of the header.
- A **data block** of whitespace-delimited numerical rows, one row per scan.

The parser extracts latitude, longitude, and start-time from the header, then
reads the data block into a Pandas DataFrame. Missing values (bad_flag sentinel
`-9.990e-29`) are replaced with IEEE-754 NaN before any processing.

Column order assumed (fallback parser): `pressure`, `temperature`,
`conductivity`, followed by optional variables (`salinity`, `oxygen`, …).

## 2. Loop Editing

A pressure loop occurs when the instrument reverses direction during the
downcast (e.g., due to ship heave). The algorithm:

1. Identifies indices where pressure decreases between consecutive scans
   AND then rises again (local pressure minimum).
2. At each such reversal, checks whether the adjacent temperature difference
   exceeds a configurable threshold (default 0.02 °C).
3. Flags both the reversal scan and its predecessor as bad (QC flag 3).

The algorithm works at 24 Hz scan resolution, so even brief reversals are
caught without relying on integration windows.

## 3. Spike Detection (MAD)

Two complementary algorithms are applied:

**Rolling MAD test:**
For each scan i, the local median M and MAD are computed over a sliding
window of ±`window` scans (default window=3):

```
MAD_i = median( |x_j - median(x_j)| )  for j in [i-w, i+w]
spike if |x_i - M_i| > threshold * MAD_i
```

Applied to: temperature and conductivity.  
Default threshold: 3.0 (≈ 3σ for Gaussian data; MAD is more robust to
contamination).

## 4. Pressure Bin Averaging

Following SBE Data Processing Application Note 51:

- Bin edges are placed at `n - 0.5` and `n + 0.5` dbar for each integer n.
- Bin centre assigned as the lower bin edge (integer dbar).
- All valid scans in each bin are averaged arithmetically.
- Bins with no data are omitted from the output (not filled with NaN).
- QC flags are reset to "good" (1) after averaging, reflecting the averaging
  process that suppresses isolated anomalies.

## 5. TEOS-10 Derived Variables

All thermodynamic calculations use the [gsw](https://www.teos-10.org/)
Gibbs Seawater Toolbox (v3.6+), implementing the full TEOS-10 standard:

| Symbol | Variable | Function |
|--------|----------|----------|
| **SP** | Practical Salinity | `gsw.SP_from_C(C, t, p)` |
| **SA** | Absolute Salinity | `gsw.SA_from_SP(SP, p, lon, lat)` |
| **CT** | Conservative Temperature | `gsw.CT_from_t(SA, t, p)` |
| **ρ** | In-situ density | `gsw.rho(SA, CT, p)` |
| **σ₀** | Potential density anomaly | `ρ(SA, CT, 0) − 1000` |
| **c** | Speed of sound | `gsw.sound_speed(SA, CT, p)` |

Conductivity input to `gsw.SP_from_C` is in **mS/cm** (Seabird standard).
Longitude and latitude from the CNV header are used for the haline contraction
correction in SA; defaults to (0, 0) if metadata is absent.

## 6. Quality Control Flag Scale

WOCE CTD QC flags (WOCE Hydrographic Operations Manual, Table 3.1):

| Flag | Meaning |
|------|---------|
| 1 | Good |
| 2 | Suspicious / potentially correctable (spike) |
| 3 | Bad — pressure reversal / loop |
| 4 | Bad — not correctable |
| 9 | Missing / not sampled |

### 6.1 Density Inversion Detection

Potential density anomaly σ₀ is computed from simplified coefficients
(1027.6 − 0.5T + 0.78S) for a fast in-situ check. A scan is flagged
(flag 3) if σ₀ decreases by more than `threshold` kg m⁻³ relative to the
scan above, indicating static instability. The full gsw.rho route is used
in the derived-variable pipeline.

## 7. Output — NetCDF-4

The output NetCDF follows CF Conventions 1.8 and ACDD 1.3:

- Coordinate dimension: `obs` (observation index)
- `pressure` carries `standard_name="sea_water_pressure"`, `units="dbar"`,
  `axis="Z"`, `positive="down"`
- Each measured variable carries `standard_name`, `units`, `long_name`
- Global attributes: `Conventions`, `title`, `summary`, `cruise_id`,
  `platform`, `instrument`, `date_created`, `history`, `source`,
  `geospatial_lat_min/max`, `geospatial_lon_min/max`
- Compression: zlib level 4 on all data variables

## 8. Provenance

Every processing step appends an entry to `processing_log`:

```json
{
  "timestamp": "2026-05-14T10:00:00Z",
  "action": "apply_qc",
  "loop_edit_threshold": 0.02,
  "despike_threshold": 3.0,
  "suspicious_points": 7
}
```

The log is stored in the JSON sidecar (`*_metadata.json`) and mirrored as a
`→`-delimited `history` global attribute in the NetCDF file.

## 9. References

- WOCE Hydrographic Operations Manual (1994).
- ARGO Quality Control Manual for CTD and Trajectory Data, v3.4 (2023).
  https://doi.org/10.13155/33951
- IOC, SCOR and IAPSO (2010). TEOS-10. http://www.teos-10.org
- McDougall & Barker (2011). Getting started with TEOS-10.
  SCOR/IAPSO WG127. ISBN 978-0-646-55621-5.
- GO-SHIP Repeat Hydrography Manual (2010). IOCCP Report No. 14.
- Seabird Scientific (2023). SBE Data Processing Application Note 51.
