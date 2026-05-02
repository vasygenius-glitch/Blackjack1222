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

@router.message(Command("craps"))
async def cmd_craps(message: types.Message):
    args = message.text.split()
    if len(args) < 2:
        return await message.answer("Укажите ставку: <code>/craps 100</code>")

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
    die1 = rand.randint(1, 6)
    die2 = rand.randint(1, 6)
    total = die1 + die2

    text = f"🎲 <b>Крэпс</b>\n\nБросок: <b>{die1} + {die2} = {total}</b>\n\n"

    if total in [7, 11]:
        await update_user_balance(chat_id, user_id, bet)
        text += f"🎉 Натуральная победа (Pass Line)! Вы выиграли <b>{bet}</b> сыроежек."
    elif total in [2, 3, 12]:
        await update_user_balance(chat_id, user_id, -bet)
        text += f"❌ Крэпс! Вы проиграли <b>{bet}</b> сыроежек."
    else:
        # Simplified craps (no point phase for chat bot simplicity, just a flat roll)
        if rand.choice([True, False]):
            await update_user_balance(chat_id, user_id, bet)
            text += f"🎯 Вы выиграли поинт! Выиграно <b>{bet}</b> сыроежек."
        else:
            await update_user_balance(chat_id, user_id, -bet)
            text += f"❌ Вы не выкинули поинт. Проиграно <b>{bet}</b> сыроежек."

    msg = await message.answer(text)
    asyncio.create_task(schedule_delete(msg, message))
