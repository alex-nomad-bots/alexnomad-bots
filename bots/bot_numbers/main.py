import asyncio
import os
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart
from dotenv import load_dotenv
from google_sheets import add_entry, get_todays_entries, get_status_updates, sh, SHEET_NAME
from aiogram.client.default import DefaultBotProperties
from datetime import datetime
import pytz
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from gspread_formatting import CellFormat, Color, format_cell_range
from google_sheets import ensure_checkboxes

load_dotenv()

ASSEMBLY_CHANNEL_ID = -1002278564402
TOKEN = os.getenv("TELEGRAM_TOKEN")
bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()



# Варианты сторон
POSITIONS = ["Перед", "Зад", "Лево", "Право"]

# Временное хранилище данных пользователя
user_data = {}

def clear_row_background(row_index):
    worksheet = sh.worksheet(SHEET_NAME)
    neutral_fill = CellFormat(backgroundColor=Color(1, 1, 1))  # белый фон
    range_str = f"A{row_index}:K{row_index}"
    format_cell_range(worksheet, range_str, neutral_fill)

def build_keyboard(selected: list[str]) -> InlineKeyboardMarkup:
    buttons = []
    for pos in POSITIONS:
        prefix = "✅ " if pos in selected else ""
        buttons.append(InlineKeyboardButton(text=prefix + pos, callback_data=pos))

    return InlineKeyboardMarkup(
        inline_keyboard=[
            buttons[:2],
            buttons[2:],
            [InlineKeyboardButton(text="🔘 ВСЕ", callback_data="ВСЕ")],
            [InlineKeyboardButton(text="✏️ Изменить номер", callback_data="change_number")],
            [InlineKeyboardButton(text="✅ Подтвердить", callback_data="confirm")]
        ]
    )

@dp.message(CommandStart())
async def start(message: Message):
    await message.answer("Привет! Введи номер самоката (например: HH123Y):")

@dp.message(F.text)
async def handle_number_input(message: Message):
    if message.chat.type != 'private':
        return  # Выходим, если это не личный чат
    number = message.text.strip()
    if len(number) > 6:
        await message.answer("❗ Номер самоката должен быть не более 6 символов. Попробуй ещё раз:")
        return
    user_data[message.from_user.id] = {
        "number": number,
        "positions": []
    }
    await message.answer(
        f"Номер <b>{number}</b> получен. Выбери стороны, где он находится:",
        reply_markup=build_keyboard([])
    )

@dp.callback_query(F.data == "confirm")
async def handle_confirm(callback: CallbackQuery):
    user_id = callback.from_user.id
    data = user_data.get(user_id)

    if not data:
        await callback.answer("Сначала введите номер самоката", show_alert=True)
        return

    if not data["positions"]:
        await callback.answer("Выберите хотя бы одну сторону", show_alert=True)
        return

    # Запись в таблицу
    result = add_entry(
        user_id=user_id,
        username=callback.from_user.username or "-",
        number=data["number"],
        sides=data["positions"]
    )
    # Уведомление в канал о новом заказе
    await bot.send_message(
        chat_id=ASSEMBLY_CHANNEL_ID,
        text=(
        f"🔔 Новый заказ на номер <b>{data['number']}</b>\n"
        f"📍 Стороны: <i>{', '.join(data['positions'])}</i>"
        )
    )
    worksheet = sh.worksheet(SHEET_NAME)
    row_index = len(worksheet.get_all_values())  # последняя добавленная строка
    clear_row_background(row_index)

    await callback.message.edit_text(
        f"✅ Заявка на номер <b>{data['number']}</b> отправлена.\nСтороны: {', '.join(data['positions'])}"
    )
    user_data.pop(user_id, None)
    await callback.answer()

@dp.callback_query(F.data == "ВСЕ")
async def handle_all_toggle(callback: CallbackQuery):
    user_id = callback.from_user.id
    data = user_data.get(user_id)

    if not data:
        await callback.answer("Сначала введите номер самоката", show_alert=True)
        return

    # Если уже выбраны все — снимаем, иначе выбираем все
    if set(data["positions"]) == set(POSITIONS):
        data["positions"] = []
        await callback.answer("❌ Сняты все стороны")
    else:
        data["positions"] = POSITIONS.copy()
        await callback.answer("✅ Выбраны все стороны")

    # Обновляем клавиатуру
    await callback.message.edit_reply_markup(reply_markup=build_keyboard(data["positions"]))

@dp.callback_query(lambda c: c.data in POSITIONS)
async def handle_position_select(callback: CallbackQuery):
    user_id = callback.from_user.id
    data = user_data.get(user_id)

    if not data:
        await callback.answer("Сначала введите номер самоката", show_alert=True)
        return

    position = callback.data
    if position in data["positions"]:
        data["positions"].remove(position)
    else:
        data["positions"].append(position)

    await callback.message.edit_reply_markup(reply_markup=build_keyboard(data["positions"]))
    await callback.answer()

@dp.callback_query(F.data == "change_number")
async def handle_change_number(callback: CallbackQuery):
    user_id = callback.from_user.id
    if user_id in user_data:
        user_data.pop(user_id)
    await callback.message.edit_text("✏️ Введите новый номер самоката:")
    await callback.answer()

async def notify_status_change():
    while True:
        entries = get_status_updates()
        for entry in entries:
            status = entry["status"]
            user_id = entry["user_id"]

            if not user_id:
                continue

            print(f"Обработка статуса: {status}, номер: {entry['scooter_number']}")

            if status == "готово":
                text = f"✅ Номер самоката <b>{entry['scooter_number']}</b> готов!"
            elif status == "номер отсутствует":
                text = f"🔴 Номер <b>{entry['scooter_number']}</b> отсутствует. Заявка не может быть выполнена."

            try:
                await bot.send_message(chat_id=user_id, text=text)
            except Exception as e:
                print(f"Ошибка при отправке: {e}")

        await asyncio.sleep(300)  # каждые 300 секунд

REPORT_USER_IDS = [285742976, 703311980, 1123621831, 788329249]  # ← добавь сюда свои и начальника Telegram ID

async def send_daily_report():
    print("📨 Старт отправки отчёта: send_daily_report()")
    today = datetime.now(pytz.timezone("Europe/Moscow")).strftime('%d.%m.%Y')
    entries = get_todays_entries()

    print("⏰ Отправка ежедневного отчета запущена...")

    if not entries:
        text = f"📆 Отчет за {today}:\nНет заявок на сегодня."
    else:
        lines = []
        for i, e in enumerate(entries, start=1):
            lines.append(
                f"<b>{i}.</b> <code>{e['number']}</code>\n"
                f"└ 📍 <i>{e['sides']}</i>\n"
                f"└ 📌 <b>{e['status'] or 'Без статуса'}</b>\n"
            )
        text = f"📆 <b>Отчет за {today}</b>\n\n" + "\n".join(lines) + f"\n<b>Всего:</b> {len(entries)}"

    for user_id in REPORT_USER_IDS:
        try:
            await bot.send_message(chat_id=user_id, text=text)
        except Exception as e:
            print(f"Ошибка: {e}")
        await asyncio.sleep(1)

    await highlight_next_empty_row()


async def highlight_next_empty_row():
    worksheet = sh.worksheet(SHEET_NAME)
    values = worksheet.col_values(1)
    next_row = len(values) + 1  # следующая строка

    # Убедимся, что строка существует — добавим пустую
    num_cols = 11  # A–K
    values = worksheet.get_all_values()
    if next_row > len(values):
        worksheet.append_row(["День окончен"] + [""] * (num_cols - 1))

    # Цвет: жёлтый
    yellow_fill = CellFormat(backgroundColor=Color(1, 1, 0.6))
    cell_range = f"A{next_row}:K{next_row}"
    format_cell_range(worksheet, cell_range, yellow_fill)

async def main():
    try:
        ensure_checkboxes()  # <-- создаёт флажки в нужных колонках
    except Exception as e:
        print(f"Ошибка при создании флажков: {e}")
    
    scheduler = AsyncIOScheduler(timezone="Europe/Moscow")
    scheduler.add_job(send_daily_report, CronTrigger(hour=19, minute=40))
    scheduler.start()

    await asyncio.gather(
        dp.start_polling(bot),
        notify_status_change()  # если есть
    )

if __name__ == "__main__":
    asyncio.run(main())