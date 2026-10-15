import os
import boto3
import json
import asyncio
import dataclasses
from utils.settings import load_settings
from .logger import setup_logger

logger = setup_logger("aws-utils")
settings = load_settings()


def _aws_region() -> str | None:
    """Read AWS region from environment. Prefers AWS_REGION (used by LiveKit
    log drains), falls back to AWS_DEFAULT_REGION (used by boto3 natively)."""
    return os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION")

def make_json_safe(obj):
    """Recursively convert any non-JSON-serialisable object to a safe representation.
    
    Handles dicts, lists, dataclasses, Pydantic models, and any other object by
    rendering it as a readable placeholder string instead of crashing json.dumps.
    """
    if isinstance(obj, dict):
        return {k: make_json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [make_json_safe(i) for i in obj]
    if isinstance(obj, (str, int, float, bool)) or obj is None:
        return obj
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return make_json_safe(dataclasses.asdict(obj))
    if hasattr(obj, "model_dump"):          # Pydantic v2
        return make_json_safe(obj.model_dump())
    if hasattr(obj, "__dict__"):            # Catch-all: plugin objects like TTS
        return f"<non-serialisable: {type(obj).__qualname__}>"
    # Primitive fallback (e.g. bytes, sets)
    try:
        json.dumps(obj)
        return obj
    except TypeError:
        return f"<non-serialisable: {type(obj).__qualname__}>"


def _sync_put_object(content: dict, key: str, json_safe: bool) -> None:
    """Synchronous helper for S3 upload to be run in a thread."""
    s3 = boto3.client("s3", region_name=_aws_region())
    safe_content = make_json_safe(content) if json_safe else content
    s3.put_object(
        Bucket=settings.s3_bucket_name,
        Key=key,
        Body=json.dumps(safe_content),
        ContentType="application/json"
    )


async def upload_data_to_s3(content: dict, key: str, json_safe: bool = False) -> None:
    """Asynchronous wrapper for S3 upload using a thread pool."""
    await asyncio.to_thread(_sync_put_object, content, key, json_safe)
    logger.info(f"Uploaded data to s3://{settings.s3_bucket_name}/{key}")