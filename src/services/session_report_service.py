import json
from dataclasses import asdict
from utils.aws_utils import upload_data_to_s3
from core.metadata import CallMetadata
from utils.logger import setup_logger

logger = setup_logger("session-report-service")


def scan_non_serialisable(report_dict: dict) -> bool:
    """Walk every top-level key in report_dict and log a WARNING for any value
    that is not JSON-serialisable.

    Returns True if any non-serialisable value is found.
    """
    found_any = False

    for key, value in report_dict.items():
        try:
            json.dumps(value)
        except (TypeError, ValueError):
            found_any = True
            logger.warning(
                "Non-serialisable field in report_dict — will be converted before upload",
                extra={
                    "key": key,
                    "value_type": type(value).__qualname__,
                },
            )

    if not found_any:
        logger.debug("report_dict passed JSON-serialisability scan — all fields are clean")

    return found_any

def merge_metadata_and_options(report_dict: dict, metadata: CallMetadata) -> dict:
    """Merge runtime options into job_metadata,
    removing duplicate fields already defined in CallMetadata schema.
    """
    # Existing runtime options from session_report
    options = report_dict.get("options", {}) or {}

    # Base metadata from Pydantic model
    job_metadata = metadata.model_dump()

    # All valid CallMetadata fields (schema authority)
    metadata_fields = set(CallMetadata.model_fields.keys())

    # Keep only option fields NOT already in metadata schema
    cleaned_options = {
        k: v for k, v in options.items()
        if k not in metadata_fields
    }

    # Merge remaining runtime-only options
    job_metadata.update(cleaned_options)

    return job_metadata


async def upload_session_report(
    *,
    report_dict,
    room_name: str,
    call_id: str,
    metadata: CallMetadata,
    call_state_report: dict,
    summary,
    egress_id: str | None = None,
    platform_ids: dict | None = None,
):
    try:
        # session_report carries the conversation_item_added and chat_history.
        # We would need to pop the chat_history out of the session_report once the integration is done on LiveKit SAM side and conversation is extracted via events.
        
        # 3. Append custom fields
        # Merge metadata + runtime options
        merged_metadata = merge_metadata_and_options(report_dict, metadata)

        # Remove raw options (since we are normalizing)
        report_dict.pop("options", None)

        _platform_ids = platform_ids or {}
        collisions = set(_platform_ids).intersection(report_dict)
        if collisions:
            logger.warning(
                "Platform ID fields overwrite SDK report fields",
                extra={"fields": sorted(collisions)},
            )

        report_dict = {
            **report_dict,
            "call_id": call_id,
            "room_name": room_name,  # backward-compatible alias of SDK "room"
            "call_state": call_state_report,
            "metrics": asdict(summary) if summary else None,
            "job_metadata": merged_metadata,
            "egress_id": egress_id,
            **_platform_ids,
        }

        # Scan for non-serialisable fields and log warnings for each one found.
        # make_json_safe() in aws_utils will sanitise them before the actual upload.
        json_safe = scan_non_serialisable(report_dict)
        logger.info(
            f"Uploading session report to S3 call_id={call_id} room={room_name}"
        )

        await upload_data_to_s3(
            report_dict,
            key=f"calls/{call_id}/session_report.json",
            json_safe=json_safe,
        )
    except Exception:
        logger.exception(
            f"Session report upload FAILED call_id={call_id} room={room_name}",
        )