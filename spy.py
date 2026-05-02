from db import get_db

_spy_cache = None

async def get_spy_chats() -> list:
    global _spy_cache
    if _spy_cache is not None:
        return _spy_cache

    db = get_db()
    ref = db.collection('bot_settings').document('spy')
    doc = await ref.get()
    if doc.exists:
        _spy_cache = doc.to_dict().get('chats', [])
    else:
        _spy_cache = []
    return _spy_cache

async def toggle_spy(chat_id: int) -> bool:
    global _spy_cache
    db = get_db()
    ref = db.collection('bot_settings').document('spy')
    chats = await get_spy_chats()

    is_enabled = False
    if chat_id in chats:
        chats.remove(chat_id)
    else:
        chats.append(chat_id)
        is_enabled = True

    _spy_cache = chats
    await ref.set({'chats': chats}, merge=True)
    return is_enabled
