# Alex Nomad | Telegram Bots Studio

Разработка Telegram-ботов под ключ:
- автоматизация процессов
- интеграция с Google Sheets / CRM / API
- уведомления, отчётность, бронирование, заявки

Технологии:
- Python 3.x
- Aiogram 3.x
- Google Sheets API (gspread)
- APScheduler
- Docker / systemd деплой

## Структура репозитория

bots/
- bot_reports/      # бот ежедневных отчётов мастеров
- bot_numbers/      # бот учёта заказов и статусов готовности
- bot_booking/      # бот записи/бронирования (в разработке)
- bot_shop/         # бот-каталог с заказом и оплатой (в разработке)

core/
- gsheet_service.py # модуль для работы с Google Sheets
- logger.py         # единый логгер
- utils.py          # вспомогательные функции
- config_template.py# структура конфигурации (без секретов)

deploy/
- systemd/          # сервисы для запуска на сервере
- docker/           # Dockerfile и docker-compose (опционально)

## Автор
Alex Nomad
Telegram: @Kudinovv_AM
