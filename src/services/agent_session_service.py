import asyncio
from livekit.agents import AgentSession, UserStateChangedEvent
from livekit.agents import inference
from livekit.agents import TurnHandlingOptions
from livekit.plugins.turn_detector.english import EnglishModel
from livekit.plugins import silero, noise_cancellation
from livekit.agents.voice import room_io
from agent import Assistant
from core.metadata import CallMetadata
from utils.logger import setup_logger
from livekit.plugins import elevenlabs, cartesia
from utils.settings import load_settings
from livekit.plugins.elevenlabs import VoiceSettings
from livekit.plugins import assemblyai

logger = setup_logger("agent-session")
settings = load_settings()


async def start_agent_session(
    agent: Assistant,
    metadata: CallMetadata,
    room,
    on_timeout,
) -> AgentSession:

    # Base timeout and Session configuration
    default_timeout = metadata.max_silence_duration
    logger.info("Starting agent session (timeout=%s)", default_timeout)

    if metadata.tts_inference == "elevenlabs":
        logger.info("Using ElevenLabs TTS")
        tts_engine = elevenlabs.TTS(
            api_key=settings.eleven_api_key,
            voice_id=metadata.tts_voice,
            model=metadata.tts_model,
            auto_mode=metadata.auto_mode,
            apply_text_normalization=metadata.apply_text_normalization,
            voice_settings=VoiceSettings(
                stability=metadata.stability,
                similarity_boost=metadata.similarity_boost,
                speed=metadata.speed,
                use_speaker_boost=metadata.use_speaker_boost
            ),
        )
    elif metadata.tts_inference == "cartesia":
        logger.info("Using Cartesia TTS")
        tts_engine = cartesia.TTS(
            api_key=settings.cartesia_api_key,
            voice=metadata.tts_voice,
            model=metadata.tts_model,
            language=metadata.language,
            speed=metadata.cartesia_speed
        )
    elif metadata.tts_inference == "livekit":
        logger.info("Using default inference TTS")
        tts_engine = inference.TTS(
            model=metadata.tts_model,
            voice=metadata.tts_voice,
            extra_kwargs={
                "speed": metadata.tts_speed,
            }
        )

    if metadata.stt_inference == "assemblyai":
        logger.info("Using AssemblyAI STT")
        logger.info(
            "Applying STT key terms",
            extra={
                "configured_fields": metadata.keyterm_fields,
                "static_terms": metadata.keyterm_values,
                "resolved_count": len(metadata.keyterms_prompt),
            },
        )
        stt_engine = assemblyai.STT(
            api_key=settings.assemblyai_api_key,
            model=metadata.stt,
            language_codes=metadata.language,
            min_turn_silence=metadata.min_turn_silence,
            max_turn_silence=metadata.max_turn_silence,
            vad_threshold=metadata.vad_threshold,
            mode=metadata.stt_mode,
            keyterms_prompt=metadata.keyterms_prompt,
        )
    elif metadata.stt_inference == "livekit":
        logger.info("Using default inference STT")
        stt_engine = inference.STT(
            model=metadata.stt,
            language=metadata.language,
            extra_kwargs={
                "min_turn_silence": metadata.min_turn_silence,
                "max_turn_silence": metadata.max_turn_silence,
                "vad_threshold": metadata.vad_threshold,
                "mode": metadata.stt_mode,
            }
        )

    session = AgentSession(
        stt=stt_engine,
        llm=inference.LLM(model=metadata.llm_model,
                          extra_kwargs={
                              "temperature": metadata.llm_temperature,
                            }
                 ),
        tts=tts_engine,
        turn_handling=TurnHandlingOptions(
        turn_detection=inference.TurnDetector(),
        endpointing={
            "mode": "fixed",
            "min_delay": metadata.min_endpointing_delay,
            "max_delay": metadata.max_endpointing_delay,
        },
        interruption={
            "mode": "adaptive",  
            "min_duration": metadata.min_interruption_duration,
            "min_words": metadata.min_interruption_words,
            "false_interruption_timeout": metadata.false_interruption_timeout,
            "resume_false_interruption": metadata.resume_false_interruption,
        },
        preemptive_generation={
            "enabled": metadata.preemptive_generation,
        },
    ),
        vad=silero.VAD.load(activation_threshold=metadata.vad_threshold),
        use_tts_aligned_transcript=metadata.use_tts_aligned_transcript
        if metadata.use_tts_aligned_transcript is not None
        else True,
        user_away_timeout=default_timeout,
        ivr_detection=metadata.ivr_detection,
        min_consecutive_speech_delay=metadata.min_consecutive_speech_delay
    )
    # Attach session to agent
    agent.session = session 

    # Dynamic timeout
    timeout_config = {"current": default_timeout}

    def reset_user_away_timeout():
        if timeout_config["current"] != default_timeout:
            logger.debug("User away timeout reset to default: %s seconds", default_timeout)
            timeout_config["current"] = default_timeout

    # Start session
    logger.info("Connecting agent to room and initializing AI providers...")
    await session.start(
        room=room,
        agent=agent,
        room_options=room_io.RoomOptions(
            close_on_disconnect=False,
            delete_room_on_close=False,
            audio_input=room_io.AudioInputOptions(
                noise_cancellation=None,
            ),
            audio_output=room_io.RoomOutputOptions(sync_transcription=True),
        ),
    )

    logger.info("Agent session is fully initialized and ready.")

    # User away handling
    inactivity_task: asyncio.Task | None = None

    async def user_presence_task():
        """
        This task will:
        - wait for user_away_timeout
        - ask "Are you still there?"
        - repeat 3 times
        - then call on_timeout() to end the call
        """
        for _ in range(3):
            wait_time = timeout_config["current"]
            await asyncio.sleep(wait_time)

            if getattr(agent, "_transferring", False):
                logger.info("Transfer in progress, skipping user-away check")
                return

            logger.info(
                "User away for %s seconds, asking check-in",
                wait_time,
            )
            await session.say("Are you still there?")

        if not getattr(agent, "_transferring", False):
            await on_timeout()

    @session.on("user_state_changed")
    def _user_state_changed(ev: UserStateChangedEvent):
        nonlocal inactivity_task

        if ev.new_state == "away":
            if getattr(agent, "_transferring", False):
                logger.info("User marked away during transfer — ignoring")
                return
            inactivity_task = asyncio.create_task(user_presence_task())
            return

        if inactivity_task:
            inactivity_task.cancel()
            inactivity_task = None

        reset_user_away_timeout()
    return session
