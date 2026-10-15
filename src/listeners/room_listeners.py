import asyncio
from livekit import rtc
from utils.logger import setup_logger
from services.sip_utils import extract_sip_data
from core.call_state import CallState
from livekit.rtc import DisconnectReason

logger = setup_logger("room-listeners")


def register_room_listeners(room: rtc.Room, call_state: CallState, timeout_seconds: int, on_timeout):

    async def timeout_task():
        await asyncio.sleep(timeout_seconds)
        logger.info("Max call duration reached, deleting room")
        await on_timeout()

    def on_participant_connected(participant: rtc.RemoteParticipant):
        if participant.kind != rtc.ParticipantKind.PARTICIPANT_KIND_SIP:
            return

        logger.info(f"SIP {participant.kind} joined !")

        # Idempotency guard
        if call_state.status == "active":
            logger.debug("Call already active — skipping activation logic "
            "(warm transfer or secondary SIP leg)")
            return

        # First SIP participant only
        call_state.mark_active()
        call_state.sip = extract_sip_data(participant, call_state)

        asyncio.create_task(timeout_task())
        logger.info(
        f"Call activated by SIP participant {participant.identity}. "
        f"Max duration timer set for {timeout_seconds}s"
       )


    def on_participant_disconnected(participant: rtc.RemoteParticipant):
        if participant.kind == rtc.ParticipantKind.PARTICIPANT_KIND_SIP:
            reason_code = participant.disconnect_reason
            reason_name = DisconnectReason.Name(reason_code)
            logger.info(f"SIP participant disconnected. disconnect_reason: {reason_name}")
            call_state.mark_ended(reason_name)

    def on_attr_changed(updated_attrs, participant: rtc.RemoteParticipant):
        if participant.kind != rtc.ParticipantKind.PARTICIPANT_KIND_SIP:
            return

        if "sip.is_voicemail" in updated_attrs:
            call_state.in_voicemail = updated_attrs["sip.is_voicemail"] == "true"
            if call_state.in_voicemail:
                logger.debug("Voicemail detected")

        sip_status = (
            updated_attrs.get("sip.callStatus")
            or updated_attrs.get("sip.status")
        )

        if sip_status:
            logger.info(f"SIP status update: {sip_status} (PSTN call)")

        if any(k.startswith("sip.") for k in updated_attrs):
            call_state.sip = extract_sip_data(participant,call_state, log=False)

    room.on("participant_connected", on_participant_connected)
    room.on("participant_disconnected", on_participant_disconnected)
    room.on("participant_attributes_changed", on_attr_changed)
