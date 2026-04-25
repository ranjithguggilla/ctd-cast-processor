"""Command-line interface for CTD processor."""

import click
import logging
import json
from pathlib import Path
from typing import List

from ctd_processor import CTDProfile
from ctd_processor.visualization import CTDVisualizer
from ctd_processor.compliance import ComplianceChecker

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(message)s'
)
logger = logging.getLogger(__name__)


@click.group()
def main():
    """CTD Cast Processor — Seabird CTD processing with TEOS-10 and IOOS compliance."""
    pass


@main.command()
@click.argument("input_file", type=click.Path(exists=True))
@click.option("--output", "-o", default="output/", help="Output directory")
@click.option("--cruise", default="UNKNOWN", help="Cruise identifier")
@click.option("--vessel", default="UNKNOWN", help="Vessel name")
@click.option("--mad-threshold", default=3.0, help="Despike MAD threshold")
@click.option("--bin-size", default=1.0, help="Depth bin size (dbar)")
def process(input_file: str, output: str, cruise: str, vessel: str, mad_threshold: float, bin_size: float):
    """Process a single CTD cast."""
    input_path = Path(input_file)
    output_dir = Path(output)
    output_dir.mkdir(parents=True, exist_ok=True)

    click.echo(f"Loading {input_path.name}...")
    ctd = CTDProfile.from_seabird_cnv(str(input_path), cruise=cruise, vessel=vessel)

    if ctd.data.empty:
        click.echo("Error: No data loaded", err=True)
        return

    click.echo(f"Applying QC (despike threshold: {mad_threshold}σ, bin: {bin_size} dbar)...")
    ctd.apply_qc(despike_threshold=mad_threshold, bin_size=bin_size)

    click.echo("Calculating TEOS-10 derived variables...")
    ctd.calculate_derived_parameters()

    # Export
    csv_path = output_dir / f"{ctd.cast_id}_processed.csv"
    nc_path = output_dir / f"{ctd.cast_id}.nc"
    meta_path = output_dir / f"{ctd.cast_id}_metadata.json"

    ctd.to_csv(str(csv_path))
    ctd.to_netcdf(str(nc_path))
    ctd.save_metadata(str(meta_path))

    click.echo(f"✓ Processing complete:")
    click.echo(f"  CSV: {csv_path}")
    click.echo(f"  NetCDF: {nc_path}")
    click.echo(f"  Metadata: {meta_path}")


@main.command()
@click.argument("input_dir", type=click.Path(exists=True))
@click.option("--output", "-o", default="output/", help="Output directory")
@click.option("--cruise", default="UNKNOWN", help="Cruise identifier")
@click.option("--pattern", default="*.cnv", help="File pattern to match")
@click.option("--parallel", "-p", default=1, help="Number of parallel processes")
def batch(input_dir: str, output: str, cruise: str, pattern: str, parallel: int):
    """Batch process all CTD files in a directory."""
    input_path = Path(input_dir)
    output_dir = Path(output)
    output_dir.mkdir(parents=True, exist_ok=True)

    cnv_files = sorted(input_path.glob(pattern))
    click.echo(f"Found {len(cnv_files)} files matching '{pattern}'")

    for cnv_file in cnv_files:
        try:
            ctd = CTDProfile.from_seabird_cnv(str(cnv_file), cruise=cruise)
            ctd.apply_qc()
            ctd.calculate_derived_parameters()

            # Export all formats
            nc_path = output_dir / f"{ctd.cast_id}.nc"
            csv_path = output_dir / f"{ctd.cast_id}_processed.csv"
            meta_path = output_dir / f"{ctd.cast_id}_metadata.json"

            ctd.to_netcdf(str(nc_path))
            ctd.to_csv(str(csv_path))
            ctd.save_metadata(str(meta_path))
            click.echo(f"✓ {cnv_file.name}")
        except Exception as e:
            click.echo(f"✗ {cnv_file.name}: {e}", err=True)

    click.echo(f"Batch processing complete. Outputs in {output_dir}")


@main.command()
@click.argument("input_dir", type=click.Path(exists=True))
@click.option("--output", "-o", default=None, help="Save plots to directory")
def plot_ts(input_dir: str, output: str):
    """Generate T-S diagram from processed casts."""
    input_path = Path(input_dir)
    output_dir = Path(output) if output else input_path

    # Load all metadata.json files to find profiles
    profiles = []
    for meta_file in sorted(input_path.glob("*_metadata.json")):
        with open(meta_file) as f:
            meta = json.load(f)
        cast_id = meta["profile"]["cast_id"]
        nc_file = input_path / f"{cast_id}.nc"

        if nc_file.exists():
            try:
                # Reload profile from NetCDF for plotting
                import xarray as xr
                ds = xr.open_dataset(str(nc_file))
                # Create minimal profile object for plotting
                class PlotProfile:
                    def __init__(self):
                        self.cast_id = cast_id
                        self.data = ds.to_pandas()
                        ds.close()

                profiles.append(PlotProfile())
            except Exception as e:
                click.echo(f"Warning: Could not load {nc_file}: {e}", err=True)

    if not profiles:
        click.echo("No profiles found", err=True)
        return

    viz = CTDVisualizer()
    if output:
        output_dir.mkdir(parents=True, exist_ok=True)
        plot_path = output_dir / "ts_diagram.png"
    else:
        plot_path = input_path / "ts_diagram.png"

    viz.plot_ts_diagram(profiles, output_path=str(plot_path))
    click.echo(f"✓ T-S diagram saved: {plot_path}")


@main.command()
@click.argument("nc_files", nargs=-1, required=True, type=click.Path(exists=True))
def check_compliance(nc_files):
    """Check IOOS compliance of NetCDF files."""
    checker = ComplianceChecker()
    results = {}

    for nc_file in nc_files:
        is_compliant, details = checker.check_ioos_compliance(nc_file)

        if is_compliant is None:
            click.echo(f"⚠ {nc_file}: Compliance checker not installed")
        elif is_compliant:
            click.echo(f"✓ {nc_file}: PASSED")
        else:
            click.echo(f"✗ {nc_file}: FAILED")
            if "stderr" in details:
                click.echo(f"  {details.get('stderr', 'No details')[:100]}")

        # Manual CF checks
        cf_issues = checker.check_cf_conventions(nc_file)
        if cf_issues:
            for issue in cf_issues:
                click.echo(f"  Warning: {issue}")


if __name__ == "__main__":
    main()
