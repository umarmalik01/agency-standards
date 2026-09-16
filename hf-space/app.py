"""Gradio + ZeroGPU backend for tarjeeh-ugc-ai.

FREE ZeroGPU only. @spaces.GPU wraps just the operations that genuinely need a GPU, so the free
allowance is spent on diffusion and lip-sync rather than on file shuffling. No paid hardware, no
paid inference endpoint, no pay-per-generation provider - if the allowance is gone this returns
FREE_GPU_QUOTA_EXHAUSTED and keeps the job for a later render.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
import traceback
import uuid
from pathlib import Path

import gradio as gr

try:
    import spaces  # provided by the ZeroGPU runtime
except ImportError:  # local dev - make the decorator a no-op
    class _Spaces:
        @staticmethod
        def GPU(*args, **kwargs):  # noqa: N802
            def wrap(fn):
                return fn
            return wrap if not args or not callable(args[0]) else args[0]
    spaces = _Spaces()  # type: ignore[assignment]

QUOTA_EXHAUSTED = "FREE_GPU_QUOTA_EXHAUSTED"
JOBS_ROOT = Path(os.environ.get("TARJEEH_JOBS", "/tmp/tarjeeh_jobs"))
JOBS_ROOT.mkdir(parents=True, exist_ok=True)

MODEL_ID = os.environ.get("TARJEEH_WAN_MODEL", "Wan-AI/Wan2.2-TI2V-5B-Diffusers")
SPATIAL_MULTIPLE = 16
BASE_NEGATIVE = (
    "cgi, 3d render, plastic skin, warped label, distorted text, unreadable logo, extra fingers, "
    "deformed hands, watermark, subtitles, gimbal glide, studio lighting, low quality, blurry"
)

_PIPE = None
_PIPE_MODE = None


# ----------------------------------------------------------------------------- helpers
def _quota(exc: BaseException) -> bool:
    text = f"{type(exc).__name__}: {exc}".lower()
    return any(m in text for m in
               ("quota", "exceeded your", "gpu task aborted", "no gpu available", "zerogpu"))


def _job_dir(job_id: str) -> Path:
    path = JOBS_ROOT / job_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def _write_status(job_id: str, **fields) -> dict:
    path = _job_dir(job_id) / "status.json"
    status = json.loads(path.read_text()) if path.exists() else {"job_id": job_id, "events": []}
    status.update(fields)
    status.setdefault("events", []).append({"t": time.time(), **fields})
    path.write_text(json.dumps(status, indent=2))
    return status


def _snap(width: int, height: int, frames: int) -> tuple[int, int, int]:
    width = max(SPATIAL_MULTIPLE, round(width / SPATIAL_MULTIPLE) * SPATIAL_MULTIPLE)
    height = max(SPATIAL_MULTIPLE, round(height / SPATIAL_MULTIPLE) * SPATIAL_MULTIPLE)
    frames = max(5, int(round((frames - 1) / 4)) * 4 + 1)
    return width, height, frames


# ----------------------------------------------------------------------------- endpoints
def health_check() -> dict:
    """Dependencies, GPU and policy state. No GPU is claimed for this - it must stay cheap."""
    def has(mod: str) -> bool:
        try:
            __import__(mod)
            return True
        except Exception:  # noqa: BLE001
            return False

    gpu = {"available": False}
    if has("torch"):
        import torch
        if torch.cuda.is_available():
            p = torch.cuda.get_device_properties(0)
            gpu = {"available": True, "name": p.name,
                   "vram_gb": round(p.total_memory / 1024**3, 1)}
    return {
        "status": "ok",
        "model": MODEL_ID,
        "hardware": "ZeroGPU (free)" if os.environ.get("SPACES_ZERO_GPU") else "local/other",
        "gpu": gpu,
        "dependencies": {m: has(m) for m in
                         ("torch", "diffusers", "transformers", "kokoro", "whisper")},
        "ffmpeg": bool(shutil.which("ffmpeg")),
        "paid_api_fallback": False,
        "policy": "open weights only; no pay-per-generation provider is ever called",
    }


@spaces.GPU(duration=240)
def generate_scene(
    product_image, prompt: str, seed: int = 0, negative_prompt: str = BASE_NEGATIVE,
    width: int = 720, height: int = 1280, num_frames: int = 97,
    num_inference_steps: int = 30, guidance_scale: float = 5.0,
    fps: int = 24, output_name: str = "scene.mp4", job_id: str = "",
):
    """Wan 2.2 image-to-video. Image-to-video whenever a product photo exists - no text prompt
    reconstructs a real label."""
    global _PIPE, _PIPE_MODE
    job_id = job_id or uuid.uuid4().hex[:10]
    out = _job_dir(job_id) / Path(output_name).name
    width, height, num_frames = _snap(width, height, num_frames)

    try:
        import torch
        from diffusers import AutoencoderKLWan
        from diffusers.utils import export_to_video, load_image

        mode = "i2v" if product_image is not None else "t2v"
        if _PIPE is None or _PIPE_MODE != mode:
            if mode == "i2v":
                from diffusers import WanImageToVideoPipeline as Pipe
            else:
                from diffusers import WanPipeline as Pipe
            # fp32 VAE alongside a bf16 transformer, per the model card - the Wan VAE is
            # numerically fragile in half precision.
            vae = AutoencoderKLWan.from_pretrained(MODEL_ID, subfolder="vae", torch_dtype=torch.float32)
            _PIPE = Pipe.from_pretrained(MODEL_ID, vae=vae, torch_dtype=torch.bfloat16)
            _PIPE.to("cuda")
            for opt in ("enable_tiling", "enable_slicing"):
                fn = getattr(getattr(_PIPE, "vae", None), opt, None)
                if callable(fn):
                    fn()
            _PIPE_MODE = mode

        kwargs = dict(prompt=prompt, negative_prompt=negative_prompt, height=height, width=width,
                      num_frames=num_frames, num_inference_steps=num_inference_steps,
                      guidance_scale=guidance_scale,
                      generator=torch.Generator(device="cpu").manual_seed(int(seed)))
        if mode == "i2v":
            kwargs["image"] = load_image(product_image).resize((width, height))

        frames = _PIPE(**kwargs).frames[0]
        export_to_video(frames, str(out), fps=fps)
        _write_status(job_id, stage="scene", state="done", output=str(out))
        return str(out), {"job_id": job_id, "output": str(out), "frames": num_frames,
                          "size": f"{width}x{height}", "mode": mode}
    except Exception as exc:  # noqa: BLE001
        if _quota(exc):
            _write_status(job_id, stage="scene", state=QUOTA_EXHAUSTED, detail=str(exc)[:300])
            return None, {"error": QUOTA_EXHAUSTED, "job_id": job_id,
                          "detail": "job preserved; render later. No paid fallback exists."}
        _write_status(job_id, stage="scene", state="error", detail=str(exc)[:300])
        return None, {"error": str(exc), "trace": traceback.format_exc()[-800:], "job_id": job_id}


def generate_voice(script: str, voice: str = "af_heart", lang_code: str = "a",
                   speed: float = 1.0, job_id: str = ""):
    """Kokoro TTS. CPU-capable, so it is deliberately not wrapped in @spaces.GPU - the free GPU
    allowance belongs to diffusion."""
    job_id = job_id or uuid.uuid4().hex[:10]
    out = _job_dir(job_id) / "voice.wav"
    if "[SLOT:" in script:
        return None, {"error": "script contains an unresolved [SLOT:] placeholder - "
                               "a factual value is missing; never voice a placeholder"}
    try:
        import numpy as np
        import soundfile as sf
        from kokoro import KPipeline
        chunks = [a for _, _, a in KPipeline(lang_code=lang_code)(script, voice=voice, speed=speed)]
        if not chunks:
            return None, {"error": "Kokoro produced no audio"}
        sf.write(str(out), np.concatenate(chunks), 24000)
        _write_status(job_id, stage="voice", state="done", output=str(out))
        return str(out), {"job_id": job_id, "output": str(out)}
    except Exception as exc:  # noqa: BLE001
        return None, {"error": str(exc), "job_id": job_id}


@spaces.GPU(duration=180)
def lip_sync(scene_video, voice_audio, job_id: str = "", bbox_shift: int = 0):
    """MuseTalk, optional. If it is unavailable the caller ships a voice-over cut instead -
    never a paid lip-sync service."""
    job_id = job_id or uuid.uuid4().hex[:10]
    home = Path(os.environ.get("MUSETALK_HOME", "MuseTalk"))
    out_dir = _job_dir(job_id)
    if not home.exists():
        return None, {"error": "musetalk_unavailable",
                      "fallback": "ship a voice-over cut: B-roll, reaction shots, product close-ups"}
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "scripts.inference", "--video_path", str(scene_video),
             "--audio_path", str(voice_audio), "--result_dir", str(out_dir),
             "--bbox_shift", str(bbox_shift)],
            cwd=home, capture_output=True, text=True, timeout=600,
        )
        if proc.returncode != 0:
            if _quota(Exception(proc.stderr)):
                return None, {"error": QUOTA_EXHAUSTED, "job_id": job_id}
            return None, {"error": proc.stderr[-400:], "job_id": job_id,
                          "fallback": "ship a voice-over cut"}
        produced = sorted(out_dir.glob("*.mp4"), key=lambda p: p.stat().st_mtime)
        return (str(produced[-1]), {"job_id": job_id}) if produced else \
               (None, {"error": "no output", "job_id": job_id})
    except subprocess.TimeoutExpired:
        return None, {"error": "musetalk_timeout", "fallback": "ship a voice-over cut"}


def assemble_ad(scene_files, voice_file, cta: str = "Order Now", job_id: str = ""):
    """FFmpeg assembly. CPU-only, so no GPU allowance is consumed here."""
    job_id = job_id or uuid.uuid4().hex[:10]
    project = _job_dir(job_id)
    for sub in ("scenes", "audio", "renders", "captions", "qa"):
        (project / sub).mkdir(parents=True, exist_ok=True)
    for i, f in enumerate(scene_files or []):
        shutil.copy(f, project / "scenes" / f"scene_{i:02d}.mp4")
    if voice_file:
        shutil.copy(voice_file, project / "audio" / "voice.wav")
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from assemble_ad import assemble  # type: ignore
        final = assemble(project, 1, cta=cta)
        _write_status(job_id, stage="assemble", state="done", output=str(final))
        return str(final), {"job_id": job_id, "output": str(final)}
    except Exception as exc:  # noqa: BLE001
        return None, {"error": str(exc), "job_id": job_id}


def job_status(job_id: str) -> dict:
    path = _job_dir(job_id) / "status.json"
    return json.loads(path.read_text()) if path.exists() else {"job_id": job_id, "state": "unknown"}


def download_result(job_id: str, name: str = "final_v1.mp4"):
    for candidate in (_job_dir(job_id) / "renders" / name, _job_dir(job_id) / name):
        if candidate.exists():
            return str(candidate)
    return None


# ----------------------------------------------------------------------------- UI
with gr.Blocks(title="Tarjeeh UGC AI") as demo:
    gr.Markdown(
        "# Tarjeeh UGC AI\n"
        "Open-source UGC ad backend — Wan 2.2 I2V · Kokoro · MuseTalk · Whisper · FFmpeg.\n\n"
        "**Free ZeroGPU only.** No paid generation API is reachable from this Space. "
        "When the free allowance runs out you get `FREE_GPU_QUOTA_EXHAUSTED` and the job is kept."
    )
    with gr.Tab("Health"):
        hb = gr.Button("Check", variant="primary")
        ho = gr.JSON()
        hb.click(health_check, outputs=ho, api_name="health_check")

    with gr.Tab("Scene"):
        with gr.Row():
            with gr.Column():
                s_img = gr.Image(type="filepath", label="Product / creator reference (image-to-video)")
                s_prompt = gr.Textbox(label="Scene prompt", lines=4)
                s_neg = gr.Textbox(label="Negative prompt", value=BASE_NEGATIVE, lines=2)
                with gr.Row():
                    s_seed = gr.Number(value=0, label="Seed", precision=0)
                    s_frames = gr.Slider(49, 121, value=97, step=4, label="Frames (4k+1)")
                with gr.Row():
                    s_w = gr.Slider(320, 1080, value=720, step=16, label="Width")
                    s_h = gr.Slider(320, 1920, value=1280, step=16, label="Height")
                with gr.Row():
                    s_steps = gr.Slider(10, 50, value=30, step=1, label="Steps")
                    s_cfg = gr.Slider(1.0, 10.0, value=5.0, step=0.5, label="Guidance")
                s_btn = gr.Button("Generate scene", variant="primary")
            with gr.Column():
                s_vid = gr.Video(label="Scene")
                s_json = gr.JSON()
        s_btn.click(generate_scene,
                    inputs=[s_img, s_prompt, s_seed, s_neg, s_w, s_h, s_frames, s_steps, s_cfg],
                    outputs=[s_vid, s_json], api_name="generate_scene")

    with gr.Tab("Voice"):
        v_text = gr.Textbox(label="Script", lines=4)
        v_voice = gr.Textbox(label="Kokoro voice", value="af_heart")
        v_btn = gr.Button("Generate voice", variant="primary")
        v_out, v_json = gr.Audio(label="Voice"), gr.JSON()
        v_btn.click(generate_voice, inputs=[v_text, v_voice], outputs=[v_out, v_json],
                    api_name="generate_voice")

    with gr.Tab("Lip-sync"):
        l_vid, l_aud = gr.Video(label="Scene"), gr.Audio(type="filepath", label="Voice")
        l_btn = gr.Button("Lip-sync (optional)")
        l_out, l_json = gr.Video(label="Result"), gr.JSON()
        l_btn.click(lip_sync, inputs=[l_vid, l_aud], outputs=[l_out, l_json], api_name="lip_sync")

    with gr.Tab("Assemble"):
        a_scenes = gr.File(file_count="multiple", label="Scenes (in order)")
        a_voice = gr.Audio(type="filepath", label="Voice")
        a_cta = gr.Textbox(label="CTA", value="Order Now")
        a_btn = gr.Button("Assemble 9:16 ad", variant="primary")
        a_out, a_json = gr.Video(label="Final"), gr.JSON()
        a_btn.click(assemble_ad, inputs=[a_scenes, a_voice, a_cta], outputs=[a_out, a_json],
                    api_name="assemble_ad")

    with gr.Tab("Jobs"):
        j_id = gr.Textbox(label="Job ID")
        with gr.Row():
            j_btn, d_btn = gr.Button("Status"), gr.Button("Download")
        j_json, d_file = gr.JSON(), gr.File(label="Render")
        j_btn.click(job_status, inputs=j_id, outputs=j_json, api_name="job_status")
        d_btn.click(download_result, inputs=j_id, outputs=d_file, api_name="download_result")

if __name__ == "__main__":
    demo.queue(max_size=12).launch()
