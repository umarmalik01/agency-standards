#!/usr/bin/env python3
"""Fail the build if any executable file actively integrates a paid generation provider.

Documentation may name these providers - POLICY_NO_PAID_APIS.md names all of them, and the skills
warn against them by name. What is forbidden is an *active integration*: importing a provider SDK,
installing one, calling a provider endpoint, or reading a provider credential.

The distinction is drawn structurally, not by keyword:
  * Python  - the AST is parsed; only real `import` statements count.
  * All files - provider API hostnames, credential env-var names, and package installs count.
A provider name sitting in prose or a comment never trips the audit.

    python scripts/audit_no_paid_apis.py [--root .] [--verbose]
Exit 0 = clean, 1 = forbidden integration found.
"""
from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from pathlib import Path

FORBIDDEN_IMPORTS = {
    "fal", "fal_client", "falai", "wavespeed", "replicate", "runwayml", "runway",
    "elevenlabs", "heygen", "kling", "klingai", "veo", "seedance", "together",
    "fireworks", "stability_sdk", "playht", "pyht", "resemble", "lmnt", "deepgram",
    "assemblyai", "murf",
}

FORBIDDEN_HOSTS = [
    "fal.ai", "fal.run", "queue.fal.run", "api.wavespeed.ai", "wavespeed.ai",
    "api.replicate.com", "replicate.delivery", "api.runwayml.com", "api.dev.runwayml.com",
    "api.elevenlabs.io", "api.heygen.com", "api.klingai.com", "api-singapore.klingai.com",
    "generativelanguage.googleapis.com/v1beta/models/veo", "aiplatform.googleapis.com",
    "api.together.xyz", "api.fireworks.ai", "api.stability.ai",
    "api-inference.huggingface.co", "router.huggingface.co",
    "api.openai.com/v1/audio", "api.openai.com/v1/images", "api.openai.com/v1/video",
    "api.play.ht", "api.murf.ai", "api.deepgram.com",
]

FORBIDDEN_ENV_KEYS = [
    "FAL_KEY", "FAL_API_KEY", "WAVESPEED_API_KEY", "REPLICATE_API_TOKEN", "REPLICATE_API_KEY",
    "RUNWAY_API_KEY", "RUNWAYML_API_SECRET", "ELEVENLABS_API_KEY", "ELEVEN_API_KEY",
    "HEYGEN_API_KEY", "KLING_ACCESS_KEY", "KLING_SECRET_KEY", "SEEDANCE_API_KEY",
    "TOGETHER_API_KEY", "FIREWORKS_API_KEY", "STABILITY_API_KEY", "PLAYHT_API_KEY",
    "HF_INFERENCE_ENDPOINT",
]

# `pip install replicate`, `npm i @fal-ai/client`, etc.
INSTALL_RE = re.compile(
    r"(?:pip3?\s+install|uv\s+pip\s+install|npm\s+(?:i|install)|yarn\s+add|pnpm\s+add)"
    r"[^\n;&|]*?\b(fal|fal-client|@fal-ai/[\w-]+|wavespeed|replicate|runwayml|elevenlabs|"
    r"heygen|kling|seedance|together|fireworks|stability-sdk|pyht|playht)\b",
    re.IGNORECASE,
)

EXECUTABLE_SUFFIXES = {".py", ".sh", ".bash", ".yaml", ".yml", ".json", ".toml",
                       ".ipynb", ".js", ".ts", ".mjs", ".cfg", ".ini", ".env"}
SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv", "third_party",
             ".mypy_cache", ".pytest_cache", "projects"}
# Documentation may discuss the providers freely.
DOC_SUFFIXES = {".md", ".txt", ".rst"}


def python_imports(source: str) -> set[str]:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return set()
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            found.add(node.module.split(".")[0])
    return found


def scan_file(path: Path) -> list[dict]:
    findings: list[dict] = []
    try:
        text = path.read_text(errors="ignore")
    except OSError:
        return findings
    lower = text.lower()

    if path.suffix == ".py":
        for mod in sorted(python_imports(text) & FORBIDDEN_IMPORTS):
            findings.append({"file": str(path), "kind": "forbidden_import", "match": mod})
    elif path.suffix == ".ipynb":
        try:
            nb = json.loads(text)
        except json.JSONDecodeError:
            nb = {}
        for cell in nb.get("cells", []):
            if cell.get("cell_type") != "code":
                continue
            src = "".join(cell.get("source", []))
            for mod in sorted(python_imports(src) & FORBIDDEN_IMPORTS):
                findings.append({"file": str(path), "kind": "forbidden_import", "match": mod})

    for host in FORBIDDEN_HOSTS:
        if host.lower() in lower:
            findings.append({"file": str(path), "kind": "provider_endpoint", "match": host})
    for key in FORBIDDEN_ENV_KEYS:
        # A bare mention is prose; reading or assigning it is an integration.
        if re.search(
            rf"""(?:getenv|environ(?:\.get)?|os\.environ|process\.env|export|ENV)\s*"""
            rf"""[\(\[\.]?\s*["']?{re.escape(key)}\b|^\s*{re.escape(key)}\s*=""",
            text, re.MULTILINE):
            findings.append({"file": str(path), "kind": "provider_credential", "match": key})
    for m in INSTALL_RE.finditer(text):
        findings.append({"file": str(path), "kind": "provider_install", "match": m.group(1)})
    return findings


def audit(root: Path, verbose: bool = False) -> tuple[list[dict], int]:
    findings: list[dict] = []
    scanned = 0
    for path in sorted(root.rglob("*")):
        if not path.is_file() or any(p in SKIP_DIRS for p in path.parts):
            continue
        if path.suffix in DOC_SUFFIXES or path.suffix not in EXECUTABLE_SUFFIXES:
            continue
        if path.name == "audit_no_paid_apis.py":
            continue  # this file necessarily lists every provider name
        scanned += 1
        if verbose:
            print(f"  scanned {path}")
        findings.extend(scan_file(path))
    return findings, scanned


def main() -> int:
    ap = argparse.ArgumentParser(description="Audit for active paid-provider integrations.")
    ap.add_argument("--root", type=Path, default=Path(__file__).resolve().parent.parent)
    ap.add_argument("--verbose", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    findings, scanned = audit(args.root, args.verbose)
    if args.json:
        print(json.dumps({"scanned": scanned, "findings": findings,
                          "result": "FAIL" if findings else "PASS"}, indent=2))
    else:
        print(f"no-paid-API audit: {scanned} executable file(s) scanned under {args.root}")
        if findings:
            print(f"\nFORBIDDEN INTEGRATIONS ({len(findings)}):")
            for f in findings:
                print(f"  {f['kind']:<22} {f['match']:<28} {f['file']}")
            print("\nRESULT: FAIL - remove the integration. Do not substitute a paid provider.")
        else:
            print("RESULT: PASS - no active paid-generation provider found.")
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
