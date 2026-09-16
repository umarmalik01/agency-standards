"""Optional lip-sync via MuseTalk (https://github.com/TMElyralab/MuseTalk, open source).

Optional by design. Lip-sync is the most fragile and most GPU-hungry stage in the pipeline, so when
it will not fit in the free allowance the ad still ships as a voice-over cut: B-roll, reaction
shots, product close-ups and non-speaking creator shots. That degradation is a supported outcome,
not a failure - and never a reason to reach for a paid lip-sync service.
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

from .jobs import FreeGpuQuotaExhausted

MUSETALK_REPO = "https://github.com/TMElyralab/MuseTalk"
MUSETALK_HOME = Path(os.environ.get("MUSETALK_HOME", "third_party/MuseTalk"))


def musetalk_status() -> dict[str, object]:
    """Report readiness without importing it - MuseTalk pulls heavy deps at import time."""
    home = MUSETALK_HOME
    weights = home / "models"
    return {
        "repo_present": home.exists(),
        "weights_present": weights.exists() and any(weights.iterdir()) if weights.exists() else False,
        "home": str(home),
        "install": f"git clone {MUSETALK_REPO} {home} && follow its download_weights script",
    }


def available() -> bool:
    status = musetalk_status()
    return bool(status["repo_present"] and status["weights_present"])


def lip_sync(
    video_path: str | Path,
    audio_path: str | Path,
    out_path: str | Path,
    *,
    bbox_shift: int = 0,
    timeout_seconds: int = 900,
) -> Path:
    """Drive a generated creator shot with the voice track.

    Raises RuntimeError if MuseTalk is not installed, so the caller can fall back to a
    non-speaking cut rather than failing the whole ad.
    """
    video_path, audio_path, out_path = Path(video_path), Path(audio_path), Path(out_path)
    if not available():
        raise RuntimeError(
            f"MuseTalk not ready at {MUSETALK_HOME}. Fall back to a voice-over cut "
            "(non-speaking creator shots + product close-ups)."
        )
    out_path.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        "python", "-m", "scripts.inference",
        "--video_path", str(video_path.resolve()),
        "--audio_path", str(audio_path.resolve()),
        "--result_dir", str(out_path.parent.resolve()),
        "--bbox_shift", str(bbox_shift),
    ]
    try:
        proc = subprocess.run(
            cmd, cwd=MUSETALK_HOME, capture_output=True, text=True, timeout=timeout_seconds
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(
            f"MuseTalk exceeded {timeout_seconds}s of free GPU runtime. "
            "Ship the voice-over cut instead."
        ) from exc

    combined = f"{proc.stdout}\n{proc.stderr}".lower()
    if proc.returncode != 0:
        if any(m in combined for m in ("quota", "no gpu available", "zerogpu")):
            raise FreeGpuQuotaExhausted(f"lip-sync: {proc.stderr[-400:]}")
        raise RuntimeError(f"MuseTalk failed (exit {proc.returncode}): {proc.stderr[-400:]}")

    produced = sorted(out_path.parent.glob("*.mp4"), key=lambda p: p.stat().st_mtime)
    if not produced:
        raise RuntimeError("MuseTalk reported success but wrote no MP4")
    if produced[-1] != out_path:
        produced[-1].replace(out_path)
    return out_path


def plan_lipsync(scenes: list[dict]) -> dict[str, list[int]]:
    """Split scenes into those needing lip-sync and those that can stay silent.

    Only shots where the creator is on camera speaking need it; product close-ups, B-roll and
    reaction shots carry the voice-over without any mouth to match.
    """
    speaking = [s.get("scene_index", i) for i, s in enumerate(scenes) if s.get("speaking")]
    silent = [s.get("scene_index", i) for i, s in enumerate(scenes) if not s.get("speaking")]
    return {"needs_lipsync": speaking, "voiceover_only": silent}
