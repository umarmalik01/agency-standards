---
title: Tarjeeh UGC AI
emoji: 🎬
colorFrom: indigo
colorTo: pink
sdk: gradio
sdk_version: 4.44.1
app_file: app.py
pinned: false
suggested_hardware: zero-a10g
license: apache-2.0
short_description: Open-source UGC ad generation - Wan 2.2 I2V, Kokoro, Whisper, FFmpeg
---

# Tarjeeh UGC AI — free generation backend

Scene generation, voice, optional lip-sync and assembly for `tarjeeh-ugc-ai`.

## Hardware — read before changing anything

`suggested_hardware: zero-a10g` is **ZeroGPU**, which is free. Do not switch this Space to
A10G / L4 / A100 / H100 dedicated hardware, and do not enable a paid Inference Endpoint or a
pay-as-you-go provider: all of those bill per hour or per call. If ZeroGPU quota is exhausted the
Space returns `FREE_GPU_QUOTA_EXHAUSTED` and preserves the job — that is the intended behaviour.
Use `kaggle/tarjeeh_ugc_ai.ipynb` as the free fallback.

## Interfaces

A Gradio UI, and the same functions over the API for the Claude workflow:

| Endpoint | Purpose |
| --- | --- |
| `/health_check` | dependency + GPU report |
| `/generate_scene` | product image + prompt + seed → scene MP4 |
| `/generate_voice` | script → Kokoro WAV |
| `/lip_sync` | scene + voice → lip-synced MP4 (optional) |
| `/assemble_ad` | scenes + voice → captioned 9:16 MP4 |
| `/job_status` | state of a submitted job |
| `/download_result` | fetch a finished render |

```python
from gradio_client import Client
client = Client("<your-username>/tarjeeh-ugc-ai")
print(client.predict(api_name="/health_check"))
```

## Deploy

```bash
pip install huggingface_hub
huggingface-cli login                 # free account; token stays local, never committed
huggingface-cli repo create tarjeeh-ugc-ai --type space --space_sdk gradio
git clone https://huggingface.co/spaces/<your-username>/tarjeeh-ugc-ai
cp -r hf-space/* tarjeeh-ugc-ai/ && cd tarjeeh-ugc-ai && git add -A
git commit -m "tarjeeh-ugc-ai backend" && git push
```

Then confirm in Settings that hardware reads **ZeroGPU**, and record the Space URL in
`config/defaults.yaml` under `compute.hf_space_url`.
