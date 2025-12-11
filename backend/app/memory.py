from typing import Dict, Any
import time

class ConversationMemory:
    def __init__(self):
        self._mem: Dict[str, List[Dict]] = {}

    def add_turn(self, session_id: str, role: str, text: str):
        self._mem.setdefault(session_id, []).append({
            "role": role,
            "text": text,
            "timestamp": time.time()
        })

    def get_history(self, session_id: str, max_turns: int = 10):
        return self._mem.get(session_id, [])[-max_turns:]

    def reset(self, session_id: str):
        self._mem[session_id] = []