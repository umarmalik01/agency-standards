# Policy — no paid generation APIs

**This project spends nothing per generation. There is no exception, no trial, and no fallback.**

Every image, video, voice and transcription stage runs on open weights, on hardware we already
have: a local GPU, a free Hugging Face ZeroGPU Space, or a free Kaggle GPU session.

## Never integrate

fal / fal.ai · WaveSpeed · Replicate · Runway · ElevenLabs · HeyGen · Kling API · Veo API ·
Seedance API · OpenAI generation APIs (image, video, audio, paid transcription) · Stability paid
APIs · Together paid inference · Fireworks · paid Hugging Face Inference Endpoints · paid GPU
Spaces · any other pay-per-generation provider.

Do not add these as an "optional" provider, a "premium tier", or a convenience fallback. Do not
ask the operator for their API keys. The absence of these is the product requirement.

## What replaces them

| Stage | Tool | Licence / cost |
| --- | --- | --- |
| Video generation | `Wan-AI/Wan2.2-TI2V-5B-Diffusers` | Apache-2.0 open weights, self-hosted |
| Voice | Kokoro (or the user's own recording) | Apache-2.0, runs on CPU |
| Lip-sync (optional) | MuseTalk | open source, self-hosted |
| Transcription | openai-whisper, the **open-source package** | MIT, runs locally |
| Editing / encode | FFmpeg | LGPL/GPL, local |

Note the one genuinely confusing name: `openai-whisper` is the free, locally-run pip package. It is
not the OpenAI transcription API. Installing it costs nothing and sends nothing anywhere.

## When free capacity runs out

Return the sentinel `FREE_GPU_QUOTA_EXHAUSTED`, preserve the job and every scene already rendered,
and stop. The operator renders later, or switches to the Kaggle fallback.

**Waiting is the correct outcome. Paying is not.** A blocked render is a scheduling inconvenience;
a silent switch to a billable provider is a breach of the one rule this project exists to keep.

## Enforcement

`scripts/audit_no_paid_apis.py` runs over every executable and config file and exits non-zero on
any active integration — a provider import, a provider endpoint, a provider credential read, or a
provider package install. It is deliberately structural rather than keyword-based, so that
documentation (including this file, which names every banned provider) does not trip it.

```bash
python scripts/audit_no_paid_apis.py    # 0 = clean, 1 = violation
```

Run it before every commit. If it fails, remove the integration — never suppress the check.
