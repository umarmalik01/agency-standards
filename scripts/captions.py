"""Captions from local Whisper word timings.

Local open-source Whisper only. OpenAI's paid transcription API is never called.
"""
from __future__ import annotations

import json
from pathlib import Path

# 1080x1920 safe area. Meta, TikTok and Shorts all draw UI over the frame; text outside this band
# gets covered by the CTA button, the caption overlay or TikTok's right-hand action rail.
CANVAS_W, CANVAS_H = 1080, 1920
UNSAFE_TOP = 0.14
UNSAFE_BOTTOM = 0.22
UNSAFE_RIGHT = 0.14

SAFE_TOP_PX = int(CANVAS_H * UNSAFE_TOP)
SAFE_BOTTOM_PX = int(CANVAS_H * (1 - UNSAFE_BOTTOM))
CAPTION_BASELINE_PX = 1180  # inside the band, low enough to leave the face clear

MIN_WORDS, MAX_WORDS = 2, 5


def transcribe(audio_path: str | Path, model_size: str = "base") -> dict:
    """Word-level timings from local Whisper. Downloads weights once, then runs offline."""
    try:
        import whisper
    except ImportError as exc:
        raise RuntimeError(
            "openai-whisper (the open-source package, not the paid API) is not installed. "
            "Run bootstrap.sh."
        ) from exc
    model = whisper.load_model(model_size)
    return model.transcribe(str(audio_path), word_timestamps=True, fp16=False)


def words_from_result(result: dict) -> list[dict]:
    words: list[dict] = []
    for segment in result.get("segments", []):
        for w in segment.get("words", []):
            text = w.get("word", "").strip()
            if text:
                words.append({"text": text, "start": float(w["start"]), "end": float(w["end"])})
    return words


def group_words(words: list[dict], max_words: int = MAX_WORDS, max_gap: float = 0.55) -> list[dict]:
    """Group words into short cards. Breaks on a pause or on sentence-final punctuation."""
    cards: list[dict] = []
    current: list[dict] = []
    for i, w in enumerate(words):
        current.append(w)
        gap = words[i + 1]["start"] - w["end"] if i + 1 < len(words) else 0.0
        ends_sentence = w["text"].endswith((".", "!", "?", ","))
        full = len(current) >= max_words
        if full or (len(current) >= MIN_WORDS and (gap > max_gap or ends_sentence)) or i == len(words) - 1:
            cards.append({
                "text": " ".join(x["text"] for x in current),
                "start": current[0]["start"],
                "end": current[-1]["end"],
            })
            current = []
    return cards


def _ts(seconds: float, sep: str = ",") -> str:
    ms = int(round(seconds * 1000))
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d}{sep}{ms:03d}"


def write_srt(cards: list[dict], path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    body = "\n".join(
        f"{i}\n{_ts(c['start'])} --> {_ts(c['end'])}\n{c['text']}\n"
        for i, c in enumerate(cards, 1)
    )
    path.write_text(body, encoding="utf-8")
    return path


def write_vtt(cards: list[dict], path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    body = "WEBVTT\n\n" + "\n".join(
        f"{_ts(c['start'], '.')} --> {_ts(c['end'], '.')}\n{c['text']}\n" for c in cards
    )
    path.write_text(body, encoding="utf-8")
    return path


def ass_style(font_size: int = 68) -> str:
    """Burned-in caption style: heavy sans, white on a soft shadow, centred in the safe band."""
    margin_v = CANVAS_H - CAPTION_BASELINE_PX
    return (
        f"FontName=DejaVu Sans,FontSize={font_size},PrimaryColour=&H00FFFFFF,"
        f"OutlineColour=&H00000000,BackColour=&H80000000,BorderStyle=1,Outline=4,Shadow=2,"
        f"Bold=1,Alignment=2,MarginL=90,MarginR=90,MarginV={margin_v}"
    )


def captions_within_safe_area(font_size: int = 68, lines: int = 2) -> bool:
    top = CAPTION_BASELINE_PX - lines * int(font_size * 1.35)
    return SAFE_TOP_PX <= top and CAPTION_BASELINE_PX <= SAFE_BOTTOM_PX


def build_captions(audio_path: str | Path, out_dir: str | Path, model_size: str = "base") -> dict:
    out_dir = Path(out_dir)
    result = transcribe(audio_path, model_size)
    cards = group_words(words_from_result(result))
    srt = write_srt(cards, out_dir / "captions.srt")
    vtt = write_vtt(cards, out_dir / "captions.vtt")
    (out_dir / "captions.json").write_text(json.dumps(cards, indent=2))
    return {"srt": str(srt), "vtt": str(vtt), "cards": len(cards)}
