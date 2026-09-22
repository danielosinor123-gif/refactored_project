"""Data processing pipeline orchestrator.

Refactored from the original monolithic DataProcessor: configuration,
logging, database access, file loading, transformations, statistics,
exports, reports, email, backups, and cleanup are delegated to the
dedicated packages while preserving the original public behavior.
"""

from __future__ import annotations

import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
import requests

from config import get_config, load_config_from_file
from database import DatabaseConnection
from file_handlers import load_csv_file, load_json_file, validate_file
from reports import EmailSender, ReportGenerator, generate_html_report as build_html_report
from transformers import clean_data, transform_data
from utils import BackupManager, calculate_file_hash, setup_logging
from utils.logging_setup import get_logger
from visualizations import generate_visualizations as build_visualizations

logger = get_logger(__name__)

DEFAULT_CONFIG_FILE = "config/settings.ini"


class DataProcessor:
    """Orchestrates the full data processing workflow.

    Every responsibility is delegated to the dedicated packages; this class
    keeps the original public method names and behavior.
    """

    def __init__(self, config_file: Optional[str] = None):
        """Create a processor, initialize logging, and set up the database.

        Args:
            config_file: Optional INI file to load configuration overrides
                from after applying the defaults.
        """
        self.config: Dict[str, Any] = get_config()
        if config_file:
            self.config = load_config_from_file(self.config, config_file)

        setup_logging(
            log_directory=Path("logs"),
            level="INFO",
            log_file_name=Path(self.config["log_file"]).name,
        )

        self.db_connection = DatabaseConnection(self.config["database_path"])
        self.setup_database()

        self.raw_data: List[pd.DataFrame] = []
        self.processed_data: List[pd.DataFrame] = []
        self.summary_stats: Dict[str, Any] = {}
        self.reports_generated: List[str] = []

        self.backup_manager = BackupManager(backup_enabled=self.config["backup_enabled"])
        self.email_sender = EmailSender(
            email_server=self.config["email_server"],
            email_port=self.config["email_port"],
            email_user=self.config["email_user"],
            email_password=self.config["email_password"],
        )
        self.report_generator = ReportGenerator(
            db=self.db_connection,
            report_directory=self.config["reports_directory"],
            email_sender=self.email_sender,
        )

    def setup_database(self) -> None:
        """Initialize the database connection and create tables if needed."""
        try:
            self.db_connection.initialize()
            logger.info("Database initialized successfully")
        except Exception as exc:  # noqa: BLE001 - setup failures are logged
            logger.error("Database setup failed: %s", exc)
            raise

    def load_config_from_file(self, config_file: str) -> None:
        """Load configuration overrides from an INI file.

        Args:
            config_file: Path to the INI configuration file.
        """
        self.config = load_config_from_file(self.config, config_file)
        logger.info("Configuration loaded from %s", config_file)

    def validate_file(self, file_path: str | Path) -> bool:
        """Validate an input file.

        Args:
            file_path: Path to the file to validate.

        Returns:
            ``True`` when the file passes all checks, otherwise ``False``.
        """
        return validate_file(file_path, self.config["max_file_size"])

    def calculate_file_hash(self, file_path: str | Path) -> str:
        """Calculate the MD5 hash of a file.

        Args:
            file_path: Path to the file to hash.

        Returns:
            Hex digest string, or an empty string when hashing fails.
        """
        return calculate_file_hash(file_path)

    def load_csv_file(self, file_path: str | Path) -> Optional[pd.DataFrame]:
        """Load a CSV file with validation and database logging.

        Args:
            file_path: Path to the CSV file.

        Returns:
            The loaded DataFrame, or ``None`` on failure.
        """
        frame = load_csv_file(file_path, db=self.db_connection,
                              chunk_size=self.config["chunk_size"],
                              max_file_size=self.config["max_file_size"])
        if frame is not None:
            self.raw_data.append(frame)
        return frame

    def load_json_file(self, file_path: str | Path) -> Optional[pd.DataFrame]:
        """Load a JSON file with validation and database logging.

        Args:
            file_path: Path to the JSON file.

        Returns:
            The loaded DataFrame, or ``None`` on failure.
        """
        frame = load_json_file(file_path, db=self.db_connection,
                               max_file_size=self.config["max_file_size"])
        if frame is not None:
            self.raw_data.append(frame)
        return frame

    def fetch_data_from_api(self, endpoint: str, params: Optional[dict] = None) -> Optional[pd.DataFrame]:
        """Fetch data from the configured API endpoint.

        Args:
            endpoint: Endpoint path appended to the configured base URL.
            params: Optional query parameters.

        Returns:
            The fetched DataFrame, or ``None`` on failure.
        """
        try:
            logger.info("Fetching data from API: %s", endpoint)
            headers = {
                "Authorization": f"Bearer {self.config['api_key']}",
                "Content-Type": "application/json",
            }
            url = f"{self.config['api_base_url']}/{endpoint}"
            response = requests.get(url, headers=headers, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()

            if isinstance(data, dict) and "data" in data:
                df = pd.DataFrame(data["data"])
            elif isinstance(data, list):
                df = pd.DataFrame(data)
            else:
                df = pd.DataFrame([data])
            logger.info("Successfully fetched %d records from API", len(df))
            return df
        except Exception as exc:  # noqa: BLE001 - API failures are logged
            logger.error("API fetch failed: %s", exc)
            return None

    def clean_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """Clean and preprocess data.

        Args:
            df: Input DataFrame.

        Returns:
            The cleaned DataFrame.
        """
        return clean_data(df)

    def transform_data(self, df: pd.DataFrame, transformation_type: str = "standard") -> pd.DataFrame:
        """Apply a data transformation.

        Args:
            df: Input DataFrame.
            transformation_type: ``"standard"``, ``"normalize"``, or
                ``"categorical"``.

        Returns:
            The transformed DataFrame.
        """
        return transform_data(df, transformation_type)

    def calculate_statistics(self, df: pd.DataFrame) -> dict:
        """Calculate summary statistics over the processed data.

        Preserves the original metrics: row/column counts, memory usage,
        per-column numeric and categorical statistics, overall quality
        score, and completeness ratio.

        Args:
            df: Processed DataFrame.

        Returns:
            Dictionary of statistic names to values.
        """
        try:
            logger.info("Calculating summary statistics")
            stats: Dict[str, Any] = {}
            stats["total_rows"] = len(df)
            stats["total_columns"] = len(df.columns)
            stats["memory_usage"] = df.memory_usage(deep=True).sum()

            numeric_columns = df.select_dtypes(include=[np.number]).columns
            for col in numeric_columns:
                stats[f"{col}_mean"] = df[col].mean()
                stats[f"{col}_median"] = df[col].median()
                stats[f"{col}_std"] = df[col].std()
                stats[f"{col}_min"] = df[col].min()
                stats[f"{col}_max"] = df[col].max()
                stats[f"{col}_null_count"] = df[col].isnull().sum()

            text_columns = df.select_dtypes(include=["object"]).columns
            for col in text_columns:
                stats[f"{col}_unique_count"] = df[col].nunique()
                stats[f"{col}_most_common"] = (
                    df[col].mode().iloc[0] if not df[col].mode().empty else "N/A"
                )
                stats[f"{col}_null_count"] = df[col].isnull().sum()

            stats["overall_quality_score"] = df.get("quality_score", pd.Series([0])).mean()
            stats["completeness_ratio"] = 1 - (df.isnull().sum().sum() / (len(df) * len(df.columns)))

            self.summary_stats = stats
            logger.info("Statistics calculation complete")
            return stats
        except Exception as exc:  # noqa: BLE001 - statistics failures are logged
            logger.error("Statistics calculation failed: %s", exc)
            return {}

    def generate_visualizations(self, df: pd.DataFrame, output_dir: str | Path) -> None:
        """Generate data visualizations.

        Args:
            df: Processed DataFrame.
            output_dir: Directory where chart images are saved.
        """
        build_visualizations(df, output_dir)

    def export_data(self, df: pd.DataFrame, output_path: str | Path, format_type: str = "csv") -> None:
        """Export processed data to a file.

        Args:
            df: Processed DataFrame.
            output_path: Destination file path.
            format_type: One of ``"csv"``, ``"json"``, ``"xlsx"``, or
                ``"parquet"``.

        Raises:
            ValueError: When the export format is unsupported.
        """
        try:
            logger.info("Exporting data to %s as %s", output_path, format_type)
            os.makedirs(os.path.dirname(output_path), exist_ok=True)

            if format_type.lower() == "csv":
                df.to_csv(output_path, index=False)
            elif format_type.lower() == "json":
                df.to_json(output_path, orient="records", indent=2)
            elif format_type.lower() == "xlsx":
                df.to_excel(output_path, index=False)
            elif format_type.lower() == "parquet":
                df.to_parquet(output_path, index=False)
            else:
                raise ValueError(f"Unsupported export format: {format_type}")
            logger.info("Data exported successfully to %s", output_path)
        except Exception as exc:  # noqa: BLE001 - export failures are logged
            logger.error("Data export failed: %s", exc)

    def generate_report(self, report_type: str = "summary") -> Optional[str]:
        """Generate a report of the given type and log it to the database.

        Args:
            report_type: ``"summary"`` or ``"detailed"``.

        Returns:
            Path of the generated report, or ``None`` on failure.
        """
        path = self.report_generator.generate_report(report_type, self.summary_stats)
        if path is not None:
            self.reports_generated.append(str(path))
            self.db_connection.log_processed(
                None, "report", str(path), self.summary_stats.get("overall_quality_score")
            )
        return str(path) if path else None

    def generate_html_report(self) -> str:
        """Generate the HTML report content from the summary statistics.

        Returns:
            A full HTML document string.
        """
        return build_html_report(self.summary_stats)

    def send_email_report(self, report_path: str | Path, recipient_email: str) -> bool:
        """Send a report via email.

        Args:
            report_path: Path to the report file to attach.
            recipient_email: To address.

        Returns:
            ``True`` when sending succeeded, ``False`` otherwise.
        """
        sent = self.email_sender.send_email_report(report_path, recipient_email)
        if sent:
            self.db_connection.log_report(
                "emailed", str(report_path), status="sent", recipient_email=recipient_email
            )
        return sent

    def backup_data(self) -> None:
        """Create a backup of the database, output, and reports."""
        self.backup_manager.create_backup(
            self.config["database_path"],
            self.config["output_directory"],
            self.config["reports_directory"],
        )

    def cleanup_old_files(self, days_old: int = 30) -> None:
        """Clean up old files in the output and reports directories.

        Args:
            days_old: Age threshold in days.
        """
        self.backup_manager.cleanup_old_files(
            days_old, [self.config["output_directory"], self.config["reports_directory"]]
        )

    def process_directory(self, input_directory: str | Path) -> Optional[pd.DataFrame]:
        """Process all files in a directory: the main orchestration method.

        Loads each CSV/JSON file, cleans and transforms the data, exports
        per-file outputs, then combines everything and calculates
        statistics, visualizations, reports, a backup, and cleanup.

        Args:
            input_directory: Directory containing the input files.

        Returns:
            The combined processed DataFrame, or ``None`` on failure.
        """
        try:
            logger.info("Processing directory: %s", input_directory)
            all_processed_data: List[pd.DataFrame] = []

            for file_path in Path(input_directory).glob("*"):
                if not file_path.is_file():
                    continue
                logger.info("Processing file: %s", file_path)

                if file_path.suffix.lower() == ".csv":
                    df = self.load_csv_file(str(file_path))
                elif file_path.suffix.lower() == ".json":
                    df = self.load_json_file(str(file_path))
                else:
                    logger.warning("Unsupported file type: %s", file_path)
                    continue

                if df is not None:
                    df = self.clean_data(df)
                    df = self.transform_data(df)
                    all_processed_data.append(df)
                    output_path = f"{self.config['output_directory']}/processed_{file_path.stem}.csv"
                    self.export_data(df, output_path)
                    self.db_connection.log_processed(
                        None, "standard", output_path,
                        float(df.get("quality_score", pd.Series([0])).mean()),
                    )

            if not all_processed_data:
                return None

            combined_df = pd.concat(all_processed_data, ignore_index=True)
            self.calculate_statistics(combined_df)

            viz_dir = f"{self.config['output_directory']}/visualizations"
            self.generate_visualizations(combined_df, viz_dir)

            self.generate_report("summary")
            self.generate_report("detailed")
            self.backup_data()
            self.cleanup_old_files()

            logger.info("Directory processing completed successfully")
            return combined_df
        except Exception as exc:  # noqa: BLE001 - orchestration failures are logged
            logger.error("Directory processing failed: %s", exc)
            return None

    def __del__(self):
        """Cleanup database connection."""
        if self.db_connection:
            self.db_connection.close()


def main() -> None:
    """Main function to run the data processor."""
    try:
        processor = DataProcessor()

        config_file = DEFAULT_CONFIG_FILE
        if os.path.exists(config_file):
            processor.load_config_from_file(config_file)

        result = processor.process_directory(processor.config["input_directory"])

        if result is not None:
            print(f"Processing completed. {len(result)} total rows processed.")
            print(f"Reports generated: {len(processor.reports_generated)}")
        else:
            print("Processing failed.")
    except Exception as exc:  # noqa: BLE001 - top-level guard reports all failures
        print(f"Application failed: {exc}")


if __name__ == "__main__":
    sys.exit(main())
