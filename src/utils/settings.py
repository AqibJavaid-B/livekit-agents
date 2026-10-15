import os
from dataclasses import dataclass
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).parent.parent
ENV_FILES = [
    BASE_DIR / ".env",
    BASE_DIR / ".env.local",
    BASE_DIR / ".settings",
]


@dataclass(frozen=True)
class Settings:
    # Env variable names are centralized here to avoid string duplication
    # across the codebase. Update names here if env vars change.
    SIP_OUTBOUND_TRUNK_ID = "SIP_OUTBOUND_TRUNK_ID"
    AGENT_NAME = "AGENT_NAME"
    ELEVEN_API_KEY = "ELEVEN_API_KEY"
    S3_BUCKET_NAME = "S3_BUCKET_NAME"
    CARTESIA_API_KEY = "CARTESIA_API_KEY"
    ASSEMBLYAI_API_KEY = "ASSEMBLYAI_API_KEY"

    # Typed settings exposed to the rest of the app.
    sip_outbound_trunk_id: str
    agent_name: str
    eleven_api_key: str
    s3_bucket_name: str
    cartesia_api_key: str
    assemblyai_api_key: str


FIELD_TO_KEY = {
    # Note: load_dotenv reads all environment variables into the process,
    # but we only expose the subset listed here via Settings.
    # Add new keys here (and fields on Settings) to make them available in code.
    "sip_outbound_trunk_id": Settings.SIP_OUTBOUND_TRUNK_ID,
    "agent_name": Settings.AGENT_NAME,
    "eleven_api_key": Settings.ELEVEN_API_KEY,
    "s3_bucket_name": Settings.S3_BUCKET_NAME,
    "cartesia_api_key": Settings.CARTESIA_API_KEY,
    "assemblyai_api_key": Settings.ASSEMBLYAI_API_KEY,
}

REQUIRED_FIELDS = FIELD_TO_KEY.keys()


def _load_env_files() -> None:
    # Load .env first (defaults), then .env.local (overrides)
    # to allow local developer overrides without changing defaults.
    for idx, env_path in enumerate(ENV_FILES):
        if env_path.exists():
            load_dotenv(dotenv_path=env_path, override=idx == 1)


def _validate_required(values: dict) -> None:
    # Fail fast if any required values are missing so services
    # don't crash later with unclear errors.
    missing = [
        FIELD_TO_KEY[field]
        for field in REQUIRED_FIELDS
        if not values.get(field)
    ]
    if missing:
        attempted = ", ".join([str(p) for p in ENV_FILES])
        raise EnvironmentError(
            f"Missing required environment variables: {', '.join(missing)} from files located at: {attempted}",
        )


def load_settings() -> Settings:
    _load_env_files()
    values = {field: os.getenv(key) for field, key in FIELD_TO_KEY.items()}
    _validate_required(values)
    return Settings(**values)
