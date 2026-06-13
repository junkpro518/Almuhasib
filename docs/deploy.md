# VPS Deployment Guide

Production runs as a Docker Compose app behind Traefik on the shared `proxy` network.

## 1. Server paths

- Project path: `/opt/projects/Almuhasib`
- Runtime env file: `/opt/projects/Almuhasib/.runtime.env`
- Public URL: `https://almuhasib.mohammed518.com`
- Shortcut endpoint: `POST https://almuhasib.mohammed518.com/transaction`

## 2. Copy project files

```bash
rsync -az --delete \
  --exclude='.git' \
  --exclude='.venv' \
  --exclude='__pycache__' \
  --exclude='.pytest_cache' \
  --exclude='.DS_Store' \
  /path/to/Almuhasib/ claude@109.199.111.27:/tmp/almuhasib-upload/
```

Then install on the VPS:

```bash
sudo mkdir -p /opt/projects/Almuhasib
sudo rsync -a --delete \
  --exclude='.git' \
  --exclude='.venv' \
  --exclude='__pycache__' \
  --exclude='.pytest_cache' \
  --exclude='.DS_Store' \
  /tmp/almuhasib-upload/ /opt/projects/Almuhasib/
sudo chown -R root:root /opt/projects/Almuhasib
```

## 3. Runtime environment

Create `/opt/projects/Almuhasib/.runtime.env` and keep it out of Git:

```
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_OWNER_CHAT_ID=your_chat_id_here
REPORT_RECIPIENT_CHAT_ID=43444478
NOTION_API_KEY=secret_xxxxxxxxxxxx
NOTION_DATABASE_ID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
WEBHOOK_SECRET_KEY=choose_a_strong_random_secret
WEBHOOK_PORT=8080
```

```bash
sudo chmod 600 /opt/projects/Almuhasib/.runtime.env
```

The Compose file uses `env_file.format: raw` so secrets containing `$` are passed as-is.

## 4. Start or update

Run from `/opt/projects/Almuhasib`:

```bash
sudo docker compose config
sudo docker compose up -d --build
sudo docker compose ps
```

Do not open port `8080` publicly. Traefik routes the domain to the container through the external Docker network `proxy`.

## 5. DNS

Cloudflare DNS record:

- Type: `A`
- Name: `almuhasib.mohammed518.com`
- Content: `109.199.111.27`
- Proxied: `false`

## 6. Verification

```bash
sudo docker inspect --format '{{.State.Health.Status}}' almuhasib
curl -sS -o /tmp/almuhasib_body.txt -w 'code=%{http_code} verify=%{ssl_verify_result}\n' \
  -X POST https://almuhasib.mohammed518.com/transaction \
  -H 'Content-Type: application/json' \
  --data '{}'
```

Expected unauthenticated result: HTTP `401`.
