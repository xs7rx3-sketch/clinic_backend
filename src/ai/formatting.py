import re
from typing import Optional


def clean_conversational_text(text: Optional[str]) -> str:
    """Sanitizes AI responses to ensure clean conversational text for Flutter UI and Voice TTS:
    - Removes markdown code fences (```markdown ... ```)
    - Strips markdown headers (#, ##, ###)
    - Removes accidental raw database UUIDs
    - Normalizes spacing
    """
    if not text:
        return ""

    cleaned = str(text).strip()

    # Strip markdown code fence wrapper if present
    cleaned = re.sub(r"^```(?:markdown)?\s*\n([\s\S]*?)\n```$", r"\1", cleaned)

    # Strip markdown header syntax at start of lines (e.g. "### Title" -> "Title")
    cleaned = re.sub(r"^\s*#{1,6}\s+", "", cleaned, flags=re.MULTILINE)

    # Strip accidental raw UUIDs to prevent leaking internal database IDs
    cleaned = re.sub(
        r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b",
        "",
        cleaned,
    )

    # Clean double spaces or orphaned punctuation resulting from removed UUIDs
    cleaned = re.sub(r" {2,}", " ", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)

    return cleaned.strip()
