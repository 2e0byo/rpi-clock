import logging

import logfire
import structlog
from structlog import DropEvent, get_logger
from structlog.typing import WrappedLogger

logger = get_logger()

_stdlib_level_map = logging.getLevelNamesMapping() | {
    k.lower(): v for k, v in logging.getLevelNamesMapping().items()
}


def setup_logging(log_level: str) -> None:
    logfire.configure()
    assert log_level in _stdlib_level_map

    def _filter_by_level(_: WrappedLogger, level_name: str, event_dict: dict) -> dict:
        if _stdlib_level_map[level_name] < _stdlib_level_map[log_level]:
            raise DropEvent
        else:
            return event_dict

    structlog.configure(
        processors=[
            _filter_by_level,
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.dev.set_exc_info,
            structlog.processors.TimeStamper("iso"),
            structlog.processors.CallsiteParameterAdder(
                {
                    structlog.processors.CallsiteParameter.FILENAME,
                    structlog.processors.CallsiteParameter.FUNC_NAME,
                    structlog.processors.CallsiteParameter.LINENO,
                }
            ),
            logfire.StructlogProcessor(),
            structlog.dev.ConsoleRenderer(),
        ],
    )
    logger.info("Set up logging", level=log_level)
