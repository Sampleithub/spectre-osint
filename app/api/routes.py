from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, Form
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
import os

from app.models.schemas import Investigation
from app.services.agent import process_turn
from app.services.report import generate_report
from app.services.session_store import store

router = APIRouter()
templates = Jinja2Templates(
    directory=os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates")
)


@router.get("/", response_class=HTMLResponse)
async def index(request: Request):
    investigations = store.list_all()
    return templates.TemplateResponse(
        "index.html",
        {"request": request, "investigations": investigations},
    )


@router.post("/investigation/new")
async def create_investigation(
    target_type: str = Form(...),
    target_value: str = Form(...),
):
    if not target_type or not target_value:
        raise HTTPException(400, "target_type and target_value are required")
    inv = Investigation(target_type, target_value)
    store.save(inv)
    return RedirectResponse(url=f"/investigation/{inv.id}", status_code=302)


@router.get("/investigation/{investigation_id}", response_class=HTMLResponse)
async def view_investigation(request: Request, investigation_id: str):
    inv = store.load(investigation_id)
    if not inv:
        raise HTTPException(404, "Investigation not found")
    return templates.TemplateResponse(
        "investigation.html",
        {"request": request, "inv": inv},
    )


@router.post("/api/investigation/{investigation_id}/turn")
async def submit_turn(investigation_id: str, request: Request):
    inv = store.load(investigation_id)
    if not inv:
        raise HTTPException(404, "Investigation not found")
    if inv.status != "active":
        raise HTTPException(400, "Investigation is not active")

    body = await request.json()
    user_msg = body.get("message", "").strip()
    if not user_msg:
        raise HTTPException(400, "Message is required")

    response = await process_turn(inv, user_msg)
    store.save(inv)

    return JSONResponse({
        "response": response,
    })


@router.post("/api/investigation/{investigation_id}/reset")
async def reset_conversation(investigation_id: str):
    inv = store.load(investigation_id)
    if not inv:
        raise HTTPException(404, "Investigation not found")
    inv.messages = []
    store.save(inv)
    return JSONResponse({"status": "ok"})


@router.post("/api/investigation/{investigation_id}/complete")
async def complete_investigation(investigation_id: str):
    inv = store.load(investigation_id)
    if not inv:
        raise HTTPException(404, "Investigation not found")
    inv.status = "completed"
    store.save(inv)
    return JSONResponse({"status": "ok"})


@router.get("/investigation/{investigation_id}/report", response_class=HTMLResponse)
async def view_report(request: Request, investigation_id: str):
    inv = store.load(investigation_id)
    if not inv:
        raise HTTPException(404, "Investigation not found")

    report_md = generate_report(inv)

    import markdown
    report_html = markdown.markdown(
        report_md,
        extensions=["extra", "codehilite", "tables"],
    )

    return templates.TemplateResponse(
        "report.html",
        {
            "request": request,
            "inv": inv,
            "report_html": report_html,
            "report_md": report_md,
        },
    )


@router.get("/api/investigation/{investigation_id}/report", response_class=HTMLResponse)
async def get_report_markdown(investigation_id: str):
    inv = store.load(investigation_id)
    if not inv:
        raise HTTPException(404, "Investigation not found")
    return generate_report(inv)
