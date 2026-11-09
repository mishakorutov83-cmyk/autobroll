#!/usr/bin/env bash
# One-command setup of the video agent on a fresh Ubuntu 22.04 / 24.04 server (run as root).
#
#   curl -fsSL https://raw.githubusercontent.com/mishakorutov83-cmyk/autobroll/claude/determined-cray-29iq60/deploy/server-setup.sh -o setup.sh
#   bash setup.sh
#
# It installs Docker, a firewall (22/80/443 only), fail2ban and a swap file, downloads the code to /opt/autobroll,
# asks for the keys (typed on the server, never in a chat), and starts the agent behind Caddy with an automatic HTTPS
# address https://<ip-with-dashes>.sslip.io (or your own domain). Safe to run again: it updates the code and restarts.
# Test mode: DRY_RUN=1 NONINTERACTIVE=1 DIR=/tmp/x WEB_PASSWORD=… bash deploy/server-setup.sh  (only writes the .env)
set -euo pipefail

REPO="${REPO:-https://github.com/mishakorutov83-cmyk/autobroll.git}"
BRANCH="${BRANCH:-claude/determined-cray-29iq60}"
DIR="${DIR:-/opt/autobroll}"
DRY_RUN="${DRY_RUN:-}"
TTY=/dev/tty

say() { printf '\n\033[1;36m== %s\033[0m\n' "$*"; }
warn() { printf '\033[1;33m!! %s\033[0m\n' "$*"; }

# ask VAR "question" [default]  — keeps a value already given through the environment
ask() {
  local var=$1 prompt=$2 def=${3:-} val=""
  [ -n "${!var:-}" ] && return 0
  if [ -z "${NONINTERACTIVE:-}" ] && [ -r "$TTY" ]; then read -r -p "$prompt${def:+ [$def]}: " val <"$TTY" || true; fi
  printf -v "$var" '%s' "${val:-$def}"
}
ask_secret() {
  local var=$1 prompt=$2 val=""
  [ -n "${!var:-}" ] && return 0
  if [ -z "${NONINTERACTIVE:-}" ] && [ -r "$TTY" ]; then read -r -s -p "$prompt: " val <"$TTY" || true; echo; fi
  printf -v "$var" '%s' "$val"
}

if [ -z "$DRY_RUN" ]; then
  [ "$(id -u)" = 0 ] || { echo "Запустите от root (ssh root@<ip>)."; exit 1; }
  export DEBIAN_FRONTEND=noninteractive

  say "1/7 Система и базовые пакеты"
  apt-get update -y
  apt-get install -y ca-certificates curl git ufw fail2ban openssl
  free -h | head -2; df -h / | tail -1

  say "2/7 Файл подкачки (swap) — запас памяти для рендера"
  if [ "$(swapon --show --noheadings | wc -l)" = 0 ]; then
    fallocate -l 4G /swapfile || dd if=/dev/zero of=/swapfile bs=1M count=4096
    chmod 600 /swapfile && mkswap /swapfile && swapon /swapfile
    grep -q '^/swapfile' /etc/fstab || echo '/swapfile none swap sw 0 0' >> /etc/fstab
  else
    echo "swap уже есть"
  fi

  say "3/7 Docker"
  if ! command -v docker >/dev/null 2>&1; then
    install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
    chmod a+r /etc/apt/keyrings/docker.asc
    # shellcheck disable=SC1091
    codename=$(. /etc/os-release && echo "$VERSION_CODENAME")
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu $codename stable" \
      > /etc/apt/sources.list.d/docker.list
    apt-get update -y
    apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
  fi
  systemctl enable --now docker
  docker --version && docker compose version

  say "4/7 Защита: файрвол (открыты только SSH, 80, 443) и fail2ban"
  ssh_port=$(ss -tlnp 2>/dev/null | awk '/sshd/ {n=split($4,a,":"); print a[n]}' | sort -u | sed -n 1p || true)
  ufw default deny incoming
  ufw default allow outgoing
  ufw allow "${ssh_port:-22}/tcp"
  ufw allow 22/tcp
  ufw allow 80/tcp
  ufw allow 443/tcp
  ufw --force enable
  systemctl enable --now fail2ban

  say "5/7 Код агента → $DIR"
  if [ -d "$DIR/.git" ]; then
    git -C "$DIR" fetch origin "$BRANCH"
    git -C "$DIR" reset --hard "origin/$BRANCH"
  else
    git clone -b "$BRANCH" "$REPO" "$DIR"
  fi
else
  mkdir -p "$DIR"
fi

say "6/7 Настройки (.env)"
ip=$(curl -4 -fsS --max-time 10 https://api.ipify.org 2>/dev/null || hostname -I 2>/dev/null | awk '{print $1}' || true)
default_domain="${ip//./-}.sslip.io"
touch "$DIR/.env" && chmod 600 "$DIR/.env"

# values already in .env stay; only missing keys are asked for and appended
have() { grep -q "^$1=" "$DIR/.env"; }
put() { have "$1" || printf '%s=%s\n' "$1" "$2" >> "$DIR/.env"; }

generated=""
if ! have WEB_PASSWORD; then
  ask_secret WEB_PASSWORD "Код входа в приложение (Enter — сгенерировать)"
  if [ -z "${WEB_PASSWORD:-}" ]; then WEB_PASSWORD=$(openssl rand -hex 10); generated=1; fi
  put WEB_PASSWORD "$WEB_PASSWORD"
fi
if ! have ANTHROPIC_API_KEY; then
  ask_secret ANTHROPIC_API_KEY "Ключ Claude API (sk-ant-…, Enter — пропустить)"
  put ANTHROPIC_API_KEY "${ANTHROPIC_API_KEY:-}"
fi
if ! have BOT_TOKEN; then
  ask_secret BOT_TOKEN "Токен Telegram-бота от @BotFather (Enter — без бота)"
  put BOT_TOKEN "${BOT_TOKEN:-}"
fi
if ! have ALLOWED_USERS; then
  ask ALLOWED_USERS "Ваш Telegram id (от @userinfobot; несколько — через запятую)"
  put ALLOWED_USERS "${ALLOWED_USERS:-}"
fi
if ! have DOMAIN; then
  ask DOMAIN "Домен (Enter — $default_domain, бесплатный адрес с HTTPS)" "$default_domain"
  put DOMAIN "$DOMAIN"
fi
domain=$(grep '^DOMAIN=' "$DIR/.env" | head -1 | cut -d= -f2-)
put PUBLIC_URL "https://$domain"
put AGENT_BIND "127.0.0.1"     # the app is reachable only through Caddy (HTTPS), not directly on port 8080
put COMPOSE_PROFILES "https"   # plain «docker compose up -d --build» now includes Caddy
put AGENT_PROFILE "balanced"
echo ".env готов ($DIR/.env, права 600)"

if [ -n "$DRY_RUN" ]; then echo "DRY_RUN: на этом остановились"; exit 0; fi

say "7/7 Сборка и запуск (первый раз 10–20 минут: качаются Chrome для рендера, библиотеки)"
cd "$DIR"
docker compose up -d --build

say "Жду, пока адрес заработает (сертификат HTTPS выпускается за 10–60 секунд)"
ok=""
for _ in $(seq 1 36); do
  if curl -fsS --max-time 8 "https://$domain/health" 2>/dev/null | grep -qx ok; then ok=1; break; fi
  sleep 5
done

echo
if [ -n "$ok" ]; then
  printf '\033[1;32m✔ Готово.\033[0m\n'
else
  warn "Адрес пока не отвечает. Посмотрите: cd $DIR && docker compose logs --tail 40 caddy agent"
fi
echo "Приложение:  https://$domain"
if [ -n "$generated" ]; then echo "Код входа:   $WEB_PASSWORD   (запишите; он же лежит в $DIR/.env)"; else echo "Код входа:   тот, что вы ввели (или стоит в $DIR/.env)"; fi
echo "Логи:        cd $DIR && docker compose logs -f agent"
echo "Обновление:  bash $DIR/deploy/server-setup.sh"
