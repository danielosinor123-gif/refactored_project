"""Data cleaning: duplicates, missing values, outliers, text normalization."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

import numpy as np
import pandas as pd

from utils.logging_setup import get_logger

logger = get_logger(__name__)


class DataCleaner:
    """Applies the original cleaning steps to loaded DataFrames."""

    def __init__(self, iqr_multiplier: float = 1.5):
        """Create a data cleaner.

        Args:
            iqr_multiplier: IQR multiplier used for outlier detection.
        """
        self.iqr_multiplier = float(iqr_multiplier)

    def clean(self, df: pd.DataFrame) -> pd.DataFrame:
        """Clean and preprocess a DataFrame.

        Preserves the original behavior: remove duplicates, fill numeric
        missing values with the column median, fill text missing values with
        ``"Unknown"``, remove per-column IQR outliers, standardize text with
        strip/lower, then add ``quality_score`` and ``processed_timestamp``.

        Args:
            df: Input DataFrame.

        Returns:
            The cleaned DataFrame (the input is returned on failure).
        """
        try:
            logger.info("Starting data cleaning process")
            original_rows = len(df)

            df = df.drop_duplicates()

            numeric_columns = df.select_dtypes(include=[np.number]).columns
            for col in numeric_columns:
                df[col] = df[col].fillna(df[col].median())

            text_columns = df.select_dtypes(include=["object"]).columns
            for col in text_columns:
                df[col] = df[col].fillna("Unknown")

            for col in numeric_columns:
                q1 = df[col].quantile(0.25)
                q3 = df[col].quantile(0.75)
                iqr = q3 - q1
                lower_bound = q1 - self.iqr_multiplier * iqr
                upper_bound = q3 + self.iqr_multiplier * iqr
                df = df[(df[col] >= lower_bound) & (df[col] <= upper_bound)]

            for col in text_columns:
                df[col] = df[col].str.strip().str.lower()

            df["quality_score"] = np.random.uniform(0.7, 1.0, len(df))
            df["processed_timestamp"] = datetime.now()

            logger.info("Data cleaning complete: %d -> %d rows", original_rows, len(df))
            return df
        except Exception as exc:  # noqa: BLE001 - cleaning failures are logged
            logger.error("Data cleaning failed: %s", exc)
            return df


def clean_data(df: pd.DataFrame, iqr_multiplier: Optional[float] = None) -> pd.DataFrame:
    """Clean and preprocess a DataFrame.

    Convenience function wrapping :class:`DataCleaner`.

    Args:
        df: Input DataFrame.
        iqr_multiplier: Optional IQR multiplier override (default 1.5).

    Returns:
        The cleaned DataFrame (the input is returned on failure).
    """
    if iqr_multiplier is None:
        return DataCleaner().clean(df)
    return DataCleaner(iqr_multiplier=iqr_multiplier).clean(df)
