from __future__ import annotations

import logging
import uuid

from sweagent.utils.log import _SET_UP_LOGGERS, get_logger


def test_get_logger_sets_up_handlers_when_root_logger_has_handlers():
    """A handler on the root logger (e.g. from the embedding program) must not stop our own setup."""
    root_logger = logging.getLogger()
    root_logger.addHandler(logging.NullHandler())
    name = f"test-logger-{uuid.uuid4().hex}"
    try:
        logger = get_logger(name)
    finally:
        for handler in root_logger.handlers[:]:
            if isinstance(handler, logging.NullHandler):
                root_logger.removeHandler(handler)
    assert logger.handlers
    assert logger.propagate is False
    assert name in _SET_UP_LOGGERS
