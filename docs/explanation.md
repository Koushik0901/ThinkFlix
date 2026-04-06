# Explanation

## Overview

ThinkFlix is a local-first system that converts a long-form text or PDF source into a short briefing video. The output is a narrated slide deck rather than a free-form generated video. That choice is deliberate: for this challenge, the more important problem is reliable content transformation than unconstrained media generation. A briefing should be structured, source-grounded, easy to review, and affordable to regenerate.

For the current demo, the system takes the Gemma PDF, extracts the text and table content, turns that source into a sectioned briefing plan, renders slides, generates narration, and assembles the result into an MP4. The same pipeline also works for text and Markdown inputs. The core design goal was to keep the system practical on a consumer PC while still showing clear orchestration, grounding, and multimedia synthesis.

## System Design And Architecture

The pipeline has five stages, with a strong separation between source processing, planning, media generation, and final assembly.

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

In practice, the system behaves like a transformation pipeline:

`source document -> structured plan -> section visuals + section narration -> final briefing video`

That shape matters because each stage has a narrow responsibility. If a run fails, it is easy to see whether the problem came from extraction, planning, visuals, speech, or assembly. This is more maintainable than a monolithic “generate the whole briefing end-to-end” approach.

## Tools And Models Used

- **Gemma4 via Ollama**: local planner and orchestrator. It writes the briefing content and decides the visual treatment per section.
- **PyMuPDF**: PDF ingestion, page text extraction, metadata capture, and table extraction.
- **Pydantic v2**: strict validation of the structured briefing plan so the rest of the pipeline operates on predictable data.
- **Pillow**: slide rendering and local diagrams/visual treatments.
- **Kokoro-82M**: local text-to-speech for narration.
- **LTX**: optional provider-backed image generation for sections where Gemma decides a generated visual is useful.
- **FFmpeg**: final video assembly.
- **Python CLI**: orchestration, file management, retries, and failure handling.

The main principle behind these choices was to keep the expensive or fragile parts narrow. Most of the pipeline runs locally. External generation is used only for specific visual moments when a local diagram or table-focused treatment would not communicate the section as effectively.

## Cost Considerations

The cost profile is intentionally uneven in a useful way: most steps are cheap and repeatable, while the small number of more expensive steps are isolated and optional.

- **Low-cost local stages**
  - PDF extraction
  - briefing planning with local Gemma
  - slide rendering
  - narration generation
  - FFmpeg assembly

- **Selective remote stage**
  - only planner-selected generated visuals use LTX
  - if Gemma decides no generated images are needed, the entire run stays local

This matters because the target environment is a consumer machine. On an RTX 4060 with 8 GB VRAM, local planning, narration, rendering, and assembly are realistic. Full local video generation is not a practical default in that environment, so the system avoids depending on it. The remote portion is limited to still visuals rather than long generated video, which keeps latency, failure risk, and cost lower.

This also shaped the media choice. An earlier version of the project explored standalone generated video cutaways. In practice, that increased cost, runtime, and failure modes while making the final result less coherent. Moving to slide-embedded visuals was a better tradeoff:

- still satisfies the requirement for visuals and narration
- reduces the amount of remote generation needed
- produces a cleaner briefing output
- avoids burning time and budget on long generated video clips

The system also has graceful fallback behavior. If provider generation fails, the section falls back to a local visual treatment and the final briefing still completes. That keeps the deliverable dependable without forcing every run through a fragile remote dependency.

## Engineering Decisions

Several decisions shaped the final system:

**1. Narrated slides instead of generated video-first output**  
The original direction explored separate generated video segments. That produced weaker continuity and more provider risk. It also made the pipeline harder to reason about because the visual content became detached from the section it was supposed to explain. Embedding visuals directly into the slides created a clearer output and a simpler assembly path.

**2. Gemma as the orchestrator, not just a summarizer**  
Instead of limiting Gemma to bullets and narration, the system gives it responsibility for section-level visual planning. This makes the pipeline more dynamic and better suited to new documents because visual decisions are made from the source content rather than hard-coded templates. It also means the same model is responsible for narrative structure and visual intent, which keeps the output more coherent.

**3. Source grounding over stylistic freedom**  
The planner is explicitly constrained to stay grounded in the input document. Unsupported claims, invented entities, and decorative but misleading visuals are discouraged. This is important for briefing-style output, where trust matters more than spectacle. In practice, this means the system prefers a simpler but defensible slide over a more visually ambitious slide that suggests facts not present in the source.

**4. Local-first by default**  
The system is structured so it remains useful even without external generation. That improves reproducibility and keeps the project aligned with practical hardware limits. It also means the system can be demonstrated end-to-end even if the provider-backed path is unavailable.

**5. Deterministic validation around generative steps**  
Generative components produce structured data or media requests, but the rest of the pipeline validates and constrains those outputs. Pydantic schema validation, explicit visual modes, and fallback logic are used to keep the system stable. This reduces the risk that one malformed model response breaks the entire run.

## Practical Tradeoffs

The main tradeoff in this project was not “open-source versus API” in the abstract. It was deciding which parts must be local to keep the system practical, and which parts can be remote without turning the system into an API wrapper.

The resulting split was:

- local for planning, extraction, narration, slide rendering, and final assembly
- optional remote generation for a small number of visuals

That split was chosen because it gives the system three useful properties:

1. **Predictable reruns**  
   Most of the pipeline can be rerun quickly and cheaply while iterating on prompts, slide layouts, or narration.

2. **Controlled quality risk**  
   The sections that matter most for clarity, namely structure, wording, and slide composition, are controlled locally. Remote generation is used only for enrichment.

3. **Reasonable operational cost**  
   The project avoids paying for large language model planning and avoids expensive long-form media generation on every run.

Another important tradeoff was between visual ambition and output clarity. A more aggressive approach would have used many generated visuals or animated inserts. That might look more impressive at first glance, but it would also make the output more fragile and less briefing-like. The current system chooses clarity first: a strong narrated slide deck with selectively richer visuals where they materially help.

## Why This Is A Practical Implementation

This project is not optimized for the most cinematic output possible. It is optimized for a believable production path:

- it can run on a normal developer machine
- it produces a repeatable artifact
- it has clear fallbacks
- it separates planning from rendering
- it keeps the expensive stage narrow
- it remains usable even when provider generation is unavailable

Those choices are what make the implementation practical. The system does not assume perfect model behavior, unlimited GPU memory, or unlimited API usage. Instead, it assumes normal constraints and is designed to keep producing a usable briefing under those constraints.

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
