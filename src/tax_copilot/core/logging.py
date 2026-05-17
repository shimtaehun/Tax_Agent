import logging
import re
import sys
from contextvars import ContextVar

import structlog

request_id_var: ContextVar[str] = ContextVar("request_id", default="-")

_PII_PATTERNS = [
    (re.compile(r"\b\d{3}-\d{2}-\d{5}\b"), "***-**-*****"),  # 사업자등록번호
    (re.compile(r"\b\d{4}-\d{4}-\d{4}-\d{4}\b"), "****-****-****-****"),  # 카드번호
]


def _mask_pii(event: str) -> str:
    for pattern, replacement in _PII_PATTERNS:
        event = pattern.sub(replacement, event)
    return event


def _add_request_id(
    logger: logging.Logger,
    method: str,
    event_dict: structlog.types.EventDict,
) -> structlog.types.EventDict:
    event_dict["request_id"] = request_id_var.get()
    return event_dict


def _mask_pii_processor(
    logger: logging.Logger,
    method: str,
    event_dict: structlog.types.EventDict,
) -> structlog.types.EventDict:
    if "event" in event_dict and isinstance(event_dict["event"], str):
        event_dict["event"] = _mask_pii(event_dict["event"])
    return event_dict


def configure_logging(json_logs: bool = True) -> None:
    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        _add_request_id,
        _mask_pii_processor,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
    ]

    if json_logs:
        renderer: structlog.types.Processor = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer()

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared_processors,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(logging.INFO)
