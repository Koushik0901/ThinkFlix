# Cost Report

Final output: `dist\gemma-briefing-api\briefing.mp4`
Final duration: 194.6 seconds

## Fixed compute cost
PDF/text extraction, local planning, visual rendering, slide composition, TTS, validation, and FFmpeg assembly run on commodity CPU or local GPU.

## Bursty high-cost step
Provider-generated still visuals are planner-selected and capped so only a small number of sections use remote generation.

## API justification
The target local machine is an RTX 4060 with 8GB VRAM. Provider-backed still visuals are the only stage routed to an API because final media polish is the least practical stage to run locally in this environment. All non-visual-provider stages remain local.

## Marginal cost
Additional non-provider runs are near-zero cost; marginal cost mainly scales with extra generated still visuals.

Most stages run cheaply on commodity hardware. The only bursty high-cost step is optional provider-generated still imagery, which is isolated and capped.

## Visual status
- section_01: generated_image
- section_02: diagram
- section_03: generated_image
- section_04: table_focus
- section_05: diagram
- section_06: none
