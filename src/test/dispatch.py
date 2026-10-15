"""CLI helper to create a LiveKit agent dispatch for local testing."""

import argparse
import asyncio
import json
import uuid

from livekit import api

from utils.settings import load_settings

# Load settings so we can fallback to AGENT_NAME if provided.
settings = load_settings()

# Hardcoded fallbacks for CLI overrides (except room_name which is always a UUID).
DEFAULT_AGENT_NAME = "default_outbound_agent_local"
DEFAULT_TO_NUMBER = "+14244249872"
DEFAULT_FROM_NUMBER = "+12063097916"
DEFAULT_TRANSFER_NUMBER = "+16319704702"

def parse_args() -> argparse.Namespace:
    """Parse CLI overrides for dispatch configuration."""
    parser = argparse.ArgumentParser(
        description="Create a LiveKit agent dispatch for testing.",
    )
    # Only agent_name has env/settings fallback.
    parser.add_argument(
        "--agent-name",
        default=settings.agent_name or DEFAULT_AGENT_NAME,
        help="Agent name to dispatch (env AGENT_NAME overrides default).",
    )
    parser.add_argument(
        "--to-number",
        default=DEFAULT_TO_NUMBER,
        help="Destination phone number for the call.",
    )
    parser.add_argument(
        "--from-number",
        default=DEFAULT_FROM_NUMBER,
        help="Caller ID phone number for the call.",
    )
    parser.add_argument(
        "--transfer-number",
        default=DEFAULT_TRANSFER_NUMBER,
        help="Caller ID phone number for the call to transfer to.",
    )
    return parser.parse_args()


async def create_explicit_dispatch(args: argparse.Namespace) -> None:
    """Create a dispatch using CLI arguments and print the results."""
    # Always generate a unique room for each test run.
    room_name = str(uuid.uuid4())

    # Build metadata as JSON to keep formatting consistent.
    metadata = json.dumps(
        {
            "call_id": room_name,
            "to_number": args.to_number,
            "from_number": args.from_number,
            "transfer_number": args.transfer_number,
            "instructions": "You are a polite outbound agent. If user says 'hold on', reply exactly the following: 'NO_RESPONSE_NEEDED'. Use transfer_call tool to initiate the transfer if user requests to talk to a different agent/human being. Use end_call tool to end the call."
        }
    )

    lkapi = api.LiveKitAPI()
    dispatch = await lkapi.agent_dispatch.create_dispatch(
        api.CreateAgentDispatchRequest(
            agent_name=args.agent_name,
            room=room_name,
            metadata=metadata,
        )
    )
    print("created dispatch", dispatch)

    dispatches = await lkapi.agent_dispatch.list_dispatch(room_name=room_name)
    print(f"there are {len(dispatches)} dispatches in {room_name}")
    await lkapi.aclose()

if __name__ == "__main__":
    # Entry point: parse CLI args and run the async dispatch creation.
    asyncio.run(create_explicit_dispatch(parse_args()))