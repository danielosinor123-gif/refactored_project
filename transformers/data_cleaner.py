"""Data cleaning: duplicates, missing values, outliers, text normalization."""

from __future__ import annotations

import re
from typing import Optional

import pandas as pd

from utils.logging_setup import get_logger

logger = get_logger(__name__)

_WHITESPACE_RE = re.compile(r"\s+")


def clean_data(
    frame: pd.DataFrame,
    missing_strategy: str = "drop",
    fill_value: float = 0.0,
    handle_outliers: Optional[bool] = None,
) -> pd.DataFrame:
    """Run the full cleaning pipeline over a DataFrame.

    Convenience function wrapping :class:`DataCleaner`.

    Args:
        frame: Input DataFrame.
        missing_strategy: How to handle missing values: ``"drop"``,
            ``"fill"`` (numeric with ``fill_value``), or ``"none"``.
        fill_value: Value used when ``missing_strategy`` is ``"fill"``.
        handle_outliers: Optional override; defaults to enabled.

    Returns:
        The cleaned DataFrame with a ``processed_at`` column.
    """
    cleaner = DataCleaner(
        missing_strategy=missing_strategy,
        fill_value=fill_value,
    )
    return cleaner.clean(frame, handle_outliers=handle_outliers)


class DataCleaner:
    """Applies cleaning steps to loaded DataFrames and scores quality."""

    def __init__(
        self,
        missing_strategy: str = "drop",
        fill_value: float = 0.0,
        outlier_iqr_multiplier: float = 1.5,
    ):
        """Create a data cleaner.

        Args:
            missing_strategy: How to handle missing values: ``"drop"``,
                ``"fill"`` (numeric with ``fill_value``), or ``"none"``.
            fill_value: Value used when ``missing_strategy`` is ``"fill"``.
            outlier_iqr_multiplier: IQR multiplier used for outlier detection.
        """
        self.missing_strategy = missing_strategy
        self.fill_value = fill_value
        self.outlier_iqr_multiplier = float(outlier_iqr_multiplier)

    def remove_duplicates(self, frame: pd.DataFrame) -> pd.DataFrame:
        """Remove duplicate rows from a DataFrame.

        Args:
            frame: Input DataFrame.

        Returns:
            DataFrame without duplicate rows.
        """
        before = len(frame)
        result = frame.drop_duplicates().reset_index(drop=True)
        removed = before - len(result)
        if removed:
            logger.info("Removed %d duplicate row(s)", removed)
        return result

    def handle_missing_values(self, frame: pd.DataFrame) -> pd.DataFrame:
        """Handle missing values according to the configured strategy.

        Args:
            frame: Input DataFrame.

        Returns:
            DataFrame with missing values dropped, filled, or untouched.
        """
        missing_total = int(frame.isna().sum().sum())
        if missing_total == 0 or self.missing_strategy == "none":
            return frame
        if self.missing_strategy == "fill":
            result = frame.copy()
            numeric_columns = result.select_dtypes(include="number").columns
            result[numeric_columns] = result[numeric_columns].fillna(self.fill_value)
            result = result.fillna("")
            logger.info("Filled %d missing value(s) with %r", missing_total, self.fill_value)
            return result
        result = frame.dropna().reset_index(drop=True)
        logger.info("Dropped %d row(s) containing missing values", missing_total)
        return result

    def handle_outliers(self, frame: pd.DataFrame) -> pd.DataFrame:
        """Remove rows whose numeric values fall outside the IQR bounds.

        Args:
            frame: Input DataFrame.

        Returns:
            DataFrame with outlier rows removed.
        """
        numeric = frame.select_dtypes(include="number")
        if numeric.empty or len(frame) < 4:
            return frame
        q1 = numeric.quantile(0.25)
        q3 = numeric.quantile(0.75)
        iqr = q3 - q1
        mask = ~((numeric < (q1 - self.outlier_iqr_multiplier * iqr))
                 | (numeric > (q3 + self.outlier_iqr_multiplier * iqr))).any(axis=1)
        result = frame.loc[mask].reset_index(drop=True)
        removed = len(frame) - len(result)
        if removed:
            logger.info("Removed %d outlier row(s)", removed)
        return result

    def normalize_text(self, frame: pd.DataFrame) -> pd.DataFrame:
        """Normalize text columns: trim, collapse whitespace, lowercase.

        Args:
            frame: Input DataFrame.

        Returns:
            DataFrame with normalized text/object columns.
        """
        result = frame.copy()
        text_columns = result.select_dtypes(include=["object", "string"]).columns
        for column in text_columns:
            normalized = result[column].map(
                lambda value: _WHITESPACE_RE.sub(" ", str(value)).strip().lower()
                if pd.notna(value)
                else value
            )
            result[column] = normalized
        if len(text_columns):
            logger.info("Normalized %d text column(s)", len(text_columns))
        return result

    def compute_quality_score(self, frame: pd.DataFrame) -> float:
        """Compute an aggregate data quality score between 0 and 100.

        The score weights completeness (no missing values) and uniqueness
        (no duplicate rows) equally.

        Args:
            frame: Input DataFrame.

        Returns:
            Quality score as a float between 0.0 and 100.0.
        """
        if frame.empty:
            return 0.0
        total_cells = frame.size
        missing_ratio = float(frame.isna().sum().sum()) / total_cells if total_cells else 0.0
        duplicate_ratio = float(frame.duplicated().sum()) / len(frame) if len(frame) else 0.0
        score = (1.0 - missing_ratio) * 50.0 + (1.0 - duplicate_ratio) * 50.0
        return round(max(0.0, min(100.0, score)), 2)

    def add_processing_timestamp(self, frame: pd.DataFrame) -> pd.DataFrame:
        """Add a ``processed_at`` timestamp column to a DataFrame.

        Args:
            frame: Input DataFrame.

        Returns:
            DataFrame including the ``processed_at`` column.
        """
        result = frame.copy()
        result["processed_at"] = pd.Timestamp.now(tz="UTC").isoformat()
        return result

    def clean(self, frame: pd.DataFrame, handle_outliers: Optional[bool] = None) -> pd.DataFrame:
        """Run the full cleaning pipeline over a DataFrame.

        Args:
            frame: Input DataFrame.
            handle_outliers: Optional override; defaults to enabled.

        Returns:
            The cleaned DataFrame with a ``processed_at`` column.
        """
        result = self.remove_duplicates(frame)
        result = self.handle_missing_values(result)
        if handle_outliers is None or handle_outliers:
            result = self.handle_outliers(result)
        result = self.normalize_text(result)
        result = self.add_processing_timestamp(result)
        return result
