# tarjeeh-ugc-ai

Zero-cost UGC video advertising system. Give it a product photo and a brief; it produces
9:16 advertisements for Meta, Instagram Reels, TikTok and YouTube Shorts.

**Every generation stage runs on open weights on free/local compute.** No pay-per-generation
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
| Primary compute | Kaggle free GPU notebook |
| Secondary compute | local GPU → free HF ZeroGPU Space |

## Fastest way to make a video now

Use `kaggle/tarjeeh_ugc_ai.ipynb` as the primary renderer.

1. Kaggle → Create/New Notebook → Import Notebook.
2. Upload `kaggle/tarjeeh_ugc_ai.ipynb`.
3. Settings → Accelerator → GPU (T4 x2 if offered), Internet On.
4. Upload the product image as a Kaggle input/dataset.
5. Edit Cell 1 only.
6. Run All.
7. Download `/kaggle/working/tarjeeh-ugc-output/final_v1.mp4` etc.

Full instructions: [`docs/KAGGLE.md`](docs/KAGGLE.md).

## Claude Code usage

Tell Claude:

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
Prepare the ad plan for the Kaggle primary renderer.
Do not use any paid API.
```

Claude prepares the campaign/script/storyboard/prompts. Kaggle performs the actual GPU rendering.
The notebook can also run standalone with built-in claim-safe generic concepts when no `adplan.json` is supplied.

## Project restore / audit

```bash
./bootstrap.sh
python scripts/check_setup.py
python scripts/audit_no_paid_apis.py
```

## Layout

```
.claude/skills/        permanent Claude skills
  tarjeeh-ugc/           master orchestration skill
  planning-campaigns/    text-only advertising planning
  writing-ad-copy/
  writing-video-scripts/
  writing-video-prompts/ Wan-targeted prompts
  analyzing-products/
  analyzing-brand/
  auto-edit-video/       restored from pinned upstream
backend/               Wan generation, voice, lip-sync, job schema
hf-space/              optional free ZeroGPU Gradio Space
kaggle/                PRIMARY free Kaggle GPU renderer
scripts/               assembly, QA, audit, setup checks
config/defaults.yaml   central configuration
examples/              job file template
projects/<job_id>/     campaign working directory (gitignored)
```

## How a 20-second ad is built

Wan generates short clips, so **a 20-second ad is composed from multiple 3–5 second scenes**, never
one huge diffusion pass. The Kaggle renderer starts at 704×1280 and steps down automatically on GPU
memory pressure, then exports the final ad at 1080×1920.

The final 3-second CTA is budgeted **inside** the requested ad duration. A 20-second brief therefore
produces a 20-second file, not a 23-second file.

## Product and creator consistency

- **Product:** real product photography is used as the image-to-video reference when product accuracy matters.
- **Creator:** optionally supply one `CREATOR_IMAGE`; it is reused as the creator reference for creator shots.
- Without a creator image, the free renderer defaults to product-focused / voice-over UGC instead of inventing a stable human identity.

## The factual-claims rule

The system never invents prices, discounts, offers, fragrance notes, ingredients, longevity,
medical/performance claims, reviews, ratings, or business facts. Claude-prepared plans should carry
only facts you supplied. The standalone Kaggle scripts intentionally use subjective/generic language.

## When free GPU runs out

The run returns `FREE_GPU_QUOTA_EXHAUSTED`, preserves completed scenes, and stops. Resume later.
There is **no paid fallback** by design.

## Licences

Vendored skills and dependencies are documented in
[`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md). Model weights carry their own licences; review
Wan and MuseTalk terms before commercial use.

## Pinned dependency restore

`./bootstrap.sh` restores the audited third-party Claude skills at immutable commits: SuperCMO
`a6dd060ed46132e1944b1dd38981cb9ffcc42fc8` and auto-edit-video
`934f081c737028b537a8e40b8286c635a783297f`.
