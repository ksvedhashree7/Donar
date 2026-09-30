from __future__ import annotations

from uuid import UUID

from jose import JWTError
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.core.database import SessionFactory
from app.core.security import decode_access_token
from app.services.audit import record_audit_event


class AuditMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        response = await call_next(request)
        if request.url.path in {"/", "/health"}:
            return response

        actor_id = None
        actor_role = "ANONYMOUS"
        auth_header = request.headers.get("authorization", "")
        if auth_header.lower().startswith("bearer "):
            try:
                claims = decode_access_token(auth_header[7:])
                actor_id = UUID(claims["sub"])
                actor_role = str(claims.get("role", "UNKNOWN"))
            except (JWTError, ValueError, KeyError):
                pass
        route = request.scope.get("route")
        resource_type = str(getattr(route, "path", request.url.path))[:80]
        purpose = request.query_params.get("purpose")
        if purpose not in {"medical_evaluation", "matching", "coordination"}:
            purpose = None

        session_factory = getattr(request.app.state, "session_factory", SessionFactory)
        db = session_factory()
        try:
            record_audit_event(
                db,
                actor_id=actor_id,
                actor_role=actor_role,
                action=f"HTTP_{request.method}_{response.status_code}",
                resource_type=resource_type,
                resource_id=None,
                purpose=purpose,
                ip_address=request.client.host if request.client else None,
                user_agent=request.headers.get("user-agent", "")[:255] or None,
                success=response.status_code < 400,
            )
            db.commit()
        except Exception:
            db.rollback()
            if request.app.state.environment != "development":
                raise
        finally:
            db.close()
        return response
