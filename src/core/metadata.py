from pydantic import BaseModel, Field, ConfigDict, field_validator
from typing import Optional, List, Any, Literal

class CallMetadata(BaseModel):
    model_config = ConfigDict(extra="ignore")

    # ---------------- Call info ----------------
    to_number: str
    from_number: str
    call_id: Optional[str] = None
    instructions: str = "You are a helpful assistant."

    # ---------------- Models ----------------
    stt: str = "assemblyai/universal-streaming"
    llm_model: str = "openai/gpt-4.1"
    tts_model: str = "inworld/inworld-tts-1.5-max"          
    tts_voice: str = "Ashley"
    tts_inference: str = Field("livekit", pattern="^(livekit|elevenlabs|cartesia)$")
    stt_inference: str = Field("livekit", pattern="^(livekit|assemblyai)$")
    llm_temperature: float = 0
    
    #-----------------ElevenLabs TTS settings-----------------
    auto_mode: bool = False
    stability: float = 0.95
    similarity_boost: float = 0.75
    speed: float = 0.8
    use_speaker_boost: bool = True
    apply_text_normalization: Literal["on", "off", "auto"] = "on"

    #----------------- Livekit TTS Settings -----------------

    tts_speed: float = 0.8

    #----------------- Cartesia TTS Settings -----------------

    cartesia_speed: float = 1.2

    # ---------------- Call settings ----------------
    language: str = "en"
    max_call_duration: int = 1800
    max_silence_duration: int = 180
    min_interruption_words: int = 3
    preemptive_generation: bool = True
    min_interruption_duration: float = 0.5

    # ---------------- Agent parameters ----------------
    metadata: Optional[Any] = None
    tools: List[Any] = Field(default_factory=list)
    turn_detection: Optional[Any] = None
    mcp_servers: Optional[List[Any]] = None
    allow_interruptions: Optional[bool] = None
    min_endpointing_delay: float = 0.5
    max_endpointing_delay: float = 3.0
    min_consecutive_speech_delay: float = 0.0
    use_tts_aligned_transcript: bool = True
    discard_audio_if_uninterruptible: bool = True
    false_interruption_timeout: float = 2.0
    resume_false_interruption: bool = True
    ivr_detection: bool = False

    # ---------------- Background audio ----------------
    background_audio_enabled: bool = False
    # office ambience (continuous)
    background_ambient_volume: float = 0.3       # 0.0-1.0
    background_ambient_fade_in: float = 2.0      # seconds; smooth ramp-in on answer
    background_ambient_fade_out: float = 1.0     # seconds; taper on stop
    # keyboard typing (while the agent is thinking)
    background_thinking_volume: float = 0.5      # 0.0-1.0
    background_thinking_fade_in: float = 0.25    # seconds
    background_thinking_fade_out: float = 0.5    # seconds

    service_tier: Literal["auto", "default", "flex", "scale", "priority"] = "priority"

    # #---------------- stt settings ----------------
    # language_detection: bool = False
    # inactivity_timeout: float = 30.0
    max_turn_silence: int = 1000
    min_turn_silence: int = 100
    vad_threshold: float = 0.3
    stt_mode: Literal["min_latency", "balanced", "max_accuracy"] = "balanced"
    keyterms_prompt: List[str] = Field(default_factory=list)  # derived per call in main.py from keyterm_fields + keyterm_values
    keyterm_fields: List[str] = Field(default_factory=list)  # metadata keys to source keyterms_prompt values from
    keyterm_values: List[str] = Field(default_factory=list)  # literal key terms passed through as-is (e.g. "NPI")

    # ---------------- Transfer ----------------
    transfer_type: str = Field("warm", pattern="^(cold|warm)$")
    allow_transfer: bool = False

    @field_validator(
        "stt",
        "llm_model",
        "tts_model",
        "max_call_duration",
        "max_silence_duration",
        "service_tier",
        "background_audio_enabled",
        "background_ambient_volume",
        "background_ambient_fade_in",
        "background_ambient_fade_out",
        "background_thinking_volume",
        "background_thinking_fade_in",
        "background_thinking_fade_out",
        mode="before",
    )
    @classmethod
    def replace_none_with_default(cls, v, info):
        if v is None:
            field_name = info.field_name
            return cls.model_fields[field_name].default
        return v
