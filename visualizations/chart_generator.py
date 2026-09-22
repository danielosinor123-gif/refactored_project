"""Chart generation: correlation heatmap, distributions, and box plots."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

import pandas as pd  # noqa: E402

from utils.logging_setup import get_logger

logger = get_logger(__name__)


class ChartGenerator:
    """Generates and saves matplotlib charts for processed data."""

    def __init__(self, output_directory: str | Path, dpi: int = 150):
        """Create a chart generator.

        Args:
            output_directory: Directory where chart images are saved.
            dpi: Resolution of the saved images.
        """
        self.output_directory = Path(output_directory)
        self.dpi = int(dpi)

    def _ensure_output_directory(self) -> Path:
        """Create the chart output directory if it does not exist."""
        self.output_directory.mkdir(parents=True, exist_ok=True)
        return self.output_directory

    def _save(self, figure: plt.Figure, file_name: str) -> Optional[Path]:
        """Save a figure to the output directory and close it.

        Args:
            figure: Matplotlib figure to save.
            file_name: Destination image file name.

        Returns:
            Path of the saved image, or ``None`` when saving fails.
        """
        path = self._ensure_output_directory() / file_name
        try:
            figure.savefig(path, dpi=self.dpi, bbox_inches="tight")
            logger.info("Chart saved to %s", path)
            return path
        except OSError as exc:
            logger.error("Failed to save chart %s: %s", path, exc)
            return None
        finally:
            plt.close(figure)

    def _numeric(self, frame: pd.DataFrame) -> pd.DataFrame:
        """Return only numeric columns, excluding helper columns."""
        numeric = frame.select_dtypes(include="number")
        return numeric.drop(
            columns=[c for c in ("row_sum", "row_mean", "row_min", "row_max") if c in numeric.columns],
            errors="ignore",
        )

    def correlation_heatmap(self, frame: pd.DataFrame, file_name: str = "correlation_heatmap.png") -> Optional[Path]:
        """Generate a correlation heatmap for numeric columns.

        Args:
            frame: Input DataFrame.
            file_name: Destination image file name.

        Returns:
            Path of the saved image, or ``None`` when no numeric data exists.
        """
        numeric = self._numeric(frame)
        if numeric.shape[1] < 2:
            logger.info("Not enough numeric columns for a correlation heatmap; skipping")
            return None
        figure, axis = plt.subplots(figsize=(10, 8))
        correlation = numeric.corr(numeric_only=True)
        image = axis.imshow(correlation, cmap="coolwarm", vmin=-1.0, vmax=1.0)
        axis.set_xticks(range(len(correlation.columns)))
        axis.set_xticklabels(correlation.columns, rotation=45, ha="right", fontsize=8)
        axis.set_yticks(range(len(correlation.columns)))
        axis.set_yticklabels(correlation.columns, fontsize=8)
        axis.set_title("Correlation Heatmap")
        figure.colorbar(image, ax=axis, fraction=0.046, pad=0.04)
        return self._save(figure, file_name)

    def numeric_distributions(self, frame: pd.DataFrame, max_columns: int = 6,
                              file_name: str = "numeric_distributions.png") -> Optional[Path]:
        """Generate histogram distributions for numeric columns.

        Args:
            frame: Input DataFrame.
            max_columns: Maximum number of columns to plot.
            file_name: Destination image file name.

        Returns:
            Path of the saved image, or ``None`` when no numeric data exists.
        """
        numeric = self._numeric(frame)
        columns = list(numeric.columns)[:max_columns]
        if not columns:
            logger.info("No numeric columns for distribution plots; skipping")
            return None
        figure, axes = plt.subplots(
            nrows=len(columns), ncols=1, figsize=(8, 3 * len(columns)), squeeze=False
        )
        for axis, column in zip(axes.flat, columns):
            numeric[column].plot(kind="hist", bins=30, ax=axis, color="#4a7", edgecolor="white")
            axis.set_title(f"Distribution of {column}")
            axis.set_xlabel(column)
        figure.tight_layout()
        return self._save(figure, file_name)

    def box_plots(self, frame: pd.DataFrame, max_columns: int = 6,
                  file_name: str = "box_plots.png") -> Optional[Path]:
        """Generate box plots for numeric columns.

        Args:
            frame: Input DataFrame.
            max_columns: Maximum number of columns to plot.
            file_name: Destination image file name.

        Returns:
            Path of the saved image, or ``None`` when no numeric data exists.
        """
        numeric = self._numeric(frame)
        columns = list(numeric.columns)[:max_columns]
        if not columns:
            logger.info("No numeric columns for box plots; skipping")
            return None
        figure, axis = plt.subplots(figsize=(10, 6))
        numeric[columns].plot(kind="box", ax=axis)
        axis.set_title("Box Plots of Numeric Columns")
        axis.set_xticklabels(axis.get_xticklabels(), rotation=45, ha="right", fontsize=8)
        return self._save(figure, file_name)

    def generate_all(self, frame: pd.DataFrame) -> list:
        """Generate every supported chart for a DataFrame.

        Args:
            frame: Input DataFrame.

        Returns:
            List of saved image paths (skipping chart types with no data).
        """
        saved = []
        for chart in (self.correlation_heatmap, self.numeric_distributions, self.box_plots):
            path = chart(frame)
            if path is not None:
                saved.append(path)
        return saved

    generate_visualizations = generate_all


def generate_visualizations(
    frame: pd.DataFrame,
    output_directory: str | Path,
    dpi: int = 150,
) -> list:
    """Generate all supported charts for a DataFrame.

    Convenience function wrapping :class:`ChartGenerator`. Creates the
    output directory, saves every chart image, and closes figures after
    saving to avoid memory leaks.

    Args:
        frame: Input DataFrame.
        output_directory: Directory where chart images are saved.
        dpi: Resolution of the saved images.

    Returns:
        List of saved image paths (skipping chart types with no data).
    """
    return ChartGenerator(output_directory, dpi=dpi).generate_all(frame)
