from __future__ import annotations

import logging
import sys
import threading
from concurrent.futures import ThreadPoolExecutor

import sweagent.utils.log as log_module
from sweagent.utils.log import add_file_handler, get_logger, remove_file_handler


def test_get_logger_thread_safe_with_concurrent_file_handlers(tmp_path):
    """Regression test for #981: get_logger must not crash with
    'RuntimeError: dictionary/set changed size during iteration' when other
    threads add or remove file handlers at the same time.

    #981 was reported as a crash inside get_logger while iterating
    ``_ADDITIONAL_HANDLERS`` and was closed by #993. #993 (and the earlier
    handler-locking commit) only wrapped the *readers* that iterate the shared
    globals ``_SET_UP_LOGGERS`` and ``_ADDITIONAL_HANDLERS`` in ``_LOG_LOCK``.
    The *writers* were left unlocked: get_logger did ``_SET_UP_LOGGERS.add(name)``
    outside the lock, and add_file_handler / remove_file_handler mutated
    ``_ADDITIONAL_HANDLERS`` outside the lock. Holding the lock only for the
    reader gives no protection when another thread mutates the same container
    without the lock, so the crash can still happen under run-batch with
    num_workers > 1.

    This test hammers get_logger (writes ``_SET_UP_LOGGERS``, reads
    ``_ADDITIONAL_HANDLERS``) against add_file_handler / remove_file_handler
    (read ``_SET_UP_LOGGERS``, write ``_ADDITIONAL_HANDLERS``) from many threads
    and fails if any thread raises.
    """
    errors: list[Exception] = []
    stop = threading.Event()
    name_prefix = "test-log-race-"

    # Pre-populate the shared globals so the locked reader loops iterate large
    # containers. This widens the window in which an unlocked writer in another
    # thread can mutate the same container mid-iteration, making the race
    # reproducible instead of relying on a lucky interleaving.
    preexisting_logger_names = [f"{name_prefix}preexisting-{i}" for i in range(2000)]
    preexisting_handler_ids = [f"{name_prefix}preexisting-handler-{i}" for i in range(500)]
    for name in preexisting_logger_names:
        log_module._SET_UP_LOGGERS.add(name)
    for handler_id in preexisting_handler_ids:
        log_module._ADDITIONAL_HANDLERS[handler_id] = logging.NullHandler()

    # Encourage frequent thread switches so the race surfaces quickly.
    old_switch_interval = sys.getswitchinterval()
    sys.setswitchinterval(1e-6)

    # get_logger short-circuits (never reaching the racy writer) if the logger
    # already ``hasHandlers()``. pytest attaches capture handlers to the root
    # logger, which would make every fresh logger report handlers via the root,
    # so temporarily detach them to exercise the real production code path.
    root_logger = logging.getLogger()
    saved_root_handlers = root_logger.handlers[:]
    root_logger.handlers.clear()

    def make_loggers(worker_id: int) -> None:
        try:
            i = 0
            while not stop.is_set():
                get_logger(f"{name_prefix}{worker_id}-{i}")
                i += 1
        except Exception as e:
            errors.append(e)
            stop.set()

    def churn_file_handlers(worker_id: int) -> None:
        try:
            i = 0
            while not stop.is_set():
                id_ = add_file_handler(tmp_path / f"handler-{worker_id}-{i}.log")
                remove_file_handler(id_)
                i += 1
        except Exception as e:
            errors.append(e)
            stop.set()

    timer = threading.Timer(2.0, stop.set)
    timer.start()
    try:
        with ThreadPoolExecutor(max_workers=12) as pool:
            futures = [pool.submit(make_loggers, w) for w in range(6)]
            futures += [pool.submit(churn_file_handlers, w) for w in range(6)]
            for future in futures:
                future.result()
    finally:
        timer.cancel()
        stop.set()
        sys.setswitchinterval(old_switch_interval)
        root_logger.handlers[:] = saved_root_handlers
        # Clean up the module-level global state we polluted so we don't leak
        # loggers/handlers into other tests.
        for name in [name for name in list(log_module._SET_UP_LOGGERS) if name.startswith(name_prefix)]:
            logger = logging.getLogger(name)
            for handler in list(logger.handlers):
                logger.removeHandler(handler)
            log_module._SET_UP_LOGGERS.discard(name)
        for handler_id in preexisting_handler_ids:
            log_module._ADDITIONAL_HANDLERS.pop(handler_id, None)

    assert not errors, f"get_logger raced with file-handler mutation: {errors[0]!r}"
