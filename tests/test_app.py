"""End-to-end test with a fake Gemini model: intake, quick draft, rendering, download, access control."""
import io, json, os, sys, time, zipfile
from pathlib import Path

os.environ["AUTH_MODE"] = "none"
os.environ["WORK_DIR"] = "/tmp/sa-test-jobs"
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient  # noqa: E402
from app import main, agent  # noqa: E402

EXAMPLE = json.loads((Path(main.HERE) / "examples" / "public-cloud-ai.json").read_text())


class FakeModel:
    def __init__(self):
        self.calls = []
        self.bad_first = True

    def generate(self, prompt, json_schema=None, history=None, notify=None):
        self.calls.append(prompt[:40])
        if prompt.startswith("INTAKE"):
            asked = sum(1 for h in history if h["role"] == "model")
            return json.dumps({"ready": asked >= 2, "question": "" if asked >= 2 else f"Question {asked + 1}?"})
        if prompt.startswith("DESIGN STEP (repair)"):
            return json.dumps({"slug": "test-opportunity", "title": "Test opportunity", "design_brief": "Options A/B/C.", "spec": EXAMPLE})
        if prompt.startswith("DESIGN"):
            bad = json.loads(json.dumps(EXAMPLE)); bad["components"][0]["kind"] = "not_a_kind"   # force one repair
            return json.dumps({"slug": "test-opportunity", "title": "Test opportunity", "design_brief": "Options A/B/C.", "spec": bad})
        if prompt.startswith("PACKAGE"):
            return ("## Section 0 — Mode and assumptions\n\nAssumed things. <script>alert(1)</script>\n\n"
                    "## Section 5 — Recommended architecture\n\nNarrative.\n\n{{SPEC_TABLES}}\n\n{{DIAGRAMS}}\n\n{{SERVICE_MAPPING}}\n\n"
                    "Differences.\n\n## Section 9 — Open questions and items to verify\n\n- Model Armor (v)\n")
        raise AssertionError(prompt[:60])


def wait(c, jid):
    for _ in range(120):
        s = c.get(f"/jobs/{jid}/status").json()
        if s["status"] != "running":
            return s
        time.sleep(0.5)
    raise AssertionError("timeout")


def test_full_flow():
    fake = FakeModel()
    main._model = fake
    c = TestClient(main.app)
    assert c.get("/health").json() == {"ok": True}
    assert "New opportunity" in c.get("/").text

    # guided intake: two questions then ready
    r = c.post("/intake", data={"brief": "State agency wants an AI assistant for permit records."}, follow_redirects=True)
    assert "Question 1?" in r.text
    iid = str(r.url).rstrip("/").split("/")[-1]
    r = c.post(f"/intake/{iid}/answer", data={"answer": "400 officers"}, follow_redirects=True)
    assert "Question 2?" in r.text
    r = c.post(f"/intake/{iid}/answer", data={"answer": "Personal data, keep in Malaysia"}, follow_redirects=True)
    assert "enough to draft" in r.text
    r = c.post(f"/intake/{iid}/draft", follow_redirects=False)
    jid = r.headers["location"].split("/")[-1]
    s = wait(c, jid)
    assert s["status"] == "done", s
    assert any("Fixing the architecture spec" in l for l in main.JOBS[jid]["log"]), "repair loop not exercised"

    page = c.get(f"/jobs/{jid}").text
    assert "<script>alert" not in page                       # model HTML sanitised
    assert f"/jobs/{jid}/files/diagrams/aws.png" in page      # images rewritten to authenticated route
    assert "Amazon Bedrock" in page and "Gemini via Vertex AI" in page   # service mapping inserted
    assert "| ID | Name |" not in page and "<table>" in page   # spec tables rendered as HTML

    img = c.get(f"/jobs/{jid}/files/diagrams/gcp.png")
    assert img.status_code == 200 and img.content[:4] == b"\x89PNG"
    assert c.get(f"/jobs/{jid}/files/../../etc/passwd").status_code in (200, 404) and "root:" not in c.get(f"/jobs/{jid}/files/../../etc/passwd").text

    z = zipfile.ZipFile(io.BytesIO(c.get(f"/jobs/{jid}/download").content))
    names = set(z.namelist())
    for n in ["proposal.md", "proposal.html", "spec.json", "diagrams/aws.png", "diagrams/azure.png", "diagrams/gcp.png",
              "diagrams/generic.png", "diagrams/multicloud.drawio", "diagrams/service_mapping.md"]:
        assert f"test-opportunity/{n}" in names, n
    md = z.read("test-opportunity/proposal.md").decode()
    assert "{{" not in md and "](diagrams/aws.png)" in md

    # quick draft path and one-running-job limit
    r = c.post("/quick", data={"brief": "A GLC wants a data platform for asset inspection records across states."}, follow_redirects=False)
    jid2 = r.headers["location"].split("/")[-1]
    assert wait(c, jid2)["status"] == "done"

    # another user cannot see the job
    main.JOBS[jid2]["owner"] = "someone@else.com"
    assert "Not found" in c.get(f"/jobs/{jid2}").text


def test_allowlist():
    main.ALLOWED_USERS.clear(); main.ALLOWED_USERS.update({"jimbh1515", "colleague"})
    assert main.user_allowed("Jimbh1515")      # GitHub usernames are case-insensitive
    assert main.user_allowed("colleague")
    assert not main.user_allowed("jimbh15150")
    assert not main.user_allowed("")


def test_github_signin_flow(monkeypatch):
    import urllib.parse
    monkeypatch.setattr(main, "AUTH_DISABLED", False)
    monkeypatch.setenv("GITHUB_CLIENT_ID", "Iv1.test"); monkeypatch.setenv("GITHUB_CLIENT_SECRET", "secret")
    monkeypatch.setenv("PUBLIC_BASE_URL", "https://sa.onrender.com")
    main.oauth.github.client_id = "Iv1.test"; main.oauth.github.client_secret = "secret"
    main.ALLOWED_USERS.clear(); main.ALLOWED_USERS.add("jimbh1515")
    c = TestClient(main.app, base_url="https://testserver")

    assert c.get("/", follow_redirects=False).headers["location"] == "/login"
    assert "Sign in with GitHub" in c.get("/login").text
    r = c.get("/login/github", follow_redirects=False)
    loc = urllib.parse.urlparse(r.headers["location"]); q = urllib.parse.parse_qs(loc.query)
    assert loc.netloc == "github.com" and loc.path == "/login/oauth/authorize"
    assert q["redirect_uri"] == ["https://sa.onrender.com/auth/callback"] and q["scope"] == ["read:user"] and "state" in q

    class Resp:
        def __init__(self, login): self._l = login
        def raise_for_status(self): pass
        def json(self): return {"login": self._l}

    async def token(request): return {"access_token": "t", "token_type": "bearer"}
    monkeypatch.setattr(main.oauth.github, "authorize_access_token", token)

    async def get_denied(path, token=None): return Resp("Stranger")
    monkeypatch.setattr(main.oauth.github, "get", get_denied)
    assert "not on the list" in c.get("/auth/callback?code=x&state=y").text
    assert c.get("/", follow_redirects=False).headers["location"] == "/login"

    async def get_ok(path, token=None): return Resp("Jimbh1515")
    monkeypatch.setattr(main.oauth.github, "get", get_ok)
    r = c.get("/auth/callback?code=x&state=y", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/"
    home = c.get("/")
    assert "New opportunity" in home.text and "jimbh1515" in home.text
    c.get("/logout")
    assert c.get("/", follow_redirects=False).headers["location"] == "/login"


def test_open_mode_isolation_and_global_cap(monkeypatch):
    monkeypatch.setattr(main, "AUTH_DISABLED", True)
    main._model = FakeModel()
    a, b = TestClient(main.app), TestClient(main.app)          # two different browsers
    assert "New opportunity" in a.get("/").text                # no sign-in needed
    assert a.get("/login", follow_redirects=False).headers["location"] == "/"
    r = a.post("/quick", data={"brief": "A GLC wants a data platform for asset inspection records across states."}, follow_redirects=False)
    jid = r.headers["location"].split("/")[-1]
    assert wait(a, jid)["status"] == "done"
    assert "Not found" in b.get(f"/jobs/{jid}").text            # browser B cannot open browser A's result
    assert jid not in b.get("/").text
    monkeypatch.setattr(main, "MAX_JOBS_TOTAL_PER_DAY", main.jobs_today())   # cap reached for everyone
    r = b.post("/quick", data={"brief": "Another agency wants a citizen chatbot for licence renewals online."}, follow_redirects=True)
    assert "daily limit for everyone" in r.text


def test_intake_survives_reloads_and_failures(monkeypatch):
    monkeypatch.setattr(main, "AUTH_DISABLED", True)
    fake = FakeModel(); main._model = fake
    c = TestClient(main.app)

    # the screenshot case: a plain visit to /intake or /quick must not be a 405
    for path in ("/intake", "/quick"):
        r = c.get(path)
        assert r.status_code == 200 and "Please submit again" in r.text

    r = c.post("/intake", data={"brief": "State agency wants an AI assistant for permit records."}, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"].startswith("/intake/")
    iid = r.headers["location"].split("/")[-1]
    page1 = c.get(f"/intake/{iid}").text
    assert "Question 1?" in page1
    calls = len(fake.calls)
    assert "Question 1?" in c.get(f"/intake/{iid}").text          # refresh: same question,
    assert len(fake.calls) == calls                                # and no extra AI call
    assert c.get(f"/intake/{iid}/answer", follow_redirects=False).headers["location"] == f"/intake/{iid}"

    # AI failure shows Try again, then recovers on retry
    real = fake.generate
    def boom(*a, **k): raise RuntimeError("503 model overloaded")
    fake.generate = boom
    c.post(f"/intake/{iid}/answer", data={"answer": "400 officers"}, follow_redirects=False)
    r = c.get(f"/intake/{iid}")
    assert "did not respond" in r.text and "Try again" in r.text
    fake.generate = real
    assert "Question 2?" in c.get(f"/intake/{iid}").text
    assert c.get(f"/intake/{iid}").text.count("400 officers") == 1  # answer recorded once

    # double submit of "draft" goes to the same job
    j1 = c.post(f"/intake/{iid}/draft", follow_redirects=False).headers["location"]
    j2 = c.post(f"/intake/{iid}/draft", follow_redirects=False).headers["location"]
    assert j1 == j2
    assert wait(c, j1.split("/")[-1])["status"] == "done"

    # expired intake gives a clear message
    assert "expired" in c.get("/intake/doesnotexist").text


def test_retries_fallback_and_friendly_errors(monkeypatch):
    from google.genai import errors
    monkeypatch.setenv("GEMINI_RETRY_DELAYS", "1,2")
    busy = lambda: errors.ServerError(503, {"error": {"code": 503, "message": "high demand", "status": "UNAVAILABLE"}})
    slept, notes, tried = [], [], []

    def flaky(model):                       # main model busy 3 times, backup succeeds
        tried.append(model)
        if model == "main":
            raise busy()
        return "ok"
    assert agent.with_retries(flaky, "main", "backup", notes.append, slept.append) == "ok"
    assert tried == ["main", "main", "main", "backup"] and slept == [1, 2]
    assert any("backup model" in n for n in notes)

    def always_busy(model): raise busy()
    try:
        agent.with_retries(always_busy, "main", "backup", sleep=lambda s: None); raise AssertionError
    except errors.ServerError as e:
        assert "overloaded" in agent.friendly_error(e)

    def bad_key(model): raise errors.ClientError(400, {"error": {"code": 400, "message": "API key not valid", "status": "INVALID_ARGUMENT"}})
    calls = []
    try:
        agent.with_retries(lambda m: (calls.append(m), bad_key(m)), "main", "backup", sleep=lambda s: None)
    except errors.ClientError as e:
        assert calls == ["main"]            # not retried
        assert "GEMINI_API_KEY" in agent.friendly_error(e)


def test_failed_job_retry_button(monkeypatch):
    from google.genai import errors
    monkeypatch.setattr(main, "AUTH_DISABLED", True)
    fake = FakeModel(); main._model = fake
    real = fake.generate
    def busy(*a, **k): raise errors.ServerError(503, {"error": {"code": 503, "message": "high demand", "status": "UNAVAILABLE"}})
    fake.generate = busy
    c = TestClient(main.app)
    r = c.post("/quick", data={"brief": "A GLC wants a data platform for asset inspection records across states."}, follow_redirects=False)
    jid = r.headers["location"].split("/")[-1]
    assert wait(c, jid)["status"] == "failed"
    pg = c.get(f"/jobs/{jid}").text
    assert "overloaded" in pg and "Try again" in pg and "Technical details" in pg
    fake.generate = real
    r = c.post(f"/jobs/{jid}/retry", follow_redirects=False)
    new = r.headers["location"].split("/")[-1]
    assert new != jid and wait(c, new)["status"] == "done"
    assert c.post(f"/jobs/{jid}/retry", follow_redirects=False).headers["location"].endswith(new)   # no duplicate retries
