import time
from typing import Optional, Dict, Any, List 

from utils.logger import setup_logger
logger = setup_logger("call-state")

class CallState:
    def __init__(self):
        self.status: str = "dialing"
        self.disconnection_reason: Optional[str] = None
        self.in_voicemail: bool = False
        self.sip: Optional[Dict[str, Any]] = None
        self.timestamps: Dict[str, float] = {
            "started_at": time.time()
        }
        self.seen_sip_participants: set[str] = set()

        self.metrics_raw: List[Dict[str, Any]] = []

    def mark_active(self):
        self.status = "active"
        self.timestamps["answered_at"] = time.time()

    def mark_ended(self, reason: Optional[str] = None):
        self.status = "ended"
        self.disconnection_reason = reason
        self.timestamps["ended_at"] = time.time()

    def mark_failed(self, reason: str | Dict[str, Any]):
        self.status = "failed"
        self.timestamps["ended_at"] = time.time()

        if isinstance(reason, dict):
            if self.sip is None:
                self.sip = {}
            for k in ["sip_status", "sip_status_code"]:
                if k in reason:
                    self.sip[k] = reason[k]
            self.disconnection_reason = reason.get("sip_status") or str(reason)
        else:
            self.disconnection_reason = reason
    # stable serialization boundary
    def to_dict(self) -> dict:
        started_at = self.timestamps.get("started_at")
        answered_at = self.timestamps.get("answered_at")
        ended_at = self.timestamps.get("ended_at")

        return {
            "status": self.status,
            "disconnection_reason": self.disconnection_reason,
            "in_voicemail": self.in_voicemail,
            "timestamps": dict(self.timestamps),
            "durations": {
                "total_seconds": (
                    ended_at - started_at
                    if ended_at and started_at
                    else None
                ),
                "time_to_answer_seconds": (
                    answered_at - started_at
                    if answered_at and started_at
                    else None
                ),
            },
            "sip": {
                "sip_call_id": (self.sip or {}).get("sip_call_id"),
                "sip_trunk_id": (self.sip or {}).get("sip_trunk_id"),
                "sip_status": (self.sip or {}).get("sip_status"),
                "sip_status_code": (self.sip or {}).get("sip_status_code"),
                "from_number": (self.sip or {}).get("from_number"),
                "to_number": (self.sip or {}).get("to_number"),
                "sip_hostname": (self.sip or {}).get("sip_hostname"),
            },
        }
