import logging
import time
from collections.abc import Awaitable, Callable
from dataclasses import asdict
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from checker import check

STATIC_DIR = Path(__file__).parent / "static"
NOTE = "Passing these static checks does not prove the script compiles in TradingView's Pine Editor."

logger = logging.getLogger(__name__)

# The interactive docs pages load scripts from a CDN, which the content security policy forbids.
app = FastAPI(title="Pine v6 Copilot", docs_url=None, redoc_url=None)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


class CheckRequest(BaseModel):
    code: str


@app.middleware("http")
async def content_security_policy(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    response = await call_next(request)
    response.headers["Content-Security-Policy"] = "default-src 'self'"
    return response


@app.exception_handler(RequestValidationError)
async def malformed_request(request: Request, error: RequestValidationError) -> JSONResponse:
    # FastAPI's default 422 body repeats the submitted input; a plain message is enough here.
    return JSONResponse(status_code=422, content={"detail": 'Send a JSON body with a "code" string.'})


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.post("/check")
def check_code(request: CheckRequest) -> dict[str, object]:
    if not request.code.strip():
        raise HTTPException(status_code=422, detail="Paste some Pine Script code to check.")
    started = time.perf_counter()
    try:
        findings = check(request.code)
    except ValueError as err:
        raise HTTPException(status_code=422, detail=str(err)) from None
    logger.info("check duration_ms=%.0f findings=%d", (time.perf_counter() - started) * 1000, len(findings))
    return {
        "findings": [asdict(finding) for finding in findings],
        "errors": sum(finding.severity == "error" for finding in findings),
        "warnings": sum(finding.severity == "warning" for finding in findings),
        "note": NOTE,
    }
