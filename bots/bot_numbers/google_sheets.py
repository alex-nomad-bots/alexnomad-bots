import gspread
from oauth2client.service_account import ServiceAccountCredentials
import os
from dotenv import load_dotenv
from datetime import datetime
import pytz
from gspread_formatting import DataValidationRule, BooleanCondition, set_data_validation_for_cell_range
from gspread_formatting import format_cell_range, CellFormat, Color
from gspread_formatting import CellFormat, set_data_validation_for_cell_range
from gspread_formatting.dataframe import format_with_dataframe
load_dotenv()

GOOGLE_KEY_PATH = os.getenv('GOOGLE_KEY_PATH')
GOOGLE_SHEET_URL = os.getenv('GOOGLE_SHEET_URL')
SHEET_NAME = 'Заявки'


scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
credentials = ServiceAccountCredentials.from_json_keyfile_name(GOOGLE_KEY_PATH, scope)
gc = gspread.authorize(credentials)
sh = gc.open_by_url(GOOGLE_SHEET_URL)

## Создание листа, если его нет
try:
    worksheet = sh.worksheet(SHEET_NAME)
except gspread.exceptions.WorksheetNotFound:
    worksheet = sh.add_worksheet(title=SHEET_NAME, rows="1000", cols="11")
    worksheet.append_row([
        "Telegram ID", "Ник", "Номер самоката", "Стороны", "Дата", "Статус", "Уведомлено",
        "Перед (☑️)", "Зад (☑️)", "Лево (☑️)", "Право (☑️)"
    ])

def ensure_checkboxes():
    rule = DataValidationRule(
        condition=BooleanCondition('BOOLEAN'),
        showCustomUi=True
    )
    checkbox_range = 'H2:K1000'  # ← обновлённая строка
    set_data_validation_for_cell_range(worksheet, checkbox_range, rule)

# В любом случае применим чекбоксы
ensure_checkboxes()

def add_entry(user_id, username, number, sides):
    try:
        print("🚀 Попытка записи в таблицу...")
        date_now = datetime.now().strftime('%d.%m.%Y | %H:%M')

        print(f"Записываем данные: {user_id}, {username}, {number}, {', '.join(sides)}, {date_now}, 'В работе', ''")

        result = worksheet.append_row([
            str(user_id),
            username,
            number,
            ', '.join(sides),
            date_now,
            'В работе',
            '',         # Уведомлено
            False,  # сюда добавим чекбоксы
            False,
            False,
            False
        ])

        print(f"Результат записи: {result}")
        print("✅ Запись прошла успешно!")

    except Exception as e:
        print("❌ Ошибка при записи в таблицу:", e)

def get_status_updates():
    worksheet = sh.worksheet(SHEET_NAME)
    data = worksheet.get_all_records()
    result = []

    for idx, row in enumerate(data, start=2):  # начинаем с 2 из-за заголовков
        status = str(row.get("Статус", "")).strip().lower()
        notified = str(row.get("Уведомлено", "")).strip()

        if status in ["готово", "номер отсутствует"] and notified == "":
            result.append({
                "row_index": idx,
                "user_id": row.get("Telegram ID"),
                "username": row.get("Ник"),
                "scooter_number": row.get("Номер самоката"),
                "status": status
            })

            worksheet.update_cell(idx, 7, "✅")  # отметка как уведомлён

    return result

def get_todays_entries():
    today = datetime.now(pytz.timezone("Europe/Moscow")).strftime('%d.%m.%Y')
    entries = []
    for row in worksheet.get_all_records():
        if row['Дата'].startswith(today):
            entries.append({
                "number": row["Номер самоката"],
                "sides": row["Стороны"],
                "status": row.get("Статус", "")
            })
    return entries

def highlight_next_empty_row():
    worksheet = sh.worksheet(SHEET_NAME)
    values = worksheet.col_values(1)
    next_row = len(values) + 1

    # Попытка вставить строку, если она ещё не существует
    try:
        worksheet.insert_row([''] * 11, index=next_row)
    except gspread.exceptions.APIError as e:
        print(f"⚠️ Строка уже существует или не удалось вставить: {e}")

    # Затем окрашиваем
    yellow_fill = CellFormat(backgroundColor=Color(1, 1, 0))  # жёлтый
    cell_range = f"A{next_row}:K{next_row}"
    format_cell_range(worksheet, cell_range, yellow_fill)

if __name__ == "__main__":
    try:
        highlight_next_empty_row()
    except Exception as e:
        print(f"❌ Ошибка при создании и заливке строки: {e}")