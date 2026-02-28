"""Gmailify Home Assistant Add-on - Main entry point.

Starts the web UI server and (if Gmail is authorized) the sync engine.
"""
import asyncio
import logging
import signal
import sys

from aiohttp import web

from config import load_config
from gmail_client import GmailClient
from gmx_client import GmxClient
from sync_engine import SyncEngine
from sync_state import SyncState
from web.server import create_web_app

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger("gmailify")


async def run_web_server(app: web.Application, port: int = 8099) -> None:
    """Run the aiohttp web server."""
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logger.info("Web UI running on port %d", port)

    # Wait forever (until cancelled)
    try:
        await asyncio.Event().wait()
    finally:
        await runner.cleanup()


async def async_main() -> None:
    config = load_config()
    state = SyncState()
    await state.initialize()

    engine = None

    if config.has_gmail_token:
        logger.info("Gmail token found, starting sync engine...")
        gmail = GmailClient(config.gmail_credentials)
        gmx = GmxClient(
            host=config.gmx_host,
            port=config.gmx_port,
            email_addr=config.gmx_email,
            password=config.gmx_password,
        )
        engine = SyncEngine(gmx, gmail, state, config)
    else:
        logger.info("No Gmail token found. Open the web UI to authorize Gmail.")

    # Create web app with engine reference
    app = create_web_app(config, state, engine)

    # Setup shutdown handler
    stop_event = asyncio.Event()

    def handle_signal():
        logger.info("Shutdown signal received")
        stop_event.set()
        if engine:
            asyncio.ensure_future(engine.stop())

    loop = asyncio.get_event_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(sig, handle_signal)
        except NotImplementedError:
            # Windows doesn't support add_signal_handler
            pass

    # Start tasks
    tasks = [run_web_server(app)]
    if engine:
        tasks.append(engine.run())

    try:
        await asyncio.gather(*tasks)
    except asyncio.CancelledError:
        pass
    finally:
        await state.close()
        logger.info("Gmailify stopped")


def main():
    try:
        asyncio.run(async_main())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
