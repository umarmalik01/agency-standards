#!/usr/bin/env python3
"""Report what the system needs and what is actually present. READY / PARTIALLY READY / NOT READY.

    python scripts/check_setup.py
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REQUIRED_SKILLS = ("tarjeeh-ugc", "planning-campaigns", "writing-ad-copy",
                   "writing-video-scripts", "writing-video-prompts", "auto-edit-video")
OPTIONAL_SKILLS = ("analyzing-products", "analyzing-brand")

# Stages that must work before any ad can ship. Optional ones degrade gracefully.
CRITICAL = {"permanent_skills", "python", "ffmpeg", "ffprobe", "no_paid_api_audit", "config"}


def _module(name: str) -> bool:
    try:
        return importlib.util.find_spec(name) is not None
    except (ImportError, ValueError):
        return False


def _binary(name: str) -> str | None:
    return shutil.which(name)


def gather() -> list[dict]:
    results: list[dict] = []

    def add(name: str, ok: bool, detail: str, optional: bool = False) -> None:
        results.append({"component": name, "ok": ok, "detail": detail,
                        "optional": optional or name not in CRITICAL})

    skills_dir = ROOT / ".claude" / "skills"
    present = [s for s in REQUIRED_SKILLS if (skills_dir / s / "SKILL.md").exists()]
    missing = [s for s in REQUIRED_SKILLS if s not in present]
    add("permanent_skills", not missing,
        f"{len(present)}/{len(REQUIRED_SKILLS)} in {skills_dir}" +
        (f" - missing {', '.join(missing)}" if missing else ""))
    opt_present = [s for s in OPTIONAL_SKILLS if (skills_dir / s / "SKILL.md").exists()]
    add("optional_skills", True, f"{len(opt_present)}/{len(OPTIONAL_SKILLS)}: {', '.join(opt_present) or 'none'}", True)

    v = sys.version_info
    add("python", v >= (3, 10), f"{v.major}.{v.minor}.{v.micro} (need >= 3.10)")

    for binary in ("ffmpeg", "ffprobe"):
        path = _binary(binary)
        detail = path or "not installed - run bootstrap.sh"
        if path:
            try:
                ver = subprocess.run([binary, "-version"], capture_output=True, text=True).stdout
                detail = f"{ver.splitlines()[0].split()[2]} at {path}"
            except (OSError, IndexError):
                pass
        add(binary, bool(path), detail)

    add("whisper", _module("whisper"),
        "openai-whisper (local, open-source)" if _module("whisper") else "not installed - captions unavailable")
    add("kokoro", _module("kokoro"),
        "local TTS ready" if _module("kokoro") else "not installed - supply a real voice recording instead", True)

    wan_deps = {d: _module(d) for d in ("torch", "diffusers", "transformers", "accelerate", "safetensors")}
    missing_wan = [d for d, ok in wan_deps.items() if not ok]
    add("wan_dependencies", not missing_wan,
        "torch/diffusers/transformers/accelerate/safetensors present" if not missing_wan
        else f"missing {', '.join(missing_wan)} - generation runs on HF Space or Kaggle instead", True)

    musetalk = Path(os.environ.get("MUSETALK_HOME", ROOT / "third_party" / "MuseTalk"))
    add("musetalk", musetalk.exists(),
        f"present at {musetalk}" if musetalk.exists()
        else "not installed - optional; ads fall back to voice-over cuts", True)

    gpu = "no GPU (generation runs on HF Space or Kaggle)"
    gpu_ok = False
    if _module("torch"):
        try:
            import torch
            if torch.cuda.is_available():
                gpu_ok = True
                p = torch.cuda.get_device_properties(0)
                gpu = f"{p.name}, {p.total_memory / 1024**3:.1f} GB VRAM"
        except Exception as exc:  # noqa: BLE001
            gpu = f"torch present but CUDA probe failed: {exc}"
    add("gpu", gpu_ok, gpu, True)

    hf_token = bool(os.environ.get("HF_TOKEN") or os.environ.get("HUGGING_FACE_HUB_TOKEN"))
    add("huggingface_config", hf_token,
        "HF_TOKEN set (never committed)" if hf_token else "HF_TOKEN not set - needed only to deploy the Space", True)

    space = ROOT / "hf-space" / "app.py"
    hardware = "unknown"
    readme = ROOT / "hf-space" / "README.md"
    if readme.exists():
        for line in readme.read_text().splitlines():
            if line.strip().startswith("suggested_hardware:"):
                hardware = line.split(":", 1)[1].strip()
    add("zerogpu_config", space.exists() and hardware == "zero-a10g",
        f"hf-space present, suggested_hardware={hardware}" if space.exists() else "hf-space/app.py missing", True)

    nb = ROOT / "kaggle" / "tarjeeh_ugc_ai.ipynb"
    add("kaggle_fallback", nb.exists(), str(nb) if nb.exists() else "missing", True)

    audit = subprocess.run([sys.executable, str(ROOT / "scripts" / "audit_no_paid_apis.py")],
                           capture_output=True, text=True)
    add("no_paid_api_audit", audit.returncode == 0,
        "PASS - no active paid provider" if audit.returncode == 0 else audit.stdout.strip()[-300:])

    cfg = ROOT / "config" / "defaults.yaml"
    add("config", cfg.exists(), str(cfg) if cfg.exists() else "missing")
    return results


def main() -> int:
    ap = argparse.ArgumentParser(description="Environment readiness for tarjeeh-ugc-ai.")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    results = gather()
    critical_fail = [r for r in results if not r["ok"] and not r["optional"]]
    optional_fail = [r for r in results if not r["ok"] and r["optional"]]
    state = "READY" if not critical_fail and not optional_fail else \
            "NOT READY" if critical_fail else "PARTIALLY READY"

    if args.json:
        print(json.dumps({"state": state, "components": results}, indent=2))
    else:
        print(f"tarjeeh-ugc-ai setup check  ({ROOT})\n")
        for r in results:
            mark = "ok  " if r["ok"] else ("MISS" if r["optional"] else "FAIL")
            tag = " (optional)" if r["optional"] and not r["ok"] else ""
            print(f"  [{mark}] {r['component']:<20} {r['detail']}{tag}")
        print(f"\nSTATE: {state}")
        if critical_fail:
            print("  blocking: " + ", ".join(r["component"] for r in critical_fail))
        if optional_fail:
            print("  degraded: " + ", ".join(r["component"] for r in optional_fail))
            print("  (optional gaps never justify a paid provider - see POLICY_NO_PAID_APIS.md)")
    return 0 if not critical_fail else 1


if __name__ == "__main__":
    raise SystemExit(main())
