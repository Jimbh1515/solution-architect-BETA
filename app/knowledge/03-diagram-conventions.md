# 03 Diagram Conventions

Purpose: how the recommended architecture is described and drawn. In Antigravity, diagrams are never written by hand. You write one provider-neutral specification (`spec.json`), and the renderer in `scripts/render_multicloud.py` draws it four times: provider-neutral, Amazon Web Services, Microsoft Azure and Google Cloud. File 05 explains the spec format and the commands.

## 1. What the diagrams look like

The style follows the reference diagram the user supplied: a hybrid serving architecture with a self-managed Kubernetes cluster and a hyperscaler model called through a gated API.

| Element | Spec container type | Appearance |
|---|---|---|
| Client environment | `environment` | Blue-bordered panel enclosing everything the client owns |
| Subsystem | `subsystem` | Light grey rounded box, title top-left (e.g. "Serving subsystem") |
| Runtime platform | `platform` | Lighter grey box inside a subsystem, title top-right (e.g. "Self-managed Kubernetes cluster") |
| Provider zone | `provider_zone` | Pale blue box, titled with the cloud's name on each cloud page (e.g. "Amazon Web Services") |
| On-premises or sovereign site | `onprem_site` | Pale yellow dashed box (e.g. "Agency premises", "Malaysian sovereign facility (provider to be identified)") |
| Component | component `kind` | The official icon for that service on each cloud, or a generic icon on-premises, with the component label and service name underneath |
| Request / response flow | flow `type: request` | Green arrow |
| Data / integration flow | flow `type: data` | Navy arrow |
| Telemetry | flow `type: telemetry` | Dashed green arrow |

Layout rules the renderer applies automatically: nested boxes, top-to-bottom flow (use `--rankdir LR` for wide designs), and every flow that crosses into or out of a provider zone labelled with the data class that crosses it.

## 2. Rules for writing the specification

- Every component has a `kind` from the table in file 05. Never invent a kind. If nothing fits, use the closest kind and say so in the component's `tech` field and in Section 9 of the package.
- `placement` decides the icon:
  - `cloud`: drawn with each provider's own service icon on the AWS, Azure and Google Cloud pages, and as a named capability on the provider-neutral page.
  - `onprem` or `sovereign`: drawn with a generic icon on every page. Put the example technology in `tech` (e.g. "PostgreSQL with pgvector").
  - `external`: users and data sources outside the client environment.
- Any flow that crosses a provider or national boundary must set `crosses_boundary: true` and a `data_class` saying what data crosses (e.g. "approved data only", "anonymised records"). This supports the data residency discussion in the policy mapping.
- Use `service_override` only when the design needs a different service than the default for that kind on a given cloud (e.g. Amazon Aurora instead of Amazon RDS). The icon stays the kind's icon, so choose the kind carefully.
- Keep labels short (under about 30 characters). The renderer wraps text and escapes special characters itself.
- More than about 25 components: split into one spec per subsystem, plus an overview spec with one component per subsystem, and render each.

## 3. Specification tables (Section 5.2 of the package)

These three tables are the human-readable form of `spec.json`. They must match it exactly.

### Containers

| ID | Name | Type | Parent |
|---|---|---|---|

### Components

| ID | Name | Kind | Placement | Container | Example technology (on-premises / sovereign) | Layer (1–7) | Notes |
|---|---|---|---|---|---|---|---|

### Flows

| ID | From | To | Label | Type | Crosses boundary? (data class) |
|---|---|---|---|---|---|

## 4. Example

`examples/reference-hybrid-ai.json` reproduces the user's reference diagram. Only the managed model sits in the provider zone, so the three cloud pages differ only in that component: Amazon Bedrock, Azure OpenAI and Gemini via Vertex AI. `examples/public-cloud-ai.json` shows a design where almost every component is cloud-hosted, so each cloud page uses that provider's icons throughout.

## 5. Editing the output

The draw.io files are fully editable. Open them at app.diagrams.net or in the draw.io desktop app. If a change is structural (new component, new flow), change `spec.json` and re-run the renderer rather than editing the drawing, so the spec, the tables and the four diagrams stay consistent.
