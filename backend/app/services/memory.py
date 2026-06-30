from backend.app.db import load_memory, save_memory
from backend.app.schemas import MemoryPayload


class MemoryStore:
    def save(self, payload: MemoryPayload) -> dict[str, str]:
        save_memory(payload.user_id, payload.preferences)
        return {"userId": payload.user_id, "preferences": payload.preferences}

    def get(self, user_id: str = "local-user") -> dict[str, str]:
        return {"userId": user_id, "preferences": load_memory(user_id)}
