---
name: tarjeeh-ugc
description: >-
  Produces UGC-style short-form video advertisements end to end — product analysis, ad angle,
  hooks, script, creator spec, written storyboard, Wan scene prompts, image-to-video generation on
  free GPU, local voice, optional lip-sync, captions, CTA, FFmpeg assembly and QA — exporting
  9:16 MP4s for Meta, Instagram Reels, TikTok and YouTube Shorts. Use when the user asks to create
  UGC ads, product ads, testimonial ads, unboxing, demonstration, problem/solution or lifestyle ads,
  or says "create N UGC ads for this product". Every generation stage runs on open-source models we
  host ourselves. Never calls a paid generation API.
---

# tarjeeh-ugc — zero-cost UGC ad production

Turn a product image plus a brief into finished 9:16 advertisements.

**Cost rule, absolute.** Every generation stage runs on open weights on free GPU. There is no paid
fallback anywhere in this skill. If free GPU capacity is gone, return `FREE_GPU_QUOTA_EXHAUSTED`,
preserve the job, and stop — never substitute a paid provider. See `POLICY_NO_PAID_APIS.md`.

## Defaults

| Setting | Default | Allowed |
| --- | --- | --- |
| Aspect ratio | `9:16` | fixed for this skill |
| Final resolution | 1080×1920 | fixed |
| Duration | 20s | 15–30s |
| Variations | 3 | 1–5 |
| Platforms | Meta / Reels / TikTok | + YouTube Shorts |
| Language | English | any the script is written in |
| Video model | `Wan2.2-TI2V-5B-Diffusers` | — |
| Voice | user recording (preferred) → Kokoro | — |
| Lip-sync | MuseTalk, optional | — |
| Transcription | local Whisper | — |
| Editor | FFmpeg | — |

## Intents

```
/tarjeeh-ugc create 3 UGC ads for this product
/tarjeeh-ugc create a 20-second Meta UGC ad
/tarjeeh-ugc create a perfume testimonial ad for UAE
/tarjeeh-ugc clone the STRUCTURE and pacing of this reference ad using my own assets
```

On the clone intent, reproduce **structure only** — beat timing, shot order, hook mechanism, pacing.
Never reproduce the reference's footage, audio, music, script lines, voice or on-screen talent.
Say in the output which structural elements were carried across.

## The factual-claims rule — read before writing a word

This skill writes advertising that goes in front of a paid-ads review team. **Never invent a fact.**

Never invent: prices, discounts, offers, perfume or fragrance notes, ingredients, longevity or
"lasts N hours", medical or health claims, performance claims, reviews, testimonials, ratings,
star counts, customer counts, awards, certifications, delivery times, stock levels, or any
business fact.

Every factual claim must trace to a value the user supplied in the job file or in their message.
Where a claim is required and the fact is missing, leave a visible `[SLOT: description]` in the
script and list it under **Facts needed** in your reply. Ship the structure, ask for the fact.
Subjective creator language ("I love how this smells on me") is fine; a measurable assertion is not.

Keep claims suitable for advertising review: no before/after implication of physical change, no
health outcomes, no absolute superlatives presented as verified fact.

## Pipeline

Run these in order. Stages 1–15 are text and run wherever you are. Stages 16–23 need the backend
and a free GPU.

### 1–4 · Understand
1. **Product analysis.** A real product image is required for visual accuracy. Read it: container
   shape, colour, finish, label position, logotype, cap, proportions. Use `analyzing-products` for
   structure. Record to `projects/<slug>/product/product_profile.json`. No image → say so, and
   produce the text deliverables only.
2. **Audience.** Country, language, buying context, what they already use.
3. **Offer.** Exactly what the user supplied, verbatim. Nothing added.
4. **Angle.** Pick one per variation, and make the three genuinely different — different mechanism,
   not three rewrites. Use `planning-campaigns` when the user wants the reasoning shown.

### 5–7 · Write
5. **Hooks.** At least 3 distinct options per variation. The first 3 seconds carry the ad: open on a
   concrete claim, a number, a visible action or a confession. Never "Hey guys", never a logo card,
   never a slow establishing shot.
6. **Script.** Use `writing-video-scripts`. Natural spoken register — contractions, one idea per
   sentence, the way a person actually talks to a phone. Budget **~2.6 words per second**: a 20s ad
   is 50–55 spoken words. Avoid corporate voice unless the user asks for it.
7. **Scene split.** Wan generates ~3–5s per pass. A 20s ad is 4–6 shots. Never attempt a 20s
   single diffusion pass. Each scene gets: duration, spoken line, action, and whether the creator's
   face is visible and speaking (which decides lip-sync).

### 8–12 · Direct
8. **Written storyboard** — one row per scene: framing, subject action, camera move, product
   visibility, continuity notes. Markdown, to `storyboards/`. This is written, not generated art.
9. **Creator appearance** — from the user's supplied direction only. Write it to
   `creator/creator_profile.json`. Do not infer sensitive attributes about, or build a likeness of,
   any real identifiable person. The creator is a fictional composite from the user's brief.
10. **Framing** — handheld phone distances: selfie arm's-length, chest-height product hold, close
    detail. Mixed, never static throughout.
11. **Movement** — small natural handheld drift, micro-shake, a breath of reframe. No crane, no
    dolly, no gimbal glide; those read as produced commercial and kill UGC credibility.
12. **Lighting / environment** — practical domestic light, window daylight, lamp spill. The
    location the user named.

### 13–15 · Prompt
13. **Scene prompts.** Use `writing-video-prompts`, which is pinned to `references/prompt-wan.md`.
    One prompt per scene → `prompts/scene_NN.json`, matching `references/SCENE_PROMPT_SCHEMA.md`.
14. **Actor consistency.** One master creator reference image per campaign, reused as the reference
    into every scene, with a fixed `creator_seed`. Never re-describe her per scene — describe her
    once, reference her thereafter.
15. **Product consistency.** Whenever a real product image exists, the scene runs **image-to-video
    from that photograph**, not text-to-video. No text prompt reconstructs a real label. Never
    substitute a hallucinated product for the supplied one. Masters live in `product/`.

### 16–23 · Produce
16. **Generate scenes** — `backend/wan_backend.py`, or the HF Space, or the Kaggle notebook.
    On exhausted free GPU: emit `FREE_GPU_QUOTA_EXHAUSTED`, keep the job file, stop.
17. **Voice** — user's own recording if supplied (always better for UGC); otherwise Kokoro locally.
    Never send script text to a cloud TTS.
18. **Lip-sync** — MuseTalk, optional, only on shots where she is on camera speaking. If it will not
    fit in free GPU runtime, fall back to a voice-over cut: B-roll, reaction shots, product close-ups
    and non-speaking creator shots. The ad still ships.
19. **Assemble** — `scripts/assemble_ad.py`.
20. **Captions** — local Whisper word timings → 2–5 words per card, centred, inside the safe area.
21. **CTA** — last ~3s on screen, and repeated in the ad copy since in-video CTAs are not clickable.
22. **QA** — `scripts/qa_video.py` → `qa/qa_report.json`. Do not deliver a failing render.
23. **Export** — `renders/final_v1.mp4`, `final_v2.mp4`, `final_v3.mp4`.

## Safe areas, 1080×1920

Meta, TikTok and Shorts all draw UI over the frame. Keep captions and any burned-in text inside
the centre band: **top 14% and bottom 22% are unsafe**, plus the right 14% for TikTok's action rail.
The QA script enforces this.

## Job file

`examples/job.example.json` is the canonical shape; `config/defaults.yaml` fills anything omitted.
Write the resolved job to `projects/<slug>/job.json` before generating, so any run is reproducible.

## Output contract

Report per variation: angle, chosen hook, scene count, render path, QA verdict, and any unresolved
`[SLOT]` facts. Never report a render as delivered until QA has passed it.
