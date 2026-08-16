# Lawve submission packet — regulatory-threat-model

Form: https://lawve.ai/new/skill (owner dropdown: **Ansvar AI** / @ansvar-ai)

| Field | Value |
|---|---|
| Upload | Zip of **SKILL.md + README.md + LICENSE only** — `fragments/` and `scripts/` are build inputs, not part of the skill. Lawve auto-parses name, files, language, and LICENSE |
| Name | Regulatory Threat Model (STRIDE + LINDDUN) |
| Description | Runs a server-enforced STRIDE threat model and LINDDUN privacy threat model over a system described in prose, screens named dependencies against live CVE/KEV/EPSS data, and builds a cited screen of which EU security obligations (GDPR, NIS2, CRA, AI Act) may apply and which need determination — every regulatory statement fetched from officially published text through the Ansvar Gateway connector at answer time, with scope, role, and application-date limits stated. Never answered from model memory; never a compliance verdict. |
| Category (practice area) | Compliance & Regulatory |
| Jurisdiction | EU |
| Language | English |
| License | **CC BY 4.0 — change it; the picker defaults to AGPL** |

Notes for the submitter:

- Lawve renders the uploaded README as the listing body (verified on
  prior submissions); the README is written in their listing shape.
- Cross-link the `ansvar-gateway` connector listing after approval, as
  with the prior two skills.
- Positioning context: the 2026-07-19 sweep found zero threat-modeling
  skills across the directory (203 checked) — this is the first. The
  showcase is that a Free signup can run a real server-enforced STRIDE
  threat model, once a month, within the included-run allowance; the
  free lane (dependency and obligations screens) keeps the skill useful
  once that run is spent.
- This packet tracks **v1.3**. Re-uploading the zip after a release is
  an operator action on lawve.ai — neither this repo nor its CI
  publishes to the directory, so a version bump here is a reminder, not
  a trigger.
- Sibling listings for the series pattern:
  `lawve.ai/@ansvar-ai/skill/cra-vulnerability-obligations`,
  `lawve.ai/@ansvar-ai/skill/incident-reporting-navigator`.
