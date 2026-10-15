from livekit import rtc

PARTICIPANT_KIND_MAP = {
    rtc.ParticipantKind.PARTICIPANT_KIND_STANDARD: "STANDARD",
    rtc.ParticipantKind.PARTICIPANT_KIND_INGRESS: "INGRESS",
    rtc.ParticipantKind.PARTICIPANT_KIND_EGRESS: "EGRESS",
    rtc.ParticipantKind.PARTICIPANT_KIND_SIP: "SIP",
    rtc.ParticipantKind.PARTICIPANT_KIND_AGENT: "AGENT",
}

DISCONNECT_REASON_MAP = {
    0: "UNKNOWN_REASON",
    1: "CLIENT_INITIATED",
    11: "USER_UNAVAILABLE",
    12: "USER_REJECTED",
    13: "SIP_TRUNK_FAILURE",
    14: "CONNECTION_TIMEOUT",
    15: "MEDIA_FAILURE",
}

# ---------------- Transfer Configuration (NEW) ----------------

TRANSFER_TYPE_COLD = "cold"
TRANSFER_TYPE_WARM = "warm"

ALLOWED_TRANSFER_TYPES = {
    TRANSFER_TYPE_COLD,
    TRANSFER_TYPE_WARM,
}

WAIT_PHRASES = {
    "no_response_needed": "",
    "No response needed": ""
}

TRANSFER_HOLD_MESSAGE = "Please hold while I connect you to a live representative."

def build_human_agent_handoff_instructions(rx_number: str) -> str:
    # Bakes in the RX number directly since it may never be said aloud in the conversation.
    return (
        "Important: disregard the earlier instruction to open with a summary of "
        "the conversation. Do not say anything else first. Follow this exact "
        "sequence instead:\n"
        f'1. Say exactly: "Memory Arcs transfer - the RX number is {rx_number}. '
        'Would you like me to repeat it or connect the call?"\n'
        "2. If they ask you to repeat it, repeat the RX number exactly.\n"
        "3. Once they're ready, call the tool to connect them to the caller."
    )
