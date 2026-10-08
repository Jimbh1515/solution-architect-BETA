# 01 Malaysia Digital Policy Reference

Purpose: the seven-layer architecture stack used to structure every solution, and the Malaysian policies, laws and frameworks associated with each layer. Source: reference table supplied by the user (Gamuda Technologies pre-sales). Use it as a guideline, not as an exhaustive list.

Important: this file lists instrument titles only. It does not describe their content. Do not state what any instrument requires unless the user supplies the source text.

## The seven-layer stack

| # | Architecture layer | Layer scope and key components | What Malaysia has today (policies, laws, frameworks) |
|---|---|---|---|
| 1 | Physical Infrastructure | Water; electricity; land | National Energy Policy 2022–2040; National Water Resources Policy; Kanun Tanah Negara (National Land Code) |
| 2 | Connectivity | 5G / 6G; subsea cable; IX (Internet Exchange); satellite | Communications and Multimedia Act 1998 (Act 588); Malaysian Communications and Multimedia Commission Act 1998 (Act 589) |
| 3 | Digital Public Infrastructure (DPI) | Digital identity; payment; consent | Digital Signature Act 1997 (Act 562); Financial Services Act 2013 |
| 4 | Compute and Processing | Data centre; HPC / GPU; cloud; edge compute | National Cloud Computing Policy |
| 5 | Data | Data governance; data exchange; data lake | Personal Data Protection Act 2010 (Act 709); Akta Perkongsian Data 2025 (Data Sharing Act 2025) — Federal Government only |
| 6 | AI | AI models; AI agents | National AI Action Plan 2030; AI Governance and Ethics (AIGE) guidance / framework |
| 7 | Orchestration | Automated command and control | Malaysia Digital / MD2030; National AI Action Plan 2026–2030 |

## How to use the stack in a proposal

- Place every architecture component in exactly one layer. A component that genuinely spans layers (for example an AI agent platform that also orchestrates workflows) goes in the layer that best describes its primary function, with a note.
- For every in-scope layer, list the instruments above in the policy mapping section and say what the design must be checked against. Do not paraphrase their content.
- Layers 1 to 3 are often outside the scope of a software or cloud proposal, but they still matter: data centre power and land (layer 1), connectivity between agencies and to cloud regions (layer 2), and national digital identity or payment integration (layer 3). Mark each as "in scope", "dependency" or "out of scope".

## Items flagged for verification

Carry these flags into any proposal that cites the item.

1. **Possible title inconsistency.** Layer 6 cites "National AI Action Plan 2030" and layer 7 cites "National AI Action Plan 2026–2030". These may be the same document. Confirm the exact official title before citing.
2. **Akta Perkongsian Data 2025 (Data Sharing Act 2025).** The table notes it applies to the Federal Government only. Confirm the official title, Act number and scope against the gazetted text before citing, especially for state agencies or GLCs.
3. **AI Governance and Ethics (AIGE) guidance / framework.** Confirm the exact title, issuing body and current version.
4. **National Cloud Computing Policy.** Confirm the exact title and current version.
5. **Malaysia Digital / MD2030.** Confirm the exact programme title as used in current official documents.

## Possibly relevant instruments not in the table

These are raised by the builder of this agent from general knowledge and are not in the user's reference table. Treat them as "Not in reference table — verify before use". Their existence, titles and current status have not been checked against official sources.

| Instrument | Likely layer | Note |
|---|---|---|
| Cyber Security Act 2024 (Act 854) | 4, 5, 7 (security across the stack) | Believed to exist; verify title, Act number and applicability (for example to national critical information infrastructure sectors). |
| Personal Data Protection (Amendment) Act 2024 | 5 | Believed to amend Act 709; verify whether and how it applies to the specific client (the PDPA's application to federal and state governments should be checked). |

Add instruments to this table only when the user provides them or asks for them to be added.
