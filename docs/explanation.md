# Automated Multimedia Briefing

## Architecture

This project builds a 3-5 minute multimedia briefing from a long-form text or PDF input. Python owns orchestration and validation. FFmpeg owns final media composition because it is deterministic, lightweight, and production-proven.

Pipeline stages:

1. Ingest `.txt`, `.md`, or `.pdf` input and normalize it into chunks. PDF extraction uses PyMuPDF only, including metadata, page markers, page text, and detected tables serialized as Markdown.
2. Ask local Gemma4 through Ollama to return a strict briefing JSON plan.
3. Validate the plan with Pydantic v2 and fall back to a deterministic local heuristic when local model serving is unavailable.
4. Render executive-style slides with Pillow.
5. Generate narration with Kokoro-82M; if Kokoro is unavailable, generate placeholder WAV timing so the pipeline remains testable.
6. Generate at least one abstract cutaway with a Wan2.2 API call when `FAL_KEY` is configured, or use a static placeholder in no-cost local mode.
7. Assemble sections and cutaways with FFmpeg into H.264/AAC MP4 output.

## Tools and Models

- Gemma4 via Ollama for planning and structuring. No language-model API is used.
- Fallback local model: smaller Ollama Gemma4 variant such as `gemma4:e4b` when hardware is limited.
- Kokoro-82M for local text-to-speech narration.
- Wan2.2 via fal.ai API for one required generated cutaway on the RTX 4060 8GB target machine, with second and third clips only if time allows and budget permits.
- Pillow for slide rendering.
- PyMuPDF for PDF text extraction and table extraction.
- FFmpeg and FFprobe for deterministic media assembly and validation.
- Pydantic v2 for schema contracts and validation.

## Cost Considerations

The system is designed so most pipeline stages run cheaply on commodity hardware. Ingestion, planning, slides, TTS, validation, and FFmpeg assembly are fixed local compute costs.

The only bursty high-cost step is optional short video generation, which is isolated and capped. On the target RTX 4060 8GB PC, this step uses a Wan2.2 API call because local video generation is the only stage that exceeds the local VRAM profile. No-GPU runs use static placeholders.

Variable marginal cost is near-zero for additional non-video runs. Extra cost scales mainly with additional generated cutaways, which are explicitly opportunistic and do not block delivery.

## Limitations

- Final MP4 rendering uses system FFmpeg when available and falls back to the packaged `imageio-ffmpeg` binary. FFprobe is optional because duration probing can fall back to FFmpeg output parsing.
- Wan2.2 API generation requires `FAL_KEY`. Local Wan2.2 generation is still possible only on a compatible larger-GPU environment with model checkpoints.
- Generated video is used only for abstract visual cutaways. Factual claims stay in source-backed narration and slides.
- The deterministic heuristic planner is a fallback, not a substitute for reviewing the source-backed briefing plan.
- The PDF path intentionally avoids Docling and other heavy document backends for the current clean sample PDF.

## Reproduction

```powershell
uv sync --extra dev
uv run briefing run --input "data/input/Gemma_(language_model).pdf" --out dist/gemma-briefing --config configs/default.yaml --no-video-model
```

For API cutaway generation on the RTX 4060 8GB PC, set `FAL_KEY`, then run:

```powershell
$env:FAL_KEY="YOUR_FAL_KEY"
uv run briefing run --input "data/input/Gemma_(language_model).pdf" --out dist/gemma-briefing-api --config configs/default.yaml --video-mode api
```
