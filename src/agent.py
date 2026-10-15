from livekit.agents.llm import function_tool
from livekit import api, rtc
from livekit.agents import Agent, get_job_context, AgentSession, RunContext
from utils.logger import setup_logger
from utils.stream_filters import stream_filter
from utils.agent_helper import RoomManager
from core.call_state import CallState
from livekit.agents.beta.workflows import WarmTransferTask, WorkflowInstructions
from livekit.agents.llm.tool_context import ToolError
from utils.settings import load_settings
from core.ivr_state import IVRState
from utils.constants import TRANSFER_HOLD_MESSAGE, build_human_agent_handoff_instructions
import json
import time
from typing import Optional
import asyncio
from livekit.agents.beta.workflows.utils import DtmfEvent, dtmf_event_to_code

logger = setup_logger("agent")
settings = load_settings()
sip_trunk_id = settings.sip_outbound_trunk_id


def _extract_rx_number(dial_info: dict) -> str | None:
    call_context_raw = dial_info.get("call_context")
    if not call_context_raw:
        logger.warning(
            "No 'call_context' in dial_info; top-level keys=%s",
            list(dial_info.keys()),
        )
        return None

    call_context = call_context_raw
    # call_context may be JSON-encoded one or more times depending on the
    # upstream payload; keep decoding while it's still a string.
    for _ in range(2):
        if not isinstance(call_context, str):
            break
        try:
            call_context = json.loads(call_context)
        except (json.JSONDecodeError, TypeError):
            logger.warning(
                "Failed to JSON-decode call_context; raw value=%r", call_context
            )
            return None

    if not isinstance(call_context, dict):
        logger.warning("call_context did not decode to a dict; got %r", call_context)
        return None

    rx_number = (call_context.get("rx_number") or {}).get("canonical")
    if not rx_number:
        logger.warning(
            "No rx_number.canonical in call_context; call_context keys=%s",
            list(call_context.keys()),
        )
    return rx_number

class Assistant(Agent):
    def __init__(
        self,
        llm_model,
        *,
        dial_info: dict,
        instructions: str,
        transfer_type: str = "warm",
        allow_transfer: bool = False,
    ):
        super().__init__(instructions=instructions, llm=llm_model)
        self.dial_info = dial_info
        self.transfer_type = transfer_type
        self.allow_transfer = allow_transfer
        self._participant: rtc.RemoteParticipant | None = None
        self._session = AgentSession
        self._transferring = False  # Idempotency guard
        self.call_state = CallState()
        # Initialize IVR state
        self.ivr_state = IVRState()

    @property
    def session(self):
        # getter for session
        return self._session

    @session.setter
    def session(self, value):
        # setter for session
        self._session = value

    def set_participant(self, participant: rtc.RemoteParticipant):
        self._participant = participant
    
    # setter for llm
    @property
    def llm(self):
        return self._llm

    @property
    def participant_id(self) -> str:
        if self._participant:
            return self._participant.identity
        return "unknown"

    async def hangup(self, reason: str | None = None):
        await RoomManager.delete_current_room(reason)

    async def llm_node(self, chat_ctx, tools, model_settings:None):
        if self._transferring:
            # A transfer is in progress or has completed: the agent is
            # muted and only monitoring the line, so it must not generate
            # replies. Otherwise the LLM keeps answering the human agent's
            # questions in text, and those phantom turns leak into the
            # chat context / transcript even though nothing is spoken.
            async def _silence():
                return
                yield  # pragma: no cover

            return _silence()

        stream = self.llm.chat(
            chat_ctx=chat_ctx,
            tools=tools,
            tool_choice=None,
        )
        filtered_stream = stream_filter(stream)
        return filtered_stream

    # ---------------- Transfer Logic (ROBUST) ----------------

    @function_tool()
    async def transfer_call(self):
        """Transfers the call to another agent or department (idempotent)."""

        # Prevent duplicate tool calls
        if self._transferring:
            logger.info("Transfer already in progress. Ignoring duplicate request.")
            return "A transfer is already in progress. Please wait."

        if not self.allow_transfer:
            logger.info("Transfer requested but disabled for this agent")
            await self.session.say(
                "I'm sorry, I'm not able to transfer you to a live representative "
                "on this call. Is there anything else I can help you with?",
                allow_interruptions=True,
            )
            return "Transfers are disabled for this agent. Do not attempt to transfer again; continue assisting the caller."

        if not self._participant:
            logger.info("Transfer attempted before SIP participant joined")
            return "Transfer is not available yet. Please wait until the call is connected."

        transfer_to = self.dial_info.get("transfer_to") or self.dial_info.get("transfer_number")
        transfer_from = self.dial_info.get("from_number")

        if not transfer_to:
            return "No transfer number configured."

        self._transferring = True
        ctx = get_job_context()

        logger.info("Starting %s transfer to %s", self.transfer_type, transfer_to)

        try:
            # Warm transfer prompt (once)
            if self.transfer_type == "warm":
                # ---------------- WARM TRANSFER ----------------
                handle = await self.session.say(
                    TRANSFER_HOLD_MESSAGE,
                    allow_interruptions=False,
                )
                await handle.wait_for_playout()

                if not sip_trunk_id:
                    logger.error("No SIP trunk configured for warm transfer")
                    return "Transfer unsuccessful: No SIP trunk configured."

                logger.info("Using SIP trunk for warm transfer: %s", sip_trunk_id)

                # Caller hears hold music (WarmTransferTask's default hold_audio)
                # while we dial the human agent and brief them on the call.
                rx_number = _extract_rx_number(self.dial_info)
                task = await WarmTransferTask(
                    sip_call_to=transfer_to,
                    chat_ctx=self.chat_ctx,
                    sip_trunk_id=sip_trunk_id,
                    sip_number=transfer_from,
                    instructions=WorkflowInstructions(
                        extra=build_human_agent_handoff_instructions(rx_number)
                    ),
                )

                logger.info(
                    "Warm transfer successful. Human agent identity=%s",
                    task.human_agent_identity,
                )

                # Stay on the line so the recording keeps capturing the live
                # conversation, but mute our own output so we don't talk over
                # the human agent and caller. Keep STT on to keep monitoring.
                if self.session.output.audio:
                    self.session.output.set_audio_enabled(False)

                return "Transfer successful."

            else:
                # ---------------- COLD TRANSFER ----------------
                await ctx.api.sip.transfer_sip_participant(
                    api.TransferSIPParticipantRequest(
                        room_name=ctx.room.name,
                        participant_identity=self.participant_id,
                        play_dialtone=True,
                        transfer_to=f"tel:{transfer_to}",
                    )
                )

                logger.info("Cold transfer successful")

                self.session.shutdown(drain=True)
                #await ctx.api.room.delete_room(api.DeleteRoomRequest(room_name=ctx.room.name))

                return "Transfer successful."

        except ToolError as e:
            # This catches ToolError from warm transfers
            error_msg = str(e).lower()
            
            # Determine the reason from the error message
            if "busy" in error_msg or "486" in error_msg:
                reason = "user_busy"
                logger.error("Warm transfer not answered (user_busy)")
            elif "voicemail" in error_msg:
                reason = "voicemail_detected"
                logger.error("Warm transfer failed (voicemail detected)")
            elif "declined" in error_msg or "rejected" in error_msg:
                reason = "rejected"
                logger.error("Warm transfer declined by human agent")
            else:
                reason = "transfer_failed"
                logger.error("Warm transfer failed: %s", e)
            
            self._transferring = False
            
            await self.session.say(
                "Looks like our agent is assisting another client. "
                "We'll reach out to you later when they're available. "
                "Bye, have a great day!",
                allow_interruptions=False,
            )
            await self.hangup(reason)
            return "Transfer unsuccessful."

        except Exception as e:
            logger.error("Unexpected transfer error: %s", e)
            self._transferring = False
            
            await self.session.say(
                "Something went wrong while transferring your call. "
                "Please try again later.",
                allow_interruptions=False,
            )
            await self.hangup("transfer_failed")
            return "Transfer unsuccessful."
        
        # ---------------- IVR Navigation ----------------
        
    @function_tool()
    async def send_dtmf_code(self, events: list[DtmfEvent]):
        """
        Send a list of DTMF events (one digit per event) to navigate an IVR menu. 
        Handles cooldowns, updates IVR menu history, and ensures proper delay between digits. 

        Instructions for LLM:
        - Provide a list of DtmfEvent objects for the digits to send.
        - Do not include extra text; just generate the DtmfEvent sequence to reach the caller's goal.
        - The tool manages timing, state updates, and logging automatically.

        Returns a success message or an error if sending fails.

        """

        now = time.time()
        ctx = get_job_context()

        # Cooldown protection
        if now - self.ivr_state.last_dtmf_press < 3:
            logger.info("DTMF rejected due to cooldown")
            return "Cooldown active. DTMF not sent."

        if not self._participant or not self.session:
            return "Cannot send DTMF: No participant/session connected."

        if not events:
            return "No DTMF events provided."

        logger.info(f"Sending DTMF sequence: {[e.value for e in events]}")

        # Send each DTMF event
        for event in events:
            try:
                code = dtmf_event_to_code(event)

                await ctx.room.local_participant.publish_dtmf(
                    code=code,
                    digit=event.value,
                )

                await asyncio.sleep(0.3)  # Short delay between digits

            except Exception as e:
                logger.exception("Failed to send DTMF event")
                return f"Failed to send DTMF event '{event.value}': {str(e)}"

        # Update IVR state
        self.ivr_state.last_dtmf_press = now

        return f"DTMF sequence {[e.value for e in events]} sent successfully."


    # ---------------- Call Termination ----------------
    @function_tool()
    async def end_call(self, ctx: RunContext):
        """
        Ends the current call and disconnects the user.
        
        Instructions for LLM:
        - Use this tool when the conversation has naturally concluded.
        - Use this tool if the user explicitly requests to end the call, hang up, or say goodbye.
        - Use this tool when the primary goal of the call has been successfully achieved and no further assistance is needed.
        - Avoid using this tool abruptly if the user is still speaking or might need additional help.
        """
        logger.info(f"Ending call for {self.participant_id}")
        try:
            await ctx.wait_for_playout()
        except Exception as e:
            logger.warning(f"Error waiting for playout: {e}")
        await self.hangup("agent_ended_call")
        return "Ending the call now."

    @function_tool()
    async def detected_answering_machine(self, message: Optional[str] = None):
        """
        Called when a voicemail or answering machine is detected.

        Parameters:
            message (optional): Custom message to speak before hanging up.
                                If not provided, a default message is used.
        """
        logger.info(f"Voicemail detected for {self.participant_id}")

        # Default fallback message (backward compatibility)
        default_message = (
            "We have detected that you have reached a voicemail or answering machine. "
            "We will not leave a message. Goodbye!"
        )

        final_message = message if message else default_message

        try:
            await self.session.say(
                final_message,
                allow_interruptions=False,
            )

            await self.hangup("voicemail_detected")
            return "Voicemail detected, hanging up."

        except Exception as e:
            logger.error(
                f"Error during detected_answering_machine: {e}")
            await self.hangup("voicemail_detected")
            return "Error handling voicemail detection."