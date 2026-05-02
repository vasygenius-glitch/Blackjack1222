import time
from aiogram import Router, types, F, Bot
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from db import get_db
from escape import escape_html
from user_manager import get_user_data, update_user_balance, update_user_field, get_all_users_in_chat
from shop import ITEMS

router = Router()

@router.message(Command("profile"))
async def cmd_profile(message: types.Message):
    chat_id = message.chat.id
    # Определяем, чей профиль смотрим (свой или чужой через реплай)
    if message.reply_to_message:
        target_id = message.reply_to_message.from_user.id
        target_name = escape_html(message.reply_to_message.from_user.full_name)
    else:
        target_id = message.from_user.id
        target_name = escape_html(message.from_user.full_name)

    data = await get_user_data(chat_id, target_id, target_name)

    vip_status = "💎 VIP" if data.get('is_vip') else "Обычный"
    balance = data.get('balance', 0)
    rep = data.get('reputation', 0)
    clan = escape_html(data.get('clan', 'Нет'))
    warns = len(data.get('warns', []))
    
    # Счётчик эскорта
    escort_count = data.get('escort_count', 0)
    escort_text = f"\n🔞 Выебан(а): {escort_count} раз" if escort_count > 0 else ""

    # --- НОВАЯ ЛОГИКА ДОЛГОВ (ПЕРЕД ИГРОКАМИ) ---
    debts = data.get('debts', {})
    debt_display = ""
    if debts:
        debt_list = []
        for lender_id_str, amount in debts.items():
            if amount > 0:
                # Получаем данные кредитора, чтобы узнать его имя
                lender_data = await get_user_data(chat_id, int(lender_id_str))
                lender_name = escape_html(lender_data.get('full_name', f"Юзер {lender_id_str}"))
                debt_list.append(f"<b>{lender_name}</b> ({amount} сыр.)")
        
        if debt_list:
            debt_display = f"\n💸 <b>Брал(а) в долг у:</b> {', '.join(debt_list)}"
    # --------------------------------------------

    # Брак
    partner_id = data.get('partner')
    partner_text = "Нет"
    if partner_id:
        p_data = await get_user_data(chat_id, partner_id)
        partner_text = escape_html(p_data.get('full_name', f"ID: {partner_id}"))

    # Имущество
    inventory = data.get('inventory', {})
    cars = sum(v for k, v in inventory.items() if ITEMS.get(k, {}).get('cat') == 'cars')
    biz = sum(v for k, v in inventory.items() if ITEMS.get(k, {}).get('cat') == 'biz')

    bank_deposit = data.get('bank_deposit', 0)

    # Статистика сообщений (из отдельной коллекции)
    db = get_db()
    stats_doc = await db.collection('chats').document(str(chat_id)).collection('stats').document(str(target_id)).get()
    msg_count = stats_doc.to_dict().get('all_time', 0) if stats_doc.exists else 0

    bio = escape_html(data.get('bio', 'Нет описания.'))

    text = (
        f"👤 <b>Профиль: {target_name}</b>\n"
        f"<i>{bio}</i>\n\n"
        f"Статус: {vip_status}\n"
        f"Репутация: {rep} 📈\n"
        f"Предупреждения: {warns}/3 ⚠️{escort_text}\n"
        f"{debt_display}\n" # Список реальных долгов перед людьми
        f"💰 Баланс: <b>{balance}</b> сыр.\n"
        f"🏦 В банке: <b>{bank_deposit}</b> сыр.\n\n"
        f"🛡 Клан: {clan}\n"
        f"💍 Брак: {partner_text}\n\n"
        f"🚗 Машин: {cars}\n"
        f"🏢 Бизнесов: {biz}\n\n"
        f"💬 Сообщений в чате: {msg_count}"
    )

    await message.answer(text)

@router.message(Command("bank"))
async def cmd_bank(message: types.Message):
    chat_id = message.chat.id
    user_id = message.from_user.id

    args = message.text.split()
    if len(args) < 2:
        return await message.answer(
            "🏦 <b>Банк Сыроежек</b>\n\n"
            "Минимальный вклад: 10.000.000\n"
            "Команды:\n"
            "<code>/bank deposit [сумма]</code>\n"
            "<code>/bank withdraw [сумма]</code>"
        )

    action = args[1].lower()
    if len(args) < 3: return await message.answer("Укажите сумму.")

    try:
        amount = int(args[2])
        if amount <= 0: return
    except: return

    data = await get_user_data(chat_id, user_id)
    current_deposit = data.get('bank_deposit', 0)

    if action == "deposit":
        if amount < 10000000 and current_deposit == 0:
            return await message.answer("Минимальный первоначальный вклад: 10.000.000 сыроежек.")
        if data.get('balance', 0) < amount:
            return await message.answer("Недостаточно средств на балансе.")

        await update_user_balance(chat_id, user_id, -amount)
        await update_user_field(chat_id, user_id, 'bank_deposit', current_deposit + amount)
        await message.answer(f"✅ Депозит пополнен на {amount} сыр. Всего: {current_deposit + amount}.")

    elif action == "withdraw":
        if current_deposit < amount:
            return await message.answer(f"В банке только {current_deposit} сыроежек.")

        await update_user_field(chat_id, user_id, 'bank_deposit', current_deposit - amount)
        await update_user_balance(chat_id, user_id, amount)
        await message.answer(f"💸 Снято {amount} сыроежек со счета.")

@router.message(Command("bank_stats"))
async def cmd_bank_stats(message: types.Message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    data = await get_user_data(chat_id, user_id)
    if not data.get('is_banker'):
        return await message.answer("❌ Эта команда доступна только банкирам.")

    docs = await get_all_users_in_chat(chat_id)
    depositors = []
    debtors = []
    str_uid = str(user_id)

    for doc in docs:
        udata = doc.to_dict()
        uid = doc.id
        if udata.get('bank_deposit', 0) > 0:
            depositors.append({'id': uid, 'name': escape_html(udata.get('full_name', f'ID {uid}')), 'amount': udata.get('bank_deposit'), 'vip': udata.get('bank_vip', False)})
        if str_uid in udata.get('debts', {}):
            debtors.append({'id': uid, 'name': escape_html(udata.get('full_name', f'ID {uid}')), 'amount': udata.get('debts')[str_uid]})

    depositors.sort(key=lambda x: x['amount'], reverse=True)
    debtors.sort(key=lambda x: x['amount'], reverse=True)

    text = "📊 <b>Панель Банкира</b>\n\n"
    text += "🏆 <b>Топ-5 вкладчиков:</b>\n"
    if not depositors:
        text += "Нет вкладчиков.\n"
    for i, d in enumerate(depositors[:5], 1):
        vip_star = "⭐ " if d['vip'] else ""
        text += f"{i}. {vip_star}{d['name']} — <b>{d['amount']}</b> сыр.\n"

    text += "\n💸 <b>Топ-5 должников:</b>\n"
    if not debtors:
        text += "Нет должников.\n"
    for i, d in enumerate(debtors[:5], 1):
        text += f"{i}. {d['name']} — Долг: <b>{d['amount']}</b> сыр.\n"

    builder = InlineKeyboardBuilder()
    builder.button(text="🛡 Купить охрану (10кк)", callback_data="bank_buy_sec")
    builder.button(text="💸 Управление долгами", callback_data="bank_manage_debts")
    builder.button(text="⭐ Управление VIP", callback_data="bank_manage_vip")
    builder.adjust(1)

    await message.answer(text, reply_markup=builder.as_markup())

@router.callback_query(F.data == "bank_buy_sec")
async def cb_bank_buy_sec(callback: types.CallbackQuery):
    chat_id = callback.message.chat.id
    user_id = callback.from_user.id
    data = await get_user_data(chat_id, user_id)

    if not data.get('is_banker'):
        return await callback.answer("❌ Только банкиры могут покупать банковскую охрану.", show_alert=True)

    if data.get('bank_security'):
        return await callback.answer("У вас уже есть лицензия на вооруженную охрану.", show_alert=True)

    price = 10000000
    if data.get('balance', 0) < price:
        return await callback.answer(f"❌ Недостаточно средств. Лицензия стоит {price} сыр.", show_alert=True)

    await update_user_balance(chat_id, user_id, -price)
    await update_user_field(chat_id, user_id, 'bank_security', True)
    await callback.message.edit_text("🛡 Вы успешно приобрели <b>Лицензию на вооруженную охрану</b>. Теперь шанс успешного ограбления вашего банка снижен!")

@router.callback_query(F.data == "bank_manage_debts")
async def cb_bank_manage_debts(callback: types.CallbackQuery):
    chat_id = callback.message.chat.id
    user_id = callback.from_user.id
    data = await get_user_data(chat_id, user_id)
    if not data.get('is_banker'):
        return await callback.answer("❌ Только для банкиров.", show_alert=True)

    docs = await get_all_users_in_chat(chat_id)
    debtors = []
    str_uid = str(user_id)

    for doc in docs:
        udata = doc.to_dict()
        uid = doc.id
        if str_uid in udata.get('debts', {}):
            debtors.append({'id': uid, 'name': udata.get('full_name', f'ID {uid}'), 'amount': udata.get('debts')[str_uid]})

    if not debtors:
        return await callback.answer("У вас нет должников.", show_alert=True)

    builder = InlineKeyboardBuilder()
    for d in debtors[:10]:
        builder.button(text=f"{d['name']} ({d['amount']})", callback_data=f"bank_debtor_{d['id']}")
    builder.button(text="🔙 Назад", callback_data="bank_panel_back")
    builder.adjust(1)

    await callback.message.edit_text("💸 <b>Выберите должника для управления:</b>", reply_markup=builder.as_markup())

@router.callback_query(F.data.startswith("bank_debtor_"))
async def cb_bank_debtor(callback: types.CallbackQuery):
    target_id = callback.data.split("_")[2]
    chat_id = callback.message.chat.id
    user_id = callback.from_user.id
    data = await get_user_data(chat_id, user_id)
    if not data.get('is_banker'): return await callback.answer()

    target_data = await get_user_data(chat_id, target_id)
    str_uid = str(user_id)
    debts = target_data.get('debts', {})

    if str_uid not in debts:
        return await callback.answer("Долг уже погашен или прощен.", show_alert=True)

    amount = debts[str_uid]
    name = escape_html(target_data.get('full_name', f'ID {target_id}'))

    builder = InlineKeyboardBuilder()
    builder.button(text="Простить долг", callback_data=f"bank_forgive_{target_id}")
    builder.button(text="Снизить долг на 10% (Рефинанс)", callback_data=f"bank_refinance_{target_id}")
    builder.button(text="🔙 Назад", callback_data="bank_manage_debts")
    builder.adjust(1)

    await callback.message.edit_text(f"Управление долгом: <b>{name}</b>\nТекущий долг: <b>{amount}</b>", reply_markup=builder.as_markup())

@router.callback_query(F.data.startswith("bank_forgive_"))
async def cb_bank_forgive(callback: types.CallbackQuery):
    target_id = callback.data.split("_")[2]
    chat_id = callback.message.chat.id
    user_id = callback.from_user.id
    data = await get_user_data(chat_id, user_id)
    if not data.get('is_banker'): return await callback.answer()

    target_data = await get_user_data(chat_id, target_id)
    debts = target_data.get('debts', {})
    str_uid = str(user_id)

    if str_uid in debts:
        del debts[str_uid]
        await update_user_field(chat_id, target_id, 'debts', debts)
        await callback.answer("Долг прощен!", show_alert=True)
        await cb_bank_manage_debts(callback)
    else:
        await callback.answer("Долга нет.", show_alert=True)

@router.callback_query(F.data.startswith("bank_refinance_"))
async def cb_bank_refinance(callback: types.CallbackQuery):
    target_id = callback.data.split("_")[2]
    chat_id = callback.message.chat.id
    user_id = callback.from_user.id
    data = await get_user_data(chat_id, user_id)
    if not data.get('is_banker'): return await callback.answer()

    target_data = await get_user_data(chat_id, target_id)
    debts = target_data.get('debts', {})
    str_uid = str(user_id)

    if str_uid in debts:
        new_amount = int(debts[str_uid] * 0.9)
        if new_amount <= 0:
            del debts[str_uid]
        else:
            debts[str_uid] = new_amount
        await update_user_field(chat_id, target_id, 'debts', debts)
        await callback.answer(f"Долг снижен! Новая сумма: {new_amount}", show_alert=True)
        # Manually construct the panel instead of modifying the pydantic model `callback.data`
        name = escape_html(target_data.get('full_name', f'ID {target_id}'))
        builder = InlineKeyboardBuilder()
        builder.button(text="Простить долг", callback_data=f"bank_forgive_{target_id}")
        builder.button(text="Снизить долг на 10% (Рефинанс)", callback_data=f"bank_refinance_{target_id}")
        builder.button(text="🔙 Назад", callback_data="bank_manage_debts")
        builder.adjust(1)
        await callback.message.edit_text(f"Управление долгом: <b>{name}</b>\nТекущий долг: <b>{new_amount}</b>", reply_markup=builder.as_markup())
    else:
        await callback.answer("Долга нет.", show_alert=True)

@router.callback_query(F.data == "bank_manage_vip")
async def cb_bank_manage_vip(callback: types.CallbackQuery):
    chat_id = callback.message.chat.id
    user_id = callback.from_user.id
    data = await get_user_data(chat_id, user_id)
    if not data.get('is_banker'):
        return await callback.answer("❌ Только для банкиров.", show_alert=True)

    docs = await get_all_users_in_chat(chat_id)
    depositors = []

    for doc in docs:
        udata = doc.to_dict()
        uid = doc.id
        if udata.get('bank_deposit', 0) > 0:
            depositors.append({'id': uid, 'name': udata.get('full_name', f'ID {uid}'), 'amount': udata.get('bank_deposit'), 'vip': udata.get('bank_vip', False)})

    if not depositors:
        return await callback.answer("У вас нет вкладчиков.", show_alert=True)

    depositors.sort(key=lambda x: x['amount'], reverse=True)

    builder = InlineKeyboardBuilder()
    for d in depositors[:10]:
        star = "⭐ " if d['vip'] else ""
        builder.button(text=f"{star}{d['name']} ({d['amount']})", callback_data=f"bank_toggle_vip_{d['id']}")
    builder.button(text="🔙 Назад", callback_data="bank_panel_back")
    builder.adjust(1)

    await callback.message.edit_text("⭐ <b>Нажмите на вкладчика, чтобы выдать/забрать VIP:</b>", reply_markup=builder.as_markup())

@router.callback_query(F.data.startswith("bank_toggle_vip_"))
async def cb_bank_toggle_vip(callback: types.CallbackQuery):
    target_id = callback.data.split("_")[3]
    chat_id = callback.message.chat.id
    user_id = callback.from_user.id
    data = await get_user_data(chat_id, user_id)
    if not data.get('is_banker'): return await callback.answer()

    target_data = await get_user_data(chat_id, target_id)
    current_status = target_data.get('bank_vip', False)
    new_status = not current_status
    await update_user_field(chat_id, target_id, 'bank_vip', new_status)

    status_text = "выдан" if new_status else "забран"
    await callback.answer(f"VIP статус {status_text}!", show_alert=True)
    await cb_bank_manage_vip(callback)

@router.callback_query(F.data == "bank_panel_back")
async def cb_bank_panel_back(callback: types.CallbackQuery):
    chat_id = callback.message.chat.id
    user_id = callback.from_user.id
    data = await get_user_data(chat_id, user_id)
    if not data.get('is_banker'): return await callback.answer()

    docs = await get_all_users_in_chat(chat_id)
    depositors = []
    debtors = []
    str_uid = str(user_id)

    for doc in docs:
        udata = doc.to_dict()
        uid = doc.id
        if udata.get('bank_deposit', 0) > 0:
            depositors.append({'id': uid, 'name': escape_html(udata.get('full_name', f'ID {uid}')), 'amount': udata.get('bank_deposit'), 'vip': udata.get('bank_vip', False)})
        if str_uid in udata.get('debts', {}):
            debtors.append({'id': uid, 'name': escape_html(udata.get('full_name', f'ID {uid}')), 'amount': udata.get('debts')[str_uid]})

    depositors.sort(key=lambda x: x['amount'], reverse=True)
    debtors.sort(key=lambda x: x['amount'], reverse=True)

    text = "📊 <b>Панель Банкира</b>\n\n"
    text += "🏆 <b>Топ-5 вкладчиков:</b>\n"
    if not depositors:
        text += "Нет вкладчиков.\n"
    for i, d in enumerate(depositors[:5], 1):
        vip_star = "⭐ " if d['vip'] else ""
        text += f"{i}. {vip_star}{d['name']} — <b>{d['amount']}</b> сыр.\n"

    text += "\n💸 <b>Топ-5 должников:</b>\n"
    if not debtors:
        text += "Нет должников.\n"
    for i, d in enumerate(debtors[:5], 1):
        text += f"{i}. {d['name']} — Долг: <b>{d['amount']}</b> сыр.\n"

    builder = InlineKeyboardBuilder()
    builder.button(text="🛡 Купить охрану (10кк)", callback_data="bank_buy_sec")
    builder.button(text="💸 Управление долгами", callback_data="bank_manage_debts")
    builder.button(text="⭐ Управление VIP", callback_data="bank_manage_vip")
    builder.adjust(1)

    await callback.message.edit_text(text, reply_markup=builder.as_markup())
