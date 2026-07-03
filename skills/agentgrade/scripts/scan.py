#!/usr/bin/env python3
"""agentgrade evidence scanner — fast, deterministic signal sweep of an agent repo.

Outputs JSON of rubric-signal hits grouped by pillar. Hits are LEADS for the
auditing model to verify by reading the flagged files — never verdicts.
Absence of a signal here is citable as "searched, nothing found".

Usage:
    python3 scan.py [repo_root]      # default: cwd
    python3 scan.py --self-test
"""

import json
import os
import re
import sys
import tempfile

EXCLUDED_DIRS = {
    ".git", "node_modules", ".venv", "venv", "env", "__pycache__",
    "dist", "build", ".next", "out", "vendor", "target",
    ".tox", "site-packages", ".mypy_cache", ".pytest_cache",
    ".ruff_cache", ".cache", "coverage",
}
EXCLUDED_FILES = re.compile(r"(package-lock\.json|yarn\.lock|pnpm-lock\.yaml|.*\.lock|.*\.min\.(js|css)|.*\.map)$")
TEXT_EXTS = {
    ".py", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".go", ".rs",
    ".java", ".rb", ".php", ".yaml", ".yml", ".toml", ".json", ".jsonl",
    ".md", ".txt", ".cfg", ".ini", ".sh", ".env.example",
}
TEXT_NAMES = {"Makefile", "Dockerfile", "Justfile", "Procfile"}
MAX_FILE_BYTES = 1_000_000
MAX_HITS_PER_SIGNAL = 8

# pillar -> signal -> regex (searched per line, case-insensitive)
SIGNALS = {
    "scope": {
        "llm_sdk": r"(?:\b|['\"/@])(anthropic|openai|google\.generativeai|google-genai|litellm|ollama|cohere|mistralai|groq|together_?ai|bedrock-runtime|@ai-sdk/|\bai-sdk\b)",
        "framework": r"(langchain|langgraph|crewai|autogen|pydantic_ai|pydantic-ai|llama_?index|haystack|\bdspy\b|semantic[-_]kernel|smolagents|mastra|openai[-_]agents|agents\s+sdk|fastmcp|mcp\.server|modelcontextprotocol)",
        "multi_agent_hint": r"(crewai|langgraph|autogen|message[-_ ]bus|task[-_ ]queue|celery|rabbitmq|kafka|\borchestrator\b|swarm\b)",
        "deploy_surface": r"(uvicorn|gunicorn|fastapi|flask|express\(\)|next start|Authorization:|\bjwt\b|oauth)",
    },
    "evaluation": {
        "eval_runner": r"(promptfoo|deepeval|\bragas\b|braintrust|openai[-_ ]?evals|inspect_ai|evalplus)",
        "golden_cases": r"(golden|eval[-_ ]?(set|case|data)|test[-_ ]?cases?\.(json|jsonl|csv|ya?ml)|expected[-_ ](output|answer|action))",
        "judge_layer": r"(llm[-_ ]?(as[-_ ]?)?judge|judge[-_ ]?(prompt|model)|\bgrader\b|groundedness|rubric)",
        "behavioral_asserts": r"(max[-_ ]?(steps|iterations|tool[-_ ]?calls)|tool[-_ ]?call.*assert|assert.*tool[-_ ]?call|cost[-_ ]?budget|latency[-_ ]?(budget|threshold))",
        "quality_metrics": r"(accuracy|recall|precision|pass[-_ ]?rate|f1[-_ ]?score)\s*[=:<>]",
    },
    "observability": {
        "tracing_lib": r"(opentelemetry|langsmith|langfuse|mlflow|logfire|arize|phoenix|\bweave\b|wandb|honeycomb)",
        "spans": r"(start_span|with[-_ ]?span|@traced?\b|trace_id|span_id|parent_span)",
        "llm_io_capture": r"(log.*(prompt|completion|response)|(prompt|completion).*log)",
        "feedback_capture": r"(thumbs[-_ ]?(up|down)|user[-_ ]?feedback|\brating\b)",
        "retry_fallback": r"(tenacity|\bbackoff\b|circuit[-_ ]?breaker|max_retries|\bfallback\b|dead[-_ ]?letter)",
        "alerting": r"(pagerduty|opsgenie|alertmanager|on[-_ ]?call|webhook.*alert|alert.*threshold)",
    },
    "data_foundation": {
        "vector_store": r"(chromadb?|faiss|pgvector|qdrant|pinecone|weaviate|milvus|lancedb|\bembedding)",
        "ingestion": r"(ingest|\betl\b|chunk(er|ing)|document[-_ ]?loader)",
        "refresh": r"(re[-_ ]?embed|re[-_ ]?index|rebuild[-_ ]?index|refresh|\bupsert\b|schedule|cron)",
        "freshness": r"(stale|freshness|\bttl\b|ingested_at|last[-_ ]?(updated|synced)|provenance)",
        "contracts": r"(pydantic|zod\.|jsonschema|marshmallow|schema[-_ ]?valid)",
    },
    "governance": {
        "prompt_mgmt": r"(system[-_ ]?prompt|prompt[-_ ]?(template|version|registry)|prompts?/)",
        "pii": r"(\bpii\b|redact|scrub|presidio|\bmask(ing)?\b|anonymi[sz]e|moderation|guardrail)",
        "audit_trail": r"(audit[-_ ]?(log|trail|event))",
        "model_config": r"(model[-_ ]?(name|id)\s*[=:]|MODEL\s*[=:])",
        "injection_defense": r"(prompt[-_ ]?injection|sanitiz|allowlist|whitelist.*tool|tool.*permission)",
    },
}

# structural presence checks: label -> glob-ish relative names
STRUCTURE = {
    "eval_dir": ["evals", "eval", "benchmarks", "golden"],
    "ci": [".github/workflows", ".gitlab-ci.yml", ".circleci"],
    "playbook": ["PLAYBOOK.md", "RUNBOOK.md", "playbook.md", "runbook.md", "docs/runbook.md", "docs/playbook.md", "docs/incidents.md"],
    "prompt_changelog": ["prompts/CHANGELOG.md", "PROMPTS.md", "prompts/README.md"],
    "container": ["Dockerfile", "docker-compose.yml", "docker-compose.yaml", "compose.yaml"],
}

COMPILED = {p: {s: re.compile(rx, re.IGNORECASE) for s, rx in sigs.items()} for p, sigs in SIGNALS.items()}


def iter_files(root):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in EXCLUDED_DIRS and not d.startswith(".claude")]
        for name in filenames:
            if EXCLUDED_FILES.match(name):
                continue
            ext = os.path.splitext(name)[1]
            if ext not in TEXT_EXTS and name not in TEXT_NAMES:
                continue
            path = os.path.join(dirpath, name)
            try:
                if os.path.getsize(path) > MAX_FILE_BYTES:
                    continue
            except OSError:
                continue
            yield path


def scan(root):
    root = os.path.abspath(root)
    hits = {p: {s: [] for s in sigs} for p, sigs in SIGNALS.items()}
    counts = {p: {s: 0 for s in sigs} for p, sigs in SIGNALS.items()}
    n_files = 0
    for path in iter_files(root):
        n_files += 1
        rel = os.path.relpath(path, root)
        try:
            with open(path, encoding="utf-8", errors="ignore") as f:
                for lineno, line in enumerate(f, 1):
                    if len(line) > 500:  # ponytail: skip minified/data lines
                        continue
                    for pillar, sigs in COMPILED.items():
                        for sig, rx in sigs.items():
                            if rx.search(line):
                                counts[pillar][sig] += 1
                                if len(hits[pillar][sig]) < MAX_HITS_PER_SIGNAL:
                                    hits[pillar][sig].append(f"{rel}:{lineno}: {line.strip()[:100]}")
        except OSError:
            continue

    structure = {}
    for label, candidates in STRUCTURE.items():
        found = [c for c in candidates if os.path.exists(os.path.join(root, c))]
        structure[label] = found or None

    return {
        "root": root,
        "files_scanned": n_files,
        "structure": structure,
        "signals": {
            p: {s: {"count": counts[p][s], "hits": h} for s, h in sigs.items() if counts[p][s]}
            for p, sigs in hits.items()
        },
        "absent": {
            p: [s for s, c in counts[p].items() if c == 0] for p in SIGNALS
        },
    }


def self_test():
    with tempfile.TemporaryDirectory() as tmp:
        os.makedirs(os.path.join(tmp, "evals"))
        with open(os.path.join(tmp, "agent.py"), "w") as f:
            f.write("import langfuse\nfrom anthropic import Anthropic\nMAX_RETRIES = 3\n")
        with open(os.path.join(tmp, "evals", "cases.jsonl"), "w") as f:
            f.write('{"input": "hi", "expected_output": "hello"}\n')
        os.makedirs(os.path.join(tmp, "node_modules", "junk"))
        with open(os.path.join(tmp, "node_modules", "junk", "x.py"), "w") as f:
            f.write("import langfuse\n")  # must be excluded

        r = scan(tmp)
        assert r["signals"]["observability"]["tracing_lib"]["count"] == 1, "langfuse: node_modules not excluded"
        assert "llm_sdk" in r["signals"]["scope"], "anthropic sdk not detected"
        assert "retry_fallback" in r["signals"]["observability"], "max_retries not detected"
        assert r["structure"]["eval_dir"] == ["evals"], "evals/ dir not detected"
        assert r["structure"]["playbook"] is None, "playbook false positive"
    print("self-test OK")


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        self_test()
    else:
        root = next((a for a in sys.argv[1:] if not a.startswith("-")), ".")
        json.dump(scan(root), sys.stdout, indent=1)
        print()
