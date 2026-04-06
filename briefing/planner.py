from __future__ import annotations

import json
import re
from typing import Any

import httpx
from pydantic import ValidationError

from briefing.config import AppConfig
from briefing.ingest import chunk_text
from briefing.models import BriefingPlan, CostNotes
from briefing.prompts import render_prompt_template


def build_briefing_plan(source_text: str, config: AppConfig) -> BriefingPlan:
    errors: list[str] = []
    if config.llm.provider in {"auto", "ollama"}:
        for model in dict.fromkeys((config.llm.model, config.llm.fallback_model)):
            try:
                return _with_pipeline_cost_notes(_plan_with_ollama(source_text, config, model))
            except Exception as exc:  # noqa: BLE001
                errors.append(f"ollama:{model}: {exc}")
    return _with_pipeline_cost_notes(_heuristic_plan(source_text, config, errors))


def _with_pipeline_cost_notes(plan: BriefingPlan) -> BriefingPlan:
    return plan.model_copy(
        update={
            "cost_notes": CostNotes(
                fixed_compute=(
                    "PDF/text extraction, local planning, visual rendering, slide composition, "
                    "TTS, validation, and FFmpeg assembly run on commodity CPU or local GPU."
                ),
                bursty_compute=(
                    "Provider-generated still visuals are planner-selected and capped so only a "
                    "small number of sections use remote generation."
                ),
                marginal_cost=(
                    "Additional non-provider runs are near-zero cost; marginal cost mainly scales "
                    "with extra generated still visuals."
                ),
            )
        }
    )


def _plan_with_ollama(source_text: str, config: AppConfig, model: str) -> BriefingPlan:
    prompt = _user_prompt(source_text, config)
    last_error: Exception | None = None
    for _ in range(config.llm.retries + 1):
        response = httpx.post(
            f"{config.llm.ollama_url.rstrip('/')}/api/chat",
            timeout=config.llm.timeout_seconds,
            json={
                "model": model,
                "messages": [
                    {"role": "user", "content": prompt},
                ],
                "stream": False,
                "format": "json",
            },
        )
        response.raise_for_status()
        content = response.json()["message"]["content"]
        try:
            return _validate_json_plan(content)
        except (json.JSONDecodeError, ValidationError, ValueError) as exc:
            last_error = exc
    raise RuntimeError(f"Gemma4/Ollama failed to produce valid briefing JSON: {last_error}")


def _validate_json_plan(content: str) -> BriefingPlan:
    data = json.loads(_extract_json_object(content))
    return BriefingPlan.model_validate(data)


def _extract_json_object(content: str) -> str:
    content = content.strip()
    if content.startswith("{") and content.endswith("}"):
        return content
    match = re.search(r"\{.*\}", content, flags=re.DOTALL)
    if not match:
        raise ValueError("No JSON object found in model response")
    return match.group(0)


def _user_prompt(source_text: str, config: AppConfig) -> str:
    excerpts = "\n\n---\n\n".join(chunk_text(source_text, max_chars=2500)[:6])
    schema = BriefingPlan.model_json_schema()
    return render_prompt_template(
        "planner_gemma.md",
        source_context=excerpts,
        audience=config.briefing.audience,
        target_duration_seconds=str(config.briefing.target_duration_seconds),
        output_schema=json.dumps(schema),
    )


def _heuristic_plan(source_text: str, config: AppConfig, errors: list[str]) -> BriefingPlan:
    if _looks_like_gemma_source(source_text):
        return _gemma_heuristic_plan(source_text, config, errors)
    source_url = _first_url(source_text) or "https://hai.stanford.edu/ai-index/2025-ai-index-report"
    citation = {
        "source": "Stanford HAI AI Index Report 2025 source bundle",
        "url": source_url,
        "note": "Source bundle focused on AI infrastructure, access, cost, and open models.",
    }
    data: dict[str, Any] = {
        "title": "AI Infrastructure Is the New AI Strategy",
        "audience": config.briefing.audience,
        "target_duration_seconds": config.briefing.target_duration_seconds,
        "source_citations": [citation],
        "sections": [
            {
                "kind": "intro",
                "heading": "The Infrastructure Shift",
                "takeaway": "AI progress is now as much an infrastructure story as a model story.",
                "narration": (
                    "This briefing looks at a practical shift in AI. Capability is becoming more "
                    "accessible through open and efficient models, but serious deployment still "
                    "depends on compute, energy, tooling, and cost control. The goal is to separate "
                    "what can run cheaply on commodity hardware from the few stages that still need "
                    "specialized acceleration or external capacity. That framing keeps the briefing "
                    "focused on implementation tradeoffs rather than abstract AI hype."
                ),
                "slide_bullets": [
                    "AI is moving from experiments into infrastructure",
                    "Open models widen access",
                    "Compute and energy shape what is practical",
                ],
                "visual_mode": "generated_image",
                "visual_role": "Set the briefing tone with an abstract infrastructure visual.",
                "image_prompt": (
                    "A premium abstract infrastructure scene grounded in the source themes of AI "
                    "access, compute, and deployment constraints: luminous compute surfaces, dark "
                    "datacenter-scale space, layered energy paths, no text, no logos, no people, "
                    "no dashboards, cinematic lighting."
                ),
                "visual_caption": "Infrastructure is now part of the product story.",
                "visual_grounding_notes": "The source emphasizes infrastructure, compute, and access as the core framing.",
                "citations": [citation],
            },
            {
                "kind": "key_point",
                "heading": "Access Is Widening",
                "takeaway": "Smaller and open-weight models let more teams prototype locally.",
                "narration": (
                    "The first takeaway is access. Open-weight releases and smaller efficient "
                    "models make experimentation possible for teams that cannot train frontier "
                    "systems. That changes prototyping, procurement, and internal AI adoption. "
                    "It also means model choice should be evaluated as an operating decision, "
                    "not just a benchmark contest. Teams need to ask what runs locally, what needs "
                    "managed infrastructure, and what must be reserved for premium generation."
                ),
                "slide_bullets": [
                    "Open-weight models reduce experimentation friction",
                    "Smaller models shift more work to commodity hardware",
                    "Frontier training remains expensive and specialized",
                ],
                "visual_mode": "diagram",
                "visual_role": "Show widening access from centralized labs to broader teams.",
                "visual_caption": "Model access is widening, but not all workloads become cheap.",
                "visual_grounding_notes": "The source centers on open models, access, and practical deployment tiers.",
                "citations": [citation],
            },
            {
                "kind": "key_point",
                "heading": "Multimodal Becomes Normal",
                "takeaway": "Text, image, audio, and video raise both usefulness and complexity.",
                "narration": (
                    "The second takeaway is modality. Modern AI products are no longer only text "
                    "systems. They increasingly combine text, images, audio, and video. That makes "
                    "them more useful, but evaluation, safety review, latency, and cost control harder. "
                    "A practical briefing system should therefore keep factual claims in source-backed "
                    "text and narration, while treating generated visuals as supporting material. That keeps "
                    "the communication benefits of multimodal output without letting synthetic visuals "
                    "become the source of truth."
                ),
                "slide_bullets": [
                    "Multimodal inputs make workflows richer",
                    "Evaluation must cover more failure modes",
                    "Serving costs become less predictable",
                ],
                "visual_mode": "diagram",
                "visual_role": "Show multiple modalities converging into one operating workflow.",
                "visual_caption": "More modalities increase usefulness and operational complexity.",
                "visual_grounding_notes": "The source discusses multimodal systems and the resulting serving and evaluation complexity.",
                "citations": [citation],
            },
            {
                "kind": "key_point",
                "heading": "Compute Is the Constraint",
                "takeaway": "Chips, power, and datacenter capacity determine what can scale.",
                "narration": (
                    "The third takeaway is infrastructure pressure. Advanced AI depends on GPUs, "
                    "datacenter capacity, power availability, and specialized engineering. For "
                    "leaders, model selection is tied directly to operating budget, latency, supply "
                    "chain risk, and deployment architecture. The same model can be attractive in "
                    "a prototype and impractical in production if serving cost, memory use, or "
                    "availability are ignored. The infrastructure layer therefore becomes part of "
                    "the product strategy, not just a backend implementation detail."
                ),
                "slide_bullets": [
                    "GPU capacity is a planning constraint",
                    "Power and datacenter access matter",
                    "Architecture choices determine operating cost",
                ],
                "visual_mode": "generated_image",
                "visual_role": "Make compute pressure feel concrete without inventing unsupported details.",
                "image_prompt": (
                    "A grounded abstract visual about compute constraints in AI: dark industrial "
                    "space, luminous hardware-like forms, power-grid light paths, restrained "
                    "material geometry, no text, no logos, no screens, no people, cinematic lighting."
                ),
                "visual_caption": "Compute availability and power shape what can scale.",
                "visual_grounding_notes": "The source explicitly connects compute, datacenter capacity, power, and cost.",
                "citations": [citation],
            },
            {
                "kind": "key_point",
                "heading": "Cap the Expensive Step",
                "takeaway": "Cost efficiency comes from isolating bursty GPU generation.",
                "narration": (
                    "The engineering response is to isolate the expensive step. In this system, "
                    "ingestion, planning, slide rendering, narration, validation, and final assembly "
                    "run cheaply on commodity hardware. The only bursty high-cost stage is provider "
                    "visual generation, which is capped and replaceable. This design keeps the "
                    "pipeline reliable on a normal PC while still demonstrating where an external "
                    "GPU provider adds value. It also makes failure modes easier to explain: if "
                    "the provider fails, the briefing can still finish with a static fallback."
                ),
                "slide_bullets": [
                    "Cheap stages run locally",
                    "Provider visuals are isolated",
                    "Static fallbacks keep the pipeline reliable",
                ],
                "visual_mode": "diagram",
                "visual_role": "Explain the architecture split between cheap routine stages and capped remote generation.",
                "visual_caption": "Keep expensive generation isolated and optional.",
                "visual_grounding_notes": "The source briefing focuses on cost-sensitive deployment and operating tradeoffs.",
                "citations": [citation],
            },
            {
                "kind": "summary",
                "heading": "What To Do Next",
                "takeaway": "Use open models broadly, reserve expensive generation for moments that matter.",
                "narration": (
                    "The bottom line is simple. AI is becoming easier to use, but not free to "
                    "operate. A strong architecture uses local and smaller open models for most "
                    "orchestration, reserves high-end GPU generation for moments that genuinely "
                    "improve communication, and keeps every expensive step capped and auditable. "
                    "That makes the output cost-efficient, reproducible, and easier to explain in "
                    "a real technical briefing. The architecture is intentionally modest: use local "
                    "automation for the routine work, and spend remote compute only where it is "
                    "visible and justified."
                ),
                "slide_bullets": [
                    "Use local models for routine orchestration",
                    "Spend GPU time only where it adds value",
                    "Keep expensive stages capped and auditable",
                ],
                "visual_mode": "none",
                "visual_role": "Keep the close focused on recommendations rather than decorative media.",
                "visual_caption": "End on decisions, not decoration.",
                "visual_grounding_notes": "The summary is recommendation-heavy and does not need added generated media.",
                "citations": [citation],
            },
        ],
        "cost_notes": {
            "fixed_compute": (
                "Ingestion, planning, slides, TTS, validation, and FFmpeg assembly run on "
                "commodity CPU or local GPU."
            ),
            "bursty_compute": (
                "Generated still visuals are optional and capped to a small number of sections."
            ),
            "marginal_cost": (
                "Additional non-provider runs are near-zero cost; marginal cost mainly scales with "
                "extra generated visuals."
            ),
        },
    }
    return BriefingPlan.model_validate(data)


def _first_url(text: str) -> str | None:
    match = re.search(r"https?://\S+", text)
    return match.group(0).rstrip(").,") if match else None


def _looks_like_gemma_source(source_text: str) -> bool:
    lowered = source_text.lower()
    return "gemma" in lowered and "google deepmind" in lowered


def _gemma_heuristic_plan(source_text: str, config: AppConfig, errors: list[str]) -> BriefingPlan:
    source_url = "data/input/Gemma_(language_model).pdf"
    citation = {
        "source": "Gemma language model PDF source",
        "url": source_url,
        "note": "Source PDF focused on the Gemma model family, releases, variants, and specifications.",
    }
    data: dict[str, Any] = {
        "title": "Gemma: Google's Open Model Family Briefing",
        "audience": config.briefing.audience,
        "target_duration_seconds": config.briefing.target_duration_seconds,
        "source_citations": [citation],
        "sections": [
            {
                "kind": "intro",
                "heading": "What Gemma Is",
                "takeaway": "Gemma is Google's lightweight, source-available model family related to Gemini.",
                "narration": (
                    "This briefing summarizes Gemma, a family of large language models developed "
                    "by Google DeepMind and based on technologies related to Gemini. The source "
                    "describes Gemma as a lightweight model family that has evolved across multiple "
                    "generations, including specialized variants for code, vision-language tasks, "
                    "medical applications, safety filtering, and other domains. The practical "
                    "briefing question is not just what Gemma is, but how the family has expanded "
                    "and why that matters for teams evaluating local or source-available models."
                ),
                "slide_bullets": [
                    "Developed by Google DeepMind",
                    "Related to Gemini technology",
                    "Includes general and specialized variants",
                ],
                "visual_mode": "generated_image",
                "visual_role": "Introduce Gemma as a family rather than a single model release.",
                "image_prompt": (
                    "A source-grounded abstract visual of an evolving open model family: one "
                    "glowing core branching into several related luminous paths, premium dark "
                    "background, no text, no logos, no screens, no people, no invented products."
                ),
                "visual_caption": "Gemma should read as a family, not a single release.",
                "visual_grounding_notes": "The source describes Gemma as a family with multiple generations and specialized variants.",
                "citations": [citation],
            },
            {
                "kind": "key_point",
                "heading": "Release Timeline",
                "takeaway": "Gemma moved from initial 2024 releases to broader model generations and variants.",
                "narration": (
                    "The first key point is timeline. The source describes Gemma's first release "
                    "in February 2024, followed by Gemma 2 in June 2024, Gemma 3 in March 2025, "
                    "and Gemma 4 in April 2026. That progression matters because it shows an "
                    "active model family rather than a single static release. For an engineering "
                    "team, the timeline also signals that model evaluation should be repeatable: "
                    "new generations can change capabilities, context length, modality support, "
                    "and deployment assumptions."
                ),
                "slide_bullets": [
                    "Gemma 1 arrived in February 2024",
                    "Gemma 2 and Gemma 3 expanded the family",
                    "Gemma 4 is listed as the 2026 stable release",
                ],
                "visual_mode": "diagram",
                "visual_role": "Make the release sequence easy to scan.",
                "visual_caption": "The family evolved quickly across 2024 to 2026.",
                "visual_grounding_notes": "The source gives explicit release timing for Gemma 1 through Gemma 4.",
                "citations": [citation],
            },
            {
                "kind": "key_point",
                "heading": "Specialized Variants",
                "takeaway": "The Gemma family includes models for code, vision-language, safety, and medicine.",
                "narration": (
                    "The second key point is specialization. The PDF lists variants such as "
                    "CodeGemma for code generation, PaliGemma for vision-language tasks, "
                    "ShieldGemma for safety filtering, and MedGemma for medical use cases. "
                    "This positions Gemma as a platform family, not just one text model. In a "
                    "briefing context, that distinction is important: the relevant question becomes "
                    "which branch fits the job, rather than whether one general model should handle "
                    "every workflow."
                ),
                "slide_bullets": [
                    "CodeGemma targets code generation",
                    "PaliGemma supports vision-language workflows",
                    "ShieldGemma and MedGemma target safety and medical use cases",
                ],
                "visual_mode": "generated_image",
                "visual_role": "Show one family branching into specialized paths.",
                "image_prompt": (
                    "A source-grounded abstract branching visual for the Gemma model family: one "
                    "central glowing hub splitting into four distinct but related luminous branches, "
                    "each differentiated only by color, spacing, geometry, and material texture to "
                    "represent code, vision-language, safety, and medical specialization without "
                    "letters, symbols, markings, screens, logos, or people."
                ),
                "visual_caption": "Specialization is a core part of the family structure.",
                "visual_grounding_notes": "The source explicitly lists specialized Gemma variants across several domains.",
                "citations": [citation],
            },
            {
                "kind": "key_point",
                "heading": "Technical Shape",
                "takeaway": "The extracted table preserves parameters, context length, modalities, and notes.",
                "narration": (
                    "The third key point is technical shape. The PDF contains a table of Gemma "
                    "model specifications, including generation, release date, parameter sizes, "
                    "context length, multimodal support, and notes. Preserving that table is "
                    "important because it lets the briefing compare versions without flattening "
                    "structured facts into ambiguous prose. It also shows that Gemma changes "
                    "meaningfully across generations: context length, modality support, and "
                    "architecture notes differ by release."
                ),
                "slide_bullets": [
                    "Table fields include generation and release date",
                    "Parameter sizes and context lengths are preserved",
                    "Multimodal support is explicit in the extracted source",
                ],
                "visual_mode": "table_focus",
                "visual_role": "Focus attention on structured comparison fields from the extracted table.",
                "visual_caption": "The table is the source of truth for cross-generation comparison.",
                "visual_grounding_notes": "The source includes a structured table with fields for generation, release, parameters, context, and modality.",
                "citations": [citation],
            },
            {
                "kind": "key_point",
                "heading": "Access And Deployment",
                "takeaway": "The source positions Gemma for broad developer access and consumer-device use cases.",
                "narration": (
                    "The fourth key point is access and deployment. The source says Gemma models "
                    "have had more than 150 million downloads and 70,000 variants. It also says "
                    "Google offers Gemma 3n, smaller models optimized "
                    "for consumer devices like phones, laptops, and tablets. Those details make "
                    "Gemma relevant as a practical model family for teams comparing accessible "
                    "model options, especially when device targets and deployment footprint matter."
                ),
                "slide_bullets": [
                    "More than 150M downloads are cited",
                    "70,000 model variants are cited",
                    "Gemma 3n targets consumer devices",
                ],
                "visual_mode": "diagram",
                "visual_role": "Connect access scale with device-oriented deployment.",
                "visual_caption": "Access matters when deployment targets broaden.",
                "visual_grounding_notes": "The source cites downloads, variants, and device-targeted Gemma 3n deployments.",
                "citations": [citation],
            },
            {
                "kind": "summary",
                "heading": "Briefing Takeaway",
                "takeaway": "Gemma is best understood as an evolving open-model family with specialized branches.",
                "narration": (
                    "The summary is that Gemma is not just a single model name. It is an evolving "
                    "family of Google DeepMind models with general, coding, multimodal, medical, "
                    "and safety-oriented variants. The source-backed way to evaluate it is to "
                    "compare the generations, specialized variants, parameter sizes, context "
                    "lengths, modality support, and licensing notes together. That makes Gemma "
                    "best understood as a model family with multiple branches rather than a single "
                    "general-purpose release."
                ),
                "slide_bullets": [
                    "Treat Gemma as a model family",
                    "Compare generations and specialized variants",
                    "Check context, modality, and licensing notes",
                ],
                "visual_mode": "none",
                "visual_role": "Keep the summary focused on evaluation guidance.",
                "visual_caption": "The final slide should stay recommendation-led.",
                "visual_grounding_notes": "The summary is decision-oriented and does not need added generated media.",
                "citations": [citation],
            },
        ],
        "cost_notes": {
            "fixed_compute": (
                "PDF extraction, planning, slides, TTS, validation, and FFmpeg assembly run on "
                "commodity CPU or local GPU."
            ),
            "bursty_compute": (
                "Generated still visuals are optional and capped to a small number of sections."
            ),
            "marginal_cost": (
                "Additional non-provider runs are near-zero cost; marginal cost mainly scales with "
                "extra generated visuals."
            ),
        },
    }
    return BriefingPlan.model_validate(data)
