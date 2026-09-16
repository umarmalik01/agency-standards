# tarjeeh-ugc-ai

Zero-cost UGC video advertising system. Give it a product photo and a brief; it produces
9:16 advertisements for Meta, Instagram Reels, TikTok and YouTube Shorts.

**Every generation stage runs on open weights on hardware you already have.** No pay-per-generation
provider is integrated, and none may be added — see [`POLICY_NO_PAID_APIS.md`](POLICY_NO_PAID_APIS.md).

## The stack

| Stage | Tool |
| --- | --- |
| Planning, hooks, scripts, prompts | vendored text-only Claude skills |
| Video | Wan 2.2 TI2V-5B (image-to-video, self-hosted) |
| Voice | your own recording, or Kokoro locally |
| Lip-sync (optional) | MuseTalk |
| Captions | local open-source Whisper word timings |
| Edit / encode | FFmpeg → H.264 + AAC, 1080×1920 |
| Compute | local GPU → free HF ZeroGPU Space → free Kaggle notebook |

## Quick start

```bash
./bootstrap.sh                      # free/open-source deps only; no API keys
python scripts/check_setup.py       # READY / PARTIALLY READY / NOT READY
python scripts/audit_no_paid_apis.py
```

Then, in Claude Code:

```
Create 3 UGC Meta ads for this perfume.
Audience: UAE
Creator: Filipino female, 25-35
Location: Dubai apartment
Style: natural handheld iPhone UGC
Language: English
Duration: 20 seconds
CTA: Order Now
Use the attached product photo.
```

The `tarjeeh-ugc` skill takes it from product analysis through to the final MP4s.

## Layout

```
.claude/skills/        custom master skill is committed; pinned third-party skills are restored by bootstrap.sh
  tarjeeh-ugc/           master orchestration skill
  planning-campaigns/    ) restored from pinned SuperCMO commit (Apache-2.0),
  writing-ad-copy/       ) text-only, audited: no paid generation calls
  writing-video-scripts/ )
  writing-video-prompts/ ) patched to target Wan only
  analyzing-products/    )
  analyzing-brand/       )
  auto-edit-video/       restored from pinned natyang1234 commit (MIT)
backend/               Wan generation, voice, lip-sync, job schema
hf-space/              free ZeroGPU Gradio Space
kaggle/                free Kaggle GPU fallback notebook
scripts/               assemble_ad · qa_video · captions · audit · check_setup
config/defaults.yaml   central configuration
examples/              job file template
projects/<job_id>/     per-campaign working directory (gitignored)
```

## How a 20-second ad is built

Wan generates ~3–5 seconds per diffusion pass, so **a 20s ad is composed from 4–6 shots**, never
produced in one pass. Scenes are generated at 720×1280 (free-tier VRAM) and upscaled to 1080×1920
at assembly.

Two consistency rules do most of the work:

- **Product** — whenever a real product photo exists, scenes run **image-to-video from that
  photograph**. No text prompt reconstructs a real label, so text-to-video is used only for
  environment B-roll with no product and no face in frame.
- **Creator** — one master creator reference image per campaign, reused into every scene with a
  fixed seed. She is described once and referenced thereafter.

## The factual-claims rule

The system **never invents** prices, discounts, offers, fragrance notes, ingredients, longevity,
medical or performance claims, reviews, ratings or any business fact. Facts come from
`supplied_facts` in the job file. Where a claim is needed and the fact is missing, the script keeps
a visible `[SLOT: …]` and the run reports it back as a fact needed. Placeholders are blocked from
reaching voice synthesis.

## When free GPU runs out

The run returns `FREE_GPU_QUOTA_EXHAUSTED`, preserves the job and every scene already rendered, and
stops. Resume later, or switch to `kaggle/tarjeeh_ugc_ai.ipynb`. There is no paid fallback by
design.

## Licences

Vendored skills and dependencies are documented in
[`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md). Model weights carry their own licences —
review Wan's and MuseTalk's terms before commercial use.


## Pinned dependency restore

`./bootstrap.sh` restores the audited third-party Claude skills at immutable commits: SuperCMO `a6dd060ed46132e1944b1dd38981cb9ffcc42fc8` and auto-edit-video `934f081c737028b537a8e40b8286c635a783297f`. The project-specific `tarjeeh-ugc` skill and all backend code are committed directly here.
