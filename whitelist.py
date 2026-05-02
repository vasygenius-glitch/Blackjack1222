from db import get_db

_whitelist_cache = None

async def get_whitelist():
    global _whitelist_cache
    if _whitelist_cache is not None:
        return _whitelist_cache

    db = get_db()
    ref = db.collection('bot_settings').document('whitelist')
    doc = await ref.get()
    if doc.exists:
        data = doc.to_dict()
        # Migrate old format (list) to new format (dict) if necessary
        allowed = data.get('allowed_chats', {})
        if isinstance(allowed, list):
            _whitelist_cache = {int(k): "Unknown Group" for k in allowed if str(k).strip()}
            save_data = {str(k): v for k, v in _whitelist_cache.items()}
            await ref.set({'allowed_chats': save_data})
        else:
            _whitelist_cache = {int(k): v for k, v in allowed.items() if str(k).strip()}
    else:
        _whitelist_cache = {}
    return _whitelist_cache

async def add_to_whitelist(chat_id: int, chat_title: str = "Unknown Group"):
    global _whitelist_cache
    db = get_db()
    ref = db.collection('bot_settings').document('whitelist')
    whitelist = await get_whitelist()
    if chat_id not in whitelist:
        whitelist[chat_id] = chat_title
        _whitelist_cache = whitelist
        # Firestore keys must be strings
        save_data = {str(k): v for k, v in whitelist.items()}
        await ref.set({'allowed_chats': save_data})
        return True
    return False

async def remove_from_whitelist(chat_id: int):
    global _whitelist_cache
    db = get_db()
    ref = db.collection('bot_settings').document('whitelist')
    whitelist = await get_whitelist()
    if chat_id in whitelist:
        del whitelist[chat_id]
        _whitelist_cache = whitelist
        save_data = {str(k): v for k, v in whitelist.items()}
        await ref.set({'allowed_chats': save_data})
        return True
    return False


async def log_unauthorized_chat(chat_id: int, chat_title: str):
    db = get_db()
    ref = db.collection('bot_settings').document('unauthorized_logs')
    doc = await ref.get()
    logs = doc.to_dict().get('logs', {}) if doc.exists else {}

    str_id = str(chat_id)
    if str_id not in logs:
        logs[str_id] = chat_title
        await ref.set({'logs': logs}, merge=True)
        return True
    return False
