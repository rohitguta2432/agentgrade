# agentgrade

**Production-readiness auditor for AI agents.** Point it at any agent codebase and it grades the repo against five pillars, shows you the gaps ranked by risk, and tells you exactly what to build next.

Most AI agents die in the gap between demo and production. The demo works — controlled inputs, happy path, everyone claps. Then real users arrive and nobody can answer three questions:

1. **Is it getting worse?** (no evaluation)
2. **What did it actually do?** (no tracing)
3. **Who owns it when it breaks?** (no governance)

agentgrade is a [Claude Code skill](https://docs.claude.com/en/docs/claude-code/skills) that audits your repo for those answers *before* your users find out you don't have them.

## What it checks

| Pillar | The question it answers |
|--------|------------------------|
| **Evaluation** | If the agent got worse tomorrow, would anyone find out before the users do? |
| **Observability** | When a user disputes an answer, can you reconstruct every decision the agent made? |
| **Data foundation** | When source data changes, does the agent notice — or confidently serve last month's answer? |
| **Orchestration** | When one agent stalls or loops, what happens to the rest of the system? |
| **Governance** | When it misbehaves at 3 a.m., who is accountable — and can they prove what happened? |
| **Incident playbook** | Is there a written detect → diagnose → contain → fix → learn loop? |

Every score is anchored to observable evidence — files, configs, CI steps — and every claim in the report cites `file:line`. No vibes. What can't be verified from source (like runtime tool-call behavior) is reported as *unverifiable*, which is itself a finding.

## Install

**Plugin marketplace (recommended)** — inside Claude Code:

```
/plugin marketplace add rohitguta2432/agentgrade
/plugin install agentgrade@agentgrade
```

**Manual copy** — works everywhere:

```bash
git clone https://github.com/rohitguta2432/agentgrade.git
cp -r agentgrade/skills/agentgrade ~/.claude/skills/
```

Or per-project: copy `skills/agentgrade` into your repo's `.claude/skills/` and
commit it — everyone who clones your repo gets the auditor.

## Use

Open Claude Code in the agent repo you want audited and say:

```
audit my agent
```

or `agentgrade`, or `is this production ready?`. That's it — the skill scopes the agent (framework, single vs multi-agent, RAG or not), infers your deployment context, sweeps for evidence, and emits a report like:

```markdown
# agentgrade report — support-bot

**Context:** customer-facing (inferred: Dockerfile + auth + public API)
**Verdict:** DEMO-GRADE

| Pillar            | Score | Key evidence |
|-------------------|-------|--------------|
| Evaluation        | 1/5   | 3 example prompts in scripts/try.py; no expected outputs, no runner |
| Observability     | 2/5   | model calls logged (src/llm.py:41); tool calls and retrieval invisible |
| Data foundation   | 2/5   | scripted ingestion (ingest.py) but nothing triggers re-embedding |
| Orchestration     | N/A   | single agent |
| Governance        | 2/5   | prompts in git; no change reasons, no PII screening |
| Incident playbook | missing | searched *.md, runbooks/, docs/ |

## Top gaps — build these next
1. No eval dataset — **risk:** every prompt/model change ships blind; regressions
   reach users first. **next artifact:** evals/cases.jsonl with 20 golden cases
   from real queries + a pytest runner with pass thresholds.
2. Retrieval is invisible — **risk:** stale-document failures are undiagnosable;
   you'll refund users because you can't reconstruct answers. **next artifact:**
   spans around retrieval + tool calls (langfuse/OTel), linked to request IDs.
3. No re-embedding trigger — **risk:** upstream doc updates silently never reach
   the agent. **next artifact:** refresh job keyed on source timestamps.

## Unverifiable statically
- Duplicate/looping tool calls — needs trace data (see gap 2).
```

Then it offers to scaffold gap #1 for you. Say yes and you get the file, adapted to your repo.

## Verdicts

- **PRODUCTION-GRADE** — every applicable pillar ≥ 4/5, incident playbook present
- **PILOT-GRADE** — evaluation ≥ 3, observability ≥ 3, everything else ≥ 2
- **DEMO-GRADE** — anything less

Context matters: an internal tool can responsibly run at pilot-grade. Anything customer-facing should be production-grade or have a dated plan to get there.

## Why a skill and not a linter?

Readiness isn't a syntax property. Whether `evals/cases.jsonl` is a living golden set or three stale examples requires reading it. Whether your traces capture *decisions* or just status codes requires understanding your code. A skill gets you judgment with receipts — and the two halves keep that judgment honest:

- **`scripts/scan.py`** — a deterministic, stdlib-only scanner that sweeps every rubric signal (excluding node_modules/.venv noise) and reports hits with `file:line` plus explicit per-pillar *absence* lists. Same repo in, same evidence out, every run.
- **`references/rubric.md`** — anchored score levels, so the grade is a lookup from evidence, not a mood.

The rubric is the product. If you think a signal is missing or an anchor is wrong — PR it.

## Roadmap

- **Trace-file audits** — accept exported traces (Langfuse/OTel/MLflow) so the behavioral layer (duplicate tool calls, loops, cost per request) becomes verifiable, not just "wire up tracing first".
- **Calibration fixtures** — small fixture repos with known scores, so rubric changes can be regression-tested.
- **CI mode** — run the scanner in GitHub Actions and fail PRs that drop a pillar below its floor.

## License

MIT
