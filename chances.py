from db import get_db

async def get_game_chance(game_name: str) -> int:
    db = get_db()
    ref = db.collection('bot_settings').document('chances')
    doc = await ref.get()
    if doc.exists:
        data = doc.to_dict()
        return data.get(game_name, -1) # -1 означает честный рандом
    return -1

async def set_game_chance(game_name: str, percentage: int):
    db = get_db()
    ref = db.collection('bot_settings').document('chances')
    await ref.set({game_name: percentage}, merge=True)
