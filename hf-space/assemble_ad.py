#!/usr/bin/env python3
"""Assemble generated scenes into a finished 9:16 advertisement with local FFmpeg.

Scene concatenation, audio mixing, voice alignment, caption burn-in, 1080x1920 canvas, CTA card,
optional transitions, H.264 + AAC. Nothing leaves the machine.

    python scripts/assemble_ad.py --project projects/<job_id> --variation 1
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import captions as cap  # noqa: E402

CANVAS_W, CANVAS_H, FPS = cap.CANVAS_W, cap.CANVAS_H, 24
CTA_SECONDS = 3.0


def _run(cmd: list[str]) -> None:
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg failed:\n{' '.join(cmd[:8])}...\n{proc.stderr[-800:]}")


def require_ffmpeg() -> None:
    missing = [b for b in ("ffmpeg", "ffprobe") if not shutil.which(b)]
    if missing:
        raise RuntimeError(f"missing {', '.join(missing)} - run bootstrap.sh")


def probe_duration(path: str | Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        capture_output=True, text=True, check=True,
    )
    return float(out.stdout.strip())


def normalize_scene(src: Path, dst: Path) -> Path:
    """Scale each scene onto the 1080x1920 canvas without distorting it.

    Scenes are generated at 720x1280 to fit free-tier VRAM, so this is also the upscale step:
    cover-fit, centre-crop the overflow, then pad if the source was an odd ratio.
    """
    vf = (
        f"scale={CANVAS_W}:{CANVAS_H}:force_original_aspect_ratio=increase:flags=lanczos,"
        f"crop={CANVAS_W}:{CANVAS_H},"
        f"pad={CANVAS_W}:{CANVAS_H}:(ow-iw)/2:(oh-ih)/2,"
        f"fps={FPS},setsar=1"
    )
    _run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(src), "-vf", vf,
          "-an", "-c:v", "libx264", "-preset", "medium", "-crf", "18",
          "-pix_fmt", "yuv420p", str(dst)])
    return dst


def make_cta_card(text: str, dst: Path, seconds: float = CTA_SECONDS) -> Path:
    """A plain high-contrast end card. Deliberately undecorated - it has to read in 3 seconds."""
    safe = text.replace("'", "").replace(":", "\\:").replace("%", "")
    draw = (
        f"drawtext=text='{safe}':fontcolor=white:fontsize=96:"
        f"x=(w-text_w)/2:y=(h-text_h)/2:box=1:boxcolor=black@0.55:boxborderw=40"
    )
    _run(["ffmpeg", "-y", "-loglevel", "error",
          "-f", "lavfi", "-i", f"color=c=0x101010:s={CANVAS_W}x{CANVAS_H}:d={seconds}:r={FPS}",
          "-vf", draw, "-c:v", "libx264", "-preset", "medium", "-crf", "18",
          "-pix_fmt", "yuv420p", str(dst)])
    return dst


def concat(parts: list[Path], dst: Path, workdir: Path) -> Path:
    listing = workdir / "concat.txt"
    listing.write_text("".join(f"file '{p.resolve()}'\n" for p in parts))
    _run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
          "-i", str(listing), "-c", "copy", str(dst)])
    return dst


def mux_audio(video: Path, voice: Path | None, music: Path | None, dst: Path,
              music_gain: float = 0.12) -> Path:
    """Attach the voice track, optionally under a bed. Voice stays dominant - it carries the ad."""
    if voice is None and music is None:
        _run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(video),
              "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=48000",
              "-shortest", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", str(dst)])
        return dst

    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-i", str(video)]
    inputs, filters = [], []
    if voice:
        cmd += ["-i", str(voice)]
        inputs.append(f"[{len(inputs)+1}:a]")
    if music:
        cmd += ["-i", str(music)]
        inputs.append(f"[{len(inputs)+1}:a]")

    if voice and music:
        filters.append(f"{inputs[1]}volume={music_gain}[bed]")
        filters.append(f"{inputs[0]}[bed]amix=inputs=2:duration=first:dropout_transition=0[aout]")
    else:
        filters.append(f"{inputs[0]}anull[aout]")

    cmd += ["-filter_complex", ";".join(filters), "-map", "0:v", "-map", "[aout]",
            "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest", str(dst)]
    _run(cmd)
    return dst


def burn_captions(video: Path, srt: Path, dst: Path, font_size: int = 68) -> Path:
    if not cap.captions_within_safe_area(font_size):
        raise ValueError(f"caption font size {font_size} falls outside the platform safe area")
    _run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(video),
          "-vf", f"subtitles={srt.resolve()}:force_style='{cap.ass_style(font_size)}'",
          "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
          "-c:a", "copy", str(dst)])
    return dst


def assemble(project: Path, variation: int = 1, *, cta: str = "Order Now",
             burn: bool = True, music: Path | None = None) -> Path:
    require_ffmpeg()
    scenes = sorted((project / "scenes").glob(f"v{variation}_scene_*.mp4")) or \
             sorted((project / "scenes").glob("scene_*.mp4"))
    if not scenes:
        raise FileNotFoundError(f"no scenes in {project/'scenes'} - run generation first")

    voice = next((p for p in [project / "audio" / f"voice_v{variation}.wav",
                              project / "audio" / "voice.wav"] if p.exists()), None)
    renders = project / "renders"
    renders.mkdir(parents=True, exist_ok=True)
    final = renders / f"final_v{variation}.mp4"

    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        parts = [normalize_scene(s, work / f"n_{i:02d}.mp4") for i, s in enumerate(scenes)]
        if cta:
            parts.append(make_cta_card(cta, work / "cta.mp4"))

        silent = concat(parts, work / "silent.mp4", work)
        withaudio = mux_audio(silent, voice, music, work / "withaudio.mp4")

        if burn and voice:
            built = cap.build_captions(voice, project / "captions")
            burn_captions(withaudio, Path(built["srt"]), final)
        else:
            shutil.copy(withaudio, final)

    (project / "renders" / f"final_v{variation}.json").write_text(json.dumps({
        "scenes": [s.name for s in scenes],
        "voice": str(voice) if voice else None,
        "cta": cta,
        "captions_burned": bool(burn and voice),
        "duration_seconds": round(probe_duration(final), 2),
    }, indent=2))
    return final


def main() -> int:
    ap = argparse.ArgumentParser(description="Assemble a 9:16 UGC ad from generated scenes.")
    ap.add_argument("--project", required=True, type=Path)
    ap.add_argument("--variation", type=int, default=1)
    ap.add_argument("--cta", default="Order Now")
    ap.add_argument("--music", type=Path, default=None)
    ap.add_argument("--no-captions", action="store_true")
    args = ap.parse_args()
    out = assemble(args.project, args.variation, cta=args.cta,
                   burn=not args.no_captions, music=args.music)
    print(f"wrote {out} ({probe_duration(out):.2f}s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
