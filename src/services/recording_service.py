import os
from livekit import api
from utils.settings import load_settings
from utils.logger import setup_logger

logger = setup_logger("recording")
settings = load_settings()


def _required_env(name: str) -> str:
    """Read a required environment variable or raise a clear error."""
    value = os.environ.get(name)
    if not value:
        raise EnvironmentError(f"Missing required environment variable: {name}")
    return value


def _aws_region() -> str | None:
    """Read AWS region from environment. Prefers AWS_REGION, falls back to AWS_DEFAULT_REGION."""
    return os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION")


async def start_recording(call_id: str, room_name: str):
    try:
        region = _aws_region()
        if not region:
            raise EnvironmentError("Missing required environment variable: AWS_REGION or AWS_DEFAULT_REGION")

        s3 = api.S3Upload(
            bucket=settings.s3_bucket_name,
            region=region,
            access_key=_required_env("AWS_ACCESS_KEY_ID"),
            secret=_required_env("AWS_SECRET_ACCESS_KEY"),
            session_token=os.environ.get("AWS_SESSION_TOKEN", ""),
        )

        req = api.RoomCompositeEgressRequest(
            room_name=room_name,
            audio_only=True,
            file_outputs=[
                api.EncodedFileOutput(
                    filepath=f"calls/{call_id}/recording.mp4",
                    s3=s3,
                )
            ],
        )

        lk = api.LiveKitAPI()
        try:
            egress_info = await lk.egress.start_room_composite_egress(req)
            logger.info(f"Recording Initiated Successfully. Egress ID: {egress_info.egress_id}")
            return egress_info.egress_id
        finally:
            await lk.aclose()
    except Exception as e:
        logger.error(f"Failed to start recording: {e}")
        return None
