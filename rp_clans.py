import time
import secrets
from aiogram import Router, types, F, Bot
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from db import get_db
from escape import escape_html
from user_manager import get_user_data, update_user_balance, update_user_field

router = Router()

# ================= БРАКИ =================
active_marriages = {}

@router.message(F.text.lower().in_(["брак", "/marry"]))
async def cmd_marry(message: types.Message):
    if not message.reply_to_message:
        return await message.answer("Ответьте на сообщение человека, которому хотите предложить брак.")

    chat_id = message.chat.id
    user_id = message.from_user.id
    target_id = message.reply_to_message.from_user.id

    if user_id == target_id:
        return await message.answer("Нельзя вступить в брак с самим собой.")
    if message.reply_to_message.from_user.is_bot:
        return await message.answer("Нельзя вступить в брак с ботом.")

    user_data = await get_user_data(chat_id, user_id)
    target_data = await get_user_data(chat_id, target_id)

    if user_data.get('partner'):
        return await message.answer("Вы уже в браке!")
    if target_data.get('partner'):
        return await message.answer("Этот человек уже в браке!")

    marriage_id = f"{chat_id}_{user_id}_{target_id}"
    active_marriages[marriage_id] = {'amount': 0} # Для подарков

    builder = InlineKeyboardBuilder()
    builder.button(text="Да", callback_data=f"marry_yes_{marriage_id}")
    builder.button(text="Нет", callback_data=f"marry_no_{marriage_id}")

    await message.answer(
        f"💍 <b>Предложение руки и сердца!</b>\n\n"
        f"Пользователь <b>{escape_html(message.from_user.full_name)}</b> предлагает <b>{escape_html(message.reply_to_message.from_user.full_name)}</b> стать партнерами.\n\n"
        f"<i>Зрители могут отправлять свадебные подарки, написав реплаем 'Подарок [сумма]' на это сообщение!</i>",
        reply_markup=builder.as_markup()
    )

@router.message(F.text.lower().startswith("подарок") | F.text.lower().startswith("/gift"))
async def cmd_gift(message: types.Message):
    if not message.reply_to_message or not message.reply_to_message.reply_markup:
        return

    chat_id = message.chat.id
    user_id = message.from_user.id
    args = message.text.split()
    if len(args) < 2:
        return

    try:
        amount = int(args[1])
        if amount <= 0: return
    except ValueError:
        return

    # Ищем marriage_id по кнопкам
    marriage_id = None
    for row in message.reply_to_message.reply_markup.inline_keyboard:
        for btn in row:
            if btn.callback_data and btn.callback_data.startswith("marry_yes_"):
                marriage_id = btn.callback_data.replace("marry_yes_", "")
                break

    if not marriage_id or marriage_id not in active_marriages:
        return

    user_data = await get_user_data(chat_id, user_id)
    if user_data.get('balance', 0) < amount:
        return await message.answer("У вас недостаточно сыроежек для такого подарка.")

    await update_user_balance(chat_id, user_id, -amount)
    active_marriages[marriage_id]['amount'] += amount
    await message.answer(f"🎁 <b>{escape_html(message.from_user.full_name)}</b> вложил <b>{amount}</b> сыроежек в свадебный бюджет!")

@router.callback_query(F.data.startswith("marry_"))
async def callback_marry(callback: types.CallbackQuery):
    action = callback.data.split("_")[1]
    marriage_id = callback.data.replace(f"marry_{action}_", "")
    parts = marriage_id.split("_")
    chat_id = int(parts[0])
    proposer_id = int(parts[1])
    target_id = int(parts[2])

    if callback.from_user.id != target_id:
        return await callback.answer("Это предложение не для вас!", show_alert=True)

    if marriage_id not in active_marriages:
        return await callback.answer("Предложение больше не действительно.", show_alert=True)

    gift_amount = active_marriages.pop(marriage_id, {}).get('amount', 0)

    if action == "no":
        await callback.message.edit_text("💔 Предложение отклонено. Свадьба отменяется.")
        return

    # Согласие
    proposer_name = "Ваш партнер" # В идеале получить из кэша
    target_name = escape_html(callback.from_user.full_name)

    await update_user_field(chat_id, proposer_id, 'partner', target_id)
    await update_user_field(chat_id, target_id, 'partner', proposer_id)

    text = f"🎉 <b>СВАДЬБА!</b> 🎉\n\nПоздравляем новую пару! 💍"
    if gift_amount > 0:
        half = gift_amount // 2
        await update_user_balance(chat_id, proposer_id, half)
        await update_user_balance(chat_id, target_id, gift_amount - half)
        text += f"\n\nСвадебный банк составил <b>{gift_amount}</b> сыроежек. Деньги разделены поровну между молодоженами!"

    await callback.message.edit_text(text)

@router.message(F.text.lower().in_(["развод", "/divorce"]))
async def cmd_divorce(message: types.Message):
    chat_id = message.chat.id
    user_id = message.from_user.id

    data = await get_user_data(chat_id, user_id)
    partner_id = data.get('partner')
    if not partner_id:
        return await message.answer("Вы не в браке.")

    await update_user_field(chat_id, user_id, 'partner', None)
    await update_user_field(chat_id, partner_id, 'partner', None)

    await message.answer("💔 Вы успешно расторгли брак.")

# ================= РП КОМАНДЫ И КАРМА =================

RP_COMMANDS = {
    "обнять": "🤗 {user} нежно обнял(а) {target}",
    "поцеловать": "💋 {user} поцеловал(а) {target}",
    "ударить": "👊 {user} сильно ударил(а) {target}",
    "кусь": "🧛‍♂️ {user} сделал(а) кусь {target}",
    "погладить": "✋ {user} погладил(а) {target} по голове",
    "укусить": "🧛‍♂️ {user} укусил(а) {target}"
}

karma_triggers_global = ['+', 'спасибо', 'спс', 'rep', 'реп', 'уважение']

@router.message(F.reply_to_message & F.text & (F.text.lower().in_(RP_COMMANDS.keys()) | F.text.lower().in_(karma_triggers_global)))
async def rp_and_karma(message: types.Message):
    text = message.text.lower().strip() if message.text else ""
    user_name = escape_html(message.from_user.full_name)
    target_name = escape_html(message.reply_to_message.from_user.full_name)

    # РП Команды
    if text in RP_COMMANDS:
        if message.from_user.id == message.reply_to_message.from_user.id:
            return await message.answer("Вы не можете применить это к себе.")
        if message.reply_to_message.from_user.is_bot:
            return await message.answer("Боты не чувствуют эмоций 🤖.")

        action_text = RP_COMMANDS[text].format(user=f"<b>{user_name}</b>", target=f"<b>{target_name}</b>")
        return await message.answer(action_text)

    # Карма / Репутация
    if text in karma_triggers_global:
        if message.from_user.id == message.reply_to_message.from_user.id:
            return await message.answer("Нельзя повысить репутацию самому себе.")
        if message.reply_to_message.from_user.is_bot:
            return

        chat_id = message.chat.id
        target_id = message.reply_to_message.from_user.id

        target_data = await get_user_data(chat_id, target_id, target_name)
        new_rep = target_data.get('reputation', 0) + 1
        await update_user_field(chat_id, target_id, 'reputation', new_rep)

        await message.answer(f"📈 Уважение пользователя <b>{target_name}</b> повышено! (Репутация: {new_rep})")

# ================= ДУЭЛИ =================
active_duels = {}

@router.message(F.text & (F.text.lower().startswith("дуэль") | F.text.lower().startswith("/duel")))
async def cmd_duel(message: types.Message):
    if not message.reply_to_message:
        return await message.answer("Ответьте на сообщение человека, чтобы вызвать его на дуэль.")

    chat_id = message.chat.id
    user_id = message.from_user.id
    target_id = message.reply_to_message.from_user.id

    if user_id == target_id or message.reply_to_message.from_user.is_bot:
        return await message.answer("С этим нельзя устроить дуэль.")

    args = message.text.split()
    if len(args) < 2:
        return await message.answer("Укажите ставку: <code>Дуэль 1000</code>")

    try:
        bet = int(args[1])
        if bet <= 0: return
    except ValueError:
        return

    user_data = await get_user_data(chat_id, user_id)
    if user_data.get('balance', 0) < bet:
        return await message.answer("У вас недостаточно средств.")

    duel_id = f"{chat_id}_{user_id}_{target_id}"
    active_duels[duel_id] = {'bet': bet, 'proposer_name': escape_html(message.from_user.full_name)}

    builder = InlineKeyboardBuilder()
    builder.button(text="Принять вызов ⚔️", callback_data=f"duel_accept_{duel_id}")
    builder.button(text="Сбежать 🏃", callback_data=f"duel_decline_{duel_id}")

    await message.answer(
        f"⚔️ <b>Вызов на дуэль!</b>\n\n"
        f"<b>{active_duels[duel_id]['proposer_name']}</b> вызывает <b>{escape_html(message.reply_to_message.from_user.full_name)}</b>!\n"
        f"Ставка: <b>{bet}</b> сыроежек.",
        reply_markup=builder.as_markup()
    )

@router.callback_query(F.data.startswith("duel_"))
async def callback_duel(callback: types.CallbackQuery):
    action = callback.data.split("_")[1]
    duel_id = callback.data.replace(f"duel_{action}_", "")
    parts = duel_id.split("_")
    chat_id = int(parts[0])
    proposer_id = int(parts[1])
    target_id = int(parts[2])

    if callback.from_user.id != target_id:
        return await callback.answer("Вас не вызывали на эту дуэль!", show_alert=True)

    if duel_id not in active_duels:
        return await callback.answer("Дуэль больше не актуальна.", show_alert=True)

    duel_info = active_duels.pop(duel_id)
    bet = duel_info['bet']
    proposer_name = duel_info['proposer_name']
    target_name = escape_html(callback.from_user.full_name)

    if action == "decline":
        return await callback.message.edit_text(f"🏃 <b>{target_name}</b> испугался и отказался от дуэли.")

    # Accept
    user_data = await get_user_data(chat_id, proposer_id)
    target_data = await get_user_data(chat_id, target_id)

    if user_data.get('balance', 0) < bet or target_data.get('balance', 0) < bet:
        return await callback.message.edit_text("❌ Дуэль отменена. У одного из участников недостаточно средств.")

    await update_user_balance(chat_id, proposer_id, -bet)
    await update_user_balance(chat_id, target_id, -bet)

    rand = secrets.SystemRandom()
    p1_roll = rand.randint(1, 100)
    p2_roll = rand.randint(1, 100)

    from economy_utils import get_global_tax
    tax_percent = await get_global_tax()
    pool = bet * 2
    tax_amount = int(pool * (tax_percent / 100.0))
    win_amount = pool - tax_amount

    text = f"⚔️ <b>Дуэль состоялась!</b>\n\n"
    text += f"🎲 <b>{proposer_name}</b> выбросил <b>{p1_roll}</b>\n"
    text += f"🎲 <b>{target_name}</b> выбросил <b>{p2_roll}</b>\n\n"

    if p1_roll > p2_roll:
        await update_user_balance(chat_id, proposer_id, win_amount)
        text += f"🏆 Победил <b>{proposer_name}</b> и забрал <b>{win_amount}</b> сыроежек!\n"
    elif p2_roll > p1_roll:
        await update_user_balance(chat_id, target_id, win_amount)
        text += f"🏆 Победил <b>{target_name}</b> и забрал <b>{win_amount}</b> сыроежек!\n"
    else:
        # Ничья
        await update_user_balance(chat_id, proposer_id, bet)
        await update_user_balance(chat_id, target_id, bet)
        text += f"🤝 Ничья! Ставки возвращены."
        tax_amount = 0

    if tax_amount > 0:
        text += f"<i>(Налог дуэльного клуба: {tax_amount})</i>"

    await callback.message.edit_text(text)


# ================= КЛАНЫ =================
async def get_clan_ref(chat_id: int, clan_name: str):
    db = get_db()
    return db.collection('chats').document(str(chat_id)).collection('clans').document(clan_name)

active_clan_invites = {}

@router.message(Command("clan"))
async def cmd_clan(message: types.Message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    full_name = escape_html(message.from_user.full_name)

    args = message.text.split(maxsplit=2)
    if len(args) < 2:
        return await message.answer(
            "🛡 <b>Кланы:</b>\n"
            "<code>/clan create [Название]</code> — создать (5кк сыроежек)\n"
            "<code>/clan invite [reply]</code> — пригласить\n"
            "<code>/clan kick [reply]</code> — выгнать\n"
            "<code>/clan deposit [сумма]</code> — положить в казну\n"
            "<code>/clan withdraw [сумма]</code> — снять из казны (только лидер)\n"
            "<code>/clan leave</code> — покинуть клан"
        )

    action = args[1].lower()

    data = await get_user_data(chat_id, user_id, full_name)
    clan_name = data.get('clan')

    if action == "create":
        if clan_name:
            return await message.answer("Вы уже состоите в клане.")
        if len(args) < 3:
            return await message.answer("Укажите название: <code>/clan create Название</code>")

        new_clan_name = args[2]
        if data.get('balance', 0) < 5000000:
            return await message.answer("Для создания клана нужно 5.000.000 сыроежек.")

        clan_ref = await get_clan_ref(chat_id, new_clan_name)
        doc = await clan_ref.get()
        if doc.exists:
            return await message.answer("Клан с таким названием уже существует.")

        await update_user_balance(chat_id, user_id, -5000000)
        await clan_ref.set({
            'leader_id': user_id,
            'deputy_ids':[],
            'treasury': 0,
            'members': [user_id]
        })
        await update_user_field(chat_id, user_id, 'clan', new_clan_name)
        await message.answer(f"🛡 Клан <b>{escape_html(new_clan_name)}</b> успешно создан!")

    elif action == "invite":
        if not clan_name: return await message.answer("Вы не состоите в клане.")
        if not message.reply_to_message: return await message.answer("Сделайте реплай на человека.")

        target_id = message.reply_to_message.from_user.id
        if target_id == user_id or message.reply_to_message.from_user.is_bot: return

        clan_ref = await get_clan_ref(chat_id, clan_name)
        doc = await clan_ref.get()
        clan_data = doc.to_dict()

        if user_id != clan_data['leader_id'] and user_id not in clan_data.get('deputy_ids',[]):
            return await message.answer("Приглашать могут только Лидер и Заместители.")

        target_data = await get_user_data(chat_id, target_id)
        if target_data.get('clan'): return await message.answer("Пользователь уже в клане.")

        # --- НОВАЯ СИСТЕМА ИНВАЙТОВ С КНОПКАМИ ---
        invite_id = f"{chat_id}_{clan_name}_{target_id}_{int(time.time())}"
        active_clan_invites[invite_id] = {'target': target_id, 'clan_name': clan_name}

        builder = InlineKeyboardBuilder()
        builder.button(text="Вступить 🛡", callback_data=f"claninv_yes_{invite_id}")
        builder.button(text="Отказаться ❌", callback_data=f"claninv_no_{invite_id}")

        await message.answer(
            f"🛡 <b>Приглашение в клан!</b>\n\n"
            f"Пользователь <b>{escape_html(message.from_user.full_name)}</b> приглашает <b>{escape_html(message.reply_to_message.from_user.full_name)}</b> вступить в ряды клана <b>{escape_html(clan_name)}</b>.\n\n"
            f"Согласны?",
            reply_markup=builder.as_markup()
        )

    elif action == "kick":
        if not clan_name: return
        if not message.reply_to_message: return
        target_id = message.reply_to_message.from_user.id

        clan_ref = await get_clan_ref(chat_id, clan_name)
        doc = await clan_ref.get()
        clan_data = doc.to_dict()

        if user_id != clan_data['leader_id']:
            return await message.answer("Кикать может только Лидер.")

        if target_id == clan_data['leader_id']:
            return await message.answer("Нельзя кикнуть лидера.")

        members = clan_data.get('members',[])
        if target_id in members:
            members.remove(target_id)
            await clan_ref.update({'members': members})
            await update_user_field(chat_id, target_id, 'clan', None)
            await message.answer("Пользователь изгнан из клана.")

    elif action == "leave":
        if not clan_name: return
        clan_ref = await get_clan_ref(chat_id, clan_name)
        doc = await clan_ref.get()
        clan_data = doc.to_dict()

        if user_id == clan_data['leader_id']:
            return await message.answer("Лидер не может просто так покинуть клан. Передайте лидерство (функционал в разработке) или удалите клан.")

        members = clan_data.get('members',[])
        if user_id in members:
            members.remove(user_id)
            await clan_ref.update({'members': members})
            await update_user_field(chat_id, user_id, 'clan', None)
            await message.answer("Вы покинули клан.")

    elif action == "deposit":
        if not clan_name: return
        if len(args) < 3: return await message.answer("Укажите сумму.")
        try: amount = int(args[2])
        except ValueError: return
        if amount <= 0: return

        if data.get('balance', 0) < amount: return await message.answer("Недостаточно средств.")

        await update_user_balance(chat_id, user_id, -amount)
        clan_ref = await get_clan_ref(chat_id, clan_name)
        doc = await clan_ref.get()
        new_treasury = doc.to_dict().get('treasury', 0) + amount
        await clan_ref.update({'treasury': new_treasury})
        await message.answer(f"💰 Вы пожертвовали <b>{amount}</b> в казну клана. Баланс казны: {new_treasury}.")

    elif action == "withdraw":
        if not clan_name: return
        clan_ref = await get_clan_ref(chat_id, clan_name)
        doc = await clan_ref.get()
        clan_data = doc.to_dict()

        if user_id != clan_data['leader_id']: return await message.answer("Снимать может только Лидер.")

        if len(args) < 3: return await message.answer("Укажите сумму.")
        try: amount = int(args[2])
        except ValueError: return
        if amount <= 0: return

        treasury = clan_data.get('treasury', 0)
        if treasury < amount: return await message.answer(f"В казне недостаточно средств (Доступно: {treasury}).")

        from economy_utils import get_global_tax
        tax_percent = await get_global_tax()
        tax_amount = int(amount * (tax_percent / 100.0))
        net_amount = amount - tax_amount

        await update_user_balance(chat_id, user_id, net_amount)
        await clan_ref.update({'treasury': treasury - amount})
        await message.answer(f"💸 Вы сняли <b>{amount}</b> из казны. Удержан налог {tax_amount}. На руки получено: {net_amount}.")

# --- ОБРАБОТЧИК КНОПОК ДЛЯ КЛАНА ---
@router.callback_query(F.data.startswith("claninv_"))
async def callback_claninv(callback: types.CallbackQuery):
    action = callback.data.split("_")[1]
    invite_id = callback.data.replace(f"claninv_{action}_", "")

    if invite_id not in active_clan_invites:
        return await callback.answer("Приглашение больше не действительно.", show_alert=True)

    invite_info = active_clan_invites.pop(invite_id)
    target_id = invite_info['target']
    clan_name = invite_info['clan_name']
    chat_id = callback.message.chat.id

    if callback.from_user.id != target_id:
        active_clan_invites[invite_id] = invite_info # Возвращаем в словарь, т.к. нажал не тот
        return await callback.answer("Это приглашение не для вас!", show_alert=True)

    if action == "no":
        return await callback.message.edit_text("❌ Приглашение в клан отклонено.")

    # Логика согласия
    target_data = await get_user_data(chat_id, target_id)
    if target_data.get('clan'):
        return await callback.message.edit_text("❌ Пользователь уже состоит в другом клане.")

    clan_ref = await get_clan_ref(chat_id, clan_name)
    doc = await clan_ref.get()
    if not doc.exists:
        return await callback.message.edit_text("❌ Этот клан больше не существует.")

    clan_data = doc.to_dict()
    members = clan_data.get('members', [])
    members.append(target_id)
    
    await clan_ref.update({'members': members})
    await update_user_field(chat_id, target_id, 'clan', clan_name)
    await callback.message.edit_text(f"✅ <b>{escape_html(callback.from_user.full_name)}</b> успешно вступил(а) в клан <b>{escape_html(clan_name)}</b>!")