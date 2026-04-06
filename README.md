# ThinkFlix Briefing Generator

ThinkFlix converts a long-form text or PDF source into a 3-5 minute executive briefing video with source-grounded narration, designed slides, and planner-selected visuals embedded directly into those slides.

## Demo Inputs

- `data/input/ai-index-2025.md`: AI infrastructure briefing source bundle.
- `data/input/Gemma_(language_model).pdf`: sample PDF about Google's Gemma model family.

## Architecture

- Python orchestrates ingestion, local planning, still-visual generation, slide rendering, narration, and final assembly.
- PDF ingestion uses PyMuPDF only. It extracts metadata, page text, page markers, and detected tables as Markdown.
- Gemma4 runs locally through Ollama. It acts as the planner and visual orchestrator: it creates the briefing structure, slide bullets, narration, citations, and section-level visual decisions.
- The plan is validated with Pydantic. A deterministic local fallback keeps the demo runnable if Ollama is unavailable.
- Kokoro-82M generates narration locally.
- Pillow renders executive briefing slides with a fixed text column and a strong right-side media panel.
- LTX is the only remote media provider. It is used only when Gemma explicitly selects `generated_image` for a section. The LTX prompt is passed through exactly as Gemma authored it.
- FFmpeg assembles the narrated slide deck into the final MP4.

## Planning Model

Gemma produces, per section:

- `visual_mode`: `none`, `diagram`, `table_focus`, or `generated_image`
- `visual_role`
- `image_prompt` when `generated_image` is selected
- `visual_caption`
- `visual_grounding_notes`

This keeps the visual treatment attached to the section it supports instead of breaking the briefing into a separate cutaway segment.

## Setup

System FFmpeg is recommended, but the project also installs `imageio-ffmpeg` as a packaged fallback.

```powershell
uv sync --extra dev
```

Local LLM serving:

```powershell
ollama pull gemma4
ollama pull gemma4:e4b
```

Provider-backed visuals:

```powershell
$env:LTX_API_KEY="YOUR_LTX_API_KEY"
```

You can also put `LTX_API_KEY=...` or `LTXV_API_KEY=...` in a local `.env` file in the repo root. The CLI loads `.env` automatically and `.env` is ignored by Git.

## Run With Local Visuals Only

This keeps all visuals local. If Gemma selects `generated_image` for a section, the system renders a local placeholder visual for that section instead of calling the provider.

```powershell
uv run briefing run --input "data/input/Gemma_(language_model).pdf" --out dist/gemma-briefing --config configs/default.yaml --no-visual-provider
```

## Run With Provider-Backed Section Visuals

Use this on the target RTX 4060 8GB PC. The pipeline keeps PDF extraction, Gemma/Ollama planning, slide composition, narration, and FFmpeg local, and routes only planner-selected still visuals through LTX.

```powershell
uv run briefing run --input "data/input/Gemma_(language_model).pdf" --out dist/gemma-briefing-api --config configs/default.yaml --visual-mode api
```

Expected outputs:

- `dist/gemma-briefing-api/briefing.mp4`
- `dist/gemma-briefing-api/briefing_plan.json`
- `dist/gemma-briefing-api/cost_report.md`
- `dist/gemma-briefing-api/source_index.json`
- `dist/gemma-briefing-api/slides/*.png`
- `dist/gemma-briefing-api/audio/*.wav`
- `dist/gemma-briefing-api/visuals/*.png`
- `dist/gemma-briefing-api/visuals/*_provider.mp4` for sections that used LTX-backed still extraction

## Cost Shape

Most stages run cheaply on commodity hardware.

- Fixed compute: ingestion, Gemma planning, local visual rendering, slide composition, TTS, validation, and FFmpeg assembly.
- Bursty compute: only the small number of planner-selected provider visuals.
- Marginal cost: near-zero for reruns that stay local; extra cost mainly scales with additional generated visuals.

## Test

```powershell
uv run pytest
```

## Submission Notes

Submit:

- GitHub repository link.
- `briefing.mp4` or uploaded video link.
- `docs/explanation.md` as the short explanation document covering system design, tools/models, cost considerations, and engineering decisions.
