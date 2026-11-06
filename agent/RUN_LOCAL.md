# Запуск бота на своём компьютере

Бот работает, пока компьютер включён и Docker запущен. Нужно: 16 ГБ памяти (минимум 8),
~20 ГБ свободного места, Windows 10/11 или macOS.

## 1. Один раз: установить программы
- **Docker Desktop** — https://www.docker.com/products/docker-desktop/ (на Windows при установке согласиться на WSL 2,
  после установки перезагрузить компьютер и запустить Docker Desktop).
- **Git** — https://git-scm.com/downloads (на macOS уже есть).

## 2. Один раз: получить ключи
| Что | Где | Строка в `.env` |
|---|---|---|
| Токен бота | Telegram → @BotFather → /newbot | `BOT_TOKEN` |
| Ваш Telegram id | Telegram → @userinfobot | `ALLOWED_USERS` |
| api_id и api_hash — *необязательно*, только для файлов > 20 МБ прямо в бота | https://my.telegram.org → API development tools | `TELEGRAM_API_ID`, `TELEGRAM_API_HASH`, `BOT_API_URL` |
| Ключ Claude API | https://console.anthropic.com → API keys (нужен баланс) | `ANTHROPIC_API_KEY` |

> Из России Claude API не открывается — на компьютере должен быть включён VPN в режиме
> «для всей системы» (TUN), иначе бот будет падать на шаге «Монтирую».

## 3. Один раз: скачать проект и вписать ключи
Открыть терминал (Windows: PowerShell; macOS: Терминал):
```bash
git clone -b claude/determined-cray-29iq60 https://github.com/mishakorutov83-cmyk/autobroll.git
cd autobroll
cp .env.example .env
```
Открыть файл `.env` в Блокноте (Windows: `notepad .env`, macOS: `open -e .env`), вписать ключи после `=`, сохранить.

## 4. Запуск
```bash
docker compose up -d --build
```
Так бот принимает ссылки на Google Drive (любой размер) и видеофайлы до 20 МБ.
Чтобы присылать большие файлы прямо в бота: заполнить `TELEGRAM_API_ID`, `TELEGRAM_API_HASH`,
раскомментировать `BOT_API_URL` в `.env` и запускать `docker compose --profile bigfiles up -d --build`.
Первый раз — 15–25 минут: скачиваются модель распознавания речи (~1,5 ГБ), браузер для рендера, шрифты.
Дальше запуск за секунды. Проверить, что бот жив: написать ему в Telegram `/start`.

## Каждый день
| Что | Команда (в папке autobroll) |
|---|---|
| Остановить | `docker compose down` |
| Запустить снова | `docker compose up -d` |
| Посмотреть, что делает бот | `docker compose logs -f agent` |
| Обновить до новой версии | `git pull` и `docker compose up -d --build` |

Готовые ролики лежат в папке `autobroll/out`, исходники и планы — в `autobroll/work/agent`.
