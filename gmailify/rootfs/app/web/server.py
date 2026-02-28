"""aiohttp web server for Ingress UI - OAuth2 setup + status dashboard."""
import json
import logging
import os
from urllib.parse import urlencode

from aiohttp import web
import aiohttp_jinja2
import jinja2

from config import Config, TOKEN_PATH

logger = logging.getLogger(__name__)

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GMAIL_SCOPE = "https://www.googleapis.com/auth/gmail.modify"
REDIRECT_URI = "http://localhost:1"


def create_web_app(config: Config, state, engine=None) -> web.Application:
    """Create the aiohttp web application."""
    app = web.Application(middlewares=[ingress_middleware])

    # Store references for handlers
    app["config"] = config
    app["state"] = state
    app["engine"] = engine

    # Setup Jinja2 templates
    template_dir = os.path.join(os.path.dirname(__file__), "templates")
    aiohttp_jinja2.setup(app, loader=jinja2.FileSystemLoader(template_dir))

    # Routes
    app.router.add_get("/", handle_index)
    app.router.add_get("/setup", handle_setup)
    app.router.add_post("/setup/callback", handle_oauth_callback)
    app.router.add_post("/sync/full", handle_full_sync)

    return app


@web.middleware
async def ingress_middleware(request: web.Request, handler) -> web.StreamResponse:
    """Handle Home Assistant Ingress path rewriting.

    HA Ingress sends X-Ingress-Path header with the base path.
    We store it for template URL generation.
    """
    ingress_path = request.headers.get("X-Ingress-Path", "")
    request["ingress_path"] = ingress_path.rstrip("/")
    return await handler(request)


@aiohttp_jinja2.template("index.html")
async def handle_index(request: web.Request) -> dict:
    """Dashboard showing sync status."""
    config: Config = request.app["config"]
    state = request.app["state"]
    engine = request.app["engine"]

    db_stats = await state.get_stats() if state else {}
    engine_stats = None
    if engine:
        engine_stats = {
            "is_running": engine.stats.is_running,
            "gmx_connected": engine.stats.gmx_connected,
            "messages_imported": engine.stats.messages_imported,
            "messages_skipped": engine.stats.messages_skipped,
            "messages_fetched": engine.stats.messages_fetched,
            "errors": engine.stats.errors,
            "last_sync": engine.stats.last_sync,
            "full_sync_running": engine.stats.full_sync_running,
            "last_errors": engine.stats.last_errors[-10:],
        }

    return {
        "ingress_path": request["ingress_path"],
        "has_token": config.has_gmail_token,
        "gmx_email": config.gmx_email,
        "db_stats": db_stats,
        "engine_stats": engine_stats,
    }


@aiohttp_jinja2.template("setup.html")
async def handle_setup(request: web.Request) -> dict:
    """OAuth2 setup page."""
    config: Config = request.app["config"]

    # Generate Google OAuth2 URL
    params = {
        "client_id": config.google_client_id,
        "redirect_uri": REDIRECT_URI,
        "scope": GMAIL_SCOPE,
        "response_type": "code",
        "access_type": "offline",
        "prompt": "consent",
    }
    auth_url = f"{GOOGLE_AUTH_URL}?{urlencode(params)}"

    return {
        "ingress_path": request["ingress_path"],
        "auth_url": auth_url,
        "has_token": config.has_gmail_token,
        "has_client_id": bool(config.google_client_id),
    }


async def handle_oauth_callback(request: web.Request) -> web.Response:
    """Exchange authorization code for tokens."""
    config: Config = request.app["config"]
    data = await request.post()
    auth_code = data.get("code", "").strip()

    if not auth_code:
        raise web.HTTPBadRequest(text="Authorization code is required")

    # Exchange code for tokens
    import aiohttp
    async with aiohttp.ClientSession() as session:
        async with session.post(
            GOOGLE_TOKEN_URL,
            data={
                "code": auth_code,
                "client_id": config.google_client_id,
                "client_secret": config.google_client_secret,
                "redirect_uri": REDIRECT_URI,
                "grant_type": "authorization_code",
            },
        ) as resp:
            if resp.status != 200:
                error_text = await resp.text()
                logger.error("Token exchange failed: %s", error_text)
                raise web.HTTPBadRequest(
                    text=f"Token exchange failed: {error_text}"
                )

            token_data = await resp.json()

    # Save credentials
    credentials = {
        "client_id": config.google_client_id,
        "client_secret": config.google_client_secret,
        "refresh_token": token_data["refresh_token"],
        "token_uri": GOOGLE_TOKEN_URL,
    }
    config.save_gmail_token(credentials)
    logger.info("Gmail OAuth2 tokens saved successfully")

    # Redirect to dashboard
    ingress_path = request["ingress_path"]
    raise web.HTTPFound(f"{ingress_path}/")


async def handle_full_sync(request: web.Request) -> web.Response:
    """Trigger a full sync of all folders."""
    engine = request.app["engine"]

    if engine is None:
        raise web.HTTPBadRequest(text="Sync engine not running. Authorize Gmail first.")

    if engine.stats.full_sync_running:
        raise web.HTTPBadRequest(text="Full sync already in progress")

    # Run full sync in background
    asyncio.ensure_future(engine.trigger_full_sync())
    logger.info("Full sync triggered via web UI")

    ingress_path = request["ingress_path"]
    raise web.HTTPFound(f"{ingress_path}/")


import asyncio
