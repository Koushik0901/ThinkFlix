# Explanation

## Overview

ThinkFlix is a local-first system that converts a long-form text or PDF source into a short briefing video. The output is a narrated slide deck rather than a free-form generated video. That choice keeps the result structured, easier to review, and cheaper to produce while still supporting richer visuals when they add value.

For the current demo, the system takes the Gemma PDF, extracts the text and table content, turns that source into a sectioned briefing plan, renders slides, generates narration, and assembles the result into an MP4. The same pipeline also works for text and Markdown inputs.

## System Design And Architecture

The pipeline has five main stages.

1. **Ingestion**
   - Text, Markdown, and PDF inputs are supported.
   - PDFs are processed with PyMuPDF.
   - The ingestion step preserves document structure, page markers, metadata, and detected tables so the planner can reason over both prose and structured data.

2. **Planning and orchestration**
   - Gemma4 runs locally through Ollama and acts as the planner.
   - It produces the briefing structure: title, audience, intro, key sections, summary, narration, slide bullets, citations, and visual instructions for each section.
   - Gemma also decides how each slide should be visualized. A section can stay text-led, use a local diagram treatment, focus on a table/specification view, or request a provider-generated image.

3. **Visual generation**
   - Local visuals are rendered directly in Python with Pillow.
   - If Gemma selects `generated_image`, the system sends Gemma's provider-ready prompt directly to LTX. The application does not rewrite that prompt.
   - The generated frame is then embedded into the slide itself instead of being inserted as a separate cutaway segment. This keeps the briefing coherent because each visual sits beside the specific section it supports.

4. **Narration**
   - Narration is generated locally with Kokoro-82M.
   - Each section gets its own audio file, which makes the system easier to debug and easier to reuse if a single section needs to be regenerated.

5. **Assembly**
   - Slides and narration are composed into the final MP4 with FFmpeg.
   - FFmpeg is used as the final assembler because it is deterministic, lightweight, and dependable for a time-boxed project.

In practice, the system behaves like a content transformation pipeline: input document to structured plan to slide assets plus narration to final video.

## Tools And Models Used

- **Gemma4 via Ollama**: local planner and orchestrator. It writes the briefing content and decides the visual treatment per section.
- **PyMuPDF**: PDF ingestion, page text extraction, metadata capture, and table extraction.
- **Pydantic v2**: strict validation of the structured briefing plan so the rest of the pipeline operates on predictable data.
- **Pillow**: slide rendering and local diagrams/visual treatments.
- **Kokoro-82M**: local text-to-speech for narration.
- **LTX**: optional provider-backed image generation for sections where Gemma decides a generated visual is useful.
- **FFmpeg**: final video assembly.
- **Python CLI**: orchestration, file management, retries, and failure handling.

The main design principle behind these choices is to keep the expensive or fragile parts narrow. Most of the pipeline runs locally. External generation is only used for specific visual moments when the local slide treatment would not communicate the section as effectively.

## Cost Considerations

The cost profile is intentionally uneven in a good way: most steps are cheap and repeatable, while the small number of expensive steps are isolated.

- **Low-cost local stages**
  - PDF extraction
  - briefing planning with local Gemma
  - slide rendering
  - narration generation
  - FFmpeg assembly

- **Selective remote stage**
  - only planner-selected generated visuals use LTX
  - if Gemma decides no generated images are needed, the entire run stays local

This matters because the project is designed for a consumer machine. On an RTX 4060 with 8 GB VRAM, local planning, narration, rendering, and assembly are realistic. Full local video generation is not a practical default in that environment, so the system avoids depending on it. The provider-backed portion is limited to still visuals rather than long generated video, which keeps latency, failure risk, and cost lower.

The system also has graceful fallback behavior. If provider generation fails, the section falls back to a local visual treatment and the final briefing still completes. That keeps the deliverable dependable without forcing every run through a fragile remote dependency.

## Engineering Decisions

Several decisions shaped the final system:

**1. Narrated slides instead of generated video-first output**  
The original direction explored separate generated video segments. That produced weaker continuity and more provider risk. Embedding visuals directly into the slides created a clearer output and a simpler assembly path.

**2. Gemma as the orchestrator, not just a summarizer**  
Instead of limiting Gemma to bullets and narration, the system gives it responsibility for section-level visual planning. This makes the pipeline more dynamic and better suited to new documents because visual decisions are made from the source content rather than hard-coded templates.

**3. Source grounding over stylistic freedom**  
The planner is explicitly constrained to stay grounded in the input document. Unsupported claims, invented entities, and decorative but misleading visuals are discouraged. This is important for briefing-style output, where trust matters more than spectacle.

**4. Local-first by default**  
The system is structured so it remains useful even without external generation. That improves reproducibility and keeps the project aligned with practical hardware limits.

**5. Deterministic validation around generative steps**  
Generative components produce structured data or media requests, but the rest of the pipeline validates and constrains those outputs. Pydantic schema validation, explicit visual modes, and fallback logic are used to keep the system stable.

## Reproduction

```powershell
uv sync --extra dev
ollama pull gemma4
ollama pull gemma4:e4b
$env:LTX_API_KEY="YOUR_LTX_API_KEY"
uv run briefing run --input "data/input/Gemma_(language_model).pdf" --out dist/gemma-briefing-api --config configs/default.yaml --visual-mode api
```

For a local-only run:

```powershell
uv run briefing run --input "data/input/Gemma_(language_model).pdf" --out dist/gemma-briefing --config configs/default.yaml --no-visual-provider
```
