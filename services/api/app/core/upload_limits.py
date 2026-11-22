import re

from app.core.config import settings
from starlette.exceptions import HTTPException
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

UPLOAD_PATH = re.compile(r"/api/v1/projects/[^/]+/documents/?$")
MULTIPART_OVERHEAD_BYTES = 64 * 1024
LIMIT_MESSAGE = "The document exceeds the upload limit."


class UploadBodyLimit:
    """Bound bytes delivered to the multipart parser, including direct API calls."""

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if (
            scope["type"] != "http"
            or scope["method"] != "POST"
            or not UPLOAD_PATH.fullmatch(scope["path"])
        ):
            await self.app(scope, receive, send)
            return

        # Match the BFF's bounded framing allowance; admit() still enforces the
        # exact file-byte limit. Never trust Content-Length as the actual count.
        limit = settings.max_upload_bytes + MULTIPART_OVERHEAD_BYTES
        for name, value in scope.get("headers", []):
            if name.lower() == b"content-length" and value.isdigit() and int(value) > limit:
                response = JSONResponse(
                    status_code=413,
                    content={"error": {"message": LIMIT_MESSAGE}},
                )
                await response(scope, receive, send)
                return

        received = 0

        async def limited_receive():
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > limit:
                    # Raising through request.form() also closes parser spools.
                    raise HTTPException(413, LIMIT_MESSAGE)
            return message

        await self.app(scope, limited_receive, send)
