"""Application lifecycle resources for the Gateway."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI

from ..services.upstreams import UpstreamService
from .config import settings


def build_upstream_timeout() -> httpx.Timeout:
    """Build the explicit timeout policy used by upstream requests."""

    return httpx.Timeout(
        connect=settings.upstream_connect_timeout_seconds,
        read=settings.upstream_read_timeout_seconds,
        write=settings.upstream_write_timeout_seconds,
        pool=settings.upstream_pool_timeout_seconds,
    )


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Create and close shared HTTP resources for the application lifetime."""

    timeout = build_upstream_timeout()
    client = httpx.AsyncClient(timeout=timeout)
    app.state.upstream_service = UpstreamService(
        client=client,
        timeout=timeout,
        config=settings,
    )
    try:
        yield
    finally:
        await client.aclose()
