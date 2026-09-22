"""Data scaling: standard scaling and min-max normalization."""

from __future__ import annotations

import pandas as pd

from utils.logging_setup import get_logger

logger = get_logger(__name__)


class DataScaler:
    """Applies standard scaling or min-max normalization to numeric columns."""

    def apply(self, frame: pd.DataFrame, transformation: str) -> pd.DataFrame:
        """Apply a named transformation to the numeric columns of a DataFrame.

        Args:
            frame: Input DataFrame.
            transformation: One of ``"standard"`` (zero mean, unit variance)
                or ``"normalize"`` (min-max scaled to [0, 1]).

        Returns:
            DataFrame with transformed numeric columns.

        Raises:
            ValueError: When the transformation name is unknown.
        """
        transformation = transformation.lower()
        if transformation == "standard":
            return self.standard_scale(frame)
        if transformation == "normalize":
            return self.minmax_normalize(frame)
        raise ValueError(f"Unknown transformation: {transformation!r}")

    def standard_scale(self, frame: pd.DataFrame) -> pd.DataFrame:
        """Standard-scale numeric columns to zero mean and unit variance.

        Args:
            frame: Input DataFrame.

        Returns:
            DataFrame with standard-scaled numeric columns.
        """
        result = frame.copy()
        numeric_columns = result.select_dtypes(include="number").columns
        if numeric_columns.empty:
            return result
        for column in numeric_columns:
            std = result[column].std()
            if pd.isna(std) or std == 0:
                result[column] = 0.0
            else:
                result[column] = (result[column] - result[column].mean()) / std
        logger.info("Standard-scaled %d numeric column(s)", len(numeric_columns))
        return result

    def minmax_normalize(self, frame: pd.DataFrame) -> pd.DataFrame:
        """Min-max normalize numeric columns into the [0, 1] range.

        Args:
            frame: Input DataFrame.

        Returns:
            DataFrame with min-max normalized numeric columns.
        """
        result = frame.copy()
        numeric_columns = result.select_dtypes(include="number").columns
        if numeric_columns.empty:
            return result
        for column in numeric_columns:
            minimum = result[column].min()
            maximum = result[column].max()
            span = maximum - minimum
            if pd.isna(span) or span == 0:
                result[column] = 0.0
            else:
                result[column] = (result[column] - minimum) / span
        logger.info("Min-max normalized %d numeric column(s)", len(numeric_columns))
        return result
