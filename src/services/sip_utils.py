from typing import Any, Dict
from utils.constants import PARTICIPANT_KIND_MAP
from livekit import rtc
from utils.logger import setup_logger
from livekit.api.twirp_client import TwirpError

logger = setup_logger("sip-utils")

def extract_sip_data(participant: rtc.RemoteParticipant, call_state: Any, log: bool = True) -> Dict[str, Any]:
    try:
        attrs = participant.attributes

        def get_attr(*keys):
            for k in keys:
                if val := attrs.get(k):
                    return val
            return None

        sip_call_id = get_attr("sip.call_id", "sip.callID")

        # Only log first time
        if log and participant.sid not in call_state.seen_sip_participants:
            logger.info(
                f"Extracted SIP data for participant {participant.identity}, "
                f"SIP Call ID: {sip_call_id}"
            )
            call_state.seen_sip_participants.add(participant.sid)

        return {
            "participant_identity": participant.identity,
            "participant_sid": participant.sid,
            "participant_kind": PARTICIPANT_KIND_MAP.get(participant.kind, "UNKNOWN"),
            "sip_call_id": sip_call_id,
            "sip_trunk_id": get_attr("sip.trunkID", "sip.trunk_id"),
            "sip_status": get_attr("sip.callStatus", "sip.status"),
            "sip_status_code": attrs.get("sip.status_code"),
            "from_number": get_attr("sip.trunkPhoneNumber", "sip.from_number"),
            "to_number": get_attr("sip.phoneNumber", "sip.to_number"),
            "sip_hostname": attrs.get("sip.hostname"),
            "is_voicemail": attrs.get("sip.is_voicemail") == "true",
            "all_attributes": dict(attrs),
        }

    except Exception as e:
        logger.error(f"Error extracting SIP data: {e}", exc_info=True)
        return {}

def classify_sip_error(e: TwirpError) -> Dict[str, Any]:
    logger.info("SIP Error Identification")
    status = getattr(e, "status")
    disconnection_reason = {}
    # ringing timeout
    if status == 408:
        disconnection_reason["sip_status"] = "Ringing timeout"
        disconnection_reason["sip_status_code"] = status
        logger.info("Ringing Timeout")
        return disconnection_reason
    
    if hasattr(e, "metadata") and e.metadata:
        for k in ["sip_status", "sip_status_code"]:
            if val := e.metadata.get(k):
                disconnection_reason[k] = val
                
    # Explicit rejection / busy
    if status in (486, 429):
        logger.info("Rejected Call/User Busy")
        return disconnection_reason

    # Catch-all
    logger.info("SIP dial failed: %s", e)
    return disconnection_reason
