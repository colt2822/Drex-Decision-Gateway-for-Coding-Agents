"""FastAPI application factory for Drex Decision Gateway."""
from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import urlsplit
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from drex_gateway.api.routes import create_router
from drex_gateway.config import GatewayConfig
from drex_gateway.errors import GatewayError, ProviderError, ValidationError
from drex_gateway.gateway import DrexDecisionGateway

STATIC_DIR = Path(__file__).parent.parent / "web" / "static"


def _cors_origins() -> list[str]:
    raw = os.environ.get("DREX_CORS_ORIGINS", "")
    origins = [value.strip() for value in raw.split(",") if value.strip()]
    for origin in origins:
        parsed = urlsplit(origin)
        if (
            origin == "*"
            or parsed.scheme not in {"http", "https"}
            or not parsed.netloc
            or parsed.path not in {"", "/"}
            or parsed.query
            or parsed.fragment
            or parsed.username
            or parsed.password
        ):
            raise ValueError("DREX_CORS_ORIGINS must contain exact HTTP(S) origins, not wildcards or URLs with paths")
    return origins


def create_app(gateway: DrexDecisionGateway | None = None) -> FastAPI:
    if gateway is None:
        cfg = GatewayConfig.from_env()
        gateway = DrexDecisionGateway(config=cfg)

    app = FastAPI(
        title="Drex Decision Gateway",
        description=(
            "High-throughput, structured decision gateway for coding-agent loops. "
            "Replaces expensive generative LLM calls with fast, calibrated Drex probability decisions."
        ),
        version="0.1.1",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=_cors_origins(),
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Attach router
    router = create_router(gateway)
    app.include_router(router)

    # Static UI files
    if STATIC_DIR.is_dir():
        app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

        @app.get("/", include_in_schema=False)
        async def serve_index():
            from fastapi.responses import FileResponse
            index_path = STATIC_DIR / "index.html"
            if index_path.is_file():
                return FileResponse(index_path)
            return JSONResponse({"message": "Drex Decision Gateway API active. See /docs for endpoints."})

        @app.get("/favicon.ico", include_in_schema=False)
        async def serve_favicon():
            from fastapi import Response
            return Response(status_code=204)

    # Error handling
    @app.exception_handler(ProviderError)
    async def provider_error_handler(request: Request, exc: ProviderError):
        status_code = exc.status_code if exc.status_code and exc.status_code >= 400 else 502
        return JSONResponse(
            status_code=status_code,
            content={
                "error": {
                    "kind": exc.kind.value,
                    "message": exc.message,
                    "status_code": exc.status_code,
                    "retry_after_seconds": exc.retry_after_seconds,
                }
            },
            headers={"Retry-After": str(int(exc.retry_after_seconds))} if exc.retry_after_seconds else None,
        )

    @app.exception_handler(ValidationError)
    async def validation_error_handler(request: Request, exc: ValidationError):
        return JSONResponse(status_code=422, content={"error": {"kind": "VALIDATION_ERROR", "message": exc.message}})

    @app.exception_handler(GatewayError)
    async def gateway_error_handler(request: Request, exc: GatewayError):
        return JSONResponse(status_code=500, content={"error": {"kind": "GATEWAY_ERROR", "message": exc.message}})

    return app
