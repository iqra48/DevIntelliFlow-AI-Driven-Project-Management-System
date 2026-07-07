import logging
import json
from datetime import datetime
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class StructuredJSONFormatter(logging.Formatter):
    """
    Custom formatter that outputs structured JSON logs.
    
    Converts log records to JSON with:
    - timestamp
    - level
    - message
    - extra (custom structured data)
    """
    
    def format(self, record: logging.LogRecord) -> str:
        log_obj = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "message": record.getMessage(),
        }
        
        # Extract extra fields (custom structured data)
        if hasattr(record, "extra_data") and record.extra_data:
            log_obj.update(record.extra_data)
        
        return json.dumps(log_obj, default=str)


def configure_structured_logging(log_level: str = "INFO"):
    """
    Configure logger with JSON formatting.
    
    Args:
        log_level: Logging level (INFO, DEBUG, ERROR, etc.)
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    
    # Console handler with JSON formatter
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    console_handler.setFormatter(StructuredJSONFormatter())
    
    root_logger.addHandler(console_handler)


def log_structured(
    event_type: str,
    message: str,
    level: str = "INFO",
    **kwargs
):
    """
    Log a structured event as JSON.
    
    Args:
        event_type: Type of event (e.g., "classification_decision", "abstention")
        message: Human-readable message
        level: Log level (INFO, WARNING, ERROR, DEBUG)
        **kwargs: Additional structured data to include in JSON
    """
    log_level = getattr(logging, level.upper(), logging.INFO)
    
    # Create log record
    log_record = logging.LogRecord(
        name=__name__,
        level=log_level,
        pathname="",
        lineno=0,
        msg=message,
        args=(),
        exc_info=None
    )
    
    # Attach structured data
    structured_data = {
        "event_type": event_type,
        **kwargs
    }
    log_record.extra_data = structured_data
    
    # Emit
    logger.handle(log_record)


def log_llm_failure(error):
    logger.exception(
        f"LLM execution failure [{type(error).__name__}]: {error}"
    )


class ClassificationEventLogger:
    """
    Dedicated logger for Module 2 classification events.
    Ensures consistent structured logging across pipeline.
    """
    
    @staticmethod
    def log_input_validation(requirement_id: str, text_length: int, status: str, reason: Optional[str] = None):
        """Log input validation step result."""
        log_structured(
            event_type="input_validation",
            message=f"Input validation: {status}",
            level="INFO" if status != "ABSTAIN" else "WARNING",
            requirement_id=requirement_id,
            text_length=text_length,
            status=status,
            reason=reason
        )
    
    @staticmethod
    def log_decomposition(requirement_id: str, num_units: int, status: str, reason: Optional[str] = None):
        """Log semantic decomposition result."""
        log_structured(
            event_type="semantic_decomposition",
            message=f"Decomposition: {num_units} units, {status}",
            level="INFO" if status != "ABSTAIN" else "WARNING",
            requirement_id=requirement_id,
            num_units=num_units,
            status=status,
            reason=reason
        )
    
    @staticmethod
    def log_cohesion_verification(requirement_id: str, status: str, reason: Optional[str] = None):
        """Log cohesion verification result."""
        log_structured(
            event_type="cohesion_verification",
            message=f"Cohesion check: {status}",
            level="INFO" if status != "ABSTAIN" else "WARNING",
            requirement_id=requirement_id,
            status=status,
            reason=reason
        )
    
    @staticmethod
    def log_unit_classifications(requirement_id: str, unit_results: list):
        """Log all unit-level classification results."""
        units_summary = []
        for r in unit_results:
            units_summary.append({
                "unit_id": r.requirement_id,
                "behavior_detected": r.behavior_detected,
                "quality_detected": r.quality_detected,
                "classification": r.classification
            })
        
        log_structured(
            event_type="unit_classifications",
            message=f"Unit-level classification: {len(unit_results)} units processed",
            level="INFO",
            requirement_id=requirement_id,
            units=units_summary
        )
    
    @staticmethod
    def log_aggregation_decision(
        requirement_id: str,
        classification: str,
        has_behavior: bool,
        has_quality: bool,
        basis: str
    ):
        """Log deterministic aggregation decision."""
        log_structured(
            event_type="aggregation_decision",
            message=f"Aggregation: {classification}",
            level="INFO",
            requirement_id=requirement_id,
            classification=classification,
            has_behavior=has_behavior,
            has_quality=has_quality,
            basis=basis
        )
    
    @staticmethod
    def log_mixed_split(requirement_id: str, status: str, fr_text: Optional[str] = None, nfr_text: Optional[str] = None, reason: Optional[str] = None):
        """Log mixed requirement split result."""
        log_structured(
            event_type="mixed_split",
            message=f"Mixed split: {status}",
            level="INFO" if status != "ABSTAIN" else "WARNING",
            requirement_id=requirement_id,
            status=status,
            fr_text=fr_text[:100] if fr_text else None,  # Truncate for logging
            nfr_text=nfr_text[:100] if nfr_text else None,
            reason=reason
        )
    
    @staticmethod
    def log_final_classification(
        requirement_id: str,
        classification: str,
        decision_path: list,
        audit_present: bool = False
    ):
        """Log final classification result (SUCCESS)."""
        log_structured(
            event_type="final_classification",
            message=f"Classification complete: {classification}",
            level="INFO",
            requirement_id=requirement_id,
            classification=classification,
            decision_path=decision_path,
            audit_present=audit_present
        )
    
    @staticmethod
    def log_abstention(
        requirement_id: str,
        step: str,
        reason: str
    ):
        """Log abstention decision."""
        log_structured(
            event_type="abstention",
            message=f"ABSTAIN at step {step}: {reason}",
            level="WARNING",
            requirement_id=requirement_id,
            step=step,
            reason=reason
        )
