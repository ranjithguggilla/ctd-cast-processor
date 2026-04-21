"""
Visualization module for CTD data.

Generates:
- T-S (Temperature-Salinity) diagrams with density contours
- Profile plots (depth vs T, S, density)
- Section plots (multiple casts)
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.gridspec import GridSpec
from pathlib import Path
import gsw
from typing import List, Optional, Tuple


class CTDVisualizer:
    """Generate publication-quality CTD visualizations."""

    def __init__(self, figsize: Tuple[float, float] = (12, 8)):
        """Initialize visualizer with figure size."""
        self.figsize = figsize
        plt.style.use('seaborn-v0_8-darkgrid')

    def plot_ts_diagram(
        self,
        profiles: List,  # List of CTDProfile objects
        output_path: Optional[str] = None,
        show: bool = False
    ) -> Optional[str]:
        """
        Generate T-S diagram with density contours.

        Args:
            profiles: List of CTDProfile objects
            output_path: Save figure here (optional)
            show: Display figure

        Returns:
            Path to saved figure if output_path provided
        """
        fig, ax = plt.subplots(figsize=self.figsize)

        # Temperature and salinity ranges
        t_range = np.linspace(0, 30, 100)
        s_range = np.linspace(32, 37, 100)
        T, S = np.meshgrid(t_range, s_range)

        # Compute density anomaly on grid (assuming surface pressure)
        p = 0  # Reference pressure (surface)
        rho = gsw.rho(S, gsw.CT_from_t(S, T, p), p) - 1000

        # Plot density contours
        contours = ax.contour(T, S, rho, levels=10, colors='lightgray',
                             linestyles='dashed', linewidths=0.5, alpha=0.6)
        ax.clabel(contours, inline=True, fontsize=8, fmt='%.1f')

        # Plot each profile's T-S curve
        colors = plt.cm.viridis(np.linspace(0, 1, len(profiles)))
        for profile, color in zip(profiles, colors):
            if "temperature" in profile.data.columns and \
               "salinity_absolute" in profile.data.columns:
                ax.plot(
                    profile.data["temperature"],
                    profile.data["salinity_absolute"],
                    'o-', color=color, label=profile.cast_id, linewidth=2, markersize=4
                )

        ax.set_xlabel("Temperature (°C)", fontsize=12, fontweight='bold')
        ax.set_ylabel("Absolute Salinity (g/kg)", fontsize=12, fontweight='bold')
        ax.set_title("T-S Diagram", fontsize=14, fontweight='bold')
        ax.legend(loc='best', fontsize=10)
        ax.grid(True, alpha=0.3)

        if output_path:
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            fig.savefig(output_path, dpi=300, bbox_inches='tight')
            return str(output_path)

        if show:
            plt.show()

        return None

    def plot_profile(
        self,
        profile,
        output_path: Optional[str] = None,
        show: bool = False
    ) -> Optional[str]:
        """
        Generate profile plot (T, S, density vs depth).

        Args:
            profile: CTDProfile object
            output_path: Save figure here
            show: Display figure

        Returns:
            Path to saved figure
        """
        if "pressure" not in profile.data.columns:
            return None

        fig = plt.figure(figsize=self.figsize)
        gs = GridSpec(1, 3, figure=fig, hspace=0.3, wspace=0.3)

        # Temperature profile
        ax_t = fig.add_subplot(gs[0, 0])
        ax_t.plot(profile.data["temperature"], -profile.data["pressure"], 'b-o', linewidth=2)
        ax_t.set_xlabel("Temperature (°C)", fontweight='bold')
        ax_t.set_ylabel("Pressure (dbar)", fontweight='bold')
        ax_t.invert_yaxis()
        ax_t.grid(True, alpha=0.3)

        # Salinity profile
        ax_s = fig.add_subplot(gs[0, 1])
        if "salinity_absolute" in profile.data.columns:
            ax_s.plot(profile.data["salinity_absolute"], -profile.data["pressure"], 'g-o', linewidth=2)
        elif "salinity_practical" in profile.data.columns:
            ax_s.plot(profile.data["salinity_practical"], -profile.data["pressure"], 'g-o', linewidth=2)
        ax_s.set_xlabel("Salinity (g/kg or PSU)", fontweight='bold')
        ax_s.set_ylabel("Pressure (dbar)", fontweight='bold')
        ax_s.invert_yaxis()
        ax_s.grid(True, alpha=0.3)

        # Density anomaly profile
        ax_d = fig.add_subplot(gs[0, 2])
        if "density_potential_anomaly" in profile.data.columns:
            ax_d.plot(profile.data["density_potential_anomaly"], -profile.data["pressure"],
                     'r-o', linewidth=2)
            ax_d.set_xlabel("σ₀ (kg/m³)", fontweight='bold')
        ax_d.set_ylabel("Pressure (dbar)", fontweight='bold')
        ax_d.invert_yaxis()
        ax_d.grid(True, alpha=0.3)

        fig.suptitle(f"CTD Profile: {profile.cast_id}", fontsize=14, fontweight='bold')

        if output_path:
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            fig.savefig(output_path, dpi=300, bbox_inches='tight')
            return str(output_path)

        if show:
            plt.show()

        return None

    @staticmethod
    def plot_section(
        profiles: List,
        output_path: Optional[str] = None,
        show: bool = False
    ) -> Optional[str]:
        """
        Generate section plot (multiple profiles side-by-side showing T/S/density).

        Args:
            profiles: List of CTDProfile objects
            output_path: Save figure here
            show: Display figure

        Returns:
            Path to saved figure
        """
        if not profiles:
            return None

        fig, axes = plt.subplots(1, 3, figsize=(16, 6), sharey=True)

        # Prepare section data
        max_depth = max([p.data["pressure"].max() for p in profiles])
        x_positions = np.arange(len(profiles))

        for i, profile in enumerate(profiles):
            p = profile.data["pressure"].values
            t = profile.data["temperature"].values
            d = profile.data.get("density_potential_anomaly", p * 0).values

            # Temperature section
            scatter_t = axes[0].scatter(x_positions[i] * np.ones_like(p), p,
                                       c=t, cmap='RdYlBu_r', s=50, vmin=0, vmax=30)
            axes[0].plot(x_positions[i] * np.ones_like(p), p, 'k-', alpha=0.3, linewidth=0.5)

            # Density section
            if d.max() > 0:
                scatter_d = axes[2].scatter(x_positions[i] * np.ones_like(p), p,
                                           c=d, cmap='viridis', s=50)
                axes[2].plot(x_positions[i] * np.ones_like(p), p, 'k-', alpha=0.3, linewidth=0.5)

        # Formatting
        axes[0].set_ylabel("Pressure (dbar)", fontweight='bold', fontsize=11)
        axes[0].set_xlabel("Station", fontweight='bold')
        axes[0].set_title("Temperature (°C)", fontweight='bold')
        axes[0].set_xticks(x_positions)
        axes[0].set_xticklabels([p.cast_id for p in profiles], rotation=45)
        axes[0].invert_yaxis()
        axes[0].grid(True, alpha=0.3)

        axes[1].set_xlabel("Station", fontweight='bold')
        axes[1].set_title("Salinity", fontweight='bold')
        axes[1].set_xticks(x_positions)
        axes[1].set_xticklabels([p.cast_id for p in profiles], rotation=45)
        axes[1].invert_yaxis()
        axes[1].grid(True, alpha=0.3)

        axes[2].set_xlabel("Station", fontweight='bold')
        axes[2].set_title("σ₀ (kg/m³)", fontweight='bold')
        axes[2].set_xticks(x_positions)
        axes[2].set_xticklabels([p.cast_id for p in profiles], rotation=45)
        axes[2].invert_yaxis()
        axes[2].grid(True, alpha=0.3)

        fig.suptitle("CTD Section", fontsize=14, fontweight='bold')
        plt.tight_layout()

        if output_path:
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            fig.savefig(output_path, dpi=300, bbox_inches='tight')
            return str(output_path)

        if show:
            plt.show()

        return None
