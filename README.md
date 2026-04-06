# ThinkFlix Briefing Generator

This repo implements a cost-efficient automated content briefing system. It converts a long-form text or PDF source into a 3-5 minute multimedia briefing with structured sections, slides, narration, and a capped generated video cutaway path.

## Demo Topic

The repo includes two demo inputs:

- `data/input/ai-index-2025.md`: an AI infrastructure briefing source bundle.
- `data/input/Gemma_(language_model).pdf`: a sample PDF briefing source about Google's Gemma model family.

## Architecture

- Python orchestrates ingestion, planning, TTS, slide rendering, and job manifests.
- PDF ingestion uses PyMuPDF only. It extracts document metadata, page text, page markers, and detected tables as Markdown.
- Gemma4 is the local LLM via Ollama only; no language-model API is used.
- A smaller local Ollama Gemma4 variant is the fallback when hardware is limited.
- Kokoro-82M generates narration locally.
- Wan2.2 cutaway generation defaults to a capped fal.ai API call because the target local machine is an RTX 4060 with 8GB VRAM.
- Local Wan2.2 remains available with `--video-mode wan` only for larger 24GB-plus GPU environments.
- FFmpeg is the primary final assembler. MoviePy is intentionally not part of the core composition path.

## Setup

System FFmpeg is recommended, but the project also installs `imageio-ffmpeg` as a packaged FFmpeg fallback. FFprobe is optional and only improves metadata probing.

```powershell
uv sync --extra dev
```

Local LLM serving:

```powershell
ollama pull gemma4
ollama pull gemma4:e4b
```

Optional video API setup:

```powershell
$env:FAL_KEY="YOUR_FAL_KEY"
```

## Run Without GPU Video

This produces a complete MP4 with a static cutaway placeholder.

```powershell
uv run briefing run --input data/input/Gemma_(language_model).pdf --out dist/gemma-briefing --config configs/default.yaml --no-video-model
```

Expected outputs:

- `dist/gemma-briefing/briefing.mp4`
- `dist/gemma-briefing/briefing_plan.json`
- `dist/gemma-briefing/cost_report.md`
- `dist/gemma-briefing/source_index.json`
- `dist/gemma-briefing/slides/*.png`
- `dist/gemma-briefing/audio/*.wav`
- `dist/gemma-briefing/video_clips/*.mp4`

The Markdown input can still be rendered with:

```powershell
uv run briefing run --input data/input/ai-index-2025.md --out dist/ai-infrastructure-briefing --config configs/default.yaml --no-video-model
```

## Run With Wan2.2 API Cutaway

Use this on the target RTX 4060 8GB PC. The pipeline keeps PDF extraction, planning, TTS, slides, and FFmpeg local, then sends only the short generated cutaway to fal.ai.

```powershell
uv run briefing run --input "data/input/Gemma_(language_model).pdf" --out dist/gemma-briefing-api --config configs/default.yaml --video-mode api
```

If `FAL_KEY` is not set or you want a zero-cost local run, use `--no-video-model`.

## Run Wan2.2 Locally On A Larger GPU

This is not the recommended RTX 4060 8GB path. Use it only on a 24GB-plus GPU machine after preparing the Wan2.2 repository and checkpoints.

```powershell
uv run briefing run --input data/input/Gemma_(language_model).pdf --out dist/gemma-briefing --config configs/default.yaml --video-mode wan
```

If Wan2.2 fails or the GPU window is unavailable, rerun with `--no-video-model`. The pipeline is designed so the expensive generation step is isolated and replaceable.

## Cost Story

Most stages run cheaply on commodity hardware. The only bursty high-cost step is optional short video generation, which is isolated and capped.

- Fixed compute: ingestion, planning, slides, TTS, validation, and FFmpeg assembly.
- Bursty compute: one short Wan2.2 API cutaway because it exceeds the target 8GB VRAM local profile.
- Marginal cost: near-zero for additional non-video runs; extra cost mainly scales with additional cutaways.

## Test

```powershell
uv run pytest
```

## Submission Notes

Submit:

- GitHub repository link.
- `briefing.mp4` or uploaded video link.
- `docs/explanation.md` as the 1-2 page architecture and cost explanation.
