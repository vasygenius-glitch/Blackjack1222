import asyncio
import secrets
from aiogram import Router, types
from aiogram.filters import Command
from user_manager import get_user_data, update_user_balance

router = Router()

async def schedule_delete(*messages, delay: int = 40):
    import asyncio
    await asyncio.sleep(delay)
    for msg in messages:
        try:
            if msg and hasattr(msg, 'delete'):
                await msg.delete()
        except:
            pass

def get_baccarat_value(card_val):
    if card_val > 9:
        return 0
    return card_val

@router.message(Command("baccarat"))
async def cmd_baccarat(message: types.Message):
    args = message.text.split()
    if len(args) < 2:
        return await message.answer("Укажите ставку: <code>/baccarat 100</code>")

    try:
        bet = int(args[1])
        if bet < 100 or bet > 50000000:
            raise ValueError
    except ValueError:
        return await message.answer("Ставка должна быть числом от 100 до 50,000,000 сыроежек.")

    chat_id = message.chat.id
    user_id = message.from_user.id
    data = await get_user_data(chat_id, user_id)

    if data.get('balance', 0) - bet < -5000:
        return await message.answer("Ваш кредитный лимит (-5000) исчерпан. Пополните баланс.")

    rand = secrets.SystemRandom()

    # Draw cards (1-13 where 11, 12, 13 are face cards with 0 value)
    p_cards = [rand.randint(1, 13), rand.randint(1, 13)]
    b_cards = [rand.randint(1, 13), rand.randint(1, 13)]

    p_score = sum(get_baccarat_value(c) for c in p_cards) % 10
    b_score = sum(get_baccarat_value(c) for c in b_cards) % 10

    # Draw third card logic simplified
    if p_score < 6:
        p_cards.append(rand.randint(1, 13))
        p_score = sum(get_baccarat_value(c) for c in p_cards) % 10

    if b_score < 6:
        b_cards.append(rand.randint(1, 13))
        b_score = sum(get_baccarat_value(c) for c in b_cards) % 10

    text = f"🃏 <b>Баккара</b>\n\nОчки Игрока: <b>{p_score}</b>\nОчки Банкира: <b>{b_score}</b>\n\n"

    if p_score > b_score:
        await update_user_balance(chat_id, user_id, bet)
        text += f"🎉 Игрок побеждает! Вы выиграли <b>{bet}</b> сыроежек."
    elif b_score > p_score:
        await update_user_balance(chat_id, user_id, -bet)
        text += f"❌ Банкир побеждает! Вы проиграли <b>{bet}</b> сыроежек."
    else:
        text += "🤝 Ничья! Ваша ставка возвращена."

    msg = await message.answer(text)
    asyncio.create_task(schedule_delete(msg, message))
