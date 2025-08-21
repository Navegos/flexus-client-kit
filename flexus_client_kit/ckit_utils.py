import asyncio
import logging

logger = logging.getLogger(__name__)


def report_crash(t, logger):
    try:
        exc = t.exception()
    except asyncio.CancelledError:
        return
    if exc is None:
        return
    if isinstance(exc, asyncio.CancelledError):
        return
    logger.error("crashed %s: %s", type(exc).__name__, exc, exc_info=(type(exc), exc, exc.__traceback__))
