"""Gemini-backed proposal agent: intake, design (spec), render, package."""
import json
import logging
import os
import re
import subprocess
import sys
import time
from pathlib import Path

log = logging.getLogger("agent")
HERE = Path(__file__).parent
KNOWLEDGE = HERE / "knowledge"
RENDERER = HERE / "renderer" / "render_multicloud.py"
MAX_REPAIRS = 2


# ------------------------------------------------------------------ knowledge
def _strip_frontmatter(text: str) -> str:
    return re.sub(r"^---\n.*?\n---\n", "", text, count=1, flags=re.S)


def system_instruction() -> str:
    parts = []
    for f in sorted(KNOWLEDGE.glob("*.md")):
        parts.append(f"<file name=\"{f.name}\">\n{_strip_frontmatter(f.read_text(encoding='utf-8'))}\n</file>")
    return ("You are the solutions architect described in the files below. Follow them exactly. "
            "File 10 explains how you work inside this web app and overrides tool or file instructions elsewhere.\n\n"
            + "\n\n".join(parts))


# ------------------------------------------------------------------ model client
class Model:
    """Thin wrapper so tests can substitute a fake."""

    def __init__(self):
        from google import genai
        from google.genai import types
        self.types = types
        key = os.environ.get("GEMINI_API_KEY")
        if not key:
            raise RuntimeError("GEMINI_API_KEY is not set")
        timeout_ms = int(os.environ.get("GEMINI_TIMEOUT_SECONDS", "600")) * 1000
        self.client = genai.Client(api_key=key, http_options=types.HttpOptions(timeout=timeout_ms))
        self.model = os.environ.get("GEMINI_MODEL", "gemini-3.8-flash")
        self.fallback = os.environ.get("GEMINI_FALLBACK_MODEL", "gemini-3.5-flash").strip() or None
        self.sys = system_instruction()

    def _call(self, model: str, contents, cfg):
        resp = self.client.models.generate_content(model=model, contents=contents,
                                                   config=self.types.GenerateContentConfig(**cfg))
        text = resp.text or ""
        if not text.strip():
            raise RuntimeError("The model returned an empty response (it may have been blocked or hit a limit).")
        return text

    def generate(self, prompt: str, json_schema: dict | None = None, history: list | None = None,
                 notify=lambda m: None) -> str:
        t = self.types
        contents = []
        for turn in history or []:
            contents.append(t.Content(role=turn["role"], parts=[t.Part(text=turn["text"])]))
        contents.append(t.Content(role="user", parts=[t.Part(text=prompt)]))
        cfg = dict(system_instruction=self.sys, temperature=0.3)
        if os.environ.get("GEMINI_MAX_OUTPUT_TOKENS"):
            cfg["max_output_tokens"] = int(os.environ["GEMINI_MAX_OUTPUT_TOKENS"])
        if json_schema:
            cfg.update(response_mime_type="application/json", response_json_schema=json_schema)
        return with_retries(lambda m: self._call(m, contents, cfg), self.model, self.fallback, notify)


# ------------------------------------------------------------------ retries and friendly errors
RETRYABLE = {429, 500, 502, 503, 504}


def _status(e) -> int | None:
    code = getattr(e, "code", None)
    return code if isinstance(code, int) else None


def with_retries(call, model: str, fallback: str | None, notify=lambda m: None, sleep=time.sleep):
    """Try the main model with backoff on busy/overloaded errors, then the fallback model once with backoff."""
    delays = [int(x) for x in os.environ.get("GEMINI_RETRY_DELAYS", "5,15,30").split(",") if x.strip()]
    models = [model] + ([fallback] if fallback and fallback != model else [])
    last = None
    for mi, m in enumerate(models):
        if mi:
            notify(f"Main model still busy; switching to backup model {m}")
        for attempt in range(len(delays) + 1):
            try:
                return call(m)
            except Exception as e:
                last = e
                code = _status(e)
                if code not in RETRYABLE:
                    raise
                if attempt < len(delays):
                    notify(f"Gemini is busy ({code}); retrying in {delays[attempt]} s")
                    log.warning("Gemini %s on %s, retry %d in %ss", code, m, attempt + 1, delays[attempt])
                    sleep(delays[attempt])
    raise last


def friendly_error(e: Exception) -> str:
    code = _status(e)
    text = str(e)
    if code in (500, 502, 503, 504):
        return ("Google's Gemini service is overloaded right now, even after several retries and the backup model. "
                "This is on Google's side and usually clears within minutes. Use Try again shortly.")
    if code == 429:
        return ("Gemini rate limit or quota reached for this API key. Wait a minute and try again; if it keeps happening, "
                "check the key's quota and billing in Google AI Studio.")
    if code in (401, 403) or "API key" in text or "API_KEY" in text:
        return "Gemini rejected the API key. Check GEMINI_API_KEY in Render → Environment."
    if code == 404 or "not found" in text.lower() and "model" in text.lower():
        return "The Gemini model name was not found. Check GEMINI_MODEL in Render → Environment against Google's current model list."
    if "validation" in text.lower():
        return "The AI produced an architecture that failed validation even after repairs. Try again, or add more detail to the opportunity."
    return "Something went wrong while generating the proposal. Try again; if it repeats, share the technical details with the maintainer."


# ------------------------------------------------------------------ schemas
INTAKE_SCHEMA = {
    "type": "object",
    "properties": {
        "ready": {"type": "boolean", "description": "true when enough information has been gathered to design"},
        "question": {"type": "string", "description": "the single next question; empty when ready"},
    },
    "required": ["ready", "question"],
}

_container = {"type": "object", "properties": {
    "id": {"type": "string"}, "label": {"type": "string"},
    "type": {"type": "string", "enum": ["environment", "subsystem", "platform", "provider_zone", "onprem_site"]},
    "parent": {"type": "string"}, "zone_suffix": {"type": "string"}}, "required": ["id", "label", "type"]}
_component = {"type": "object", "properties": {
    "id": {"type": "string"}, "kind": {"type": "string"}, "label": {"type": "string"},
    "placement": {"type": "string", "enum": ["cloud", "onprem", "sovereign", "external"]},
    "container": {"type": "string"}, "tech": {"type": "string"}, "layer": {"type": "integer"},
    "notes": {"type": "string"}}, "required": ["id", "kind", "label", "placement"]}
_flow = {"type": "object", "properties": {
    "id": {"type": "string"}, "from": {"type": "string"}, "to": {"type": "string"}, "label": {"type": "string"},
    "type": {"type": "string", "enum": ["request", "data", "telemetry"]},
    "crosses_boundary": {"type": "boolean"}, "data_class": {"type": "string"}}, "required": ["id", "from", "to", "type"]}

DESIGN_SCHEMA = {
    "type": "object",
    "properties": {
        "slug": {"type": "string", "description": "short lowercase-hyphenated name for the opportunity"},
        "title": {"type": "string"},
        "design_brief": {"type": "string", "description": "Markdown: the three options, weighted scores, recommendation and key assumptions"},
        "spec": {"type": "object", "properties": {
            "title": {"type": "string"},
            "containers": {"type": "array", "items": _container},
            "components": {"type": "array", "items": _component},
            "flows": {"type": "array", "items": _flow}},
            "required": ["title", "containers", "components", "flows"]},
    },
    "required": ["slug", "title", "design_brief", "spec"],
}


def _loads(text: str) -> dict:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text)
    return json.loads(text)


# ------------------------------------------------------------------ steps
def intake_next(model, history: list) -> dict:
    """history: [{'role': 'user'|'model', 'text': ...}] — returns {'ready': bool, 'question': str}."""
    prompt = ("INTAKE STEP. Based on the conversation so far, return the single next clarifying question, "
              "or ready=true if you have enough to design. Return JSON only.")
    out = _loads(model.generate(prompt, INTAKE_SCHEMA, history))
    return {"ready": bool(out.get("ready")), "question": str(out.get("question", "")).strip()}


def _validate_spec(spec: dict, workdir: Path) -> str | None:
    """Return None if valid, else the renderer's error text."""
    p = workdir / "spec.json"
    p.write_text(json.dumps(spec, indent=1), encoding="utf-8")
    r = subprocess.run([sys.executable, str(RENDERER), str(p), "--out", str(workdir / "_validate"), "--targets", "generic", "--no-png"],
                       capture_output=True, text=True, timeout=120)
    return None if r.returncode == 0 else (r.stderr or r.stdout)[-3000:]


def _clean_spec(spec: dict) -> dict:
    """Drop empty optional strings the model may emit, which would otherwise fail validation."""
    for c in spec.get("containers", []):
        for k in ("parent", "zone_suffix"):
            if not c.get(k):
                c.pop(k, None)
    for n in spec.get("components", []):
        for k in ("container", "tech", "notes"):
            if not n.get(k):
                n.pop(k, None)
    for e in spec.get("flows", []):
        if not e.get("crosses_boundary"):
            e.pop("crosses_boundary", None)
            if not e.get("data_class"):
                e.pop("data_class", None)
    return spec


def design(model, brief: str, mode: str, workdir: Path, progress=lambda m: None) -> dict:
    prompt = (f"DESIGN STEP. Mode: {mode}.\n\nOpportunity information:\n<<<\n{brief}\n>>>\n\n"
              "Return the JSON object described in file 10, step 2.")
    progress("Designing options and the recommended architecture")
    out = _loads(model.generate(prompt, DESIGN_SCHEMA, notify=progress))
    for attempt in range(MAX_REPAIRS + 1):
        out["spec"] = _clean_spec(out["spec"])
        err = _validate_spec(out["spec"], workdir)
        if err is None:
            return out
        if attempt == MAX_REPAIRS:
            raise RuntimeError("The architecture spec still failed validation after repairs:\n" + err)
        progress(f"Fixing the architecture spec (attempt {attempt + 1})")
        fix = (f"DESIGN STEP (repair). The app rejected your spec:\n{err}\n\nYour previous object:\n"
               f"{json.dumps(out)}\n\nReturn the full corrected JSON object.")
        out = _loads(model.generate(fix, DESIGN_SCHEMA, notify=progress))
    return out


def render(spec: dict, outdir: Path) -> None:
    p = outdir / "spec.json"
    p.write_text(json.dumps(spec, indent=1), encoding="utf-8")
    r = subprocess.run([sys.executable, str(RENDERER), str(p), "--out", str(outdir / "diagrams")],
                       capture_output=True, text=True, timeout=300)
    if r.returncode != 0:
        raise RuntimeError("Diagram rendering failed:\n" + (r.stderr or r.stdout)[-3000:])
    for junk in (outdir / "diagrams").glob("*.dot"):
        junk.unlink()


def spec_tables(spec: dict) -> str:
    esc = lambda s: str(s or "").replace("|", "/").replace("\n", " ")
    lines = ["**Containers**", "", "| ID | Name | Type | Parent |", "|---|---|---|---|"]
    lines += [f"| {esc(c['id'])} | {esc(c['label'])} | {esc(c['type'])} | {esc(c.get('parent', ''))} |" for c in spec["containers"]]
    lines += ["", "**Components**", "", "| ID | Name | Kind | Placement | Container | Example technology | Layer | Notes |",
              "|---|---|---|---|---|---|---|---|"]
    lines += [f"| {esc(n['id'])} | {esc(n['label'])} | {esc(n['kind'])} | {esc(n['placement'])} | {esc(n.get('container', ''))} | "
              f"{esc(n.get('tech', ''))} | {esc(n.get('layer', ''))} | {esc(n.get('notes', ''))} |" for n in spec["components"]]
    lines += ["", "**Flows**", "", "| ID | From | To | Label | Type | Crosses boundary? (data class) |", "|---|---|---|---|---|---|"]
    lines += [f"| {esc(e['id'])} | {esc(e['from'])} | {esc(e['to'])} | {esc(e.get('label', ''))} | {esc(e.get('type', 'request'))} | "
              f"{'yes — ' + esc(e.get('data_class')) if e.get('crosses_boundary') else 'no'} |" for e in spec["flows"]]
    return "\n".join(lines)


DIAGRAMS_MD = """**5.3a Provider-neutral view**

![Provider-neutral](diagrams/generic.png)

**5.3b Amazon Web Services**

![Amazon Web Services](diagrams/aws.png)

**5.3c Microsoft Azure**

![Microsoft Azure](diagrams/azure.png)

**5.3d Google Cloud**

![Google Cloud](diagrams/gcp.png)

Editable file with all four views: [multicloud.drawio](diagrams/multicloud.drawio). The three cloud views show the recommended design implemented on each provider for comparison; they do not change the recommendation in Section 4."""


def package(model, brief: str, mode: str, design_out: dict, outdir: Path, progress=lambda m: None) -> str:
    mapping = (outdir / "diagrams" / "service_mapping.md").read_text(encoding="utf-8")
    report = (outdir / "diagrams" / "render_report.md").read_text(encoding="utf-8")
    prompt = (f"PACKAGE STEP. Mode: {mode}.\n\nOpportunity information:\n<<<\n{brief}\n>>>\n\n"
              f"Your design brief:\n<<<\n{design_out['design_brief']}\n>>>\n\n"
              f"The architecture spec the app rendered (JSON):\n<<<\n{json.dumps(design_out['spec'], indent=1)}\n>>>\n\n"
              f"Cross-cloud service mapping the app produced:\n<<<\n{mapping}\n>>>\n\n"
              f"Render report (include these items in Section 9):\n<<<\n{report}\n>>>\n\n"
              "Write the full package in Markdown now, Sections 0 to 9, with the three placeholders from file 10. "
              "Return Markdown only, no code fences around the whole document.")
    progress("Writing the proposal package")
    md = model.generate(prompt, notify=progress).strip()
    md = re.sub(r"^```(?:markdown|md)?\s*\n|\n```\s*$", "", md)
    inserts = {"{{SPEC_TABLES}}": spec_tables(design_out["spec"]), "{{DIAGRAMS}}": DIAGRAMS_MD,
               "{{SERVICE_MAPPING}}": re.sub(r"^# .*\n+", "", mapping)}
    missing = []
    for ph, content in inserts.items():
        if ph in md:
            md = md.replace(ph, content, 1).replace(ph, "")
        else:
            missing.append((ph, content))
    if missing:  # model forgot a placeholder: append so nothing is lost
        md += "\n\n## Appendix — generated architecture content\n\n" + "\n\n".join(c for _, c in missing)
    return md


def run_pipeline(model, brief: str, mode: str, outdir: Path, progress=lambda m: None) -> dict:
    outdir.mkdir(parents=True, exist_ok=True)
    d = design(model, brief, mode, outdir, progress)
    progress("Drawing the provider-neutral, AWS, Azure and Google Cloud diagrams")
    render(d["spec"], outdir)
    md = package(model, brief, mode, d, outdir, progress)
    (outdir / "proposal.md").write_text(md, encoding="utf-8")
    (outdir / "design_brief.md").write_text(d["design_brief"], encoding="utf-8")
    progress("Done")
    slug = re.sub(r"[^a-z0-9-]+", "-", (d.get("slug") or "proposal").lower()).strip("-")[:60] or "proposal"
    return {"slug": slug, "title": d.get("title") or "Proposal"}
