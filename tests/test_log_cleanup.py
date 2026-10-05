import logging

import pytest

from sweagent.utils import log


def test_removing_batch_log_handlers_closes_files(tmp_path, monkeypatch):
    logger = logging.getLogger("swea-handler-cleanup-test")
    monkeypatch.setattr(log, "_SET_UP_LOGGERS", {logger.name})
    monkeypatch.setattr(log, "_ADDITIONAL_HANDLERS", {})
    streams = []
    handlers = []
    try:
        for instance in range(4):
            for level in ["trace", "debug", "info"]:
                handler_id = log.add_file_handler(tmp_path / f"{instance}.{level}.log", level=level)
                handler = log._ADDITIONAL_HANDLERS[handler_id]
                handlers.append(handler)
                streams.append(handler.stream)
                assert handler in logger.handlers
                log.remove_file_handler(handler_id)
                assert handler not in logger.handlers
                assert handler_id not in log._ADDITIONAL_HANDLERS
        assert all(stream.closed for stream in streams)
    finally:
        for handler in handlers:
            logger.removeHandler(handler)
            handler.close()


def test_unknown_handler_id_still_raises(monkeypatch):
    monkeypatch.setattr(log, "_ADDITIONAL_HANDLERS", {})
    with pytest.raises(KeyError):
        log.remove_file_handler("missing")
