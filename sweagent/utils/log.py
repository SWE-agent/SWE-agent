from __future__ import annotations

import logging
import os
import threading
import uuid
from collections.abc import Callable
from pathlib import Path, PurePath

from rich.logging import RichHandler
from rich.text import Text

_SET_UP_LOGGERS: set[str] = set()
_ADDITIONAL_HANDLERS: dict[str, logging.Handler] = {}

logging.TRACE = 5  # type: ignore
logging.addLevelName(logging.TRACE, "TRACE")  # type: ignore


def _interpret_level(level: int | str | None, *, default=logging.DEBUG) -> int:
    if not level:
        return default
    if isinstance(level, int):
        return level
    if level.isnumeric():
        return int(level)
    return getattr(logging, level.upper())


# Default levels from environment variables or CLI args
_STREAM_LEVEL = None
_FILE_LEVEL = None


def set_default_levels(stream_level: int | str | None = None, file_level: int | str | None = None) -> None:
    """Set the default logging levels for stream and file handlers.

    Args:
        stream_level: Level for stream handlers (console output)
        file_level: Level for file handlers
    """
    global _STREAM_LEVEL, _FILE_LEVEL
    _STREAM_LEVEL = _interpret_level(stream_level or os.environ.get("SWE_AGENT_LOG_STREAM_LEVEL"))
    _FILE_LEVEL = _interpret_level(file_level or os.environ.get("SWE_AGENT_LOG_FILE_LEVEL"), default=logging.TRACE)  # type: ignore


_INCLUDE_LOGGER_NAME_IN_STREAM_HANDLER = False

_THREAD_NAME_TO_LOG_SUFFIX: dict[str, str] = {}
"""Mapping from thread name to suffix to add to the logger name."""


def register_thread_name(name: str) -> None:
    """Register a suffix to add to the logger name for the current thread."""
    thread_name = threading.current_thread().name
    _THREAD_NAME_TO_LOG_SUFFIX[thread_name] = name


class _RichHandlerWithEmoji(RichHandler):
    def __init__(self, emoji: str, *args, **kwargs):
        """Subclass of RichHandler that adds an emoji to the log message."""
        super().__init__(*args, **kwargs)
        if not emoji.endswith(" "):
            emoji += " "
        self.emoji = emoji

    def get_level_text(self, record: logging.LogRecord) -> Text:
        level_name = record.levelname.replace("WARNING", "WARN")
        return Text.styled((self.emoji + level_name).ljust(10), f"logging.level.{level_name.lower()}")


def get_logger(name: str, *, emoji: str = "") -> logging.Logger:
    """Get logger. Use this instead of `logging.getLogger` to ensure
    that the logger is set up with the correct handlers.
    """
    thread_name = threading.current_thread().name
    if thread_name != "MainThread":
        name = name + "-" + _THREAD_NAME_TO_LOG_SUFFIX.get(thread_name, thread_name)
    logger = logging.getLogger(name)
    if logger.hasHandlers():
        # Already set up
        return logger
    handler = _RichHandlerWithEmoji(
        emoji=emoji,
        show_time=bool(os.environ.get("SWE_AGENT_LOG_TIME", False)),
        show_path=False,
    )
    handler.setLevel(_STREAM_LEVEL)
    logger.setLevel(min(_STREAM_LEVEL, _FILE_LEVEL))
    logger.addHandler(handler)
    logger.propagate = False
    _SET_UP_LOGGERS.add(name)
    for handler in _ADDITIONAL_HANDLERS.values():
        my_filter = getattr(handler, "my_filter", None)
        if my_filter is None:
            logger.addHandler(handler)
        elif isinstance(my_filter, str) and my_filter in name:
            logger.addHandler(handler)
        elif callable(my_filter) and my_filter(name):
            logger.addHandler(handler)
    if _INCLUDE_LOGGER_NAME_IN_STREAM_HANDLER:
        _add_logger_name_to_stream_handler(logger)
    return logger


def add_file_handler(
    path: PurePath | str,
    *,
    filter: str | Callable[[str], bool] | None = None,
    level: int | str = _FILE_LEVEL,
    id_: str = "",
) -> str:
    """Adds a file handler to all loggers that we have set up
    and all future loggers that will be set up with `get_logger`.

    Args:
        filter: If str: Check that the logger name contains the filter string.
            If callable: Check that the logger name satisfies the condition returned by the callable.
        level: The level of the handler.
        id_: The id of the handler. If not provided, a random id will be generated.

    Returns:
        The id of the handler. This can be used to remove the handler later.
    """
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    handler = logging.FileHandler(path)
    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(name)s - %(message)s")
    handler.setFormatter(formatter)
    handler.setLevel(_interpret_level(level))
    for name in _SET_UP_LOGGERS:
        if filter is not None:
            if isinstance(filter, str) and filter not in name:
                continue
            if callable(filter) and not filter(name):
                continue
        logger = logging.getLogger(name)
        logger.addHandler(handler)
    handler.my_filter = filter  # type: ignore
    if not id_:
        id_ = str(uuid.uuid4())
    _ADDITIONAL_HANDLERS[id_] = handler
    return id_


def remove_file_handler(id_: str) -> None:
    """Remove a file handler by its id."""
    handler = _ADDITIONAL_HANDLERS.pop(id_)
    for log_name in _SET_UP_LOGGERS:
        logger = logging.getLogger(log_name)
        logger.removeHandler(handler)


def _add_logger_name_to_stream_handler(logger: logging.Logger) -> None:
    for handler in logger.handlers:
        if isinstance(handler, _RichHandlerWithEmoji):
            formatter = logging.Formatter("[%(name)s] %(message)s")
            handler.setFormatter(formatter)


def add_logger_names_to_stream_handlers() -> None:
    """Add the logger name to the stream handler for all loggers that we have set up."""
    global _INCLUDE_LOGGER_NAME_IN_STREAM_HANDLER
    _INCLUDE_LOGGER_NAME_IN_STREAM_HANDLER = True
    for logger in _SET_UP_LOGGERS:
        _add_logger_name_to_stream_handler(logging.getLogger(logger))


default_logger = get_logger("swe-agent")


def set_stream_handler_levels(level: int) -> None:
    """Set the default stream level and adjust the levels of all stream handlers
    to be at most the given level.

    Note: Can only be used to lower the level, not raise it.
    """
    global _STREAM_LEVEL
    _STREAM_LEVEL = level
    for name in _SET_UP_LOGGERS:
        logger = logging.getLogger(name)
        for handler in logger.handlers:
            if isinstance(handler, _RichHandlerWithEmoji):
                current_level = handler.level
                if current_level < level:
                    handler.setLevel(level)
