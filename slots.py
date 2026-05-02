import asyncio
import random
import secrets
from aiogram import Router, types
from aiogram.filters import Command

from user_manager import get_user_data, update_user_balance, check_and_give_bonus
from chances import get_game_chance
from escape import escape_html
from config import CREATOR_ID  # <-- ИМПОРТИРУЕМ ID СОЗДАТЕЛЯ

router = Router()

async def schedule_delete(*messages):
    await asyncio.sleep(40)
    for msg in messages:
        try:
            if msg and hasattr(msg, 'delete'):
                await msg.delete()
        except:
            pass

secure_random = secrets.SystemRandom()

EMOJIS =["🍒", "🍋", "🍉", "🍇", "🔔", "💎", "7️⃣"]

@router.message(Command("slots"))
async def cmd_slots(message: types.Message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    full_name = escape_html(message.from_user.full_name)

    data = await get_user_data(chat_id, user_id, full_name)
    if data.get('is_banned', False):
        return await message.answer("Вы забанены и не можете играть.")

    args = message.text.split()
    if len(args) < 2:
        await message.answer("Укажите ставку: <code>/slots 100</code>")
        return

    try:
        bet = int(args[1])
        if bet < 10:
            await message.answer("Минимальная ставка — 10 сыроежек.")
            return
    except ValueError:
        await message.answer("Ставка должна быть числом.")
        return

    bonus_given, receipt = await check_and_give_bonus(chat_id, user_id, full_name)
    bonus_text = f"🎁 Вы получили ежедневный бонус: {receipt.get('total', 0)} сыроежек!\n" if bonus_given else ""

    # Re-fetch data after bonus check
    data = await get_user_data(chat_id, user_id, full_name)
    balance = data.get('balance', 0)

    if balance - bet < -5000:
        await message.answer(f"{bonus_text}Ваш кредитный лимит (-5000) исчерпан. Пополните баланс.")
        return

    # Deduct bet
    await update_user_balance(chat_id, user_id, -bet)

    # Initial message
    msg = await message.answer(f"{bonus_text}🎰 <b>Слоты крутятся...</b>\n\n[ ❓ | ❓ | ❓ ]")

    # Animation
    for _ in range(3):
        await asyncio.sleep(0.5)
        temp_slots = [secure_random.choice(EMOJIS) for _ in range(3)]
        try:
            await msg.edit_text(f"{bonus_text}🎰 <b>Слоты крутятся...</b>\n\n[ {temp_slots[0]} | {temp_slots[1]} | {temp_slots[2]} ]")
        except:
            pass 

    await asyncio.sleep(0.5)

    # --- ЛОГИКА ШАНСОВ И ПОДКРУТКИ ---
    chance = await get_game_chance('slots')
    is_forced_win = False

    # 👑 РЕЖИМ БОГА ДЛЯ СОЗДАТЕЛЯ (Исправлено)
    if CREATOR_ID and int(user_id) == int(CREATOR_ID):
        is_forced_win = True
    elif chance != -1:
        if secure_random.randint(1, 100) <= chance:
            is_forced_win = True

    # Final result generation
    if is_forced_win:
        # Принудительная победа (выдаем случайную выигрышную комбинацию)
        win_types =["jackpot", "mega", "three", "pair_mega", "pair_7"]
        
        # Для создателя даем шанс на джекпот еще выше
        if CREATOR_ID and int(user_id) == int(CREATOR_ID):
            chosen_win = secure_random.choice(["jackpot", "mega", "three", "jackpot"]) # 50% на жирный куш
        else:
            chosen_win = secure_random.choice(win_types)

        if chosen_win == "jackpot":
            final_slots =["7️⃣", "7️⃣", "7️⃣"]
        elif chosen_win == "mega":
            sym = secure_random.choice(["💎", "🔔"])
            final_slots = [sym, sym, sym]
        elif chosen_win == "three":
            sym = secure_random.choice(["🍒", "🍋", "🍉", "🍇"])
            final_slots = [sym, sym, sym]
        elif chosen_win == "pair_mega":
            sym = secure_random.choice(["💎", "🔔"])
            other = secure_random.choice(["🍒", "🍋", "🍉", "🍇"])
            final_slots =[sym, sym, other]
            secure_random.shuffle(final_slots)
        else: # pair_7
            other = secure_random.choice(["🍒", "🍋", "🍉", "🍇"])
            final_slots = ["7️⃣", "7️⃣", other]
            secure_random.shuffle(final_slots)
    else:
        # Обычный честный рандом
        final_slots =[secure_random.choice(EMOJIS) for _ in range(3)]

        # Гарантируем проигрыш, если игрок не попал в установленный шанс
        if chance != -1:
            while final_slots[0] == final_slots[1] or final_slots[1] == final_slots[2] or final_slots[0] == final_slots[2]:
                final_slots =[secure_random.choice(["🍒", "🍋"]), secure_random.choice(["🍉", "🍇"]), secure_random.choice(["💎", "🔔"])]

    profit = 0
    multiplier_text = ""

    # Расчет выигрыша
    if final_slots[0] == final_slots[1] == final_slots[2]:
        if final_slots[0] == "7️⃣":
            profit = bet * 20
            multiplier_text = "ДЖЕКПОТ! x20"
        elif final_slots[0] in ["💎", "🔔"]:
            profit = bet * 10
            multiplier_text = "Мега Куш! x10"
        else:
            profit = bet * 5
            multiplier_text = "Три в ряд! x5"
    elif final_slots[0] == final_slots[1] or final_slots[1] == final_slots[2] or final_slots[0] == final_slots[2]:
        # Определяем пару
        if final_slots[0] == final_slots[1] or final_slots[0] == final_slots[2]:
            pair_emoji = final_slots[0]
        else:
            pair_emoji = final_slots[1]

        if pair_emoji == "7️⃣":
            profit = bet * 2
            multiplier_text = "Пара Семёрок! x2"
        elif pair_emoji in ["💎", "🔔"]:
            profit = int(bet * 1.5)
            multiplier_text = "Крупная пара! x1.5"
        else:
            # Маленькая пара (визуально есть, но без профита в обычной игре, 
            # но мы дадим х1.1 в режиме бога чтобы всегда был плюс)
            if CREATOR_ID and int(user_id) == int(CREATOR_ID):
                profit = int(bet * 1.1)
                multiplier_text = "Удачная пара! x1.1"

    result_text = ""
    is_vip = data.get('is_vip', False)
    is_banker = data.get('is_banker', False)
    vip_bonus_text = ""

    if profit > 0:
        if is_banker:
            profit = int(profit * 0.5)
            vip_bonus_text = f" (🏦 Банкирам выплачивается только 50% от прибыли)"
        elif is_vip:
            vip_profit_bonus = int(profit * 0.1)
            profit += vip_profit_bonus
            vip_bonus_text = f" (👑 VIP бонус: +{vip_profit_bonus})"

        await update_user_balance(chat_id, user_id, bet + profit)
        result_text = f"<b>Вы выиграли {profit} сыроежек!</b> {multiplier_text}{vip_bonus_text}"
    else:
        result_text = f"<b>Вы проиграли {bet} сыроежек.</b>"

    final_text = (
        f"{bonus_text}"
        f"🎰 <b>Слоты остановились</b>\n\n"
        f"[ {final_slots[0]} | {final_slots[1]} | {final_slots[2]} ]\n\n"
        f"{result_text}"
    )

    try:
        await msg.edit_text(final_text)
    except:
        pass
    asyncio.create_task(schedule_delete(msg, message))