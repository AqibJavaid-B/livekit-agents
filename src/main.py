import json
import asyncio
from livekit import agents
from core.metadata import CallMetadata          
from core.call_state import CallState
from services.recording_service import start_recording
from utils.prompt_loader import load_prompt_from_string as load_prompt
from utils.keyterms import build_keyterms, resolved_keyterm_fields
from utils.settings import load_settings
from utils.logger import setup_logger
from services.agent_session_service import start_agent_session
from services.background_audio_service import build_background_audio
from livekit.plugins import silero
from livekit.agents import JobProcess
from agent import Assistant
from livekit import api
from listeners.room_listeners import register_room_listeners
from google.protobuf.duration_pb2 import Duration
from livekit.api.twirp_client import TwirpError
from services.sip_utils import classify_sip_error
from services.session_report_service import upload_session_report
from pydantic import ValidationError


logger = setup_logger("main")
settings = load_settings()

async def entrypoint(ctx: agents.JobContext):
    call_state = CallState()
    session = None

    try:
        raw_meta = json.loads(ctx.job.metadata)
    except (json.JSONDecodeError, TypeError) as e:
        logger.error(
            "Failed to parse job metadata JSON",
            extra={
                "error": str(e),
                "room_name": ctx.room.name,
                "metadata_length": len(ctx.job.metadata or ""),
            },
        )
        ctx.shutdown()
        return

    try:
        metadata = CallMetadata(**raw_meta)
    except ValidationError as e:
        logger.error(
            "Job metadata validation failed",
            extra={
                "validation_errors": e.errors(include_input=False),
                "room_name": ctx.room.name,
                "call_id": raw_meta.get("call_id"),
            },
        )
        ctx.shutdown()
        return
    except Exception:
        logger.exception(
            "Unexpected error parsing job metadata",
            extra={"room_name": ctx.room.name},
        )
        ctx.shutdown()
        return

    metadata.keyterms_prompt = build_keyterms(raw_meta, metadata.keyterm_fields, metadata.keyterm_values)
    logger.info(
        "STT key terms resolved",
        extra={
            "configured_fields": metadata.keyterm_fields,
            "resolved_fields": resolved_keyterm_fields(raw_meta, metadata.keyterm_fields),
            "static_terms": metadata.keyterm_values,
            "resolved_count": len(metadata.keyterms_prompt),
        },
    )

    call_id = metadata.call_id

    platform_ids = {
        "agent_name": ctx.job.agent_name if ctx.job else None,
        "dispatch_id": ctx.job.dispatch_id if ctx.job else None,
        "worker_id": getattr(ctx, "worker_id", None),
    }

    prompt = load_prompt(metadata.instructions, raw_meta)
    
    agent = Assistant(
        llm_model=metadata.llm_model,
        dial_info=raw_meta,
        instructions=prompt,
        transfer_type=metadata.transfer_type,
        allow_transfer=metadata.allow_transfer,
    )
    max_call_duration = metadata.max_call_duration
    
    register_room_listeners(
        room=ctx.room,
        call_state=call_state,
        timeout_seconds=max_call_duration,
        on_timeout=lambda: agent.hangup(reason="max_duration_reached")
    )

    try:
        session = await start_agent_session(
            room=ctx.room,
            agent=agent,
            metadata=metadata,
            on_timeout=lambda: agent.hangup(reason="user_away"),
        )
        logger.info("Agent session started")

    except Exception as e:
        logger.error("Error creating agent session", exc_info=True)
        call_state.mark_failed(f"Session start failed: {e}")
        ctx.shutdown()
        return
    
    # Background audio player (None when disabled in metadata); started below once the call is active
    background_audio = build_background_audio(metadata)

    egress_id_holder = {"value": None}
        
    async def shutdown_upload():
        try:
            logger.info("Shutdown upload initiated.")
            summary = session.usage if session else None

            # 1. Create base LiveKit session report
            report = ctx.make_session_report()
            report_dict = report.to_dict()

            await upload_session_report(
                report_dict=report_dict,
                room_name=ctx.room.name,
                call_id=call_id,
                metadata=metadata,
                call_state_report=call_state.to_dict(),
                summary=summary,
                egress_id=egress_id_holder["value"],
                platform_ids=platform_ids,
            )

        except Exception as e:
            logger.exception(f"Error during shutdown upload: {e}", exc_info=True)   


    ctx.add_shutdown_callback(shutdown_upload)

      # --- SIP Dial with Retry ---
    MAX_DIAL_ATTEMPTS = 60
    RETRY_DELAY_SECONDS = 1
 
    for attempt in range(MAX_DIAL_ATTEMPTS):
        try:
            if attempt == 0:
                logger.info(f"SIP dial initiated to {metadata.to_number}")
            else:
                logger.info(f"Retrying SIP dial to {metadata.to_number} (attempt {attempt + 1}/{MAX_DIAL_ATTEMPTS})")
 
            await ctx.api.sip.create_sip_participant(
                api.CreateSIPParticipantRequest(
                    room_name=ctx.room.name,
                    sip_trunk_id=settings.sip_outbound_trunk_id,
                    sip_number=metadata.from_number,
                    sip_call_to=metadata.to_number,
                    participant_identity=metadata.to_number,
                    wait_until_answered=True,
                    ringing_timeout=Duration(seconds=60),
                )
            )
            logger.info("SIP dial successfully initiated.")
            break  # Success
 
        except TwirpError as e:
            if "CPS limit exceeded" in str(e) and attempt < MAX_DIAL_ATTEMPTS - 1:
                logger.warning(
                    f"SIP dial failed due to CPS limit. Retrying in {RETRY_DELAY_SECONDS}s..."
                )
                await asyncio.sleep(RETRY_DELAY_SECONDS)
                continue
 
            if "CPS limit exceeded" in str(e):
                logger.error(
                    f"SIP dial failed after {MAX_DIAL_ATTEMPTS} attempts due to persistent CPS limit."
                )
           
            reason = classify_sip_error(e)
            call_state.mark_failed(reason)
            ctx.shutdown()
            return

    participant = await ctx.wait_for_participant(identity=metadata.to_number)
    agent.set_participant(participant)
    
    # Check if call failed during dial (updated by room listeners)
    if call_state.status == "failed":
        logger.info("Call failed during dial, shutting down")
        ctx.shutdown()
        return

    async def start_recording_wrapper():
        egress_id_holder["value"] = await start_recording(
            call_id,
            room_name=ctx.room.name,
        )

    if call_state.status == "active":
        asyncio.create_task(start_recording_wrapper())
        logger.info("Recording started for active call")

        if background_audio is not None:
            try:
                await background_audio.start(room=ctx.room, agent_session=session)
                logger.info("Background audio started")

                async def _close_background_audio():
                    try:
                        await background_audio.aclose()
                    except Exception as e:
                        logger.warning("Error closing background audio: %s", e)

                ctx.add_shutdown_callback(_close_background_audio)
            except Exception as e:
                logger.warning("Failed to start background audio: %s", e)
    else:
        logger.info(f"Call status is {call_state.status}, waiting for participant events...")


# ------------------- Prewarm -------------------
def prewarm(_proc: JobProcess):
    silero.VAD.load()  # warm model weights into cache; threshold is set per-call

if __name__ == "__main__":
    agents.cli.run_app(
        agents.WorkerOptions(
            entrypoint_fnc=entrypoint,
            agent_name=settings.agent_name,
            prewarm_fnc=prewarm,
        )
    )