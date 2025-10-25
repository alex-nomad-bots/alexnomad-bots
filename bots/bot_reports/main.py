# main.py
import asyncio
import logging
import gspread
from datetime import datetime
import traceback
from aiogram import Bot, Dispatcher
from aiogram.filters import CommandStart, Command
from aiogram.types import Message

from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext

from config import BOT_TOKEN, GOOGLE_SHEET_URL, GOOGLE_CREDS_PATH

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery


logging.basicConfig(level=logging.INFO)

bot = Bot(BOT_TOKEN)
dp = Dispatcher()

# --- Google Sheets ---
try:
    gc = gspread.service_account(filename=GOOGLE_CREDS_PATH)
    sh = gc.open_by_url(GOOGLE_SHEET_URL)
    worksheet = sh.sheet1
    GS_READY = True
    logging.info("Google Sheets connected successfully")
except Exception as e:
    logging.exception("Google Sheets init error")
    worksheet = None
    GS_READY = False

def append_to_sheet(row: list):
    if not GS_READY or worksheet is None:
        raise RuntimeError("Google Sheets не инициализирован. Проверьте GOOGLE_CREDS_PATH и доступ сервис-аккаунта к таблице (права 'Редактировать').")
    worksheet.append_row(row)

def get_questions():
    headers = worksheet.row_values(1)
    return headers[3:]

QUESTIONS = get_questions()

class WorkForm(StatesGroup):
    fullname = State()
    current_question = State()

@dp.message(CommandStart())
async def start(message: Message, state: FSMContext):
    await message.answer("Нажмите кнопку, чтобы начать ввод данных:", reply_markup=get_start_keyboard())

def get_start_keyboard():
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🚀 Начать", callback_data="start_work")]
        ]
    )
    return kb


# Diagnostics command to test Google Sheets connectivity
@dp.message(Command("testgs"))
async def test_gs(message: Message):
    try:
        append_to_sheet([
            datetime.now().strftime("%d.%m.%Y %H:%M:%S"),
            message.from_user.username or "",
            f"{message.from_user.full_name} (test)",
            "0", "0", "0"
        ])
        await message.answer("✅ Тестовая запись в Google Sheets успешно выполнена.")
    except Exception as e:
        await message.answer(f"❌ Ошибка Google Sheets: {e.__class__.__name__}: {e}")

@dp.callback_query(lambda c: c.data == "start_work")
async def process_start_work(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("Введите своё имя и фамилию:")
    await state.set_state(WorkForm.fullname)
    await callback.answer()

@dp.message(WorkForm.fullname)
async def enter_fullname(message: Message, state: FSMContext):
    await state.update_data(fullname=message.text.strip(), answers={}, current_index=0)
    await message.answer(f"{QUESTIONS[0]}:")
    await state.set_state(WorkForm.current_question)

@dp.message(WorkForm.current_question)
async def process_question(message: Message, state: FSMContext):
    data = await state.get_data()
    idx = data["current_index"]
    answers = data["answers"]

    current_question = QUESTIONS[idx]

    # Если вопрос "Прочие работы" → разрешаем текст
    if "прочие работы" in current_question.lower():
        answers[current_question] = message.text
    else:
        # Для остальных вопросов ждём число
        if not message.text.isdigit():
            await message.answer("Введите число!")
            return
        answers[current_question] = int(message.text)

    idx += 1

    if idx < len(QUESTIONS):
        await state.update_data(current_index=idx, answers=answers)
        await message.answer(f"{QUESTIONS[idx]}:")
    else:
        row = [
            datetime.now().strftime("%d.%m.%Y"),
            message.from_user.username or "",
            data["fullname"]
        ]
        for q in QUESTIONS:
            val = answers.get(q, "")
            if "комментарий" in q.lower() or "прочие работы" in q.lower():
                row.append(val if isinstance(val, str) else "")
            else:
                try:
                    row.append(int(val))
                except (ValueError, TypeError):
                    row.append(0)

        try:
            append_to_sheet(row)
            await message.answer("✅ Ваш отчет отправлен, спасибо!")
            await message.answer("Хотите начать заново?", reply_markup=get_start_keyboard())
        except Exception as e:
            await message.answer(f"❌ Не удалось записать в Google Sheets.\nОшибка: {e.__class__.__name__}: {e}")
        finally:
            await state.clear()

async def main():
    # Для локального теста polling — ок. Позже сделаем systemd/Docker по желанию.
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())