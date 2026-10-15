import json


def _unwrap(value):
    """call_context entries are shaped {"canonical": "..."}; unwrap to the raw value."""
    if isinstance(value, dict) and "canonical" in value:
        return value["canonical"]
    return value


def _parse_call_context(raw_meta: dict) -> dict:
    call_context = raw_meta.get("call_context")
    if isinstance(call_context, str):
        try:
            call_context = json.loads(call_context)
        except json.JSONDecodeError:
            return {}
    if not isinstance(call_context, dict):
        return {}
    return {k.lower(): v for k, v in call_context.items()}


def _resolve(raw_meta: dict, field_names: list[str]):
    """Yield (field_name, text) for each configured field with a non-empty call_context value."""
    context = _parse_call_context(raw_meta)
    for name in field_names:
        value = _unwrap(context.get(name.lower()))
        if value is None:
            continue
        text = str(value).strip()
        if text:
            yield name, text


def build_keyterms(raw_meta: dict, field_names: list[str], static_terms: list[str] = None) -> list[str]:
    """
    Build the STT key-terms list: call_context-derived values plus static passthrough terms.

    ``call_context`` is a JSON-string-encoded dict whose values are shaped
    ``{"canonical": ...}``. For each configured field name, look it up
    (case-insensitive) in the parsed call_context, unwrap the canonical
    value, and keep non-empty strings. Missing/None/empty values are skipped.

    ``static_terms`` are literal values (e.g. domain acronyms like "NPI" that
    STT commonly mis-transcribes) added as-is, no call_context lookup.

    Derived terms come first, then static terms, de-duplicated preserving order.

    :param raw_meta: The full per-call job metadata dict.
    :param field_names: call_context key names whose values become key terms
        (supplied per call from the DynamoDB agent configuration).
    :param static_terms: literal key terms to include unchanged (from the
        DynamoDB agent configuration).
    :return: Ordered, de-duplicated list of key-term strings.
    """
    terms: list[str] = []
    for _, text in _resolve(raw_meta, field_names):
        if text not in terms:
            terms.append(text)
    for value in static_terms or []:
        text = str(value).strip()
        if text and text not in terms:
            terms.append(text)
    return terms


def resolved_keyterm_fields(raw_meta: dict, field_names: list[str]) -> list[str]:
    """
    Return the subset of field_names that resolved to a non-empty call_context value.

    Field names only, never the underlying (PHI) values -- safe to log.
    """
    return [name for name, _ in _resolve(raw_meta, field_names)]
