from __future__ import annotations

import os
import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes import router, templates
from app.config import config

app = FastAPI(title="Spectre OSINT")

static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.isdir(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

app.include_router(router)


@app.exception_handler(404)
async def not_found(request: Request, _):
    return templates.TemplateResponse(
        "index.html",
        {"request": request, "investigations": []},
        status_code=404,
    )


if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=config.host,
        port=config.port,
        reload=True,
    )
