import os
import base64
from pathlib import Path
from typing import Optional

import uvicorn
import httpx
from fastapi import FastAPI, Request, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.templating import Jinja2Templates

# Configuration
API_BASE = os.getenv("API_BASE", "http://localhost:8000")
PORT = int(os.getenv("UI_PORT", "8080"))
ROOT_DIR = Path(__file__).resolve().parents[2]
TEMPLATES_DIR = ROOT_DIR / "templates"
STATIC_DIR = ROOT_DIR / "static"

app = FastAPI(title="KYC UI", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Ensure directories exist (for local dev)
TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)
STATIC_DIR.mkdir(parents=True, exist_ok=True)

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


def _to_data_url(file_bytes: bytes, content_type: str) -> str:
    b64 = base64.b64encode(file_bytes).decode("utf-8")
    return f"data:{content_type};base64,{b64}"


@app.get("/")
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request, "api_base": API_BASE})


@app.post("/run-complete")
async def run_complete(
    request: Request,
    id_image: UploadFile = File(...),
    selfie_image: Optional[UploadFile] = File(None),
    document_type: Optional[str] = Form(None),
):
    try:
        id_bytes = await id_image.read()
        id_data_url = _to_data_url(id_bytes, id_image.content_type or "image/jpeg")
        selfie_data_url = None
        if selfie_image is not None:
            selfie_bytes = await selfie_image.read()
            selfie_data_url = _to_data_url(selfie_bytes, selfie_image.content_type or "image/jpeg")

        payload = {
            "image_base64": id_data_url,
            "selfie_base64": selfie_data_url,
            "document_type": document_type,
            "session_id": "ui_session",
            "device_info": {
                "ip": request.client.host if request.client else "0.0.0.0",
                "user_agent": request.headers.get("user-agent", "ui")
            }
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(f"{API_BASE}/complete", json=payload)
            if resp.status_code != 200:
                try:
                    err = resp.json()
                except Exception:
                    err = {"error": resp.text}
                raise HTTPException(status_code=resp.status_code, detail=err)
            result = resp.json()

        return templates.TemplateResponse(
            "result.html",
            {
                "request": request,
                "api_base": API_BASE,
                "result": result,
            },
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail={"error": str(e)})


@app.get("/review")
async def review_queue(request: Request):
    # Minimal file-backed queue to align with CLI console
    data_dir = ROOT_DIR / "review_data"
    cases_file = data_dir / "cases.json"
    data_dir.mkdir(exist_ok=True)
    if cases_file.exists():
        import json
        cases = json.loads(cases_file.read_text(encoding="utf-8"))
    else:
        cases = {}
    return templates.TemplateResponse("review.html", {"request": request, "cases": cases})


@app.post("/review/action")
async def review_action(request: Request, case_id: str = Form(...), action: str = Form(...)):
    import json
    from datetime import datetime, timezone

    data_dir = ROOT_DIR / "review_data"
    cases_file = data_dir / "cases.json"
    audit_log = data_dir / "audit_log.jsonl"
    data_dir.mkdir(exist_ok=True)

    cases = {}
    if cases_file.exists():
        cases = json.loads(cases_file.read_text(encoding="utf-8"))

    case = cases.get(case_id)
    if not case:
        raise HTTPException(status_code=404, detail={"error": "Case not found"})

    old_status = case.get("status", "pending")
    case["status"] = action
    case.setdefault("actions", []).append(
        {
            "action": action,
            "reason": f"action_by_ui:{action}",
            "user": "ui_user",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    )
    cases[case_id] = case
    cases_file.write_text(json.dumps(cases, indent=2, ensure_ascii=False), encoding="utf-8")

    with open(audit_log, "a", encoding="utf-8") as f:
        f.write(
            json.dumps(
                {
                    "case_id": case_id,
                    "old_status": old_status,
                    "new_status": action,
                    "user": "ui_user",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
                ensure_ascii=False,
            )
            + "\n"
        )

    return templates.TemplateResponse("action_ok.html", {"request": request, "case": case})


def run():
    uvicorn.run("src.ui.app:app", host="0.0.0.0", port=PORT, reload=True)


if __name__ == "__main__":
    run()