"""Feature engineering: categorical encoding and aggregate features."""

from __future__ import annotations

from typing import Optional

import pandas as pd

from utils.logging_setup import get_logger

logger = get_logger(__name__)


class FeatureEngineer:
    """Adds engineered features: categorical encoding and aggregates."""

    def __init__(self, max_categorical_columns: int = 10, max_categories: int = 25):
        """Create a feature engineer.

        Args:
            max_categorical_columns: Maximum number of categorical columns to
                one-hot encode in a single pass.
            max_categories: Maximum distinct categories per column to encode;
                columns exceeding this are skipped to avoid feature explosion.
        """
        self.max_categorical_columns = int(max_categorical_columns)
        self.max_categories = int(max_categories)

    def encode_categorical(self, frame: pd.DataFrame, columns: Optional[list] = None) -> pd.DataFrame:
        """One-hot encode categorical columns.

        Args:
            frame: Input DataFrame.
            columns: Optional explicit list of columns to encode. When
                ``None``, low-cardinality object columns are selected
                automatically.

        Returns:
            DataFrame with encoded columns replacing the originals.
        """
        result = frame.copy()
        if columns is None:
            object_columns = list(result.select_dtypes(include=["object"]).columns)
            columns = [
                column
                for column in object_columns
                if column != "processed_timestamp"
                and result[column].nunique() <= self.max_categories
            ][: self.max_categorical_columns]
        if not columns:
            return result
        encoded = pd.get_dummies(result[columns].astype(str), prefix=columns, dtype=int)
        result = result.drop(columns=columns)
        result = pd.concat([result, encoded], axis=1)
        logger.info("One-hot encoded %d categorical column(s)", len(columns))
        return result

    def add_aggregate_features(self, frame: pd.DataFrame, group_column: Optional[str] = None) -> pd.DataFrame:
        """Add aggregate features over numeric columns.

        Args:
            frame: Input DataFrame.
            group_column: Optional column to group by before aggregating.

        Returns:
            DataFrame including the new aggregate feature columns.
        """
        result = frame.copy()
        numeric = result.select_dtypes(include="number")
        if group_column is not None and group_column in result.columns and not numeric.empty:
            grouped = numeric.groupby(result[group_column]).agg(["sum", "mean"])
            grouped.columns = [f"{col}_{stat}_by_{group_column}" for col, stat in grouped.columns]
            result = result.merge(grouped.reset_index(), on=group_column, how="left")
            logger.info("Added %d group aggregate feature(s)", grouped.shape[1])
        elif not numeric.empty:
            result["feature_sum"] = numeric.sum(axis=1)
            result["feature_mean"] = numeric.mean(axis=1)
            result["feature_std"] = numeric.std(axis=1)
            logger.info("Added 3 row aggregate feature(s)")
        return result


def engineer_features(frame: pd.DataFrame, group_column: Optional[str] = None) -> pd.DataFrame:
    """Add aggregate features to a DataFrame.

    Convenience function wrapping :class:`FeatureEngineer`.

    Args:
        frame: Input DataFrame.
        group_column: Optional column to group by before aggregating.

    Returns:
        DataFrame including the new aggregate feature columns.
    """
    return FeatureEngineer().add_aggregate_features(frame, group_column=group_column)
