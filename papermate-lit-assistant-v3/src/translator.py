from __future__ import annotations

from src.utils import clean_text, display_value

MAX_CHARS_PER_CHUNK = 4200


def _split_text(text: str, chunk_size: int = MAX_CHARS_PER_CHUNK) -> list[str]:
    text = clean_text(text)
    if len(text) <= chunk_size:
        return [text]

    chunks = []
    current = []
    current_len = 0
    for sentence in text.split(". "):
        piece = sentence.strip()
        if not piece:
            continue
        if current_len + len(piece) + 2 > chunk_size:
            chunks.append(". ".join(current))
            current = [piece]
            current_len = len(piece)
        else:
            current.append(piece)
            current_len += len(piece) + 2
    if current:
        chunks.append(". ".join(current))
    return chunks


def translate_text(text: str, target: str = "zh-CN") -> tuple[str | None, str | None]:
    text = display_value(text)
    if text == "N/A":
        return None, "No text available for translation."

    try:
        from deep_translator import GoogleTranslator
    except ImportError:
        return None, "Translation package is not installed. Run `pip install deep-translator` or skip translation."

    try:
        translator = GoogleTranslator(source="auto", target=target)
        translated_chunks = [translator.translate(chunk) for chunk in _split_text(text)]
        return "\n\n".join(translated_chunks), None
    except Exception as exc:
        return None, f"Translation failed, but other functions still work. Details: {exc}"
