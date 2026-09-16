"""Voice for the ad. Two modes, both free.

MODE A (preferred) - the user's own recording. For UGC, a real creator reading the line beats any
synthetic voice, and it costs nothing.
MODE B - Kokoro, an open-weights TTS that runs locally.

Script text is NEVER sent to a cloud TTS. ElevenLabs, HeyGen, Fish cloud, PlayHT, Azure and the
rest are not integrated here and must not be added.
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

KOKORO_SAMPLE_RATE = 24_000
DEFAULT_VOICE = "af_heart"

# Open-weights, local. Anything not on this list needs a policy review before it is added.
ALLOWED_TTS_BACKENDS = ("user_recording", "kokoro", "piper")


def use_user_recording(source: str | Path, out_path: str | Path) -> Path:
    """Mode A - copy the user's own recording into the project, normalizing to 24kHz mono WAV."""
    source, out_path = Path(source), Path(out_path)
    if not source.exists():
        raise FileNotFoundError(f"voice recording not found: {source}")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if not shutil.which("ffmpeg"):
        raise RuntimeError("ffmpeg is required to normalize the recording; run bootstrap.sh")
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-i", str(source),
         "-ac", "1", "-ar", str(KOKORO_SAMPLE_RATE), str(out_path)],
        check=True,
    )
    return out_path


def kokoro_available() -> bool:
    try:
        import kokoro  # noqa: F401
        return True
    except Exception:  # noqa: BLE001
        return False


def generate_voice(
    text: str,
    out_path: str | Path,
    *,
    voice: str = DEFAULT_VOICE,
    lang_code: str = "a",
    speed: float = 1.0,
) -> Path:
    """Mode B - synthesize locally with Kokoro. Runs on CPU; no network call at inference."""
    if not text.strip():
        raise ValueError("refusing to synthesize empty text")
    if "[SLOT:" in text:
        raise ValueError(
            "script still contains an unresolved [SLOT:] placeholder - a factual value is missing. "
            "Fill it from user-supplied facts before voicing; never let a placeholder reach an ad."
        )

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        import numpy as np
        import soundfile as sf
        from kokoro import KPipeline
    except ImportError as exc:
        raise RuntimeError(
            "Kokoro is not installed. Run bootstrap.sh, or supply a real voice recording "
            "(Mode A), which is the better option for UGC anyway."
        ) from exc

    pipeline = KPipeline(lang_code=lang_code)
    chunks = [audio for _, _, audio in pipeline(text, voice=voice, speed=speed)]
    if not chunks:
        raise RuntimeError("Kokoro produced no audio")
    sf.write(str(out_path), np.concatenate(chunks), KOKORO_SAMPLE_RATE)
    return out_path


def voice_duration(path: str | Path) -> float:
    """Measured duration in seconds - used to check the script actually fits the ad length."""
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        capture_output=True, text=True, check=True,
    )
    return float(out.stdout.strip())
