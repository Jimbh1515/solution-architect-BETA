# 04 Output Templates

Purpose: the exact structure of every proposal package. Produce all sections in this order, in `proposals/<opportunity-slug>/proposal.md`. Keep headings as written so the pre-sales team can lift sections straight into proposals.

## Section 0 — Mode and assumptions

- Mode: Quick draft or Guided intake
- Assumptions made (quick draft) or confirmed facts (guided intake), as a numbered list
- Items the user must confirm before this package is used externally

## Section 1 — Executive summary

Four to six sentences: the client's problem, the recommended option, why it was chosen over the alternatives, the main policy considerations, and the top two risks. No figures that have not been verified.

## Section 2 — Requirements and constraints

| Type | Requirement | Source (user stated / assumed) |
|---|---|---|
| Functional | | |
| Non-functional (availability, RTO, RPO, performance, scale) | | |
| Data (types, volumes, classification) | | |
| Hosting and residency | | |
| Integration | | |
| Timeline and procurement | | |

## Section 3 — Seven-layer policy mapping

| Layer | In scope / dependency / out of scope | Components in this layer | Instruments to check against (from file 01) | What must be checked | Verification flag |
|---|---|---|---|---|---|
| 1 Physical Infrastructure | | | | | |
| 2 Connectivity | | | | | |
| 3 Digital Public Infrastructure | | | | | |
| 4 Compute and Processing | | | | | |
| 5 Data | | | | | |
| 6 AI | | | | | |
| 7 Orchestration | | | | | |

"What must be checked" describes the design question (for example "whether personal data processed by the model may be transferred to a provider outside Malaysia"), not the content of the law. Instruments not in file 01 are marked "Not in reference table — verify before use".

## Section 4 — Options comparison

Describe each option in three to five sentences, naming the provider and main services for each.

- **Option A — Public hyperscaler:** (provider and why it fits best)
- **Option B — Hybrid:** (what stays on-premises or sovereign, what uses a hyperscaler, what data crosses)
- **Option C — Malaysian sovereign or locally hosted:** "Malaysian sovereign or local provider (to be identified)" unless the user has named one; list the capabilities such a provider must offer (in-country hosting, relevant security certifications, GPU capacity, managed Kubernetes and databases, connectivity to agencies and hyperscalers, support model)

### Weighted scoring

Adapted from the CTO advisor technology evaluation framework. Scores 1 to 5 (5 is best). Adjust weights only if the user asks, and show any change.

| Criterion | Weight | Option A | Option B | Option C | Basis for scores |
|---|---|---|---|---|---|
| Policy and data residency fit | 20% | | | | |
| Security | 15% | | | | |
| Reliability and scalability | 15% | | | | |
| Performance (including AI capability) | 10% | | | | |
| Cost profile (relative, from cost drivers, not prices) | 10% | | | | |
| Delivery speed and risk | 10% | | | | |
| Operational overhead (fully managed = 5) | 10% | | | | |
| Vendor lock-in and exit strategy | 5% | | | | |
| Local capability, skills and support | 5% | | | | |
| **Weighted total** | 100% | | | | |

Scores are architectural judgements, not measurements. State this beneath the table.

### Recommendation

The recommended option, the two or three decisive reasons, and the conditions under which a different option would be preferable.

## Section 5 — Recommended architecture

1. **Narrative:** how the architecture works, following the request path and then the data path (one to three paragraphs).
2. **Component and flow specification:** the three tables defined in file 03 (containers, components, flows). They must match `spec.json` exactly.
3. **Diagrams** (produced by the renderer, see file 05). Embed the PNGs and link the draw.io file:
   - 5.3a Provider-neutral view: `diagrams/generic.png`
   - 5.3b The same architecture on Amazon Web Services: `diagrams/aws.png`
   - 5.3c The same architecture on Microsoft Azure: `diagrams/azure.png`
   - 5.3d The same architecture on Google Cloud: `diagrams/gcp.png`
   - Editable file with all four pages: `diagrams/multicloud.drawio`
   Under the diagrams, state in one sentence that the three cloud views show the recommended design implemented on each provider for comparison, and that the recommendation in Section 4 is unchanged by them.
4. **Service mapping across clouds:** paste `diagrams/service_mapping.md`. Then add two to four sentences on material differences between the three clouds for this design (for example where one provider lacks an equivalent managed service, or where data residency differs). Mark every service whose Malaysian region availability is unconfirmed "(to verify with provider)".
5. **Well-architected review:** one line per pillar from file 02, stating how the design addresses it and any open gap.

## Section 6 — Cost drivers (MYR)

No prices or totals. The pre-sales team prices the last column.

| # | Layer | Component | Cost driver | Sizing assumption | Unit | Quantity (per month unless stated) | Indicative cost (MYR) |
|---|---|---|---|---|---|---|---|
| 1 | | | | | | | |
| | | | | | | **Total** | |

Below the table:

- **Most sensitive assumptions** — the three to five drivers most likely to change the total, and why.
- **Cost levers** — which of the levers in file 02 apply to this design.
- **One-off versus recurring** — mark which lines are one-off (design, build, migration, training) and which are recurring.

## Section 7 — Risk register

Likelihood and impact scored 1 (low) to 5 (high). Rating = likelihood × impact: 15–25 High, 8–14 Medium, 1–7 Low.

| ID | Risk description | Layer | Category (policy, security, technical, delivery, commercial, vendor) | Likelihood | Impact | Rating | Mitigation | Owner (role) |
|---|---|---|---|---|---|---|---|---|
| R1 | | | | | | | | |

Always consider: data crossing a provider or national boundary; unconfirmed region availability of a required service; GPU capacity availability; dependency on a single provider; licence changes in open-source components; skills availability for operating the platform; integration with other agencies' systems; and policy instruments still to be verified.

## Section 8 — Architecture decision records

One record per significant decision (typically three to six). Use this format:

**ADR-[number]: [title]**

- **Status:** Proposed
- **Context:** why the decision is needed
- **Decision drivers:** the requirements and constraints that matter most
- **Options considered:** two or three viable alternatives
- **Decision:** the choice and the reason
- **Consequences:** positive, negative, and risks (cross-reference risk IDs)

## Section 9 — Open questions and items to verify

Two lists:

1. **Questions for the client** — information still needed, in priority order.
2. **Items to verify before submission** — every policy title, service name, region availability, figure or claim flagged as uncertain in the package, collected in one place. Include every item listed in `diagrams/render_report.md`.
