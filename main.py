"""Data processing pipeline orchestrator.

Loads configuration, initializes logging and the database, processes files
from the configured input directory, cleans and transforms the data, exports
results, generates statistics, visualizations, and reports, then creates
backups and cleans up old files.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import List, Optional

import pandas as pd

from config import AppConfig, load_config
from database import DatabaseConnection
from file_handlers import CSVProcessor, ExcelProcessor, JSONProcessor
from reports import EmailSender, ReportGenerator
from transformers import DataCleaner, DataScaler, FeatureEngineer
from utils import BackupManager, FileValidator, setup_logging
from utils.logging_setup import get_logger
from visualizations import ChartGenerator

logger = get_logger(__name__)

EXIT_SUCCESS = 0
EXIT_FAILURE = 1


class DataProcessor:
    """Orchestrates the full data processing workflow."""

    def __init__(self, config: AppConfig):
        """Create a processor from configuration.

        Args:
            config: Fully resolved application configuration.
        """
        self.config = config
        self.validator = FileValidator(
            max_file_size_mb=config.max_file_size_mb,
            supported_extensions=config.supported_extensions,
        )
        self.db = DatabaseConnection(config.database_path)
        self.cleaner = DataCleaner()
        self.scaler = DataScaler()
        self.feature_engineer = FeatureEngineer()
        self.backup_manager = BackupManager(
            backup_directory=config.backup_directory,
            retention_days=config.backup_retention_days,
        )
        self.email_sender = self._build_email_sender()
        self.report_generator = ReportGenerator(
            db=self.db,
            report_directory=config.report_directory,
            email_sender=self.email_sender if config.email_enabled else None,
        )
        self.chart_generator = ChartGenerator(output_directory=config.output_directory)

    def _build_email_sender(self) -> Optional[EmailSender]:
        """Build the email sender when email is enabled in configuration."""
        if not self.config.email_enabled or not self.config.email_recipients:
            return None
        return EmailSender(
            smtp_server=self.config.smtp_server,
            smtp_port=self.config.smtp_port,
            sender=self.config.email_sender,
            recipients=self.config.email_recipients,
            username=self.config.smtp_username,
            password=self.config.smtp_password,
            use_tls=self.config.smtp_use_tls,
        )

    def select_handler(self, file_path: Path):
        """Select the correct file handler based on the file extension.

        Args:
            file_path: Path of the file to process.

        Returns:
            A handler with a ``load`` method, or ``None`` when unsupported.
        """
        csv_processor = CSVProcessor(self.validator, self.db, self.config.chunk_size)
        if csv_processor.can_handle(file_path):
            return csv_processor
        json_processor = JSONProcessor(self.validator, self.db)
        if json_processor.can_handle(file_path):
            return json_processor
        excel_processor = ExcelProcessor(self.validator, self.db)
        if excel_processor.can_handle(file_path):
            return excel_processor
        return None

    def process_file(self, file_path: Path) -> Optional[pd.DataFrame]:
        """Load, clean, and transform a single input file.

        Args:
            file_path: Path of the file to process.

        Returns:
            The processed DataFrame, or ``None`` when the file was skipped.
        """
        handler = self.select_handler(file_path)
        if handler is None:
            logger.warning("No handler available for %s; skipping", file_path.name)
            return None
        frame = handler.load(file_path)
        if frame is None:
            return None
        frame = self.cleaner.clean(frame)
        frame = self.feature_engineer.encode_categorical(frame)
        return frame

    def transform_data(self, frame: pd.DataFrame, transformation_type: str) -> pd.DataFrame:
        """Apply a numeric transformation to the processed data.

        Args:
            frame: Processed DataFrame.
            transformation_type: ``"standard"``, ``"normalize"``, or ``"none"``.

        Returns:
            The transformed DataFrame.
        """
        if transformation_type == "none":
            return frame
        return self.scaler.apply(frame, transformation_type)

    def export_processed_data(self, frame: pd.DataFrame, file_name: str = "processed_data.csv") -> Optional[Path]:
        """Export processed data to CSV and log it to the database.

        Args:
            frame: Processed DataFrame to export.
            file_name: Destination CSV file name in the output directory.

        Returns:
            Path of the exported file, or ``None`` on failure.
        """
        output_path = self.config.output_directory / file_name
        try:
            self.config.output_directory.mkdir(parents=True, exist_ok=True)
            frame.to_csv(output_path, index=False, encoding="utf-8")
        except OSError as exc:
            logger.error("Failed to export processed data to %s: %s", output_path, exc)
            return None
        payload_json = frame.to_json(orient="records", date_format="iso")
        self.db.insert_processed_data(file_name, len(frame), self.cleaner.compute_quality_score(frame), payload_json)
        self.db.insert_audit_log("export", f"Exported {len(frame)} rows to {output_path.name}")
        logger.info("Exported %d rows to %s", len(frame), output_path)
        return output_path

    def calculate_statistics(self, frame: pd.DataFrame, files_processed: int) -> dict:
        """Calculate summary statistics over the processed data.

        Args:
            frame: Processed DataFrame.
            files_processed: Number of files successfully processed.

        Returns:
            Dictionary of statistic names to values.
        """
        statistics = {
            "records_processed": len(frame),
            "files_processed": files_processed,
            "column_count": frame.shape[1],
            "quality_score": self.cleaner.compute_quality_score(frame),
        }
        numeric = frame.select_dtypes(include="number")
        if not numeric.empty:
            statistics["numeric_columns"] = len(numeric.columns)
            statistics["mean_of_means"] = round(float(numeric.mean().mean()), 4)
        return statistics

    def run(self, transformation_type: str = "standard") -> bool:
        """Execute the complete data processing workflow.

        Args:
            transformation_type: Numeric transformation to apply:
                ``"standard"``, ``"normalize"``, or ``"none"``.

        Returns:
            ``True`` when the run completed successfully, ``False`` when it
            failed at any stage.
        """
        logger.info("Starting data processing run (transformation=%s)", transformation_type)
        self.db.initialize()

        input_files = self.validator.find_files(self.config.input_directory)
        if not input_files:
            logger.warning("No valid input files found in %s", self.config.input_directory)
            self.db.insert_audit_log("run_skipped", "No valid input files found")
            print("Data processing failed: no valid input files found.")
            return False

        processed_frames: List[pd.DataFrame] = []
        for file_path in input_files:
            logger.info("Processing file: %s", file_path.name)
            frame = self.process_file(file_path)
            if frame is not None:
                processed_frames.append(frame)

        if not processed_frames:
            logger.error("No data could be processed from the input files")
            self.db.insert_audit_log("run_failed", "No data could be processed")
            print("Data processing failed: no data could be processed.")
            return False

        combined = pd.concat(processed_frames, ignore_index=True)
        combined = self.transform_data(combined, transformation_type)

        if self.export_processed_data(combined) is None:
            print("Data processing failed: could not export processed data.")
            return False

        statistics = self.calculate_statistics(combined, len(processed_frames))

        charts = self.chart_generator.generate_visualizations(combined)
        logger.info("Generated %d chart(s)", len(charts))

        summary_path = self.report_generator.generate_summary_report(
            statistics, send_email=self.config.email_enabled
        )
        detailed_path = self.report_generator.generate_detailed_report(
            combined, statistics, send_email=self.config.email_enabled
        )
        logger.info("Generated reports: %s, %s", summary_path, detailed_path)

        if self.config.backup_enabled:
            self.backup_manager.backup_database(self.config.database_path)
            self.backup_manager.backup_output(self.config.output_directory)
            self.backup_manager.backup_reports(self.config.report_directory)

        if self.config.cleanup_enabled:
            self.backup_manager.cleanup_old_files(self.config.backup_directory)
            self.backup_manager.cleanup_old_files(
                self.config.output_directory, self.config.file_retention_days
            )
            self.backup_manager.cleanup_old_files(
                self.config.report_directory, self.config.file_retention_days
            )

        self.db.insert_audit_log("run_completed", f"Processed {len(processed_frames)} file(s)")
        print("Data processing completed successfully.")
        return True


def main(argv: Optional[List[str]] = None) -> int:
    """Application entry point.

    Args:
        argv: Optional command-line arguments (currently unused).

    Returns:
        Process exit code: 0 on success, 1 on failure.
    """
    try:
        config = load_config()
        setup_logging(
            log_directory=config.log_directory,
            level=config.log_level,
            log_file_name=config.log_file_name,
        )
        processor = DataProcessor(config)
        success = processor.run()
        return EXIT_SUCCESS if success else EXIT_FAILURE
    except Exception as exc:  # noqa: BLE001 - top-level guard reports all failures
        logger.exception("Data processing failed with an unexpected error: %s", exc)
        print(f"Data processing failed: {exc}")
        return EXIT_FAILURE


if __name__ == "__main__":
    sys.exit(main())
