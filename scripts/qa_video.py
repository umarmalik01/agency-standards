#!/usr/bin/env python3
"""Quality assurance for a finished advertisement. Writes qa/qa_report.json.

A render that fails QA is not delivered. Every check runs locally through ffprobe/ffmpeg.

    python scripts/qa_video.py --project projects/<job_id> --variation 1
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import captions as cap  # noqa: E402

ACCEPTED_VIDEO_CODECS = {"h264"}
ACCEPTED_AUDIO_CODECS = {"aac"}
DURATION_TOLERANCE = 2.5      # seconds either side of the brief
MAX_BLACK_RUN = 0.60          # a longer black run reads as a glitch on Reels
CTA_SECONDS = 3.0             # trailing end card, excluded from black detection by design


def ffprobe(path: Path) -> dict:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-print_format", "json", "-show_format", "-show_streams", str(path)],
        capture_output=True, text=True, check=True,
    )
    return json.loads(out.stdout)


def black_runs(path: Path, threshold: float = MAX_BLACK_RUN,
               exclude_tail_seconds: float = CTA_SECONDS) -> list[float]:
    """Detect black runs, ignoring the trailing CTA card.

    The end card is intentionally near-black, so scanning it would report a guaranteed false
    failure on every correctly-built ad. Only the picture before it is checked.
    """
    duration = float(ffprobe(path)["format"]["duration"])
    scan_to = max(0.1, duration - exclude_tail_seconds)
    proc = subprocess.run(
        ["ffmpeg", "-i", str(path), "-t", f"{scan_to:.3f}",
         "-vf", f"blackdetect=d={threshold}:pix_th=0.10", "-an", "-f", "null", "-"],
        capture_output=True, text=True,
    )
    return [
        float(part.split(":")[1])
        for line in proc.stderr.splitlines() if "black_duration" in line
        for part in line.split() if part.startswith("black_duration")
    ]


def check(project: Path, variation: int, expected_duration: int | None = None,
          require_product_reference: bool = True) -> dict:
    render = project / "renders" / f"final_v{variation}.mp4"
    checks: list[dict] = []

    def record(name: str, ok: bool, detail: str = "") -> bool:
        checks.append({"check": name, "pass": bool(ok), "detail": detail})
        return ok

    if not record("file_exists", render.exists(), str(render)):
        return _report(project, variation, checks, render)

    try:
        meta = ffprobe(render)
    except subprocess.CalledProcessError as exc:
        record("decodes", False, exc.stderr[-300:] if exc.stderr else "ffprobe failed")
        return _report(project, variation, checks, render)
    record("decodes", True)

    video = next((s for s in meta["streams"] if s["codec_type"] == "video"), None)
    audio = next((s for s in meta["streams"] if s["codec_type"] == "audio"), None)

    if video:
        w, h = int(video["width"]), int(video["height"])
        record("orientation_9x16", (w, h) == (cap.CANVAS_W, cap.CANVAS_H), f"{w}x{h}")
        record("video_codec", video["codec_name"] in ACCEPTED_VIDEO_CODECS, video["codec_name"])
    else:
        record("orientation_9x16", False, "no video stream")
        record("video_codec", False, "no video stream")

    record("audio_present", audio is not None,
           audio["codec_name"] if audio else "no audio stream")
    if audio:
        record("audio_codec", audio["codec_name"] in ACCEPTED_AUDIO_CODECS, audio["codec_name"])

    duration = float(meta["format"]["duration"])
    if expected_duration:
        delta = abs(duration - expected_duration)
        record("duration_within_tolerance", delta <= DURATION_TOLERANCE,
               f"{duration:.2f}s vs {expected_duration}s (delta {delta:.2f}s)")
    else:
        record("duration_sane", 10 <= duration <= 45, f"{duration:.2f}s")

    runs = black_runs(render)
    record("no_long_black_frames", not runs,
           f"{len(runs)} run(s) over {MAX_BLACK_RUN}s" if runs else "none")

    scenes = sorted((project / "scenes").glob(f"v{variation}_scene_*.mp4")) or \
             sorted((project / "scenes").glob("scene_*.mp4"))
    record("scenes_present", bool(scenes), f"{len(scenes)} scene(s)")

    manifest = project / "renders" / f"final_v{variation}.json"
    if manifest.exists():
        data = json.loads(manifest.read_text())
        expected_scene_count = len(data.get("scenes", []))
        record("no_missing_scenes", len(scenes) >= expected_scene_count,
               f"{len(scenes)} on disk vs {expected_scene_count} in manifest")

    srt = project / "captions" / "captions.srt"
    if srt.exists():
        record("captions_in_safe_area", cap.captions_within_safe_area(),
               f"baseline {cap.CAPTION_BASELINE_PX}px, safe {cap.SAFE_TOP_PX}-{cap.SAFE_BOTTOM_PX}px")

    if require_product_reference:
        product_dir = project / "product"
        refs = [p for p in product_dir.glob("*") if p.suffix.lower() in
                {".jpg", ".jpeg", ".png", ".webp"}] if product_dir.exists() else []
        record("product_reference_supplied", bool(refs),
               f"{len(refs)} reference image(s) - required for product accuracy")

    return _report(project, variation, checks, render)


def _report(project: Path, variation: int, checks: list[dict], render: Path) -> dict:
    failed = [c["check"] for c in checks if not c["pass"]]
    report = {
        "project": str(project),
        "variation": variation,
        "render": str(render),
        "verdict": "PASS" if not failed else "FAIL",
        "failed_checks": failed,
        "checks": checks,
    }
    qa_dir = project / "qa"
    qa_dir.mkdir(parents=True, exist_ok=True)
    (qa_dir / f"qa_report_v{variation}.json").write_text(json.dumps(report, indent=2))
    (qa_dir / "qa_report.json").write_text(json.dumps(report, indent=2))
    return report


def main() -> int:
    ap = argparse.ArgumentParser(description="QA a finished advertisement render.")
    ap.add_argument("--project", required=True, type=Path)
    ap.add_argument("--variation", type=int, default=1)
    ap.add_argument("--expected-duration", type=int, default=None)
    ap.add_argument("--no-product-requirement", action="store_true")
    args = ap.parse_args()
    report = check(args.project, args.variation, args.expected_duration,
                   require_product_reference=not args.no_product_requirement)
    for c in report["checks"]:
        print(f"  [{'PASS' if c['pass'] else 'FAIL'}] {c['check']:<28} {c['detail']}")
    print(f"\nverdict: {report['verdict']}")
    return 0 if report["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
