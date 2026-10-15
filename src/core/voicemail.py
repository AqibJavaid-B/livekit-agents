from typing import List, Dict, Any

VOICEMAIL_KEYWORDS = {
    "leave a message",
    "after the tone",
    "after the beep",
    "not available",
    "cannot take your call",
    "mailbox",
    "voicemail",
}


def detect_voicemail_from_history(
    history: Dict[str, Any]
) -> bool:
    items: List[Dict[str, Any]] = history.get("items", [])
    if not items:
        return False

    first = items[0]
    if first.get("role") != "user":
        return False

    content_raw = first.get("content", "")
    if isinstance(content_raw, list):
        content = " ".join(content_raw).lower()
    elif isinstance(content_raw, str):
        content = content_raw.lower()
    else:
        content = str(content_raw).lower()
        
    return any(keyword in content for keyword in VOICEMAIL_KEYWORDS)
