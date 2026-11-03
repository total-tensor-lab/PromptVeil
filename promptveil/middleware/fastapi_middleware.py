"""
Optional FastAPI / Starlette middleware for PromptVeil.

Install the extra dependency first::

    pip install "promptveil[fastapi]"

Then add the middleware to your app::

    from fastapi import FastAPI
    from promptveil import Shield
    from promptveil.middleware import PromptVeilMiddleware

    app = FastAPI()
    shield = Shield(config_path="policy.yaml")
    app.add_middleware(PromptVeilMiddleware, shield=shield, prompt_field="prompt")

Pass ``response_field="response"`` to also scan that field of JSON responses.
"""

import json
from typing import Callable, Optional

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from ..exceptions import SensitiveDataError
from ..shield import Shield


class PromptVeilMiddleware(BaseHTTPMiddleware):
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

    When *response_field* is set, 2xx JSON object responses have that field
    scanned with :meth:`~promptveil.shield.Shield.scan_response`. A masked
    field is rewritten; a blocked one turns the response into a
    ``502 Bad Gateway`` JSON error. Other responses (non-2xx, non-JSON, or
    without a string *response_field*) pass through unchanged. Responses with
    a JSON content type are read in full before scanning, even if streamed.

    Args:
        app: The ASGI application to wrap.
        shield: A configured :class:`~promptveil.shield.Shield` instance.
        prompt_field: The JSON body key that holds the prompt text.
            Defaults to ``"prompt"``.
        response_field: The JSON response key that holds the model output.
            Defaults to ``None`` (responses are not scanned).
    """

    def __init__(
        self,
        app,
        shield: Shield,
        prompt_field: str = "prompt",
        response_field: Optional[str] = None,
    ) -> None:
        super().__init__(app)
        self._shield = shield
        self._prompt_field = prompt_field
        self._response_field = response_field

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Scan the request prompt, call the handler, then scan the response."""
        blocked = await self._scan_request(request)
        if blocked is not None:
            return blocked

        response = await call_next(request)
        if self._response_field is None:
            return response
        return await self._scan_response(response)

    async def _scan_request(self, request: Request) -> Optional[Response]:
        """Mask the prompt field in place, or return a 400 response if blocked."""
        content_type = request.headers.get("content-type", "")

        if request.method == "POST" and "application/json" in content_type:
            raw_body = await request.body()

            # If body is not valid JSON, pass it through untouched.
            try:
                body: dict = json.loads(raw_body)
            except (json.JSONDecodeError, UnicodeDecodeError):
                return None

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
                # We must update both the cached body bytes (_body) and the
                # underlying receive callable so that downstream handlers that
                # call request.body() / request.json() see the modified content.
                modified = json.dumps(body).encode("utf-8")
                request._body = modified  # type: ignore[attr-defined]

                async def _receive():
                    return {"type": "http.request", "body": modified, "more_body": False}

                request._receive = _receive  # type: ignore[method-assign]

        return None

    async def _scan_response(self, response: Response) -> Response:
        """Scan *response_field* of a 2xx JSON response; 502 if blocked."""
        content_type = response.headers.get("content-type", "")
        if not (200 <= response.status_code < 300) or "application/json" not in content_type:
            return response

        raw_body = b"".join([chunk async for chunk in response.body_iterator])  # type: ignore[attr-defined]

        try:
            body = json.loads(raw_body)
        except (json.JSONDecodeError, UnicodeDecodeError):
            return self._rebuild(response, raw_body)

        if not isinstance(body, dict) or not isinstance(body.get(self._response_field), str):
            return self._rebuild(response, raw_body)

        try:
            body[self._response_field] = self._shield.scan_response(body[self._response_field])
        except SensitiveDataError as exc:
            return JSONResponse(
                status_code=502,
                content={
                    "error": "Blocked: sensitive data detected in response.",
                    "detail": str(exc),
                    "code": "SENSITIVE_DATA_BLOCKED_RESPONSE",
                },
            )

        return self._rebuild(response, json.dumps(body).encode("utf-8"))

    @staticmethod
    def _rebuild(response: Response, body: bytes) -> Response:
        """Return a copy of *response* with *body*, keeping status and headers."""
        new = Response(content=body, status_code=response.status_code, background=response.background)
        # Copy raw headers so repeated ones (e.g. set-cookie) survive, and
        # replace content-length to match the new body.
        new.raw_headers = [
            (k, v) for k, v in response.raw_headers if k.lower() != b"content-length"
        ] + [(b"content-length", str(len(body)).encode("latin-1"))]
        return new
