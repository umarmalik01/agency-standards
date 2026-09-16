# Kaggle primary renderer

This is the zero-additional-cost rendering path for Tarjeeh UGC AI.

## One-time setup

1. Sign in to Kaggle and complete any free account/phone verification Kaggle requires before enabling GPU.
2. Create a notebook and import `kaggle/tarjeeh_ugc_ai.ipynb` from this repository.
3. In notebook Settings, set Accelerator to **GPU** (T4 x2 if offered) and turn **Internet On** for the initial dependency/model download.
4. Upload the product image through Kaggle Input / New Dataset. Kaggle will expose a path similar to `/kaggle/input/<dataset>/<file>.jpg`.

## Every ad run

Edit Cell 1 only:

- `PRODUCT_IMAGE`
- optional `CREATOR_IMAGE`
- `PRODUCT_NAME`
- `COUNTRY`
- `AUDIENCE`
- `CREATOR_TYPE`
- `LOCATION`
- `LANGUAGE`
- `DURATION_SECONDS`
- `OFFER`
- `CTA`
- `VARIATIONS`

Then choose **Run All**.

Expected status sequence:

`DOWNLOADING_MODELS → PREPARING_AD → GENERATING_SCENE_1… → GENERATING_VOICE → LIP_SYNC → ADDING_CAPTIONS → ASSEMBLING → QA → COMPLETE`

Final files are written to:

`/kaggle/working/tarjeeh-ugc-output/final_v1.mp4`

`/kaggle/working/tarjeeh-ugc-output/final_v2.mp4`

`/kaggle/working/tarjeeh-ugc-output/final_v3.mp4`

and QA to:

`/kaggle/working/tarjeeh-ugc-output/qa_report.json`

## Best workflow with Claude

Ask Claude Code to prepare an ad plan, then export it as `adplan.json`. Upload that file to Kaggle and set `ADPLAN_JSON` in Cell 1. This gives you Claude-quality scripts/storyboards/prompts while Kaggle performs the free GPU work.

Example instruction to Claude:

```
Use the permanent tarjeeh-ugc skill.
Create 3 UGC Meta ad concepts for the attached product.
Prepare a factual, claim-safe adplan.json for the Kaggle primary renderer.
Do not render in Claude and do not call any paid API.
```

If no `adplan.json` is supplied, the notebook generates three generic claim-safe concept structures on its own.

## GPU behaviour

- Primary model: `Wan-AI/Wan2.2-TI2V-5B-Diffusers`.
- Model CPU offload is enabled.
- VAE tiling/slicing are enabled where supported.
- Each ad is split into multiple 3–5 second scenes.
- Default first attempt is 704×1280; OOM fallback steps down to 640×1152 and then 576×1024 with fewer frames/steps.
- Completed scene files are reused when rerunning the same Kaggle session/cache, so an interrupted run can resume instead of regenerating every completed scene.
- Final output is upscaled/composited to 1080×1920 H.264 + AAC.

## Lip-sync

MuseTalk remains optional because it can compete with Wan for GPU memory. If MuseTalk assets are absent, fail, or do not fit the free GPU, the notebook automatically continues as a voice-over UGC cut. It must never switch to a paid lip-sync provider.

## Cost rule

The notebook may install open-source Python packages and download open model weights. It must not use FAL, WaveSpeed, Replicate, Runway, ElevenLabs, HeyGen, Kling/Veo/Seedance APIs, paid Hugging Face inference, or any pay-per-generation service.

If free GPU is unavailable, stop and report `FREE_GPU_QUOTA_EXHAUSTED` rather than buying compute.
