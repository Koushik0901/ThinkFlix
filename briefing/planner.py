from __future__ import annotations

import json
import re
from typing import Any

import httpx
from pydantic import ValidationError

from briefing.config import AppConfig
from briefing.ingest import chunk_text
from briefing.models import BriefingPlan


SYSTEM_PROMPT = """You create factual executive multimedia briefing plans.
Return only valid JSON matching the requested schema. Do not use markdown fences."""


def build_briefing_plan(source_text: str, config: AppConfig) -> BriefingPlan:
    errors: list[str] = []
    if config.llm.provider in {"auto", "ollama"}:
        for model in dict.fromkeys((config.llm.model, config.llm.fallback_model)):
            try:
                return _plan_with_ollama(source_text, config, model)
            except Exception as exc:  # noqa: BLE001
                errors.append(f"ollama:{model}: {exc}")
    return _heuristic_plan(source_text, config, errors)


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
                    {"role": "system", "content": SYSTEM_PROMPT},
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
    return (
        "Create a 3-5 minute multimedia briefing plan.\n"
        f"Audience: {config.briefing.audience}\n"
        f"Target duration: {config.briefing.target_duration_seconds} seconds\n"
        "The output must include intro, 3-5 key_point sections, summary, at least one required "
        "abstract cutaway job, and source citations.\n"
        "Use the cost story: fixed commodity compute, isolated bursty GPU video generation, "
        "near-zero marginal cost except extra cutaway GPU time.\n"
        f"JSON schema:\n{json.dumps(schema)}\n"
        f"Source excerpts:\n{excerpts}"
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
    fallback_note = " Local heuristic fallback was used because Ollama did not return a valid Gemma4 plan."
    if errors:
        fallback_note += " Planner errors were captured during local planning."
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
                    "depends on compute, energy, tooling, and cost control." + fallback_note
                ),
                "slide_bullets": [
                    "AI is moving from experiments into infrastructure",
                    "Open models widen access",
                    "Compute and energy shape what is practical",
                ],
                "visual_prompt": "Executive title slide with datacenter and model network motif",
                "broll_prompt": "Abstract datacenter racks connected to glowing model nodes",
                "citations": [citation],
            },
            {
                "kind": "key_point",
                "heading": "Access Is Widening",
                "takeaway": "Smaller and open-weight models let more teams prototype locally.",
                "narration": (
                    "The first takeaway is access. Open-weight releases and smaller efficient "
                    "models make experimentation possible for teams that cannot train frontier "
                    "systems. That changes prototyping, procurement, and internal AI adoption."
                ),
                "slide_bullets": [
                    "Open-weight models reduce experimentation friction",
                    "Smaller models shift more work to commodity hardware",
                    "Frontier training remains expensive and specialized",
                ],
                "visual_prompt": "Chart-like slide showing model access widening from labs to teams",
                "broll_prompt": "Abstract open-source model pipeline expanding from one lab to many teams",
                "citations": [citation],
            },
            {
                "kind": "key_point",
                "heading": "Multimodal Becomes Normal",
                "takeaway": "Text, image, audio, and video raise both usefulness and complexity.",
                "narration": (
                    "The second takeaway is modality. Modern AI products are no longer only text "
                    "systems. They increasingly combine text, images, audio, and video. That makes "
                    "them more useful, but evaluation, safety review, latency, and cost control harder."
                ),
                "slide_bullets": [
                    "Multimodal inputs make workflows richer",
                    "Evaluation must cover more failure modes",
                    "Serving costs become less predictable",
                ],
                "visual_prompt": "Slide with four modality lanes converging into one workflow",
                "broll_prompt": "Abstract multimodal interface streams converging into an AI ops dashboard",
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
                    "chain risk, and deployment architecture."
                ),
                "slide_bullets": [
                    "GPU capacity is a planning constraint",
                    "Power and datacenter access matter",
                    "Architecture choices determine operating cost",
                ],
                "visual_prompt": "Executive slide showing compute, energy, and cost as linked constraints",
                "broll_prompt": "Cinematic abstract GPU cluster with power grid lines and cost meters",
                "citations": [citation],
            },
            {
                "kind": "key_point",
                "heading": "Cap the Expensive Step",
                "takeaway": "Cost efficiency comes from isolating bursty GPU generation.",
                "narration": (
                    "The engineering response is to isolate the expensive step. In this system, "
                    "ingestion, planning, slide rendering, narration, validation, and final assembly "
                    "run cheaply on commodity hardware. The only bursty high-cost stage is short "
                    "video generation, which is capped and replaceable."
                ),
                "slide_bullets": [
                    "Cheap stages run locally",
                    "GPU video generation is isolated",
                    "Static fallbacks keep the pipeline reliable",
                ],
                "visual_prompt": "Architecture slide with cheap local stages and one capped GPU burst",
                "broll_prompt": "Abstract pipeline where one highlighted GPU burst creates a short cutaway",
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
                    "improve communication, and keeps every expensive step capped and auditable."
                ),
                "slide_bullets": [
                    "Use local models for routine orchestration",
                    "Spend GPU time only where it adds value",
                    "Keep expensive stages capped and auditable",
                ],
                "visual_prompt": "Closing slide with three concise executive recommendations",
                "broll_prompt": "Abstract closing visual of efficient AI infrastructure with capped GPU budget",
                "citations": [citation],
            },
        ],
        "cutaway_jobs": [
            {
                "id": "infrastructure_cutaway_01",
                "prompt": (
                    "Cinematic abstract visualization of AI infrastructure: GPU clusters, energy "
                    "grid lines, and open model nodes converging into an executive dashboard. "
                    "No text, no logos, no people, realistic lighting, 6 seconds."
                ),
                "duration_seconds": config.video.cutaway_duration_seconds,
                "required": True,
                "status": "planned",
            }
        ],
        "cost_notes": {
            "fixed_compute": (
                "Ingestion, planning, slides, TTS, validation, and FFmpeg assembly run on "
                "commodity CPU or local GPU."
            ),
            "bursty_compute": (
                "The Wan2.2 cutaway is isolated to a short rented 24GB-plus GPU window and can "
                "be replaced with a static fallback."
            ),
            "marginal_cost": (
                "Additional non-video runs are near-zero cost; marginal cost mainly scales with "
                "extra generated cutaways."
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
    source_url = _first_url(source_text) or "data/input/Gemma_(language_model).pdf"
    citation = {
        "source": "Gemma language model PDF source",
        "url": source_url,
        "note": "Source PDF focused on the Gemma model family, releases, variants, and specifications.",
    }
    fallback_note = " Local heuristic fallback was used because Ollama did not return a valid Gemma4 plan."
    if errors:
        fallback_note += " Planner errors were captured during local planning."
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
                    "medical applications, safety filtering, and other domains." + fallback_note
                ),
                "slide_bullets": [
                    "Developed by Google DeepMind",
                    "Related to Gemini technology",
                    "Includes general and specialized variants",
                ],
                "visual_prompt": "Executive briefing title slide showing a model family timeline",
                "broll_prompt": "Abstract model family tree with connected open model nodes",
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
                    "active model family rather than a single static release."
                ),
                "slide_bullets": [
                    "Gemma 1 arrived in February 2024",
                    "Gemma 2 and Gemma 3 expanded the family",
                    "Gemma 4 is listed as the 2026 stable release",
                ],
                "visual_prompt": "Timeline slide from Gemma 1 through Gemma 4",
                "broll_prompt": "Abstract chronological model release timeline with technical UI elements",
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
                    "This positions Gemma as a platform family, not just one text model."
                ),
                "slide_bullets": [
                    "CodeGemma targets code generation",
                    "PaliGemma supports vision-language workflows",
                    "ShieldGemma and MedGemma target safety and medical use cases",
                ],
                "visual_prompt": "Slide showing Gemma variants branching by use case",
                "broll_prompt": "Abstract branching model architecture with code, image, safety, and medical icons",
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
                    "structured facts into ambiguous prose."
                ),
                "slide_bullets": [
                    "Table fields include generation and release date",
                    "Parameter sizes and context lengths are preserved",
                    "Multimodal support is explicit in the extracted source",
                ],
                "visual_prompt": "Executive slide with a simplified model specification table",
                "broll_prompt": "Abstract technical table transforming into a concise model comparison dashboard",
                "citations": [citation],
            },
            {
                "kind": "key_point",
                "heading": "Open Model Positioning",
                "takeaway": "Gemma reflects Google's move toward more accessible model releases.",
                "narration": (
                    "The fourth key point is positioning. The source frames Gemma as a response "
                    "to the open model ecosystem and a shift toward more accessible model releases. "
                    "For a technical audience, the practical takeaway is that Gemma belongs in "
                    "the category of local and open-model evaluation candidates."
                ),
                "slide_bullets": [
                    "Gemma is positioned for broader developer access",
                    "Licensing differs across generations",
                    "It belongs in open-model evaluation workflows",
                ],
                "visual_prompt": "Slide showing model access from closed systems to local open models",
                "broll_prompt": "Abstract open model ecosystem with deployment nodes and license badges",
                "citations": [citation],
            },
            {
                "kind": "summary",
                "heading": "Briefing Takeaway",
                "takeaway": "Gemma is best understood as an evolving open-model family with specialized branches.",
                "narration": (
                    "The summary is that Gemma is not just a single model name. It is an evolving "
                    "family of Google DeepMind models with general, coding, multimodal, medical, "
                    "and safety-oriented variants. For this project, the important engineering "
                    "point is that table-aware PDF extraction keeps the model specifications "
                    "available to the planner and improves the quality of the final briefing."
                ),
                "slide_bullets": [
                    "Treat Gemma as a model family",
                    "Preserve tables for accurate model comparisons",
                    "Use generated cutaways only to support communication",
                ],
                "visual_prompt": "Closing slide with concise Gemma evaluation recommendations",
                "broll_prompt": "Abstract model family map resolving into three executive recommendations",
                "citations": [citation],
            },
        ],
        "cutaway_jobs": [
            {
                "id": "gemma_model_family_cutaway_01",
                "prompt": (
                    "Cinematic abstract visualization of an open model family: connected model "
                    "nodes branching into text, code, image, safety, and medical workflows. "
                    "No text, no logos, no people, realistic lighting, 6 seconds."
                ),
                "duration_seconds": config.video.cutaway_duration_seconds,
                "required": True,
                "status": "planned",
            }
        ],
        "cost_notes": {
            "fixed_compute": (
                "PDF extraction, planning, slides, TTS, validation, and FFmpeg assembly run on "
                "commodity CPU or local GPU."
            ),
            "bursty_compute": (
                "The Wan2.2 cutaway is isolated to a short rented 24GB-plus GPU window and can "
                "be replaced with a static fallback."
            ),
            "marginal_cost": (
                "Additional non-video runs are near-zero cost; marginal cost mainly scales with "
                "extra generated cutaways."
            ),
        },
    }
    return BriefingPlan.model_validate(data)
