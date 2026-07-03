---
name: agentgrade
description: Audit any AI agent codebase for production readiness. Grades the repo against five pillars — evaluation, observability, data foundation, orchestration, governance — plus an incident playbook check, then reports the gaps ranked by risk with the exact artifact to build next. Use when the user says "audit my agent", "agentgrade", "is this agent production ready", "production readiness check", "agent gap analysis", or is about to deploy/launch an AI agent to real users.
---

# agentgrade — production-readiness auditor for AI agents

Grade an AI agent codebase against five pillars, cite evidence for every score,
and hand back a short ranked list of what to build next. The output is a gap
report, not a lecture: scorecard → verdict → top 3 gaps → offer to scaffold.

## Process

### 1. Scope the agent

Identify what you're auditing before judging it:

- Find the agent surface: LLM SDK imports (`anthropic`, `openai`, `google.generativeai`,
  `litellm`, `ollama`, Vercel `ai`/`@ai-sdk`), frameworks (`langchain`, `langgraph`,
  `crewai`, `autogen`, `pydantic_ai`, `llamaindex`, `haystack`, `dspy`,
  `semantic-kernel`, `smolagents`, MCP servers), entry points, tool definitions.
- Count agents: single agent vs multi-agent (affects the orchestration pillar).
- Detect RAG: vector stores, embedding calls, ingestion scripts (affects data foundation).
- Establish deployment context — it calibrates the bar. Infer from the repo
  (Dockerfile + auth + customer-facing API ⇒ production intent; a CLI demo ⇒ demo).
  If genuinely ambiguous, ask once: internal tool, pilot with real users, or
  customer-facing production?

### 2. Read the rubric

Read [references/rubric.md](references/rubric.md). It defines, per pillar:
what to look for (grep/glob signal patterns), anchored score levels 0–5,
and when a pillar is N/A. Scores come from the anchors, never from vibes.

### 3. Collect evidence

Start with the bundled scanner — a deterministic sweep of every rubric signal:

```bash
python3 <this skill's base directory>/scripts/scan.py /path/to/agent/repo
```

It excludes vendored dirs (node_modules, .venv, dist…) and returns JSON:
signal hits with `file:line` excerpts, structural checks (eval dir, CI,
playbook, container), and an `absent` list per pillar. Two rules for using it:

- **Hits are leads, not verdicts.** Open the flagged files and confirm before
  scoring — a commented-out import or a keyword in a README scores nothing.
- **The `absent` list is your negative evidence.** Cite it directly as
  "scanner found no tracing_lib/spans/llm_io_capture signals".

Then deepen manually where the scanner can't see (quality of eval cases,
whether traces cover decisions or just calls). Rules:

- **Every scored claim cites evidence** — `file:line` for things present,
  "searched X, Y, Z — nothing found" for things absent.
- **Never guess runtime behavior.** Duplicate tool calls, loops, latency live in
  traces, not source. If tracing isn't wired, say "unverifiable statically" —
  that itself is an Observability finding.
- **N/A is a valid grade.** A single-agent tool gets "Orchestration: N/A".
  Don't pad the report with pillars that don't apply.

### 4. Score and rank

- Score each applicable pillar with the rubric anchors.
- Derive the verdict (demo-grade / pilot-grade / production-grade) from the
  verdict table in the rubric.
- Rank gaps by **risk in the stated deployment context** — what actually breaks,
  costs money, or leaks data first — not by score delta.

### 5. Report

Emit exactly this shape:

```markdown
# agentgrade report — <repo-name>

**Context:** <customer-facing | pilot | internal | demo> (stated/inferred)
**Verdict:** DEMO-GRADE | PILOT-GRADE | PRODUCTION-GRADE

| Pillar          | Score | Key evidence |
|-----------------|-------|--------------|
| Evaluation      | n/5   | ...          |
| Observability   | n/5   | ...          |
| Data foundation | n/5   | ...          |
| Orchestration   | n/5 or N/A | ...    |
| Governance      | n/5   | ...          |
| Incident playbook | present / missing | ... |

## Top gaps — build these next
1. <gap> — **risk:** <what breaks in production> — **next artifact:** <specific file/change, smallest useful version>
2. ...
3. ...

## Unverifiable statically
- <things that need trace data / runtime evidence>
```

Keep it to the top 3 gaps (5 max if the repo is large and scores are low).
A 50-finding dump gets ignored; a ranked shortlist gets built.

### 6. Offer scaffolds

End by offering to generate the #1 missing artifact. Templates for the four
common ones (eval dataset, incident playbook, prompt changelog, LLM-judge
prompt) are in [references/rubric.md](references/rubric.md) § Templates.
Generate only what the user accepts.

## Rules

- Evidence-cited scores only; anchors over impressions.
- Calibrate to deployment context; don't demand regulator-grade audit trails
  from an internal prototype — but say what the next tier requires.
- Read-only by default: the audit never edits the target repo. Scaffolds are
  written only when the user says yes.
- If the repo has no LLM/agent surface at all, say so and stop — don't force
  the rubric onto a non-agent codebase.
