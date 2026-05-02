from db import get_db

async def get_global_tax() -> int:
    db = get_db()
    doc = await db.collection('bot_settings').document('economy').get()
    if doc.exists:
        return doc.to_dict().get('tax', 10)
    return 10

async def set_global_tax(tax: int):
    db = get_db()
    await db.collection('bot_settings').document('economy').set({'tax': tax}, merge=True)
