"""Solutions Architect web app: GitHub sign-in, guided intake, quick draft, multi-cloud diagrams."""
import io
import logging
import os
import re
import secrets
import shutil
import threading
import time
import uuid
import zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import markdown as md_lib
import nh3
from authlib.integrations.starlette_client import OAuth
from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from . import agent

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("app")

HERE = Path(__file__).parent
ON_RENDER = os.environ.get("RENDER", "").lower() == "true"
# AUTH_MODE: "none" (default, open access for internal testing) or "github" (GitHub sign-in with an allowlist)
AUTH_MODE = os.environ.get("AUTH_MODE", "none").strip().lower()
AUTH_DISABLED = AUTH_MODE != "github"
MAX_JOBS_TOTAL_PER_DAY = int(os.environ.get("MAX_JOBS_TOTAL_PER_DAY", "30"))   # protects Gemini credit when open
WORK_ROOT = Path(os.environ.get("WORK_DIR", "/tmp/sa-jobs"))
JOB_TTL_SECONDS = int(os.environ.get("JOB_TTL_HOURS", "12")) * 3600
MAX_JOBS_PER_DAY = int(os.environ.get("MAX_JOBS_PER_USER_PER_DAY", "20"))
MAX_INPUT_CHARS = 20000
ALLOWED_USERS = {u.strip().lower().lstrip("@") for u in os.environ.get("ALLOWED_GITHUB_USERS", "").split(",") if u.strip()}

app = FastAPI(title="Solutions Architect", docs_url=None, redoc_url=None, openapi_url=None)
app.add_middleware(SessionMiddleware, secret_key=os.environ.get("SESSION_SECRET") or secrets.token_urlsafe(32),
                   https_only=ON_RENDER, same_site="lax", max_age=8 * 3600)
app.mount("/static", StaticFiles(directory=HERE / "static"), name="static")
templates = Jinja2Templates(directory=HERE / "templates")

oauth = OAuth()
oauth.register(name="github",
               client_id=os.environ.get("GITHUB_CLIENT_ID"), client_secret=os.environ.get("GITHUB_CLIENT_SECRET"),
               authorize_url="https://github.com/login/oauth/authorize",
               access_token_url="https://github.com/login/oauth/access_token",
               api_base_url="https://api.github.com/",
               client_kwargs={"scope": "read:user"})   # read-only profile; no repository access

_model = None
_model_lock = threading.Lock()
executor = ThreadPoolExecutor(max_workers=int(os.environ.get("MAX_CONCURRENT_JOBS", "2")))
JOBS: dict = {}       # job_id -> dict
INTAKES: dict = {}    # intake_id -> dict
STATE_LOCK = threading.Lock()


def get_model():
    global _model
    with _model_lock:
        if _model is None:
            _model = agent.Model()
        return _model


# ------------------------------------------------------------------ auth helpers
def user_allowed(login: str) -> bool:
    return bool(login) and login.lower() in ALLOWED_USERS


def current_user(request: Request):
    if AUTH_DISABLED:
        # No sign-in: give each browser its own anonymous id so visitors only see their own proposals.
        if "anon" not in request.session:
            request.session["anon"] = "guest-" + secrets.token_hex(4)
        return request.session["anon"]
    return request.session.get("user")


def require_user(request: Request) -> str:
    u = current_user(request)
    if not u:
        raise HTTPException(status_code=303, headers={"Location": "/login"})
    return u


def redirect_uri(request: Request) -> str:
    base = os.environ.get("PUBLIC_BASE_URL") or os.environ.get("RENDER_EXTERNAL_URL")
    return (base.rstrip("/") + "/auth/callback") if base else str(request.url_for("auth_callback"))


def page(request: Request, name: str, **ctx):
    ctx.update(request=request, user=current_user(request), auth_disabled=AUTH_DISABLED)
    return templates.TemplateResponse(request, name, ctx)


# ------------------------------------------------------------------ housekeeping
def cleanup():
    now = time.time()
    with STATE_LOCK:
        for jid in [j for j, v in JOBS.items() if now - v["created"] > JOB_TTL_SECONDS]:
            shutil.rmtree(JOBS[jid]["dir"], ignore_errors=True)
            JOBS.pop(jid, None)
        for iid in [i for i, v in INTAKES.items() if now - v["created"] > JOB_TTL_SECONDS]:
            INTAKES.pop(iid, None)


def jobs_today(user: str | None = None) -> int:
    since = time.time() - 86400
    return sum(1 for j in JOBS.values() if (user is None or j["owner"] == user) and j["created"] > since)


def own_job(job_id: str, user: str) -> dict:
    j = JOBS.get(job_id)
    if not j or j["owner"] != user:
        raise HTTPException(404, "Not found (results are kept for a limited time and are lost when the server restarts).")
    return j


# ------------------------------------------------------------------ routes: auth
@app.get("/health")
def health():
    return {"ok": True}


@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    if AUTH_DISABLED or current_user(request):
        return RedirectResponse("/", 303)
    configured = bool(os.environ.get("GITHUB_CLIENT_ID") and os.environ.get("GITHUB_CLIENT_SECRET"))
    return page(request, "login.html", configured=configured)


@app.get("/login/github")
async def login_github(request: Request):
    if AUTH_DISABLED:
        return RedirectResponse("/", 303)
    return await oauth.github.authorize_redirect(request, redirect_uri(request))


@app.get("/auth/callback", name="auth_callback")
async def auth_callback(request: Request):
    if AUTH_DISABLED:
        return RedirectResponse("/", 303)
    try:
        token = await oauth.github.authorize_access_token(request)
        resp = await oauth.github.get("user", token=token)
        resp.raise_for_status()
        login = (resp.json().get("login") or "").lower()
    except Exception as e:  # OAuthError, network or API errors
        log.warning("GitHub sign-in error: %s", e)
        return page(request, "message.html", title="Sign-in failed", message="GitHub sign-in did not complete. Please try again.")
    if not user_allowed(login):
        log.info("Denied sign-in for GitHub user %s", login)
        return page(request, "message.html", title="Access not granted",
                    message=f"GitHub user '{login or 'unknown'}' is not on the list of approved users. Ask the administrator to add it.")
    request.session.clear()
    request.session["user"] = login
    return RedirectResponse("/", 303)


@app.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/" if AUTH_DISABLED else "/login", 303)


# ------------------------------------------------------------------ routes: app
@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    user = require_user(request)
    cleanup()
    mine = sorted((j for j in JOBS.values() if j["owner"] == user), key=lambda j: -j["created"])
    return page(request, "index.html", jobs=mine, max_chars=MAX_INPUT_CHARS)


def _start_job(user: str, brief: str, mode: str) -> str:
    with STATE_LOCK:
        if any(j["owner"] == user and j["status"] == "running" for j in JOBS.values()):
            raise HTTPException(429, "You already have a proposal being generated. Wait for it to finish.")
        if jobs_today(user) >= MAX_JOBS_PER_DAY:
            raise HTTPException(429, "Daily limit reached. Try again tomorrow or ask the administrator to raise it.")
        if jobs_today() >= MAX_JOBS_TOTAL_PER_DAY:
            raise HTTPException(429, "The app's daily limit for everyone has been reached. Try again tomorrow or raise MAX_JOBS_TOTAL_PER_DAY in Render.")
        jid = uuid.uuid4().hex
        d = WORK_ROOT / jid
        JOBS[jid] = {"id": jid, "owner": user, "mode": mode, "brief": brief, "status": "running", "log": ["Queued"],
                     "created": time.time(), "dir": d, "title": "Generating…", "slug": "proposal", "error": None}

    def progress(msg):
        JOBS[jid]["log"].append(msg)

    def work():
        try:
            meta = agent.run_pipeline(get_model(), brief, mode, d, progress)
            JOBS[jid].update(meta, status="done")
        except Exception as e:  # report every failure to the user, keep details in logs
            log.exception("Job %s failed", jid)
            JOBS[jid].update(status="failed", error=str(e)[:2000])

    executor.submit(work)
    return jid


@app.post("/quick")
def quick(request: Request, brief: str = Form(...)):
    user = require_user(request)
    brief = brief.strip()[:MAX_INPUT_CHARS]
    if len(brief) < 30:
        return page(request, "message.html", title="Tell me a little more",
                    message="Describe the opportunity in at least a sentence or two: the agency or GLC, the problem, and anything you know.")
    jid = _start_job(user, brief, "Quick draft")
    return RedirectResponse(f"/jobs/{jid}", 303)


@app.post("/intake")
def intake_start(request: Request, brief: str = Form(...)):
    user = require_user(request)
    brief = brief.strip()[:MAX_INPUT_CHARS]
    iid = uuid.uuid4().hex
    INTAKES[iid] = {"owner": user, "created": time.time(), "history": [{"role": "user", "text": brief}], "ready": False}
    return _intake_step(request, iid)


def _intake_step(request: Request, iid: str):
    it = INTAKES[iid]
    try:
        nxt = agent.intake_next(get_model(), it["history"])
    except Exception as e:
        log.exception("Intake failed")
        return page(request, "message.html", title="The AI service did not respond", message=str(e)[:500])
    asked = sum(1 for h in it["history"] if h["role"] == "model")
    if nxt["ready"] or not nxt["question"] or asked >= 8:
        it["ready"] = True
    else:
        it["history"].append({"role": "model", "text": nxt["question"]})
    return RedirectResponse(f"/intake/{iid}", 303)


@app.get("/intake/{iid}", response_class=HTMLResponse)
def intake_view(request: Request, iid: str):
    user = require_user(request)
    it = INTAKES.get(iid)
    if not it or it["owner"] != user:
        raise HTTPException(404, "Intake not found or expired.")
    return page(request, "intake.html", iid=iid, history=it["history"], ready=it["ready"])


@app.post("/intake/{iid}/answer")
def intake_answer(request: Request, iid: str, answer: str = Form(...)):
    user = require_user(request)
    it = INTAKES.get(iid)
    if not it or it["owner"] != user:
        raise HTTPException(404, "Intake not found or expired.")
    it["history"].append({"role": "user", "text": answer.strip()[:MAX_INPUT_CHARS]})
    return _intake_step(request, iid)


@app.post("/intake/{iid}/draft")
def intake_draft(request: Request, iid: str):
    user = require_user(request)
    it = INTAKES.get(iid)
    if not it or it["owner"] != user:
        raise HTTPException(404, "Intake not found or expired.")
    transcript = "\n\n".join(("Architect asked: " if h["role"] == "model" else "User: ") + h["text"] for h in it["history"])
    jid = _start_job(user, transcript, "Guided intake")
    return RedirectResponse(f"/jobs/{jid}", 303)


ALLOWED_TAGS = {"h1", "h2", "h3", "h4", "h5", "p", "ul", "ol", "li", "strong", "em", "code", "pre", "blockquote",
                "table", "thead", "tbody", "tr", "th", "td", "a", "img", "hr", "br", "span"}


def proposal_html(job: dict) -> str:
    text = (job["dir"] / "proposal.md").read_text(encoding="utf-8")
    text = text.replace("](diagrams/", f"](/jobs/{job['id']}/files/diagrams/")
    raw = md_lib.markdown(text, extensions=["tables", "fenced_code", "sane_lists"])
    return nh3.clean(raw, tags=ALLOWED_TAGS, attributes={"a": {"href"}, "img": {"src", "alt"}},
                     url_schemes={"https"}, link_rel="noopener noreferrer")


@app.get("/jobs/{jid}", response_class=HTMLResponse)
def job_view(request: Request, jid: str):
    user = require_user(request)
    j = own_job(jid, user)
    body = proposal_html(j) if j["status"] == "done" else ""
    return page(request, "job.html", job=j, body=body)


@app.get("/jobs/{jid}/status")
def job_status(request: Request, jid: str):
    user = require_user(request)
    j = own_job(jid, user)
    return JSONResponse({"status": j["status"], "log": j["log"][-6:], "error": j["error"]})


SAFE_FILE = re.compile(r"^(proposal\.md|design_brief\.md|spec\.json|diagrams/[a-z_]+\.(png|drawio|md))$")


@app.get("/jobs/{jid}/files/{path:path}")
def job_file(request: Request, jid: str, path: str):
    user = require_user(request)
    j = own_job(jid, user)
    if not SAFE_FILE.match(path):
        raise HTTPException(404)
    f = j["dir"] / path
    if not f.is_file():
        raise HTTPException(404)
    return FileResponse(f, filename=f.name if not f.suffix == ".png" else None)


@app.get("/jobs/{jid}/download")
def job_download(request: Request, jid: str):
    user = require_user(request)
    j = own_job(jid, user)
    if j["status"] != "done":
        raise HTTPException(409, "Not ready yet.")
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted(j["dir"].rglob("*")):
            rel = f.relative_to(j["dir"]).as_posix()
            if f.is_file() and SAFE_FILE.match(rel):
                z.write(f, f"{j['slug']}/{rel}")
        html_doc = ("<!doctype html><meta charset='utf-8'><title>" + nh3.clean(j["title"]) + "</title>"
                    "<style>body{font-family:system-ui,sans-serif;max-width:980px;margin:2rem auto;padding:0 1rem;line-height:1.5}"
                    "table{border-collapse:collapse}td,th{border:1px solid #ccc;padding:4px 8px;vertical-align:top}img{max-width:100%}</style>"
                    + proposal_html(j).replace(f"/jobs/{j['id']}/files/", ""))
        z.writestr(f"{j['slug']}/proposal.html", html_doc)
    return Response(buf.getvalue(), media_type="application/zip",
                    headers={"Content-Disposition": f'attachment; filename="{j["slug"]}.zip"'})


@app.exception_handler(HTTPException)
async def http_error(request: Request, exc: HTTPException):
    if exc.status_code == 303 and exc.headers and "Location" in exc.headers:
        return RedirectResponse(exc.headers["Location"], 303)
    return page(request, "message.html", title="Something needs attention", message=str(exc.detail))
