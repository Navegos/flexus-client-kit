import logging
import asyncio
import time
from typing import Callable

import gql.transport.exceptions
import websockets

from flexus_client_kit import ckit_client, ckit_shutdown
logger = logging.getLogger("stexe")

assert "TransportConnectionFailed" in dir(gql.transport.exceptions), "pip install -U gql websockets"


async def run_typical_single_subscription_with_restart_on_network_errors(fclient: ckit_client.FlexusClient, subscribe_and_do_something: Callable, *func_args, **func_kwargs):
    ckit_shutdown.setup_signals()
    exception_attempts = 0
    last_exception_time = None
    exception_ttl = 300  # 5 minutes
    max_attempts = 3

    while not ckit_shutdown.shutdown_event.is_set():
        try:
            logger.info("Connecting %s", fclient.websocket_url)
            ws_client = await fclient.use_ws()
            try:
                ckit_shutdown.give_ws_client(fclient.service_name, ws_client)
                await subscribe_and_do_something(fclient, ws_client, *func_args, **func_kwargs)
                assert ckit_shutdown.shutdown_event.is_set()  # the only way we get there
            finally:
                ckit_shutdown.take_away_ws_client(fclient.service_name)

        except (
            websockets.exceptions.ConnectionClosedError,
            gql.transport.exceptions.TransportError,
            OSError,
            asyncio.exceptions.TimeoutError,
        ) as e:
            if ckit_shutdown.shutdown_event.is_set():
                break

            current_time = time.time()

            if last_exception_time and (current_time - last_exception_time) > exception_ttl:
                exception_attempts = 0

            exception_attempts += 1
            last_exception_time = current_time

            if exception_attempts >= max_attempts:
                logger.error("Reached %d consecutive exceptions, exiting: %s", max_attempts, e)
                raise

            if "403:" in str(e):
                logger.error("That looks bad, my key doesn't work: %s", e)
            else:
                logger.info("got %s (attempt %d/%d), sleep 60..." % (type(e).__name__, exception_attempts, max_attempts))
            await ckit_shutdown.wait(60)
