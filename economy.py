from aiogram import Router, F, types
from aiogram.filters import Command
import secrets
import time
from economy_utils import get_global_tax
from user_manager import get_user_data, update_user_balance, check_and_give_bonus, update_user_field, get_top_users
from escape import escape_html

router = Router()

@router.message(Command("start"))
async def cmd_start(message: types.Message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    full_name = escape_html(message.from_user.full_name)

    await get_user_data(chat_id, user_id, full_name)

    text = (
        f"👋 <b>Привет, {full_name}!</b>\n\n"
        "Я бот для экономики и мини-игр! Твой стартовый баланс составляет <b>500</b> сыроежек.\n\n"
        "Пиши <code>/help</code> чтобы увидеть список всех команд."
    )
    await message.answer(text)

@router.message(Command("help"))
async def cmd_help(message: types.Message):
    text = "📜 <b>ПОЛНЫЙ СПИСОК КОМАНД БОТА</b> 📜\n\n"
    
    text += "💰 <b>ЭКОНОМИКА И БАНК:</b>\n"
    text += "<code>/profile</code> - Профиль (деньги, клан, брак, варны).\n"
    text += "<code>/bank</code> - Главное меню банков (вклады, листы, инфо).\n"
    text += "<code>/bank_offshore</code> - Скрыть счет в банке за комиссию.\n"
    text += "<code>ограбить банк [Имя]</code> - Попытка кражи из банка.\n"
    text += "<code>/bonus</code> - Собрать прибыль и бонус.\n"
    text += "<code>/work</code>, <code>/crime</code> - Способы заработка.\n"
    text += "<code>/pay [сумма][реплай]</code> - Перевод денег.\n"
    text += "<code>долг [сумма] [%][реплай]</code> - Дать в долг (P2P).\n"
    text += "<code>выплатить[сумма] [реплай]</code> - Вернуть долг.\n"
    text += "<code>украсть</code> [реплай] - Карманная кража.\n\n"

    text += "🏦 <b>ДЛЯ БАНКИРОВ:</b>\n"
    text += "<code>создать банк [Имя]</code> - Открыть свой банк.\n"
    text += "<code>/bankrate [3-13]</code> - Установить % по вкладам.\n"
    text += "<code>/bank_stats</code> - Панель управления (вклады, кредиты).\n"
    text += "<code>кредит [сумма] [%] [дни] [поручитель] [реплай]</code> - Выдать кредит игроку.\n\n"

    text += "📈 <b>КРИПТОБИРЖА:</b>\n"
    text += "<code>/криптосыроежка</code> - Главное меню рынка и графики.\n"
    text += "<code>/createcoin [ТИКЕР] [Цена] [Название]</code> - Создать монету.\n"
    text += "<code>/cr_send [ТИКЕР] [Кол-во]</code> - Перевод крипты (реплай, налог 2%).\n\n"

    text += "🤝 <b>СДЕЛКИ И ДОГОВОРЫ:</b>\n"
    text += "<code>договор [текст]</code> - Заключить словесный контракт.\n"
    text += "<code>сделка [цена] [предмет] [условие]</code> - Купля-продажа вещей.\n"
    text += "<code>наследство</code> - Передать всё имущество (реплай).\n\n"

    text += "🔞 <b>ЭСКОРТ:</b>\n"
    text += "<code>нанять/заказать [сумма] [реплай]</code> - Снять путану.\n"
    text += "<code>эскорт/проститут [сумма] [реплай]</code> - Предложить услуги.\n\n"

    text += "🛒 <b>МАГАЗИН И ПРОКАЧКА:</b>\n"
    text += "<code>/shop</code> - Бизнесы, машины, VIP.\n"
    text += "<code>/upgrade [название]</code> - Улучшить бизнес.\n"
    text += "<code>/skills</code> - Прокачка навыков.\n"
    text += "<code>/pets</code>, <code>/feed</code> - Питомцы.\n\n"

    text += "🛡 <b>КЛАНЫ И СЕМЬИ:</b>\n"
    text += "<code>/clan</code> - Меню кланов.\n"
    text += "<code>Брак</code>, <code>Развод</code>, <code>Подарок [сумма]</code>.\n\n"

    text += "🎰 <b>ИГРЫ:</b>\n"
    text += "<code>/bj</code>, <code>/slots</code>, <code>/roulette [ставка] [число/цвет]</code>.\n"
    text += "<code>Дуэль [ставка]</code>, <code>/lottery</code> (розыгрыш).\n\n"

    text += "👮‍♂️ <b>АДМИНЫ (В Т.Ч. КРИПТО):</b>\n"
    text += "<code>мут</code>, <code>бан</code>, <code>варн</code>, <code>повысить</code>, <code>снять</code>.\n"
    text += "<code>кто админ</code>, <code>+правила</code>, <code>антивойс</code>, <code>антилинк</code>.\n"
    text += "<code>/cr_wipe</code> - Вайп рынка. <code>/cr_delcoin [тикер]</code> - Удалить монету.\n"
    text += "<code>/cr_crash[тикер]</code> - Обрушить курс. <code>бан/разбан крипты</code>.\n\n"

    text += "🎭 <b>РП И ИНТЕРАКТИВ:</b>\n"
    text += "<code>Обнять</code>, <code>Поцеловать</code>, <code>Ударить</code>, <code>Кусь</code>.\n"
    text += "<code>Диктор [вопрос]</code>, <code>/bio [текст]</code>, <code>/rules</code>.\n"
    text += "Репутация: <code>+</code>, <code>спасибо</code>, <code>реп</code>."
    
    await message.answer(text)

@router.message(Command("balance"))
async def cmd_balance(message: types.Message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    full_name = escape_html(message.from_user.full_name)

    data = await get_user_data(chat_id, user_id, full_name)
    balance = data.get('balance', 0)
    is_vip = data.get('is_vip', False)

    vip_icon = " 👑 VIP" if is_vip else ""
    await message.answer(f"💰 Твой баланс: <b>{balance}</b> сыроежек.{vip_icon}")

@router.message(Command("pay"))
async def cmd_pay(message: types.Message):
    chat_id = message.chat.id
    sender_id = message.from_user.id
    sender_name = escape_html(message.from_user.full_name)

    sender_data = await get_user_data(chat_id, sender_id, sender_name)
    if sender_data.get('is_banned', False):
        await message.answer("Ты в бане и не можешь переводить деньги.")
        return

    if not message.reply_to_message:
        await message.answer("Ответь на сообщение человека, которому хочешь перевести сыроежки.")
        return

    target_user = message.reply_to_message.from_user
    target_name = escape_html(target_user.full_name)
    if target_user.is_bot:
        await message.answer("Ботам деньги не нужны.")
        return

    if target_user.id == message.from_user.id:
        await message.answer("Нельзя перевести деньги самому себе.")
        return

    args = message.text.split()
    if len(args) < 2:
        await message.answer("Укажи сумму: <code>/pay 100</code>")
        return

    try:
        amount = int(args[1])
        if amount <= 0:
            await message.answer("Сумма должна быть больше нуля.")
            return
    except ValueError:
        await message.answer("Сумма должна быть числом.")
        return

    tax_percent = await get_global_tax()
    
    if tax_percent > 0:
        commission = int(amount * (tax_percent / 100.0))
        if commission == 0: commission = 1 
    else:
        commission = 0
        
    total_cost = amount + commission

    if sender_data.get('balance', 0) < total_cost:
        await message.answer(f"Мало денег. Для перевода {amount} нужно {total_cost} сыроежек (налог {tax_percent}% - минимум 1 сыр.).")
        return

    try:
        admins = await message.chat.get_administrators()
        human_admins =[admin.user.id for admin in admins if not admin.user.is_bot]
    except Exception:
        human_admins =[]

    await update_user_balance(chat_id, sender_id, -total_cost)

    await get_user_data(chat_id, target_user.id, target_name)
    await update_user_balance(chat_id, target_user.id, amount)

    if human_admins and commission > 0:
        commission_per_admin = commission // len(human_admins)
        if commission_per_admin > 0:
            for admin_id in human_admins:
                await get_user_data(chat_id, admin_id)
                await update_user_balance(chat_id, admin_id, commission_per_admin)

    phrases =[
        f"Налоговая откусила кусок в {commission} сыроежек.",
        f"Гоблины-сборщики забрали {commission} сыроежек в казну.",
        f"Крыша требует свою долю. Удержано {commission} сыроежек.",
        f"Банкирский дом забирает свои скромные {commission} сыроежек за услуги.",
        f"Местные рэкетиры взыскали налог: {commission} сыроежек.",
        f"Комиссия в {commission} сыроежек ушла на развитие экономики."
    ]
    phrase = secrets.choice(phrases) if commission > 0 else "Налог отменен! Деньги дошли без потерь."

    await message.answer(
        f"💸 <b>Успешный перевод!</b>\n\n"
        f"Отправлено: {amount} сыроежек пользователю {target_name}.\n"
        f"<i>{phrase}</i> (Налог {tax_percent}% ушел админам)."
    )

@router.message(Command("bonus"))
async def cmd_bonus(message: types.Message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    full_name = escape_html(message.from_user.full_name)

    success, receipt = await check_and_give_bonus(chat_id, user_id, full_name)
    if success:
        text = f"🧾 <b>Квитанция о доходах</b>\n\n"
        if receipt.get('base', 0) > 0:
            text += f"🎁 Ежедневный бонус: <b>{receipt['base']}</b>\n"
        text += f"🏢 Доход с бизнесов: <b>{receipt['business']}</b>\n"
        text += f"🚗 Доход с машин: <b>{receipt['car']}</b>\n"
        text += f"➖ Налог ({receipt['tax_percent']}%): <b>-{receipt['tax_amount']}</b>\n"
        text += f"-----------------------\n"
        text += f"💰 Итого на руки: <b>{receipt['total']}</b> сыроежек"

        await message.answer(text)
    else:
        await message.answer("❌ Ты уже собирал доход недавно. Попробуй позже!")

@router.message(Command("work"))
async def cmd_work(message: types.Message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    full_name = escape_html(message.from_user.full_name)

    data = await get_user_data(chat_id, user_id, full_name)
    if data.get('is_banned', False):
        return await message.answer("Ты в бане и не можешь работать.")

    last_work = data.get('last_work_time', 0)
    current_time = time.time()

    if current_time - last_work < 1800:
        remain = int(1800 - (current_time - last_work))
        mins, secs = divmod(remain, 60)
        return await message.answer(f"⏳ Ты устал. Отдохни еще {mins} минут и {secs} секунд.")

    await update_user_field(chat_id, user_id, 'last_work_time', current_time)

    rand = secrets.SystemRandom()
    base_earnings = rand.randint(500, 1500)
    
    bank_profit_msg = ""
    if data.get('is_banker', False):
        # Доход банкиров от работы урезан до 10-20%
        base_earnings = int(base_earnings * 0.15)
        if base_earnings < 1:
            base_earnings = 1

        # Банкир также приносит пользу своему банку
        bank_contribution = rand.randint(1000, 5000)
        from profile_bank import get_bank_info, create_or_update_bank
        bank_data = await get_bank_info(chat_id, user_id)
        if bank_data:
            await create_or_update_bank(chat_id, user_id, {'capital': bank_data.get('capital', 0) + bank_contribution})
            bank_profit_msg = f"\n🏢 Ваша работа принесла банку <b>{bank_contribution}</b> сыр. в капитал!"

    # --- БОНУС ПИТОМЦА ---
    pet = data.get('pet')
    pet_id = pet.get('id') if pet else None
    pet_msg = ""
    
    if pet_id == 'cat':
        base_earnings = int(base_earnings * 1.2)
        pet_msg = "\n🐱 Ваш верный кот помог заработать на 20% больше!"

    final_earnings = base_earnings

    # --- ЛОГИКА КОЛЛЕКТОРОВ ---
    collector_msg = ""
    debts = data.get('debts', {})
    balance = data.get('balance', 0)

    # Дракон защищает от коллекторов!
    if pet_id != 'dragon' and (debts or balance < 0) and rand.randint(1, 100) <= 30:
        if debts:
            lender_id_str = secrets.choice(list(debts.keys()))
            debt_amount = debts[lender_id_str]

            is_bank = lender_id_str.startswith("bank_")

            collector_cut = int(base_earnings * 0.5)
            if collector_cut == 0: collector_cut = 1
            pay_amount = min(collector_cut, debt_amount)

            if pay_amount > 0:
                final_earnings = base_earnings - pay_amount
                debts[lender_id_str] -= pay_amount
                if debts[lender_id_str] <= 0:
                    del debts[lender_id_str]
                
                await update_user_field(chat_id, user_id, 'debts', debts)
                
                if is_bank:
                    banker_id = int(lender_id_str.split("_")[1])
                    from profile_bank import get_bank_info, create_or_update_bank
                    bank_data = await get_bank_info(chat_id, banker_id)
                    lender_name = bank_data.get('name', 'Неизвестный Банк') if bank_data else 'Банк'
                    if bank_data:
                        await create_or_update_bank(chat_id, banker_id, {'capital': bank_data.get('capital', 0) + pay_amount})
                    collector_msg = f"\n\n🦹‍♂️ <b>КОЛЛЕКТОРЫ БАНКА!</b> Они поджидали тебя и забрали <b>{pay_amount}</b> сыроежек в качестве уплаты долга для <b>{escape_html(lender_name)}</b>."
                else:
                    lender_id = int(lender_id_str)
                    lender_data = await get_user_data(chat_id, lender_id)
                    lender_name = lender_data.get('full_name', 'Неизвестный кредитор')
                    await update_user_balance(chat_id, lender_id, pay_amount, is_debt_repayment=True)
                    collector_msg = f"\n\n🦹‍♂️ <b>ЧАСТНЫЕ КОЛЛЕКТОРЫ!</b> Они поджидали тебя и забрали <b>{pay_amount}</b> сыроежек в качестве уплаты долга для <b>{escape_html(lender_name)}</b>."
        else:
            penalty = rand.randint(100, 300)
            final_earnings = 0
            await update_user_balance(chat_id, user_id, -penalty, is_debt_repayment=True)
            collector_msg = f"\n\n🦹‍♂️ <b>КОЛЛЕКТОРЫ БАНКА!</b> Они отобрали весь заработок и выбили еще <b>{penalty}</b> сыроежек сверху в счет погашения кредита."
    elif pet_id == 'dragon' and (debts or balance < 0):
         pet_msg += "\n🐉 Ваш дракон отпугнул поджидавших вас коллекторов!"

    if final_earnings > 0:
        await update_user_balance(chat_id, user_id, final_earnings, is_debt_repayment=True)

    jobs =[
        "разгрузил вагоны",
        "написал код за еду",
        "доставил пиццу",
        "отработал смену на заводе",
        "собрал металлолом"
    ]
    if data.get('is_banker', False):
        jobs = ["поработал с документами", "провел встречу с инвесторами", "свел дебет с кредитом", "продал акции банка"]

    job = rand.choice(jobs)

    await message.answer(f"💼 Ты <b>{job}</b> и заработал <b>{base_earnings}</b> сыроежек!{pet_msg}{collector_msg}{bank_profit_msg}")

@router.message(Command("crime"))
async def cmd_crime(message: types.Message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    full_name = escape_html(message.from_user.full_name)

    data = await get_user_data(chat_id, user_id, full_name)
    if data.get('is_banned', False):
        return await message.answer("Ты в бане и не можешь совершать преступления.")
        
    if data.get('is_banker', False):
        return await message.answer("🏦 Вы — уважаемый Банкир. Воровать не по статусу. (Крайм отключен для банкиров)")

    last_crime = data.get('last_crime_time', 0)
    current_time = time.time()

    if current_time - last_crime < 3600:
        remain = int(3600 - (current_time - last_crime))
        mins, secs = divmod(remain, 60)
        return await message.answer(f"⏳ Копы ищут тебя. Заляг на дно еще на {mins} мин. {secs} сек.")

    await update_user_field(chat_id, user_id, 'last_crime_time', current_time)

    rand = secrets.SystemRandom()
    stealth_level = data.get('skills', {}).get('stealth', 0)
    
    # --- БОНУС ПИТОМЦА ---
    pet = data.get('pet')
    pet_id = pet.get('id') if pet else None
    dragon_bonus = 0.1 if pet_id == 'dragon' else 0
    pet_msg = "\n🐉 Дракон помог провернуть дело!" if pet_id == 'dragon' else ""

    success_chance = 0.4 + (stealth_level * 0.05) + dragon_bonus

    if rand.random() < success_chance:
        base_earnings = rand.randint(1000, 3000)
        final_earnings = base_earnings

        # --- ЛОГИКА КОЛЛЕКТОРОВ ---
        collector_msg = ""
        debts = data.get('debts', {})
        balance = data.get('balance', 0)

        # Дракон защищает от коллекторов!
        if pet_id != 'dragon' and (debts or balance < 0) and rand.randint(1, 100) <= 40:
            if debts:
                lender_id_str = secrets.choice(list(debts.keys()))
                debt_amount = debts[lender_id_str]

                is_bank = lender_id_str.startswith("bank_")

                collector_cut = int(base_earnings * 0.5)
                if collector_cut == 0: collector_cut = 1
                pay_amount = min(collector_cut, debt_amount)

                if pay_amount > 0:
                    final_earnings = base_earnings - pay_amount
                    debts[lender_id_str] -= pay_amount
                    if debts[lender_id_str] <= 0:
                        del debts[lender_id_str]
                    
                    await update_user_field(chat_id, user_id, 'debts', debts)
                    
                    if is_bank:
                        banker_id = int(lender_id_str.split("_")[1])
                        from profile_bank import get_bank_info, create_or_update_bank
                        bank_data = await get_bank_info(chat_id, banker_id)
                        lender_name = bank_data.get('name', 'Неизвестный Банк') if bank_data else 'Банк'
                        if bank_data:
                            await create_or_update_bank(chat_id, banker_id, {'capital': bank_data.get('capital', 0) + pay_amount})
                        collector_msg = f"\n\n🦹‍♂️ <b>КОЛЛЕКТОРЫ БАНКА!</b> Они выследили тебя и забрали <b>{pay_amount}</b> сыроежек в счет старого долга для <b>{escape_html(lender_name)}</b>."
                    else:
                        lender_id = int(lender_id_str)
                        lender_data = await get_user_data(chat_id, lender_id)
                        lender_name = lender_data.get('full_name', 'Неизвестный кредитор')
                        await update_user_balance(chat_id, lender_id, pay_amount, is_debt_repayment=True)
                        collector_msg = f"\n\n🦹‍♂️ <b>ЧАСТНЫЕ КОЛЛЕКТОРЫ!</b> Они выследили тебя и забрали <b>{pay_amount}</b> сыроежек в счет старого долга для <b>{escape_html(lender_name)}</b>."
            else:
                penalty = rand.randint(200, 500)
                final_earnings = 0
                await update_user_balance(chat_id, user_id, -penalty, is_debt_repayment=True)
                collector_msg = f"\n\n🦹‍♂️ <b>КОЛЛЕКТОРЫ БАНКА!</b> Они забрали всю добычу и выбили еще <b>{penalty}</b> сыроежек в счет кредита."
        elif pet_id == 'dragon' and (debts or balance < 0):
            pet_msg += " И отпугнул коллекторов!"

        if final_earnings > 0:
            await update_user_balance(chat_id, user_id, final_earnings, is_debt_repayment=True)
        
        crimes =["ограбил банк", "угнал спорткар", "взломал криптобиржу", "обчистил казино"]
        crime = rand.choice(crimes)
        await message.answer(f"🥷 Ты успешно <b>{crime}</b> и поднял <b>{base_earnings}</b> сыроежек!{pet_msg}{collector_msg}")
    else:
        fine = rand.randint(500, 1500)
        await update_user_balance(chat_id, user_id, -fine, is_debt_repayment=True)
        await message.answer(f"🚔 Тебя поймали! Суд выписал штраф в <b>{fine}</b> сыроежек.")
@router.message(F.text.lower().startswith("ограбить банк"))
async def cmd_rob_bank(message: types.Message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    full_name = escape_html(message.from_user.full_name)

    data = await get_user_data(chat_id, user_id, full_name)
    if data.get('is_banned', False):
        return await message.answer("Ты в бане и не можешь грабить банки.")

    if data.get('is_banker', False):
        return await message.answer("🏦 Банкирам запрещено грабить банки коллег!")

    args = message.text.split(maxsplit=2)
    if len(args) < 3:
        return await message.answer("Использование: <code>ограбить банк [Название или ID]</code>")

    # Cooldown (например, 12 часов)
    last_rob = data.get('last_bank_rob_time', 0)
    current_time = time.time()
    if current_time - last_rob < 43200:
        remain = int(43200 - (current_time - last_rob))
        hours, rem = divmod(remain, 3600)
        mins, _ = divmod(rem, 60)
        return await message.answer(f"⏳ Полиция патрулирует город после недавнего налета. Заляг на дно еще на {hours} ч. {mins} мин.")

    identifier = args[2]
    from profile_bank import get_bank_info, create_or_update_bank
    bank_data = await get_bank_info(chat_id, identifier)

    if not bank_data:
        return await message.answer("🏦 Банк не найден. Проверьте название.")

    target_banker_id = bank_data['banker_id']
    capital = bank_data.get('capital', 0)

    if capital < 10000:
        return await message.answer("В этом банке слишком мало денег, грабить нечего!")

    await update_user_field(chat_id, user_id, 'last_bank_rob_time', current_time)

    rand = secrets.SystemRandom()
    stealth_level = data.get('skills', {}).get('stealth', 0)

    # Базовый шанс успеха - 25% + 2% за каждый уровень стелса
    success_chance = 0.25 + (stealth_level * 0.02)

    if rand.random() < success_chance:
        # Украли от 1% до 5% от капитала банка
        steal_percent = rand.uniform(0.01, 0.05)
        stolen_amount = int(capital * steal_percent)

        await create_or_update_bank(chat_id, target_banker_id, {'capital': capital - stolen_amount})
        await update_user_balance(chat_id, user_id, stolen_amount)

        await message.answer(f"🥷 <b>УСПЕШНОЕ ОГРАБЛЕНИЕ!</b>\n\nВы ворвались в банк <b>{escape_html(bank_data.get('name'))}</b>, вскрыли сейф и вынесли <b>{stolen_amount}</b> сыроежек!\n<i>Банк понес убытки.</i>")
    else:
        # Провал
        penalty = rand.randint(5000, 20000)
        await update_user_balance(chat_id, user_id, -penalty)

        # Выдаем временный мут через aiogram
        from datetime import timedelta
        try:
            await message.bot.restrict_chat_member(
                chat_id=chat_id,
                user_id=user_id,
                permissions=types.ChatPermissions(can_send_messages=False),
                until_date=timedelta(minutes=30)
            )
            mute_text = "\nВас посадили в тюрьму (мут) на 30 минут."
        except:
            mute_text = "\nСпецназ пытался вас арестовать, но вам удалось сбежать, потеряв деньги в спешке."

        await message.answer(f"🚔 <b>ОБЛАВА! СРАБОТАЛА СИГНАЛИЗАЦИЯ!</b>\n\nОграбление банка <b>{escape_html(bank_data.get('name'))}</b> провалилось. Вы потеряли <b>{penalty}</b> сыроежек при побеге.{mute_text}")
