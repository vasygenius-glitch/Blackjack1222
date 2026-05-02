import time
from aiogram import Router, types, F
from aiogram.utils.keyboard import InlineKeyboardBuilder
from escape import escape_html
from user_manager import get_user_data, update_user_balance, update_user_field

router = Router()
active_deals = {}

# 1. ПРОСТОЙ ДОГОВОР (Словесный)
@router.message(F.text.lower().startswith("договор"))
async def cmd_contract(message: types.Message):
    if not message.reply_to_message:
        return await message.answer("Сделай реплай на того, с кем заключаешь договор.")

    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        return await message.answer("Напиши суть договора: договор [текст]")

    text = parts[1]
    deal_id = f"con_{int(time.time() * 1000)}"[-10:]
    
    active_deals[deal_id] = {
        'type': 'contract',
        'text': text,
        'from_id': message.from_user.id,
        'to_id': message.reply_to_message.from_user.id
    }

    builder = InlineKeyboardBuilder()
    builder.button(text="Подписать ✍️", callback_data=f"deal_yes_{deal_id}")
    builder.button(text="Отказаться ❌", callback_data=f"deal_no_{deal_id}")

    await message.answer(
        f"📜 <b>ОФИЦИАЛЬНЫЙ ДОГОВОР</b>\n\n"
        f"Между <b>{escape_html(message.from_user.full_name)}</b> и <b>{escape_html(message.reply_to_message.from_user.full_name)}</b>\n\n"
        f"<b>Суть:</b> {escape_html(text)}\n\n"
        f"Второй стороне нужно подписать документ.",
        reply_markup=builder.as_markup()
    )

# 2. СДЕЛКА (Деньги + Имущество)
@router.message(F.text.lower().startswith("сделка"))
async def cmd_deal(message: types.Message):
    if not message.reply_to_message:
        return await message.answer("Сделай реплай на партнера по сделке.")

    args = message.text.split()
    # формат: сделка [цена] [предмет] [условие/натура]
    if len(args) < 3:
        return await message.answer("Использование: сделка [цена] [предмет] [доп. условия]")

    try:
        price = int(args[1])
        item_name = args[2].lower()
        condition = " ".join(args[3:]) if len(args) > 3 else "Нет"
    except: return

    chat_id = message.chat.id
    seller_id = message.from_user.id
    buyer_id = message.reply_to_message.from_user.id

    # Проверка наличия предмета у продавца
    seller_data = await get_user_data(chat_id, seller_id)
    if item_name not in seller_data.get('inventory', {}):
        return await message.answer(f"У тебя нет предмета '{item_name}' в инвентаре.")

    deal_id = f"sell_{int(time.time() * 1000)}"[-10:]
    active_deals[deal_id] = {
        'type': 'trade',
        'price': price,
        'item': item_name,
        'condition': condition,
        'from_id': seller_id,
        'to_id': buyer_id
    }

    builder = InlineKeyboardBuilder()
    builder.button(text="Принять сделку ✅", callback_data=f"deal_yes_{deal_id}")
    builder.button(text="Отмена ❌", callback_data=f"deal_no_{deal_id}")

    await message.answer(
        f"🤝 <b>КУПЛЯ-ПРОДАЖА</b>\n\n"
        f"Продавец: <b>{escape_html(message.from_user.full_name)}</b>\n"
        f"Покупатель: <b>{escape_html(message.reply_to_message.from_user.full_name)}</b>\n\n"
        f"📦 Предмет: <b>{item_name}</b>\n"
        f"💰 Цена: <b>{price}</b> сыр.\n"
        f"📝 Доп. условия: {escape_html(condition)}\n\n"
        f"Покупатель, ты согласен?",
        reply_markup=builder.as_markup()
    )

# 3. НАСЛЕДСТВО
@router.message(F.text.lower().startswith("наследство"))
async def cmd_will(message: types.Message):
    if not message.reply_to_message:
        return await message.answer("Сделай реплай на того, кому передаешь всё имущество.")

    deal_id = f"will_{int(time.time() * 1000)}"[-10:]
    active_deals[deal_id] = {
        'type': 'inheritance',
        'from_id': message.from_user.id,
        'to_id': message.reply_to_message.from_user.id
    }

    builder = InlineKeyboardBuilder()
    builder.button(text="Принять всё 🏰", callback_data=f"deal_yes_{deal_id}")
    builder.button(text="Отказаться 🚫", callback_data=f"deal_no_{deal_id}")

    await message.answer(
        f"⚰️ <b>ПЕРЕДАЧА НАСЛЕДСТВА</b>\n\n"
        f"<b>{escape_html(message.from_user.full_name)}</b> хочет передать ВСЁ своё имущество (деньги, банк, инвентарь) пользователю <b>{escape_html(message.reply_to_message.from_user.full_name)}</b>.\n\n"
        f"Это действие нельзя отменить. Ты принимаешь дар?",
        reply_markup=builder.as_markup()
    )

@router.callback_query(F.data.startswith("deal_yes_") | F.data.startswith("deal_no_"))
async def process_all_deals(callback: types.CallbackQuery):
    action = callback.data.split("_")[1]
    deal_id = callback.data.split("_")[2]

    if deal_id not in active_deals:
        return await callback.answer("Сделка просрочена.", show_alert=True)

    info = active_deals.pop(deal_id)
    chat_id = callback.message.chat.id

    if callback.from_user.id != info['to_id']:
        return await callback.answer("Эта кнопка не для тебя!", show_alert=True)

    if action == "no":
        return await callback.message.edit_text("❌ Сделка отклонена второй стороной.")

    # ЛОГИКА ПОДТВЕРЖДЕНИЯ
    if info['type'] == 'contract':
        await callback.message.edit_text(f"✅ <b>Договор подписан обеими сторонами!</b>\n\nСуть: {info['text']}")

    elif info['type'] == 'trade':
        buyer_id = info['to_id']
        seller_id = info['from_id']
        price = info['price']
        item = info['item']

        buyer_data = await get_user_data(chat_id, buyer_id)
        if buyer_data.get('balance', 0) < price:
            return await callback.message.edit_text("❌ У покупателя не хватило денег!")

        # Передача денег
        await update_user_balance(chat_id, buyer_id, -price)
        await update_user_balance(chat_id, seller_id, price)

        # Передача предмета
        from user_manager import remove_item_from_inventory, add_item_to_inventory
        if await remove_item_from_inventory(chat_id, seller_id, item):
            await add_item_to_inventory(chat_id, buyer_id, item)
            await callback.message.edit_text(f"✅ <b>Сделка завершена!</b>\nПредмет <b>{item}</b> перешел к новому владельцу за <b>{price}</b> сыр.")
        else:
            await callback.message.edit_text("❌ Произошла ошибка: предмет исчез у продавца.")

    elif info['type'] == 'inheritance':
        sender_id = info['from_id']
        target_id = info['to_id']

        s_data = await get_user_data(chat_id, sender_id)
        
        # Перенос балансов
        total_cash = s_data.get('balance', 0)
        total_bank = s_data.get('bank_deposit', 0)
        
        await update_user_balance(chat_id, target_id, total_cash)
        await update_user_field(chat_id, target_id, 'bank_deposit', (await get_user_data(chat_id, target_id)).get('bank_deposit', 0) + total_bank)
        
        # Перенос инвентаря
        inv = s_data.get('inventory', {})
        target_data = await get_user_data(chat_id, target_id)
        target_inv = target_data.get('inventory', {})
        
        for item, count in inv.items():
            target_inv[item] = target_inv.get(item, 0) + count
            
        await update_user_field(chat_id, target_id, 'inventory', target_inv)
        
        # Обнуление отправителя
        await update_user_field(chat_id, sender_id, 'balance', 0)
        await update_user_field(chat_id, sender_id, 'bank_deposit', 0)
        await update_user_field(chat_id, sender_id, 'inventory', {})

        await callback.message.edit_text(f"🏰 <b>Наследство принято!</b>\nВсе активы перешли к новому владельцу. Бывший владелец теперь нищий.")