"""Wan 2.2 TI2V-5B scene generation via Hugging Face Diffusers.

Open weights, downloaded once and run on our own GPU (local, HF ZeroGPU, or Kaggle). This module
never contacts an inference API - paid or otherwise. If the free GPU is unavailable or its quota is
spent, it raises FreeGpuQuotaExhausted and the caller preserves the job for a later render.
"""
from __future__ import annotations

import gc
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .jobs import FreeGpuQuotaExhausted

MODEL_ID = os.environ.get("TARJEEH_WAN_MODEL", "Wan-AI/Wan2.2-TI2V-5B-Diffusers")

# Wan 2.2 TI2V-5B uses a 16x16x4-compression VAE: spatial dims must be multiples of 16 and
# num_frames must satisfy 4k+1, or the temporal decoder produces a truncated clip.
SPATIAL_MULTIPLE = 16
DEFAULT_FPS = 24

# Generate at 720x1280 and upscale at assembly. Native 1080x1920 diffusion OOMs free-tier GPUs for
# little visible gain once the clip is re-encoded for a phone screen.
DEFAULT_WIDTH = 720
DEFAULT_HEIGHT = 1280

BASE_NEGATIVE = (
    "cgi, 3d render, plastic skin, airbrushed, warped label, distorted text, unreadable logo, "
    "extra fingers, deformed hands, watermark, subtitles, stock footage look, gimbal glide, "
    "crane shot, studio lighting, oversaturated, low quality, blurry"
)

_PIPELINE: Any = None
_PIPELINE_MODE: str | None = None


@dataclass
class SceneSpec:
    """One Wan generation. Mirrors references/SCENE_PROMPT_SCHEMA.md."""
    prompt: str
    output_name: str
    scene_index: int = 0
    job_id: str = ""
    mode: str = "i2v"
    reference_image: str | None = None
    creator_reference: str | None = None
    negative_prompt: str = BASE_NEGATIVE
    seed: int = 0
    width: int = DEFAULT_WIDTH
    height: int = DEFAULT_HEIGHT
    num_frames: int = 97
    fps: int = DEFAULT_FPS
    num_inference_steps: int = 30
    guidance_scale: float = 5.0
    speaking: bool = False
    spoken_line: str = ""

    @classmethod
    def from_file(cls, path: str | Path) -> "SceneSpec":
        data = json.loads(Path(path).read_text())
        data.pop("duration_seconds", None)
        known = {f for f in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in data.items() if k in known})

    def normalized(self) -> "SceneSpec":
        """Snap dimensions and frame count onto the grid the VAE actually accepts."""
        self.width = max(SPATIAL_MULTIPLE, round(self.width / SPATIAL_MULTIPLE) * SPATIAL_MULTIPLE)
        self.height = max(SPATIAL_MULTIPLE, round(self.height / SPATIAL_MULTIPLE) * SPATIAL_MULTIPLE)
        if (self.num_frames - 1) % 4:
            self.num_frames = ((self.num_frames - 1) // 4) * 4 + 1
        self.num_frames = max(5, self.num_frames)
        return self


def frames_for_seconds(seconds: float, fps: int = DEFAULT_FPS) -> int:
    """Frame count for a duration, snapped to Wan's 4k+1 requirement."""
    raw = int(round(seconds * fps))
    # Round to the NEAREST valid 4k+1 rather than flooring: flooring silently shortens every
    # scene (96 -> 93 frames is 0.17s lost per shot, ~1s across a 5-shot ad).
    return max(5, int(round((raw - 1) / 4)) * 4 + 1)


def gpu_status() -> dict[str, Any]:
    try:
        import torch
    except ImportError:
        return {"available": False, "reason": "torch not installed"}
    if not torch.cuda.is_available():
        return {"available": False, "reason": "no CUDA device"}
    props = torch.cuda.get_device_properties(0)
    return {
        "available": True,
        "name": props.name,
        "total_vram_gb": round(props.total_memory / 1024**3, 1),
    }


def _is_quota_error(exc: BaseException) -> bool:
    """Distinguish 'the free allowance is spent' from an ordinary failure.

    ZeroGPU signals exhaustion through gradio's exception types or a quota message; a bare CUDA OOM
    is a sizing problem, not an allowance problem, and is handled separately.
    """
    text = f"{type(exc).__name__}: {exc}".lower()
    markers = ("quota", "exceeded your", "gpu task aborted", "no gpu available",
               "zerogpu", "rate limit", "out of credits", "usage limit")
    return any(m in text for m in markers)


def load_pipeline(mode: str = "i2v", *, offload: str = "model", dtype: str = "bfloat16") -> Any:
    """Load and cache the Wan pipeline with memory optimizations applied.

    offload: "model" (balanced, default), "sequential" (lowest VRAM, slowest), "none" (fastest).
    """
    global _PIPELINE, _PIPELINE_MODE
    if _PIPELINE is not None and _PIPELINE_MODE == mode:
        return _PIPELINE

    import torch
    from diffusers import AutoencoderKLWan

    if mode == "i2v":
        from diffusers import WanImageToVideoPipeline as Pipe
    else:
        from diffusers import WanPipeline as Pipe

    unload_pipeline()
    torch_dtype = {"bfloat16": torch.bfloat16, "float16": torch.float16}.get(dtype, torch.bfloat16)

    try:
        # The Wan VAE is numerically fragile in half precision - keep it fp32 while the
        # transformer runs in bf16. This is the configuration the model card specifies.
        vae = AutoencoderKLWan.from_pretrained(MODEL_ID, subfolder="vae", torch_dtype=torch.float32)
        pipe = Pipe.from_pretrained(MODEL_ID, vae=vae, torch_dtype=torch_dtype)
    except Exception as exc:  # noqa: BLE001 - classify before re-raising
        if _is_quota_error(exc):
            raise FreeGpuQuotaExhausted(f"could not acquire free GPU while loading: {exc}") from exc
        raise

    if offload == "sequential":
        pipe.enable_sequential_cpu_offload()
    elif offload == "model":
        pipe.enable_model_cpu_offload()
    else:
        pipe.to("cuda")

    for opt in ("enable_tiling", "enable_slicing"):
        fn = getattr(getattr(pipe, "vae", None), opt, None)
        if callable(fn):
            fn()
    if hasattr(pipe, "set_progress_bar_config"):
        pipe.set_progress_bar_config(disable=True)

    _PIPELINE, _PIPELINE_MODE = pipe, mode
    return pipe


def unload_pipeline() -> None:
    """Free the pipeline between expensive stages so lip-sync and encode get the VRAM back."""
    global _PIPELINE, _PIPELINE_MODE
    _PIPELINE, _PIPELINE_MODE = None, None
    gc.collect()
    try:
        import torch
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            torch.cuda.ipc_collect()
    except ImportError:
        pass


def generate_scene(spec: SceneSpec, out_dir: str | Path, *, offload: str = "model") -> Path:
    """Render one scene to MP4 and return its path.

    Image-to-video whenever a reference image exists: no text prompt reconstructs a real product
    label, so the supplied photograph conditions the generation directly.
    """
    import torch
    from diffusers.utils import export_to_video, load_image

    spec = spec.normalized()
    out_path = Path(out_dir) / Path(spec.output_name).name
    out_path.parent.mkdir(parents=True, exist_ok=True)

    reference = spec.reference_image or spec.creator_reference
    mode = "i2v" if (spec.mode == "i2v" and reference) else "t2v"
    if spec.mode == "i2v" and not reference:
        raise ValueError(
            f"scene {spec.scene_index} requests i2v but supplies no reference image; "
            "product accuracy requires the real photograph"
        )

    pipe = load_pipeline(mode, offload=offload)
    generator = torch.Generator(device="cpu").manual_seed(spec.seed)
    kwargs: dict[str, Any] = {
        "prompt": spec.prompt,
        "negative_prompt": spec.negative_prompt,
        "height": spec.height,
        "width": spec.width,
        "num_frames": spec.num_frames,
        "num_inference_steps": spec.num_inference_steps,
        "guidance_scale": spec.guidance_scale,
        "generator": generator,
    }
    if mode == "i2v":
        image = load_image(str(reference))
        kwargs["image"] = image.resize((spec.width, spec.height))

    try:
        frames = pipe(**kwargs).frames[0]
    except Exception as exc:  # noqa: BLE001
        if _is_quota_error(exc):
            raise FreeGpuQuotaExhausted(f"scene {spec.scene_index}: {exc}") from exc
        if isinstance(exc, torch.cuda.OutOfMemoryError) or "out of memory" in str(exc).lower():
            unload_pipeline()
            raise RuntimeError(
                f"CUDA OOM on scene {spec.scene_index} at {spec.width}x{spec.height}x"
                f"{spec.num_frames}. Retry with offload='sequential', fewer frames, or 480x854. "
                "This is a sizing problem - do not switch to a paid provider."
            ) from exc
        raise

    export_to_video(frames, str(out_path), fps=spec.fps)
    return out_path


def generate_scenes(specs: list[SceneSpec], out_dir: str | Path, *, offload: str = "model") -> list[Path]:
    """Render scenes in order, preserving completed work if the free allowance runs out mid-run."""
    done: list[Path] = []
    for spec in specs:
        try:
            done.append(generate_scene(spec, out_dir, offload=offload))
        except FreeGpuQuotaExhausted as exc:
            exc.detail = f"{exc.detail} (completed {len(done)}/{len(specs)} scenes; they are kept)"
            raise
    return done
