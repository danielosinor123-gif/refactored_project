"""Chart generation: correlation heatmap, distributions, and box plots.

Preserves the original behavior: seaborn heatmap with annotations, 2x3
distribution histograms, box plots, dpi=300 output, and figures closed
after saving to avoid memory leaks.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import seaborn as sns  # noqa: E402

from utils.logging_setup import get_logger

logger = get_logger(__name__)


class ChartGenerator:
    """Generates and saves matplotlib/seaborn charts for processed data."""

    def __init__(self, dpi: int = 300):
        """Create a chart generator.

        Args:
            dpi: Resolution of the saved images.
        """
        self.dpi = int(dpi)

    def _save(self, file_path: str, close: bool = True) -> None:
        """Save the current figure and close it to free memory.

        Args:
            file_path: Destination image file path.
            close: Whether to close the figure after saving.
        """
        plt.savefig(file_path, dpi=self.dpi, bbox_inches="tight")
        if close:
            plt.close()

    def generate_visualizations(self, df: pd.DataFrame, output_dir: str | Path) -> None:
        """Generate data visualizations for a DataFrame.

        Preserves the original behavior: creates the output directory, then
        writes ``correlation_heatmap.png``, ``distributions.png``, and
        ``boxplots.png`` for the numeric columns.

        Args:
            df: Input DataFrame.
            output_dir: Directory where chart images are saved.
        """
        try:
            logger.info("Generating visualizations")
            os.makedirs(output_dir, exist_ok=True)
            plt.style.use("seaborn-v0_8")

            numeric_df = df.select_dtypes(include=[np.number])

            # Correlation heatmap
            if len(numeric_df.columns) > 1:
                plt.figure(figsize=(12, 8))
                correlation_matrix = numeric_df.corr()
                sns.heatmap(correlation_matrix, annot=True, cmap="coolwarm", center=0)
                plt.title("Feature Correlation Heatmap")
                plt.tight_layout()
                self._save(f"{output_dir}/correlation_heatmap.png")

            # Distribution plots for numeric columns
            numeric_columns = numeric_df.columns[:6]
            if len(numeric_columns) > 0:
                fig, axes = plt.subplots(2, 3, figsize=(15, 10))
                axes = axes.ravel()
                for i, col in enumerate(numeric_columns):
                    if i < 6:
                        axes[i].hist(df[col].dropna(), bins=30, alpha=0.7)
                        axes[i].set_title(f"Distribution of {col}")
                        axes[i].set_xlabel(col)
                        axes[i].set_ylabel("Frequency")
                plt.tight_layout()
                self._save(f"{output_dir}/distributions.png")

            # Box plots for outlier detection
            if len(numeric_columns) > 0:
                plt.figure(figsize=(12, 6))
                df[numeric_columns].boxplot()
                plt.title("Box Plots for Outlier Detection")
                plt.xticks(rotation=45)
                plt.tight_layout()
                self._save(f"{output_dir}/boxplots.png")

            logger.info("Visualizations saved to %s", output_dir)
        except Exception as exc:  # noqa: BLE001 - visualization failures are logged
            logger.error("Visualization generation failed: %s", exc)

    generate_all = generate_visualizations


def generate_visualizations(df: pd.DataFrame, output_dir: str | Path, dpi: int = 300) -> None:
    """Generate data visualizations for a DataFrame.

    Convenience function wrapping :class:`ChartGenerator`.

    Args:
        df: Input DataFrame.
        output_dir: Directory where chart images are saved. Created when
            missing.
        dpi: Resolution of the saved images.
    """
    ChartGenerator(dpi=dpi).generate_visualizations(df, output_dir)
