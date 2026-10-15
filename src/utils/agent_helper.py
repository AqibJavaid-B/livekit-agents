from livekit import api
from livekit.agents import get_job_context
from utils.logger import setup_logger
logger = setup_logger("room-manager")

class AgentMessages:
    GREETING = "Hello! How can I assist you today?"
    TRANSFER_NOTICE = "Transferring you to another agent now."
    TRANSFER_ERROR = "Sorry, I couldn't transfer the call."


class RoomManager:
    @staticmethod
    async def delete_current_room(reason: str | None = None):
        try:
            ctx = get_job_context()
            await ctx.api.room.delete_room(
                api.DeleteRoomRequest(room=ctx.room.name)
            )
            logger.info(f"Room {ctx.room.name} deleted. Reason: {reason}")
        except Exception as e:
            logger.error(f"Room deletion failed: {e}")
