"""End-to-end test with a fake Gemini model: intake, quick draft, rendering, download, access control."""
import io, json, os, sys, time, zipfile
from pathlib import Path

os.environ["AUTH_DISABLED"] = "1"
os.environ.pop("RENDER", None)
os.environ["WORK_DIR"] = "/tmp/sa-test-jobs"
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient  # noqa: E402
from app import main, agent  # noqa: E402

EXAMPLE = json.loads((Path(main.HERE) / "examples" / "public-cloud-ai.json").read_text())


class FakeModel:
    def __init__(self):
        self.calls = []
        self.bad_first = True

    def generate(self, prompt, json_schema=None, history=None):
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
    main.ALLOWED_EMAILS.clear(); main.ALLOWED_DOMAINS.clear()
    main.ALLOWED_EMAILS.add("me@gmail.com"); main.ALLOWED_DOMAINS.add("gamuda.com.my")
    assert main.email_allowed("ME@gmail.com")
    assert main.email_allowed("x@gamuda.com.my")
    assert not main.email_allowed("x@evil-gamuda.com.my")
    assert not main.email_allowed("x@gmail.com")
    assert not main.email_allowed("")
