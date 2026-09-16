# Scene prompt schema

One JSON file per scene, `prompts/scene_NN.json`.

```json
{
  "job_id": "uae-perfume-20260916",
  "scene_index": 2,
  "duration_seconds": 4,
  "mode": "i2v",
  "reference_image": "product/master_front.jpg",
  "creator_reference": "creator/master_creator.png",
  "prompt": "Handheld phone shot, a woman holds the perfume bottle at chest height...",
  "negative_prompt": "cgi, plastic skin, warped label, extra fingers, text artifacts, watermark, gimbal glide",
  "seed": 778812,
  "width": 720,
  "height": 1280,
  "num_frames": 97,
  "fps": 24,
  "num_inference_steps": 30,
  "guidance_scale": 5.0,
  "speaking": true,
  "spoken_line": "Hour nine. Still there.",
  "output_name": "scenes/scene_02.mp4"
}
```

## Field notes

- **`mode`** — `i2v` whenever a real product or creator reference exists. `t2v` only for
  environment B-roll with no product and no face in frame.
- **`seed`** — fixed per campaign for the creator; vary per scene only to reroll a bad take.
- **`num_frames`** — Wan 2.2 TI2V wants `4k+1`. At 24fps: 49 ≈ 2s, 73 ≈ 3s, 97 ≈ 4s, 121 ≈ 5s.
- **`width`/`height`** — generate at 720×1280 and upscale to 1080×1920 at assembly. Generating
  native 1080×1920 will OOM a free-tier GPU for very little visible gain.
- **`speaking`** — drives whether the scene is routed through MuseTalk.
- **`negative_prompt`** — always carry the label/anatomy guards; a warped label is the single most
  common failure in product I2V.

## Prompt shape

Follow `../writing-video-prompts/references/prompt-wan.md`. Subject → scene → motion → camera →
light → style, front-loading what must be preserved. Describe the product by its **behaviour in
frame** (held, tilted, set down), never by re-describing its appearance — the reference image
already carries appearance, and re-describing it invites the model to redraw it wrong.
