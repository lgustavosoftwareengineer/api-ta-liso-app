"""Pure helper functions for chat message and tool-call parsing."""

import json
import re


def message_to_simple_string(message: str) -> str:
    """Convert message to a plain string by removing double quotes and escapes.

    E.g. 'Debito 20 \\"Corte de cabelo\\"' or 'Debito 20 "Corte de cabelo"' -> 'Debito 20 Corte de cabelo'
    """
    if not message:
        return ""
    s = message.strip()
    s = s.replace('\\"', '"')
    s = s.replace('"', "")
    return s.strip()


def extract_json_object_after_key(text: str, key: str) -> dict | None:
    """Extract a JSON object that is the value of a key (e.g. \"arguments\": {...}).
    Uses brace counting to support objects with strings containing { or }.
    """
    pattern = re.escape(key) + r"\s*:\s*(\{)"
    match = re.search(pattern, text)
    if not match:
        return None
    start = match.end(1) - 1
    depth = 0
    in_string = False
    escape = False
    quote_char = None
    i = start
    while i < len(text):
        c = text[i]
        if escape:
            escape = False
            i += 1
            continue
        if c == "\\" and in_string:
            escape = True
            i += 1
            continue
        if not in_string:
            if c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    return json.loads(text[start : i + 1])
            elif c in ('"', "'"):
                in_string = True
                quote_char = c
            i += 1
            continue
        if c == quote_char:
            in_string = False
        i += 1
    return None


def extract_tool_args_from_content(content: str) -> dict | None:
    """Fallback for models that return tool calls as text in content.
    Extracts registrar_transacao arguments when native function calling is not supported.
    """
    try:
        obj = extract_json_object_after_key(content, "arguments")
        if obj is not None:
            return obj
        match = re.search(r'"arguments"\s*:\s*(\{[^{}]+\})', content, re.DOTALL)
        if match:
            return json.loads(match.group(1))
    except (json.JSONDecodeError, AttributeError):
        pass
    return None


def normalize_category_name(raw: str) -> str:
    """Strip optional surrounding double quotes from category name for matching."""
    s = raw.strip()
    if len(s) >= 2 and s[0] == '"' and s[-1] == '"':
        s = s[1:-1].strip()
    return s.lower()
