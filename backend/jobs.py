"""Job schema, project scaffolding and the free-GPU-exhaustion contract.

No network provider is contacted from this module.
"""
from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

QUOTA_EXHAUSTED = "FREE_GPU_QUOTA_EXHAUSTED"

PROJECT_DIRS = (
    "product", "creator", "scripts", "storyboards", "prompts",
    "audio", "scenes", "captions", "renders", "qa",
)


class FreeGpuQuotaExhausted(RuntimeError):
    """Raised when free GPU capacity is gone.

    The caller preserves the job and surfaces FREE_GPU_QUOTA_EXHAUSTED. There is deliberately no
    paid fallback path: escalating to a billable provider is a policy violation, not a recovery.
    """

    def __init__(self, detail: str = "", job_path: str | None = None):
        self.detail = detail
        self.job_path = job_path
        super().__init__(f"{QUOTA_EXHAUSTED}: {detail}" if detail else QUOTA_EXHAUSTED)


def slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", (text or "project").lower()).strip("-")
    return slug or "project"


@dataclass
class Creator:
    gender: str = "female"
    age_range: str = "25-35"
    appearance_direction: str = ""
    location: str = ""
    hairstyle: str = ""
    outfit: str = ""
    lighting: str = "natural window daylight"
    camera_style: str = "handheld iPhone"


@dataclass
class Job:
    product_name: str = ""
    product_image: str = ""
    country: str = "UAE"
    audience: str = ""
    creator: Creator = field(default_factory=Creator)
    language: str = "English"
    platform: str = "Meta"
    duration: int = 20
    aspect_ratio: str = "9:16"
    style: str = "natural handheld iPhone UGC"
    offer: str = ""
    cta: str = "Order Now"
    variations: int = 3
    job_id: str = ""
    # Facts the copy is allowed to assert. Anything absent stays a [SLOT] in the script.
    supplied_facts: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if isinstance(self.creator, dict):
            known = {f for f in Creator.__dataclass_fields__}
            self.creator = Creator(**{k: v for k, v in self.creator.items() if k in known})
        if not self.job_id:
            self.job_id = f"{slugify(self.product_name)}-{time.strftime('%Y%m%d')}"

    @classmethod
    def load(cls, path: str | Path) -> "Job":
        return cls(**json.loads(Path(path).read_text()))

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def validate(self) -> list[str]:
        """Return human-readable problems. Empty list means the job is renderable."""
        problems: list[str] = []
        if not self.product_name:
            problems.append("product_name is empty")
        if not self.product_image:
            problems.append(
                "product_image is empty - without a real product photo the run cannot use "
                "image-to-video, and product accuracy cannot be guaranteed"
            )
        elif not Path(self.product_image).exists():
            problems.append(f"product_image not found: {self.product_image}")
        if not 15 <= self.duration <= 30:
            problems.append(f"duration {self.duration}s outside the supported 15-30s range")
        if self.aspect_ratio != "9:16":
            problems.append(f"aspect_ratio {self.aspect_ratio} unsupported; this system is 9:16 only")
        if not 1 <= self.variations <= 5:
            problems.append(f"variations {self.variations} outside 1-5")
        return problems


def scaffold(root: str | Path, job: Job) -> Path:
    """Create projects/<job_id>/ with the standard layout and persist the resolved job."""
    project = Path(root) / "projects" / job.job_id
    for sub in PROJECT_DIRS:
        (project / sub).mkdir(parents=True, exist_ok=True)
    (project / "job.json").write_text(json.dumps(job.to_dict(), indent=2))
    return project


def plan_scenes(duration: int, max_scene_seconds: int = 4, cta_seconds: int = 3) -> list[int]:
    """Split a briefed duration into Wan-sized shots.

    Wan generates ~3-5s per diffusion pass, so a 20s ad is composed, never generated whole.

    The CTA card is part of the briefed duration, not an extension of it: a 20s ad is 17s of
    scenes plus a 3s end card, totalling 20s. Appending the card instead would ship a 23s file
    against a 20s brief and overrun the platform's cut.
    """
    scene_budget = max(max_scene_seconds, duration - cta_seconds)
    count = max(1, -(-scene_budget // max_scene_seconds))  # ceil
    base, extra = divmod(scene_budget, count)
    return [base + (1 if i < extra else 0) for i in range(count)]
