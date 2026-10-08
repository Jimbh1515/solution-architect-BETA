# Solutions Architect — multi-cloud pre-sales web app

A private web app for Malaysian government and GLC pre-sales. You describe an opportunity, it runs a guided intake (or a quick draft), and returns the full proposal package:

- seven-layer Malaysian policy mapping
- three options (hyperscaler, hybrid, sovereign) with weighted scoring and a recommendation
- the recommended architecture drawn **four times**: provider-neutral, **AWS**, **Azure** and **Google Cloud**, each with that cloud's official icons, as PNGs and an editable draw.io file
- cross-cloud service mapping, MYR cost drivers (no prices), risk register, architecture decision records, and a list of items to verify

It runs on [Render](https://render.com) from this repository, so nothing needs to be installed on your laptop. AI work is done by Google's Gemini API. Sign-in is with Google, limited to the email addresses you approve.

## How it works

```
Browser ──Google sign-in──▶ FastAPI app (Docker on Render, Singapore region)
                              ├─ guided intake: Gemini asks one question at a time
                              ├─ design: Gemini returns options + an architecture spec (JSON)
                              │    └─ the app validates the spec; Gemini repairs it if needed
                              ├─ render: Graphviz + verified icon map → 4 × (PNG + draw.io)
                              ├─ package: Gemini writes Sections 0–9; the app inserts the
                              │    spec tables, diagrams and service mapping it generated
                              └─ download: one zip (Markdown, HTML, PNGs, draw.io, spec)
```

The knowledge files in `app/knowledge/` are the same as the Gemini Gem's (rules, policy reference, service mapping, diagram conventions, output templates). Edit them there and redeploy to change the agent's behaviour.

Nothing is stored permanently. Results stay in server memory for 12 hours and vanish when the service restarts or sleeps, so download what you need.

---

## Deploy: step by step

You need three things: a Gemini API key, a Google sign-in client, and a Render account. Allow about 30 minutes the first time.

> Google and Render change their screens from time to time. If a menu name below doesn't match what you see, look for the closest equivalent.

### Step 1. Get a Gemini API key

1. Go to Google AI Studio (aistudio.google.com) and sign in.
2. Choose **Get API key**, then **Create API key**, and copy it somewhere safe.
3. **Check the data terms before using real client information.** Google's terms for the Gemini API differ between the free tier and paid (billing-enabled) use, including whether prompts may be used to improve Google's products. For government and GLC opportunities, enable billing on the key's Google Cloud project and confirm the current terms on Google's site.

### Step 2. Create the Google sign-in client

1. Go to the Google Cloud console (console.cloud.google.com) and select or create a project, for example `solution-architect-app`.
2. Open **Google Auth Platform** (older consoles: **APIs & Services → OAuth consent screen**) and complete the **Branding / consent screen**:
   - App name: `Solutions Architect`
   - User support email: your email
   - **Audience:** *External*. While the app is in *Testing*, add the Google accounts that will sign in as **test users**.
3. Open **Clients** (older consoles: **APIs & Services → Credentials → Create credentials → OAuth client ID**):
   - Application type: **Web application**
   - Name: `Solutions Architect on Render`
   - **Authorised redirect URIs:** leave empty for now. You add the Render address in Step 4.
4. Copy the **Client ID** and **Client secret**.

### Step 3. Deploy on Render

1. Sign in to Render (render.com) with your GitHub account and allow it to access this repository.
2. Choose **New → Blueprint**, pick this repository, and confirm. Render reads `render.yaml` and proposes one web service called `solution-architect` in the **Singapore** region on the **free** plan.
3. Render asks for the secret values:

   | Setting | What to enter |
   |---|---|
   | `GEMINI_API_KEY` | the key from Step 1 |
   | `GOOGLE_CLIENT_ID` | from Step 2 |
   | `GOOGLE_CLIENT_SECRET` | from Step 2 |
   | `ALLOWED_EMAILS` | comma-separated emails allowed to sign in, e.g. `you@gmail.com,colleague@gamuda.com.my` |
   | `ALLOWED_DOMAINS` | optional: a whole domain, e.g. `gamuda.com.my`. Leave empty to allow only the listed emails |

   `SESSION_SECRET` is generated automatically. `GEMINI_MODEL` defaults to `gemini-3.8-flash`.
4. Choose **Apply**. The first build takes a few minutes. When it shows **Live**, copy the service address, e.g. `https://solution-architect-xxxx.onrender.com`.

### Step 4. Connect sign-in to the Render address

1. Back in the Google Cloud console, open the OAuth client from Step 2.
2. Under **Authorised redirect URIs**, add `https://solution-architect-xxxx.onrender.com/auth/callback`, using your real address, and save. It can take a few minutes to take effect.
3. Open your Render address, choose **Sign in with Google**, and sign in with an approved account.

### Step 5. First run

1. Paste a short opportunity description and choose **Quick draft** to check everything works end to end. It takes about one to four minutes.
2. Open the result, check the four diagrams, and download the zip.
3. Then try **Guided intake** on a real opportunity.

---

## Settings you can change later (Render → service → Environment)

| Variable | Default | Purpose |
|---|---|---|
| `GEMINI_MODEL` | `gemini-3.8-flash` | Model used. For harder work try `gemini-3.1-pro-preview`. Preview models can be withdrawn at short notice; check Google's model list. |
| `ALLOWED_EMAILS`, `ALLOWED_DOMAINS` | — | Who may sign in. Nobody can sign in if both are empty. |
| `MAX_JOBS_PER_USER_PER_DAY` | `20` | Protects your Gemini credit. |
| `MAX_CONCURRENT_JOBS` | `2` | Proposals generated at the same time. |
| `JOB_TTL_HOURS` | `12` | How long results stay available. |
| `GEMINI_TIMEOUT_SECONDS` | `600` | Per-call timeout. |
| `GEMINI_MAX_OUTPUT_TOKENS` | unset | Cap on output length if a model needs one. |
| `PUBLIC_BASE_URL` | Render's address | Set this only if you add a custom domain. Then also add `<domain>/auth/callback` to the Google client. |

Changes to environment variables redeploy the service automatically.

## Free plan behaviour

The free plan sleeps after 15 minutes without traffic. The first visit afterwards takes about a minute to wake it, and anything in memory (unfinished intakes, results not yet downloaded) is lost. If that's a problem, switch the service to a paid instance type in the Render dashboard. No code changes are needed.

## Security notes

- Every page except `/health` and the sign-in pages requires a signed-in, approved Google account (verified email only).
- Users only see their own intakes and results.
- Model output is sanitised before it is shown in the browser.
- `AUTH_DISABLED=1` exists for local testing only and is ignored when running on Render.
- Opportunity text is sent to Google's Gemini API. Do not enter classified or official-secret information. The footer of every page says so.

## Local development (optional, needs Python and Graphviz)

```bash
pip install -r requirements.txt pytest
python -m pytest -q          # end-to-end test with a fake model; no API key needed
AUTH_DISABLED=1 GEMINI_API_KEY=... uvicorn app.main:app --reload
```

## Repository layout

```
app/main.py                    web routes, Google sign-in, jobs, downloads
app/agent.py                   Gemini steps: intake, design + repair, package
app/knowledge/*.md             the agent's rules and reference files (same as the Gem)
app/renderer/render_multicloud.py  draws the 4 views from the spec
app/resources/icon_map.json    35 component kinds × 4 targets, icons verified in draw.io
app/examples/*.json            example specs
app/templates, app/static      pages and styles
Dockerfile, render.yaml        how Render builds and runs it
tests/test_app.py              end-to-end test with a fake model
```
