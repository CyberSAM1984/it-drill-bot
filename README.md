# IT Drill Bot 🤖

Telegram-тренажёр IT-инженера: 227 вопросов по 9 темам (Junior/Middle/Senior)
+ 26 разборов реальных инцидентов (P1–P3).

## Структура

```
it-drill-bot/
├── bot.py             # весь бот (движок + хендлеры)
├── requirements.txt
├── .env               # BOT_TOKEN=... (не коммитить!)
├── .env.example
├── data/
│   ├── questions.json # база вопросов (key, t, lvl, th, q, a, d, f, code, hard)
│   ├── cases.json     # инциденты (sev, tag, sym, out, hyp, diag, cause, fix, trap)
│   └── progress.json  # создаётся сам (активные сессии)
└── README.md
```

## Команды бота

- `/quiz` — 10 случайных вопросов
- `/topic` — выбрать тему (Linux, Сети, БД, ...)
- `/level` — выбрать уровень (Junior/Middle/Senior)
- `/case` — разбор инцидента; `/case_show` — показать решение
- `/stats` — статистика базы
- `/cancel` — сбросить сессию

Формат: бот задаёт вопрос → ты отвечаешь своими словами → бот показывает
подробный разбор + follow-up вопросы → в конце самооценка по кнопкам.

## Локальный запуск (Windows)

```bat
py -m venv venv
venv\Scripts\pip install -r requirements.txt
copy .env.example .env   :: вписать токен от @BotFather
venv\Scripts\python bot.py
```

## Запуск на VPS (Linux, systemd)

```bash
sudo useradd -m -s /usr/sbin/nologin drillbot
sudo mkdir -p /opt/it-drill-bot && sudo chown $USER /opt/it-drill-bot
# скопировать файлы проекта в /opt/it-drill-bot
cd /opt/it-drill-bot
python3 -m venv venv && venv/bin/pip install -r requirements.txt
```

`/etc/systemd/system/it-drill-bot.service`:

```ini
[Unit]
Description=IT Drill Telegram Bot
After=network-online.target

[Service]
User=drillbot
WorkingDirectory=/opt/it-drill-bot
ExecStart=/opt/it-drill-bot/venv/bin/python bot.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
sudo chown -R drillbot:drillbot /opt/it-drill-bot
sudo systemctl daemon-reload
sudo systemctl enable --now it-drill-bot
journalctl -u it-drill-bot -f   # логи
```
