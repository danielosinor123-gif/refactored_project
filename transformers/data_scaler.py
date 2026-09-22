"""Data scaling: standard scaling, min-max normalization, and encoding."""

from __future__ import annotations

import numpy as np
import pandas as pd

from utils.logging_setup import get_logger

logger = get_logger(__name__)


class DataScaler:
    """Applies the original transformation types to numeric columns."""

    def transform(self, df: pd.DataFrame, transformation_type: str = "standard") -> pd.DataFrame:
        """Apply a data transformation to a DataFrame.

        Preserves the original behavior: ``standard`` adds
        ``{col}_standardized`` columns (skipping ``quality_score``),
        ``normalize`` adds ``{col}_normalized`` columns, ``categorical`` adds
        ``{col}_encoded`` columns via category codes (skipping
        ``processed_timestamp``). Afterwards adds ``feature_sum``,
        ``feature_mean``, and ``feature_std`` aggregate columns.

        Args:
            df: Input DataFrame.
            transformation_type: One of ``"standard"``, ``"normalize"``, or
                ``"categorical"``. Defaults to ``"standard"``.

        Returns:
            The transformed DataFrame (the input is returned on failure).
        """
        try:
            logger.info("Applying %s transformation", transformation_type)

            if transformation_type == "standard":
                numeric_columns = df.select_dtypes(include=[np.number]).columns
                for col in numeric_columns:
                    if col not in ["quality_score"]:
                        mean_val = df[col].mean()
                        std_val = df[col].std()
                        if std_val != 0:
                            df[f"{col}_standardized"] = (df[col] - mean_val) / std_val

            elif transformation_type == "normalize":
                numeric_columns = df.select_dtypes(include=[np.number]).columns
                for col in numeric_columns:
                    if col not in ["quality_score"]:
                        min_val = df[col].min()
                        max_val = df[col].max()
                        if max_val != min_val:
                            df[f"{col}_normalized"] = (df[col] - min_val) / (max_val - min_val)

            elif transformation_type == "categorical":
                text_columns = df.select_dtypes(include=["object"]).columns
                for col in text_columns:
                    if col not in ["processed_timestamp"]:
                        df[f"{col}_encoded"] = pd.Categorical(df[col]).codes

            numeric_columns = df.select_dtypes(include=[np.number]).columns
            if len(numeric_columns) > 1:
                df["feature_sum"] = df[numeric_columns].sum(axis=1)
                df["feature_mean"] = df[numeric_columns].mean(axis=1)
                df["feature_std"] = df[numeric_columns].std(axis=1)

            logger.info("Transformation complete: %d columns", len(df.columns))
            return df
        except Exception as exc:  # noqa: BLE001 - transformation failures are logged
            logger.error("Data transformation failed: %s", exc)
            return df


def transform_data(df: pd.DataFrame, transformation_type: str = "standard") -> pd.DataFrame:
    """Apply a data transformation to a DataFrame.

    Convenience function wrapping :class:`DataScaler`.

    Args:
        df: Input DataFrame.
        transformation_type: ``"standard"``, ``"normalize"``, or
            ``"categorical"``. Defaults to ``"standard"``.

    Returns:
        The transformed DataFrame (the input is returned on failure).
    """
    return DataScaler().transform(df, transformation_type)
