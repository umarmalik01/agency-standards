# Third-party notices

This project vendors and depends on third-party open-source work. Licences are preserved
alongside the vendored code.

## Vendored into `.claude/skills/`

### SuperCMO skills — Apache License 2.0
Source: https://github.com/SupercmoHQ/superCMO-skills
Licence: `.claude/skills/LICENSE.supercmo.apache-2.0` · Notice: `.claude/skills/NOTICE.supercmo`

Vendored, text-only skills: `planning-campaigns`, `writing-ad-copy`, `writing-video-scripts`,
`writing-video-prompts`, `analyzing-products`, `analyzing-brand`.

Every skill was audited before vendoring; none calls `image_generate`, `video_generate` or
`audio_generate`. All paid-generation skills were deliberately excluded — see below.

**Modifications:** `writing-video-prompts` was patched to remove the prompt guides for paid models
(Veo, Kling, Seedance, Grok, Gemini) and to default to `wan-2.2-ti2v-5b`. The change is marked
inline in that skill's `SKILL.md` as a vendor patch.

**Excluded by policy** (they invoke paid generation): `generating-images`,
`generating-product-photos`, `generating-image-ads`, `generating-ai-actors`,
`generating-storyboards`, `generating-videos`, `generating-ugc-videos`, `generating-ad-videos`,
`generating-cartoon-videos`, `cloning-video-ads`, `generating-audio`, `adapting-formats`.
Their functionality is replaced by this project's own open-source pipeline.

### auto-edit-video — MIT
Source: https://github.com/natyang1234/auto-edit-video-skill
Licence: `.claude/skills/auto-edit-video/LICENSE`

Audited before vendoring: the install script only copies files, and the editing pipeline is local
FFmpeg + local Whisper. Its voice providers include cloud options (`rumi`, `edge`, `heygen`,
`elevenlabs`, `auto`) as **name strings only** — no endpoint or SDK is bundled. This project pins
`kokoro` and never selects `auto`, which would otherwise chain HeyGen → ElevenLabs → Kokoro.

## Runtime dependencies

| Component | Licence | Source |
| --- | --- | --- |
| Wan 2.2 TI2V-5B | Apache-2.0 | https://huggingface.co/Wan-AI/Wan2.2-TI2V-5B-Diffusers |
| Diffusers / Transformers | Apache-2.0 | https://github.com/huggingface/diffusers |
| Kokoro TTS | Apache-2.0 | https://github.com/hexgrad/kokoro |
| MuseTalk (optional) | see repo | https://github.com/TMElyralab/MuseTalk |
| Whisper (open-source pkg) | MIT | https://github.com/openai/whisper |
| FFmpeg | LGPL-2.1+/GPL-2+ | https://ffmpeg.org |
| Gradio | Apache-2.0 | https://github.com/gradio-app/gradio |

Model weights carry their own licences. Review Wan's and MuseTalk's terms before commercial use.
