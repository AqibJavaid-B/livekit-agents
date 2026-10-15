from livekit.agents import BackgroundAudioPlayer, AudioConfig, BuiltinAudioClip
from core.metadata import CallMetadata
from utils.logger import setup_logger

logger = setup_logger("background-audio")


def build_background_audio(metadata: CallMetadata) -> BackgroundAudioPlayer | None:
    """Build a background-audio player from call metadata, or None when disabled.

    Uses only built-in clips: office ambience (continuous) plus keyboard typing
    while the agent is thinking. Volume and fade in/out are metadata-controlled.
    """
    if not metadata.background_audio_enabled:
        return None

    logger.info(
        "Background audio enabled (ambient vol=%s, thinking vol=%s)",
        metadata.background_ambient_volume,
        metadata.background_thinking_volume,
    )
    return BackgroundAudioPlayer(
        ambient_sound=AudioConfig(
            BuiltinAudioClip.OFFICE_AMBIENCE,
            volume=metadata.background_ambient_volume,
            fade_in=metadata.background_ambient_fade_in,
            fade_out=metadata.background_ambient_fade_out,
        ),
        thinking_sound=[
            AudioConfig(
                BuiltinAudioClip.KEYBOARD_TYPING,
                volume=metadata.background_thinking_volume,
                fade_in=metadata.background_thinking_fade_in,
                fade_out=metadata.background_thinking_fade_out,
            ),
            AudioConfig(
                BuiltinAudioClip.KEYBOARD_TYPING2,
                volume=metadata.background_thinking_volume,
                fade_in=metadata.background_thinking_fade_in,
                fade_out=metadata.background_thinking_fade_out,
            ),
        ],
    )
