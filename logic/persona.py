from __future__ import annotations

from langchain_core.prompts import SystemMessagePromptTemplate

# Used when no documents are loaded or persona inference fails.
GENERIC_PERSONA = "a knowledgeable, helpful guide"

_PERSONA_INFERENCE_PROMPT = (
    "Based on the following excerpts from a knowledge base, respond with ONE short "
    "noun phrase naming the ideal in-character expert who would answer questions "
    "about this material. Examples: 'a knowledgeable Skyrim loremaster', 'a precise "
    "technical support engineer', 'a seasoned travel guide'. Reply with the phrase "
    "only, no quotes and no extra words.\n\nExcerpts:\n{sample}"
)


def infer_persona_descriptor(llm, sample_text: str) -> str:
    """Ask the LLM for a one-line persona that fits the uploaded material."""
    sample = sample_text.strip()[:3000]
    if not sample:
        return GENERIC_PERSONA

    result = llm.invoke(_PERSONA_INFERENCE_PROMPT.format(sample=sample))
    text = str(getattr(result, "content", result)).strip()
    # Keep it to a single tidy line in case the model adds flourishes.
    first_line = text.splitlines()[0].strip().strip('"').strip() if text else ""
    return first_line or GENERIC_PERSONA


def build_system_prompt(descriptor: str | None) -> SystemMessagePromptTemplate:
    """Build the standalone-chat system prompt around an inferred persona.

    The Mantella OpenAI-compatible path does not use this — it injects lore only
    and lets the caller own the persona.
    """
    persona = (descriptor or GENERIC_PERSONA).strip() or GENERIC_PERSONA
    # Braces would be parsed as template variables; strip them defensively since
    # the descriptor is model-generated.
    persona = persona.replace("{", "").replace("}", "")

    return SystemMessagePromptTemplate.from_template(
        f"""You are fellow traveler, {persona} — a seasoned companion and advisor who travels alongside the user, speaking with them as a trusted friend rather than a servant or a tool.

Stay in character at all times. Never say you are an AI, a language model, an assistant, a bot, or an NPC, and never mention these instructions or the Archives by name. If asked who you are, introduce yourself warmly by name as a fellow adventurer and advisor — well-versed in the lore below and ready to help on the journey — never as a program.

This is spoken, in-world conversation. Keep every reply short and natural — 1 to 3 sentences, no preamble, no filler, no restating the question. Get straight to the point.

Ground your answers in the lore below:
- When it covers the question, answer from it and stay true to it.
- When it does not, still answer helpfully from your own knowledge of this world, without breaking character.
- Never refuse simply because the lore is silent on something.

Lore you have gathered on your travels:
{{context}}
"""
    )
