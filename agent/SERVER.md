# Установка на сервер (Ubuntu 22.04 / 24.04)

Одна команда ставит Docker, файрвол (открыты только SSH, 80 и 443), fail2ban и swap, скачивает код в `/opt/autobroll`,
спрашивает ключи (вводятся на сервере) и запускает агент за Caddy с автоматическим HTTPS-адресом
`https://<ip-через-дефисы>.sslip.io` (или вашим доменом). Приложение не публикуется напрямую на порту 8080.

```bash
ssh root@<IP сервера>
curl -fsSL https://raw.githubusercontent.com/mishakorutov83-cmyk/autobroll/claude/determined-cray-29iq60/deploy/server-setup.sh -o setup.sh
bash setup.sh
```

Скрипт спросит: код входа в приложение (Enter — сгенерирует), ключ Claude API, токен Telegram-бота, ваш Telegram id, домен (Enter — `sslip.io`).
Первая сборка 10–20 минут. В конце он проверит адрес и напечатает его.

**Важно:** один и тот же Telegram-бот не может работать в двух местах сразу. Прежде чем запускать на сервере, остановите агента на ПК
(`docker compose down` в папке `autobroll`).

## Каждый день
| Что | Команда (на сервере) |
|---|---|
| Логи | `cd /opt/autobroll && docker compose logs -f agent` |
| Обновить до новой версии | `bash /opt/autobroll/deploy/server-setup.sh` |
| Перезапустить | `cd /opt/autobroll && docker compose restart agent` |
| Остановить | `cd /opt/autobroll && docker compose down` |
| Свободное место | `df -h /` |

Исходные видео — в `/opt/autobroll/inbox/`, готовые — в `/opt/autobroll/out/ready/` (скачивать через SFTP, например WinSCP).
Настройки — `/opt/autobroll/.env` (права 600; после правки: `docker compose up -d`).

Если адрес не открывается: в панели хостинга должны быть открыты порты 80 и 443; `docker compose logs --tail 40 caddy` покажет, выпущен ли сертификат.
