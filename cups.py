import asyncio
import random
import secrets
from aiogram import Router, F, types
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder

from user_manager import get_user_data, update_user_balance, check_and_give_bonus
from chances import get_game_chance
from escape import escape_html

router = Router()

async def schedule_delete(*messages):
    import asyncio
    await asyncio.sleep(40)
    for msg in messages:
        try:
            if msg and hasattr(msg, 'delete'):
                await msg.delete()
        except:
            pass

secure_random = secrets.SystemRandom()

active_cups_games = {}

def get_cups_keyboard(game_id: str):
    builder = InlineKeyboardBuilder()
    builder.button(text="🪣 1", callback_data=f"cups|{game_id}|0")
    builder.button(text="🪣 2", callback_data=f"cups|{game_id}|1")
    builder.button(text="🪣 3", callback_data=f"cups|{game_id}|2")
    return builder.as_markup()

@router.message(Command("cups"))
async def cmd_cups(message: types.Message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    full_name = escape_html(message.from_user.full_name)

    data = await get_user_data(chat_id, user_id, full_name)
    if data.get('is_banned', False):
        await message.answer("Вы забанены и не можете играть.")
        return

    args = message.text.split()
    if len(args) < 2:
        await message.answer("Укажите ставку: <code>/cups 100</code>")
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

    await update_user_balance(chat_id, user_id, -bet)

    game_id = f"{chat_id}-{user_id}-{message.message_id}"
    winning_cup = secure_random.randint(0, 2)

    active_cups_games[game_id] = {
        'original_msg': message,
        'user_id': user_id,
        'chat_id': chat_id,
        'full_name': full_name,
        'bet': bet,
        'winning_cup': winning_cup,
        'bonus_text': bonus_text
    }

    text = (
        f"{bonus_text}"
        f"🪣 <b>Игра в наперстки!</b>\n\n"
        f"Игрок: {full_name}\n"
        f"Ставка: {bet}\n\n"
        f"Шарик 🔴 спрятан под одним из наперстков. Кручу-верчу, запутать хочу... Выбирай!"
    )

    await message.answer(text, reply_markup=get_cups_keyboard(game_id))

@router.callback_query(F.data.startswith("cups|"))
async def process_cups(callback: types.CallbackQuery):
    parts = callback.data.split("|")
    if len(parts) != 3:
        await callback.answer()
        return

    game_id = parts[1]
    chosen_cup = int(parts[2])

    game = active_cups_games.pop(game_id, None)
    if not game:
        await callback.answer("Эта игра уже завершена или не найдена.", show_alert=True)
        return

    if callback.from_user.id != game['user_id']:
        await callback.answer("Это не ваша игра!", show_alert=True)
        active_cups_games[game_id] = game # Put back if wrong user
        return

    # Animation
    await callback.message.edit_text("⏳ <i>Поднимаем наперсток...</i>")
    await asyncio.sleep(1)

    winning_cup = game['winning_cup']
    bet = game['bet']

    # Проверка шансов (Подкрутка)
    chance = await get_game_chance('cups')
    if chance != -1:
        is_forced_win = (secure_random.randint(1, 100) <= chance)
        if is_forced_win:
            winning_cup = chosen_cup
        else:
            # Выбираем любую другую чашку, чтобы игрок гарантированно проиграл
            possible_cups = [0, 1, 2]
            possible_cups.remove(chosen_cup)
            winning_cup = secure_random.choice(possible_cups)
    chat_id = game['chat_id']
    user_id = game['user_id']
    full_name = game['full_name']
    bonus_text = game['bonus_text']

    cups_display = ["🪣", "🪣", "🪣"]
    cups_display[winning_cup] = "🔴"

    display_str = "  ".join(cups_display)

    data = await get_user_data(chat_id, user_id)
    is_vip = data.get('is_vip', False)

    if chosen_cup == winning_cup:
        profit = bet * 2
        vip_bonus_text = ""
        if is_vip:
            vip_profit_bonus = int(profit * 0.1)
            profit += vip_profit_bonus
            vip_bonus_text = f" (👑 VIP бонус: +{vip_profit_bonus})"

        await update_user_balance(chat_id, user_id, bet + profit)
        result_text = f"<b>Победа!</b> Вы угадали и выиграли {profit} сыроежек! {vip_bonus_text}"
    else:
        result_text = f"<b>Проигрыш!</b> Шарик был в другом месте. Вы потеряли {bet} сыроежек."

    final_text = (
        f"{bonus_text}"
        f"🪣 <b>Результат:</b>\n\n"
        f"[ {display_str} ]\n\n"
        f"Игрок: {full_name}\n"
        f"{result_text}"
    )

    await callback.message.edit_text(final_text)
    await callback.answer()
