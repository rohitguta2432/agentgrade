# Changelog

## 0.2.0 — 2026-07-03

- **Plugin marketplace packaging** — install via `/plugin marketplace add rohitguta2432/prodgrade`; manual copy still works.
- **Bundled evidence scanner** (`scripts/scan.py`, stdlib-only) — deterministic sweep of every rubric signal with `file:line` excerpts, structural checks (eval dir, CI, playbook, container), and per-pillar `absent` lists for citable negative evidence. Excludes vendored dirs (node_modules, .venv, dist…). `--self-test` included.
- **Wider agent detection** — llamaindex, haystack, dspy, semantic-kernel, smolagents, Vercel AI SDK, MCP servers; TS/JS agents covered alongside Python.
- Audit procedure updated: scanner first, manual verification of hits before any score ("hits are leads, not verdicts").

## 0.1.0 — 2026-07-03

- Initial release: five-pillar rubric with anchored 0–5 scoring, deployment-context calibration, verdict table (demo/pilot/production-grade), incident-playbook check, ranked gap report, scaffold templates (eval JSONL, PLAYBOOK.md, prompt changelog, LLM-judge prompt).
