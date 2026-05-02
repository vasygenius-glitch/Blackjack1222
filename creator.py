from aiogram import Router, types, Bot, F
from aiogram.filters import Command

from db import get_db
from user_manager import get_user_data, update_user_balance
from config import CREATOR_USERNAME
from escape import escape_html

router = Router()

def is_creator(message: types.Message):
    from config import CREATOR_ID, CREATOR_USERNAME
    if message.from_user.username == CREATOR_USERNAME:
        return True
    if CREATOR_ID and int(message.from_user.id) == int(CREATOR_ID):
        return True
    return False

# ================= БАНКИРЫ И СОФТ-ВАЙП =================

@router.message(Command("setbanker"))
async def cmd_setbanker(message: types.Message):
    if not is_creator(message):
        return
    if not message.reply_to_message:
        return await message.answer("Ответьте на сообщение будущего Банкира.")

    chat_id = message.chat.id
    target_id = message.reply_to_message.from_user.id
    target_name = escape_html(message.reply_to_message.from_user.full_name)

    from user_manager import update_user_field
    await get_user_data(chat_id, target_id, target_name)
    await update_user_field(chat_id, target_id, 'is_banker', True)
    
    await message.answer(f"💼 Пользователь <b>{target_name}</b> назначен официальным <b>Банкиром</b>!\nТеперь у него нет доступа к казино и работам, но он получает 50.000.000 в день и может кредитовать игроков.")

@router.message(Command("delbanker"))
async def cmd_delbanker(message: types.Message):
    if not is_creator(message):
        return
    if not message.reply_to_message:
        return await message.answer("Ответьте на сообщение Банкира.")

    chat_id = message.chat.id
    target_id = message.reply_to_message.from_user.id
    target_name = escape_html(message.reply_to_message.from_user.full_name)

    from user_manager import update_user_field
    await get_user_data(chat_id, target_id, target_name)
    await update_user_field(chat_id, target_id, 'is_banker', False)
    
    await message.answer(f"❌ Пользователь <b>{target_name}</b> снят с должности Банкира и возвращен к обычной жизни.")

@router.message(Command("wipe_balances"))
async def cmd_wipe_balances(message: types.Message):
    if not is_creator(message):
        return await message.answer("❌ Отказано в доступе. Только Создатель.")

    args = message.text.split()
    if len(args) < 2 or args[1] != "CONFIRM":
        return await message.answer(
            "⚠️ <b>ВНИМАНИЕ! СОФТ-ВАЙП ЭКОНОМИКИ (ТОЛЬКО ДЕНЬГИ)!</b> ⚠️\n\n"
            "Это действие обнулит ТОЛЬКО балансы и вклады всех игроков до 500 сыроежек.\n"
            "💼 <b>Сохранятся:</b> Машины, бизнесы, питомцы, крипта, кланы, скиллы и долги.\n\n"
            "Если вы УВЕРЕНЫ, введите команду:\n"
            "<code>/wipe_balances CONFIRM</code>"
        )

    status_msg = await message.answer("🔄 <i>Начинаю сброс балансов...</i>")

    import time
    from user_manager import _user_cache
    db = get_db()
    _user_cache.clear() # Очищаем кэш

    from whitelist import get_whitelist
    whitelist_dict = await get_whitelist()
    users_wiped = 0

    for chat_id in whitelist_dict.keys():
        try:
            users_ref = db.collection('chats').document(str(chat_id)).collection('users')
            user_docs = await users_ref.get()
            
            for doc in user_docs:
                doc_id = getattr(doc, 'id', None)
                if doc_id:
                    # Обнуляем только деньги
                    await users_ref.document(doc_id).set({
                        'balance': 500,
                        'bank_deposit': 0
                    }, merge=True)
                    users_wiped += 1
                
        except Exception as e:
            print(f"Ошибка при софт-вайпе чата {chat_id}: {e}")

    await status_msg.edit_text(f"✅ <b>БАЛАНСЫ УСПЕШНО СБРОШЕНЫ!</b>\n\n👤 Обнулено денег у игроков: <b>{users_wiped}</b>.\nИмущество и инвентари сохранены.")

# ================= СТАРЫЕ КОМАНДЫ СОЗДАТЕЛЯ =================

@router.message(Command("addmoney", "give"))
async def cmd_addmoney(message: types.Message):
    if not is_creator(message):
        return

    if not message.reply_to_message:
        await message.answer("Ответьте на сообщение пользователя.")
        return

    args = message.text.split()
    if len(args) < 2:
        await message.answer("Укажите сумму.")
        return

    try:
        amount = int(args[1])
        chat_id = message.chat.id
        target_id = message.reply_to_message.from_user.id
        target_name = escape_html(message.reply_to_message.from_user.full_name)

        await get_user_data(chat_id, target_id, target_name)
        await update_user_balance(chat_id, target_id, amount)
        await message.answer(f"Выдано {amount} сыроежек пользователю {target_name}.")
    except ValueError:
        pass

@router.message(Command("setmoney"))
async def cmd_setmoney(message: types.Message):
    if not is_creator(message):
        return

    if not message.reply_to_message:
        await message.answer("Ответьте на сообщение пользователя.")
        return

    args = message.text.split()
    if len(args) < 2:
        await message.answer("Укажите сумму.")
        return

    try:
        amount = int(args[1])
        chat_id = message.chat.id
        target_id = message.reply_to_message.from_user.id
        target_name = escape_html(message.reply_to_message.from_user.full_name)

        from user_manager import update_user_field
        await get_user_data(chat_id, target_id, target_name)
        await update_user_field(chat_id, target_id, 'balance', amount)
        await message.answer(f"Баланс пользователя {target_name} установлен в {amount} сыроежек.")
    except ValueError:
        pass

@router.message(Command("ban"))
async def cmd_ban(message: types.Message):
    if not is_creator(message):
        return

    if not message.reply_to_message:
        await message.answer("Ответьте на сообщение пользователя.")
        return

    chat_id = message.chat.id
    target_id = message.reply_to_message.from_user.id
    target_name = escape_html(message.reply_to_message.from_user.full_name)
    from user_manager import update_user_field
    await get_user_data(chat_id, target_id, target_name)
    await update_user_field(chat_id, target_id, 'is_banned', True)
    await message.answer(f"Пользователь забанен в боте.")

@router.message(Command("unban"))
async def cmd_unban(message: types.Message):
    if not is_creator(message):
        return

    if not message.reply_to_message:
        await message.answer("Ответьте на сообщение пользователя.")
        return

    chat_id = message.chat.id
    target_id = message.reply_to_message.from_user.id
    target_name = escape_html(message.reply_to_message.from_user.full_name)
    from user_manager import update_user_field
    await get_user_data(chat_id, target_id, target_name)
    await update_user_field(chat_id, target_id, 'is_banned', False)
    await message.answer(f"Пользователь разбанен в боте.")

@router.message(Command("hide"))
async def cmd_hide(message: types.Message):
    if not is_creator(message):
        return

    chat_id = message.chat.id
    user_id = message.from_user.id
    user_name = escape_html(message.from_user.full_name)
    from user_manager import update_user_field
    await get_user_data(chat_id, user_id, user_name)
    await update_user_field(chat_id, user_id, 'hide_in_top', True)
    await message.answer("Вы скрыты из топа.")

@router.message(Command("show"))
async def cmd_show(message: types.Message):
    if not is_creator(message):
        return

    chat_id = message.chat.id
    user_id = message.from_user.id
    user_name = escape_html(message.from_user.full_name)
    from user_manager import update_user_field
    await get_user_data(chat_id, user_id, user_name)
    await update_user_field(chat_id, user_id, 'hide_in_top', False)
    await message.answer("Вы теперь отображаетесь в топе.")

@router.message(Command("setvip"))
async def cmd_setvip(message: types.Message):
    if not is_creator(message):
        return

    if not message.reply_to_message:
        await message.answer("Ответьте на сообщение пользователя.")
        return

    chat_id = message.chat.id
    target_id = message.reply_to_message.from_user.id
    target_name = escape_html(message.reply_to_message.from_user.full_name)

    from user_manager import update_user_field
    await get_user_data(chat_id, target_id, target_name)
    await update_user_field(chat_id, target_id, 'is_vip', True)
    await message.answer(f"Пользователь {target_name} получил статус 👑 VIP!")

@router.message(Command("delvip"))
async def cmd_delvip(message: types.Message):
    if not is_creator(message):
        return

    if not message.reply_to_message:
        await message.answer("Ответьте на сообщение пользователя.")
        return

    chat_id = message.chat.id
    target_id = message.reply_to_message.from_user.id
    target_name = escape_html(message.reply_to_message.from_user.full_name)

    from user_manager import update_user_field
    await get_user_data(chat_id, target_id, target_name)
    await update_user_field(chat_id, target_id, 'is_vip', False)
    await message.answer(f"Пользователь {target_name} лишен статуса VIP.")

from whitelist import add_to_whitelist, remove_from_whitelist, get_whitelist
from spy import toggle_spy

@router.message(Command("say"))
async def cmd_say(message: types.Message, bot: Bot):
    if not is_creator(message):
        return

    parts = message.text.split(maxsplit=2)
    if len(parts) < 3:
        await message.answer("Использование: <code>/say <id_группы> <сообщение></code>")
        return

    try:
        chat_id = int(parts[1])
        text_to_say = parts[2]

        await bot.send_message(chat_id=chat_id, text=text_to_say, parse_mode=None)
        await message.answer(f"✅ Сообщение отправлено в группу <code>{chat_id}</code>")
    except ValueError:
        await message.answer("ID группы должен быть числом.")
    except Exception as e:
        await message.answer(f"❌ Ошибка отправки: {e}")

@router.message(Command("rdel"))
async def cmd_rdel(message: types.Message, bot: Bot):
    if not is_creator(message):
        return

    parts = message.text.split()
    if len(parts) < 3:
        await message.answer("Использование: <code>/rdel <id_группы> <id_сообщения></code>")
        return

    try:
        chat_id = int(parts[1])
        msg_id = int(parts[2])

        await bot.delete_message(chat_id=chat_id, message_id=msg_id)
        await message.answer(f"✅ Сообщение {msg_id} удалено из группы {chat_id}.")
    except ValueError:
        await message.answer("ID группы и сообщения должны быть числами.")
    except Exception as e:
        await message.answer(f"❌ Ошибка удаления: {e}\n(Возможно у меня нет прав админа в той группе или сообщение слишком старое)")

@router.message(Command("rban"))
async def cmd_rban(message: types.Message, bot: Bot):
    if not is_creator(message):
        return

    parts = message.text.split()
    if len(parts) < 3:
        await message.answer("Использование: <code>/rban <id_группы> <id_пользователя></code>")
        return

    try:
        chat_id = int(parts[1])
        user_id = int(parts[2])

        await bot.ban_chat_member(chat_id=chat_id, user_id=user_id)
        await message.answer(f"✅ Пользователь {user_id} забанен в группе {chat_id}.")
    except ValueError:
        await message.answer("ID должны быть числами.")
    except Exception as e:
        await message.answer(f"❌ Ошибка бана: {e}\n(Нет прав админа или пользователя нет в чате)")

@router.message(Command("runban"))
async def cmd_runban(message: types.Message, bot: Bot):
    if not is_creator(message):
        return

    parts = message.text.split()
    if len(parts) < 3:
        await message.answer("Использование: <code>/runban <id_группы> <id_пользователя></code>")
        return

    try:
        chat_id = int(parts[1])
        user_id = int(parts[2])

        await bot.unban_chat_member(chat_id=chat_id, user_id=user_id)
        await message.answer(f"✅ Пользователь {user_id} разбанен в группе {chat_id}.")
    except ValueError:
        await message.answer("ID должны быть числами.")
    except Exception as e:
        await message.answer(f"❌ Ошибка разбана: {e}")

@router.message(Command("getlink"))
async def cmd_getlink(message: types.Message, bot: Bot):
    if not is_creator(message):
        return

    parts = message.text.split()
    if len(parts) < 2:
        await message.answer("Использование: <code>/getlink <id_группы></code>")
        return

    try:
        chat_id = int(parts[1])
        link = await bot.export_chat_invite_link(chat_id=chat_id)
        await message.answer(f"🔗 Ссылка на группу <code>{chat_id}</code>:\n{link}")
    except ValueError:
        await message.answer("ID группы должен быть числом.")
    except Exception as e:
        await message.answer(f"❌ Ошибка получения ссылки: {e}\n(Нужны права админа)")

@router.message(Command("spy"))
async def cmd_spy(message: types.Message):
    if not is_creator(message):
        return

    args = message.text.split()
    if len(args) < 2:
        await message.answer("Укажите ID группы. Пример: <code>/spy -100123456789</code>")
        return

    try:
        chat_id = int(args[1])
        is_enabled = await toggle_spy(chat_id)
        if is_enabled:
            await message.answer(f"👁 Режим шпионажа для группы <code>{chat_id}</code> ВКЛЮЧЕН.\nТеперь вы будете получать все их сообщения.")
        else:
            await message.answer(f"🙈 Режим шпионажа для группы <code>{chat_id}</code> ВЫКЛЮЧЕН.")
    except ValueError:
        await message.answer("ID группы должен быть числом.")

@router.message(Command("allow"))
async def cmd_allow(message: types.Message, bot: Bot):
    if not is_creator(message):
        return

    args = message.text.split(maxsplit=2)
    if len(args) < 2:
        await message.answer("Укажите ID группы. Пример: <code>/allow -100123456789 Название</code>")
        return

    try:
        chat_id = int(args[1])
        title = args[2] if len(args) > 2 else "Unknown Group"

        try:
            chat = await bot.get_chat(chat_id)
            title = chat.title or title
        except:
            pass

        success = await add_to_whitelist(chat_id, title)
        if success:
            await message.answer(f"✅ Группа <b>{title}</b> (<code>{chat_id}</code>) добавлена в белый список.")
        else:
            await message.answer(f"Группа <code>{chat_id}</code> уже в белом списке.")
    except ValueError:
        await message.answer("ID группы должен быть числом.")

@router.message(Command("disallow"))
async def cmd_disallow(message: types.Message):
    if not is_creator(message):
        return

    args = message.text.split()
    if len(args) < 2:
        await message.answer("Укажите ID группы. Пример: <code>/disallow -100123456789</code>")
        return

    try:
        chat_id = int(args[1])
        success = await remove_from_whitelist(chat_id)
        if success:
            await message.answer(f"❌ Группа <code>{chat_id}</code> удалена из белого списка.")
        else:
            await message.answer(f"Группы <code>{chat_id}</code> нет в белом списке.")
    except ValueError:
        await message.answer("ID группы должен быть числом.")

from aiogram.filters.chat_member_updated import ChatMemberUpdatedFilter, IS_NOT_MEMBER, MEMBER, ADMINISTRATOR
from aiogram.filters.chat_member_updated import KICKED, LEFT

@router.my_chat_member(ChatMemberUpdatedFilter(member_status_changed=(LEFT | KICKED) >> (MEMBER | ADMINISTRATOR)))
async def bot_added_to_chat(event: types.ChatMemberUpdated, bot: Bot):
    chat_id = event.chat.id
    chat_title = event.chat.title or "Unknown"

    whitelist = await get_whitelist()

    if chat_id not in whitelist:
        from config import CREATOR_ID
        try:
            await bot.send_message(
                chat_id=chat_id,
                text="Хаю хай гайсы, я бот диктор тайний баний, /help узнать все мои команды"
            )
        except Exception as e:
            print(f"Ошибка при приветствии в новой группе: {e}")

        if CREATOR_ID and int(CREATOR_ID) != 0:
            try:
                await bot.send_message(
                    chat_id=CREATOR_ID,
                    text=(
                        f"⚠️ <b>Меня добавили в новую группу!</b>\n\n"
                        f"Название: <b>{chat_title}</b>\n"
                        f"ID группы: <code>{chat_id}</code>\n"
                        f"Кто добавил: <b>{event.from_user.full_name}</b> (<code>{event.from_user.id}</code>)\n\n"
                        f"Добавить в белый список: <code>/allow {chat_id}</code>\n"
                        f"Наблюдать за чатом: <code>/spy {chat_id}</code>\n"
                        f"Написать туда: <code>/say {chat_id} текст</code>"
                    )
                )
            except Exception as e:
                print(f"Ошибка при отправке уведомления создателю: {e}")

@router.message(Command("whitelist"))
async def cmd_whitelist(message: types.Message):
    if not is_creator(message):
        return

    whitelist = await get_whitelist()
    if not whitelist:
        await message.answer("Белый список пуст.")
        return

    text = "📝 <b>Разрешенные группы:</b>\n\n"
    for chat_id, title in whitelist.items():
        text += f"• <b>{title}</b>\n<code>{chat_id}</code>\n\n"

    await message.answer(text)

from chances import set_game_chance, get_game_chance

@router.message(Command("setchance"))
async def cmd_setchance(message: types.Message):
    if not is_creator(message):
        return

    args = message.text.split()
    if len(args) < 3:
        await message.answer(
            "Использование: <code>/setchance <игра> <процент></code>\n"
            "Доступные игры: <code>slots</code>, <code>cups</code>, <code>roulette</code>\n"
            "Процент: 0-100 (установите -1 для честного рандома).\n"
            "Пример: <code>/setchance slots 50</code>"
        )
        return

    game_name = args[1].lower()
    valid_games =['slots', 'cups', 'roulette']

    if game_name not in valid_games:
        await message.answer(f"Неизвестная игра. Доступные: {', '.join(valid_games)}")
        return

    try:
        percentage = int(args[2])
        if percentage < -1 or percentage > 100:
            await message.answer("Процент должен быть от -1 до 100.")
            return

        await set_game_chance(game_name, percentage)
        if percentage == -1:
            await message.answer(f"Для игры <b>{game_name}</b> установлен честный рандом.")
        else:
            await message.answer(f"Для игры <b>{game_name}</b> установлен принудительный шанс победы: <b>{percentage}%</b>")
    except ValueError:
        await message.answer("Процент должен быть числом.")

@router.message(Command("info"))
async def cmd_info(message: types.Message):
    if not is_creator(message):
        return

    if not message.reply_to_message:
        await message.answer("Ответьте на сообщение пользователя.")
        return

    chat_id = message.chat.id
    target_id = message.reply_to_message.from_user.id
    target_name = escape_html(message.reply_to_message.from_user.full_name)

    data = await get_user_data(chat_id, target_id, target_name)

    balance = data.get('balance', 0)
    is_vip = data.get('is_vip', False)
    is_banned = data.get('is_banned', False)
    inventory = data.get('inventory', {})

    inv_text = ", ".join([f"{k}: {v}" for k, v in inventory.items()]) if inventory else "Пусто"
    vip_text = "Да 👑" if is_vip else "Нет"
    ban_text = "Да 🚫" if is_banned else "Нет"

    text = (
        f"📊 <b>Информация о пользователе {target_name}</b>\n\n"
        f"ID: <code>{target_id}</code>\n"
        f"Баланс: {balance} сыроежек\n"
        f"VIP статус: {vip_text}\n"
        f"Бан: {ban_text}\n"
        f"Инвентарь: {inv_text}"
    )

    await message.answer(text)

@router.message(Command("rleave"))
async def cmd_rleave(message: types.Message, bot: Bot):
    if not is_creator(message):
        return
    parts = message.text.split()
    if len(parts) < 2:
        return await message.answer("Использование: <code>/rleave <id_группы></code>")
    try:
        chat_id = int(parts[1])
        await bot.leave_chat(chat_id)
        from whitelist import remove_from_whitelist
        await remove_from_whitelist(chat_id)
        await message.answer(f"✅ Бот успешно покинул группу {chat_id} и удален из белого списка.")
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")

@router.message(Command("rmute"))
async def cmd_rmute(message: types.Message, bot: Bot):
    if not is_creator(message):
        return
    parts = message.text.split()
    if len(parts) < 4:
        return await message.answer("Использование: <code>/rmute <id_группы> <id_юзера> <минуты></code>")
    try:
        chat_id = int(parts[1])
        user_id = int(parts[2])
        minutes = int(parts[3])
        from datetime import timedelta
        from aiogram.types import ChatPermissions

        await bot.restrict_chat_member(
            chat_id=chat_id,
            user_id=user_id,
            permissions=ChatPermissions(can_send_messages=False),
            until_date=timedelta(minutes=minutes)
        )
        await message.answer(f"✅ Пользователь {user_id} получил мут на {minutes} минут в группе {chat_id}.")
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")

@router.message(Command("rpin"))
async def cmd_rpin(message: types.Message, bot: Bot):
    if not is_creator(message):
        return
    parts = message.text.split()
    if len(parts) < 3:
        return await message.answer("Использование: <code>/rpin <id_группы> <id_сообщения></code>")
    try:
        chat_id = int(parts[1])
        msg_id = int(parts[2])
        await bot.pin_chat_message(chat_id=chat_id, message_id=msg_id)
        await message.answer(f"✅ Сообщение {msg_id} закреплено в группе {chat_id}.")
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")

@router.message(Command("runpin"))
async def cmd_runpin(message: types.Message, bot: Bot):
    if not is_creator(message):
        return
    parts = message.text.split()
    if len(parts) < 3:
        return await message.answer("Использование: <code>/runpin <id_группы> <id_сообщения></code>")
    try:
        chat_id = int(parts[1])
        msg_id = int(parts[2])
        await bot.unpin_chat_message(chat_id=chat_id, message_id=msg_id)
        await message.answer(f"✅ Сообщение {msg_id} откреплено в группе {chat_id}.")
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")

from aiogram.types import FSInputFile
from logger import get_log_file

@router.message(Command("gethistory"))
async def cmd_gethistory(message: types.Message):
    if not is_creator(message):
        return

    args = message.text.split()
    if len(args) < 2:
        await message.answer("Использование: <code>/gethistory <id_группы> [ГГГГ-ММ-ДД]</code>")
        return

    try:
        chat_id = int(args[1])
        date_str = args[2] if len(args) > 2 else None

        file_path = get_log_file(chat_id, date_str)
        if file_path:
            doc = FSInputFile(file_path)
            await message.answer_document(doc, caption=f"📁 История чата {chat_id}")
        else:
            await message.answer("❌ Файл истории за эту дату не найден.")

    except ValueError:
        await message.answer("ID группы должен быть числом.")

@router.message(Command("nalog"))
async def cmd_nalog(message: types.Message, bot: Bot):
    if not is_creator(message):
        return

    args = message.text.split()
    if len(args) < 2:
        await message.answer("Укажите процент налога: <code>/nalog 15</code>")
        return

    try:
        tax = int(args[1])
        if tax < 0 or tax > 100:
            await message.answer("Налог должен быть от 0 до 100.")
            return

        from economy_utils import set_global_tax
        await set_global_tax(tax)

        from whitelist import get_whitelist
        whitelist = await get_whitelist()

        import secrets
        phrases_up =[
            f"⚠️ <b>ВНИМАНИЕ: ЭКОНОМИЧЕСКИЙ КРИЗИС!</b>\nНалоги повышены до <b>{tax}%</b>! Запасайтесь сыроежками!",
            f"🏛 <b>УКАЗ ГУБЕРНАТОРА:</b>\nКазна пустеет. Налоги увеличены до <b>{tax}%</b>.",
            f"💼 <b>НОВОСТИ ЭКОНОМИКИ:</b>\nНалоговая ставка выросла! Теперь при переводах удерживается <b>{tax}%</b>."
        ]
        phrases_down =[
            f"🎉 <b>ПРАЗДНИК В СТРАНЕ!</b>\nНалоги снижены до <b>{tax}%</b>! Время переводить сыроежки!",
            f"🏛 <b>УКАЗ ГУБЕРНАТОРА:</b>\nЭкономика процветает. Налоги уменьшены до <b>{tax}%</b>.",
            f"💼 <b>НОВОСТИ ЭКОНОМИКИ:</b>\nНалоговое бремя ослабло! Теперь при переводах удерживается всего <b>{tax}%</b>."
        ]

        text = secrets.choice(phrases_up) if tax >= 15 else secrets.choice(phrases_down)

        success_count = 0
        for chat_id in whitelist.keys():
            try:
                await bot.send_message(chat_id, text)
                success_count += 1
            except:
                pass

        await message.answer(f"✅ Налог установлен на {tax}%. Уведомлено {success_count} групп.")
    except ValueError:
        await message.answer("Процент должен быть числом.")

@router.message(Command("wipe_economy"))
async def cmd_wipe_economy(message: types.Message):
    if not is_creator(message):
        return await message.answer("❌ Отказано в доступе. У вас нет прав Создателя для запуска вайпа!")

    args = message.text.split()
    if len(args) < 2 or args[1] != "CONFIRM":
        return await message.answer(
            "⚠️ <b>ВНИМАНИЕ! ГЛОБАЛЬНЫЙ ВАЙП ЭКОНОМИКИ!</b> ⚠️\n\n"
            "Это действие:\n"
            "1. Сбросит баланс всех игроков до 500.\n"
            "2. Обнулит банковские счета.\n"
            "3. Удалит все бизнесы и машины из инвентарей.\n"
            "4. Сбросит все навыки и удалит питомцев.\n"
            "5. Простит все долги игроков.\n"
            "6. Обнулит казну всех кланов.\n"
            "7. Полностью перезапустит крипто-рынок.\n\n"
            "<i>(Админки, репутация, браки и варны сохранятся)</i>\n\n"
            "Если вы абсолютно УВЕРЕНЫ, введите команду:\n"
            "<code>/wipe_economy CONFIRM</code>"
        )

    status_msg = await message.answer("🔄 <i>Начинаю глобальный сброс экономики... Это займет некоторое время.</i>")

    import time
    import random
    from user_manager import _user_cache
    
    db = get_db()
    
    # 1. Очищаем оперативную память (кэш), чтобы старые балансы не вернулись
    _user_cache.clear()

    from whitelist import get_whitelist
    whitelist_dict = await get_whitelist()
    users_wiped = 0
    clans_wiped = 0

    for chat_id in whitelist_dict.keys():
        try:
            # 2. Вайп пользователей (обнуление полей экономики)
            users_ref = db.collection('chats').document(str(chat_id)).collection('users')
            user_docs = await users_ref.get()
            
            for doc in user_docs:
                doc_id = getattr(doc, 'id', None)
                if doc_id:
                    await users_ref.document(doc_id).set({
                        'balance': 500,
                        'bank_deposit': 0,
                        'inventory': {},
                        'debts': {},
                        'skills': {},
                        'pet': None
                    }, merge=True)
                    users_wiped += 1

            # 3. Вайп кланов (обнуление казны)
            clans_ref = db.collection('chats').document(str(chat_id)).collection('clans')
            clan_docs = await clans_ref.get()
            
            for cdoc in clan_docs:
                cdoc_id = getattr(cdoc, 'id', None)
                if cdoc_id:
                    await clans_ref.document(cdoc_id).set({
                        'treasury': 0
                    }, merge=True)
                    clans_wiped += 1
                
        except Exception as e:
            print(f"Ошибка при вайпе чата {chat_id}: {e}")

    # 4. Полный вайп криптовалюты
    current_time = int(time.time())
    default_coins = {
        "chsyr": {"name": "Китайская Сыроежка", "ticker": "CH_SYR", "prices":[random.randint(100, 500)], "creator": 0},
        "espsyr": {"name": "Испанская Сыроежка", "ticker": "ESP_SYR", "prices":[random.randint(100, 500)], "creator": 0}
    }
    await db.collection('bot_settings').document('crypto_coins').set({
        'coins': default_coins,
        'last_update': current_time
    })

    try:
        await status_msg.edit_text(
            f"✅ <b>ЭКОНОМИКА УСПЕШНО СБРОШЕНА!</b>\n\n"
            f"👤 Обнулено игроков: <b>{users_wiped}</b>\n"
            f"🛡 Обнулено кланов: <b>{clans_wiped}</b>\n"
            f"📈 Крипторынок пересоздан с нуля.\n\n"
            f"<i>Все начали жизнь с чистого листа (баланс 500 сыроежек).</i>"
        )
    except Exception as e:
        await status_msg.reply(f"Вайп завершен! Ошибка статуса: {e}")