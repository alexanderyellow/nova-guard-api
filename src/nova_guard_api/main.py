from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from starlette.exceptions import HTTPException as StarletteHTTPException

from nova_guard_api.api.routes import artifacts, characters, factions, market, missions, planets, species, squads
from nova_guard_api.core.config import get_settings
from nova_guard_api.core.errors import ProblemError, problem, problem_error_handler, validation_exception_handler
from nova_guard_api.core.rate_limit import RateLimitMiddleware

settings = get_settings()
API_V1_PREFIX = "/api/v1"


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        description="Galactic bounty and exploration registry — REST API for API testing practice.",
        version="0.1.0",
        json_schema_extra={"jsonSchemaDialect": "https://json-schema.org/draft/2020-12/schema"},
    )

    origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
    if origins == ["*"]:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
    elif origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    app.add_middleware(RateLimitMiddleware, requests_per_minute=settings.rate_limit_per_minute)

    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(StarletteHTTPException, _http_exc_handler)
    app.add_exception_handler(ProblemError, problem_error_handler)

    # Versioned API routes (preferred)
    app.include_router(species.router, prefix=API_V1_PREFIX)
    app.include_router(characters.router, prefix=API_V1_PREFIX)
    app.include_router(planets.router, prefix=API_V1_PREFIX)
    app.include_router(factions.router, prefix=API_V1_PREFIX)
    app.include_router(squads.router, prefix=API_V1_PREFIX)
    app.include_router(missions.router, prefix=API_V1_PREFIX)
    app.include_router(artifacts.router, prefix=API_V1_PREFIX)
    app.include_router(market.router, prefix=API_V1_PREFIX)

    # Backward-compatible unversioned routes.
    app.include_router(species.router)
    app.include_router(characters.router)
    app.include_router(planets.router)
    app.include_router(factions.router)
    app.include_router(squads.router)
    app.include_router(missions.router)
    app.include_router(artifacts.router)
    app.include_router(market.router)

    @app.get("/health", tags=["meta"])
    def health():
        return {"status": "ok"}

    @app.get(f"{API_V1_PREFIX}/health", tags=["meta"])
    def health_v1():
        return {"status": "ok", "version": "v1"}

    def custom_openapi():
        if app.openapi_schema:
            return app.openapi_schema
        schema = get_openapi(
            title=app.title,
            version=app.version,
            description=app.description,
            routes=app.routes,
        )
        schema.setdefault("components", {}).setdefault("securitySchemes", {})
        schema["components"]["securitySchemes"]["NovaGuardApiKey"] = {
            "type": "apiKey",
            "in": "header",
            "name": "X-Nova-Guard-Key",
        }
        schema["components"]["securitySchemes"]["BearerAuth"] = {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
            "description": "JWT with `sub` = character id; role loaded from database.",
        }
        schema["webhooks"] = {
            "missionStatusChanged": {
                "post": {
                    "summary": "mission.status_changed",
                    "requestBody": {
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "event": {"type": "string"},
                                        "payload": {"type": "object"},
                                        "ts": {"type": "string"},
                                    },
                                }
                            }
                        }
                    },
                }
            },
            "bountyUpdated": {
                "post": {
                    "summary": "bounty.updated",
                    "requestBody": {
                        "content": {
                            "application/json": {
                                "schema": {"type": "object"},
                            }
                        }
                    },
                }
            },
            "marketListingSold": {
                "post": {
                    "summary": "market.listing_sold",
                    "requestBody": {
                        "content": {
                            "application/json": {
                                "schema": {"type": "object"},
                            }
                        }
                    },
                }
            },
        }
        app.openapi_schema = schema
        return app.openapi_schema

    app.openapi = custom_openapi

    return app


async def _http_exc_handler(request, exc: StarletteHTTPException):
    from fastapi.responses import JSONResponse

    detail = exc.detail if isinstance(exc.detail, str) else str(exc.detail)
    return JSONResponse(
        status_code=exc.status_code,
        content=problem(
            type_=f"https://nova-guard.dev/problems/http-{exc.status_code}",
            title=detail or "Error",
            status_code=exc.status_code,
            detail=detail,
            instance=str(request.url),
        ),
        media_type="application/problem+json",
    )


app = create_app()
