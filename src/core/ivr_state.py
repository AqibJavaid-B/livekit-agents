from dataclasses import dataclass

@dataclass
class IVRState:
    """Store IVR navigation state for the agent."""
    last_dtmf_press: float = 0  # timestamp of last DTMF sent
    menu_history: list[str] = None  # track DTMF history

    def __post_init__(self):
        if self.menu_history is None:
            self.menu_history = []