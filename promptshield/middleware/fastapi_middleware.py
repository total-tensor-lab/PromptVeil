"""
Optional FastAPI / Starlette middleware for PromptShield.

Install the extra dependency first::

    pip install "promptshield[fastapi]"

Then add the middleware to your app::

    from fastapi import FastAPI
    from promptshield import Shield
    from promptshield.middleware import PromptShieldMiddleware

    app = FastAPI()
    shield = Shield(config_path="policy.yaml")
    app.add_middleware(PromptShieldMiddleware, shield=shield, prompt_field="prompt")
"""

import json
from typing import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from ..exceptions import SensitiveDataError
from ..shield import Shield


class PromptShieldMiddleware(BaseHTTPMiddleware):
    """
    Starlette/FastAPI middleware that intercepts POST request bodies and scans
    the configured *prompt_field* for sensitive data before forwarding the
    request to the route handler.

    Behaviour:

    * **Mask** — the prompt field is rewritten in-place with sensitive values
      masked, and the modified request continues to the handler.
    * **Block** — a ``400 Bad Request`` JSON response is returned immediately;
      the route handler is never called.
    * Non-JSON bodies, non-POST methods, or requests without the prompt field
      are forwarded unmodified.

    Args:
        app: The ASGI application to wrap.
        shield: A configured :class:`~promptshield.shield.Shield` instance.
        prompt_field: The JSON body key that holds the prompt text.
            Defaults to ``"prompt"``.
    """

    def __init__(
        self,
        app,
        shield: Shield,
        prompt_field: str = "prompt",
    ) -> None:
        super().__init__(app)
        self._shield = shield
        self._prompt_field = prompt_field

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Intercept the request, scan the prompt field, and forward or block."""
        content_type = request.headers.get("content-type", "")

        if request.method == "POST" and "application/json" in content_type:
            raw_body = await request.body()

            # If body is not valid JSON, pass it through untouched.
            try:
                body: dict = json.loads(raw_body)
            except (json.JSONDecodeError, UnicodeDecodeError):
                return await call_next(request)

            if self._prompt_field in body:
                try:
                    safe_prompt = self._shield.scan(body[self._prompt_field])
                    body[self._prompt_field] = safe_prompt
                except SensitiveDataError as exc:
                    return JSONResponse(
                        status_code=400,
                        content={
                            "error": "Blocked: sensitive data detected in prompt.",
                            "detail": str(exc),
                            "code": "SENSITIVE_DATA_BLOCKED",
                        },
                    )

                # Rebuild the request with the sanitised body.
                modified = json.dumps(body).encode("utf-8")

                async def _receive():
                    return {"type": "http.request", "body": modified, "more_body": False}

                request._receive = _receive  # type: ignore[method-assign]

        return await call_next(request)
