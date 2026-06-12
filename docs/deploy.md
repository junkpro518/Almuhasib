# VPS Deployment Guide

## 1. Initial server setup

```bash
# Create a dedicated user (no login shell)
sudo useradd -r -s /usr/sbin/nologin -d /opt/almuhasib almuhasib
sudo mkdir -p /opt/almuhasib
sudo chown almuhasib:almuhasib /opt/almuhasib
```

## 2. Copy project files

From your local machine:

```bash
rsync -av --exclude='.git' --exclude='.venv' --exclude='__pycache__' \
  /path/to/Almuhasib/ user@YOUR_VPS_IP:/opt/almuhasib/
```

## 3. Create virtualenv and install dependencies

```bash
sudo -u almuhasib bash -c "
  cd /opt/almuhasib
  python3 -m venv .venv
  .venv/bin/pip install -r requirements.txt
"
```

## 4. Download Amiri font

```bash
sudo -u almuhasib bash -c "
  mkdir -p /opt/almuhasib/pdf/fonts
  curl -L 'https://github.com/aliftype/amiri/releases/latest/download/Amiri-1.000.zip' \
    -o /tmp/amiri.zip
  unzip -j /tmp/amiri.zip 'Amiri-Regular.ttf' -d /opt/almuhasib/pdf/fonts/
"
```

## 5. Create .env file

```bash
sudo -u almuhasib nano /opt/almuhasib/.env
```

Paste and fill in:

```
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_OWNER_CHAT_ID=your_chat_id_here
REPORT_RECIPIENT_CHAT_ID=43444478
NOTION_API_KEY=secret_xxxxxxxxxxxx
NOTION_DATABASE_ID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
WEBHOOK_SECRET_KEY=choose_a_strong_random_secret
WEBHOOK_PORT=8080
```

Secure the file:

```bash
sudo chmod 600 /opt/almuhasib/.env
```

## 6. Install and start the systemd service

```bash
sudo cp /opt/almuhasib/almuhasib.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable almuhasib
sudo systemctl start almuhasib
```

Check status:

```bash
sudo systemctl status almuhasib
sudo journalctl -u almuhasib -f
```

## 7. Open firewall port

If using `ufw`:

```bash
sudo ufw allow 8080/tcp
```

If using `iptables`:

```bash
sudo iptables -A INPUT -p tcp --dport 8080 -j ACCEPT
```

## 8. Updating the bot

```bash
rsync -av --exclude='.git' --exclude='.venv' --exclude='__pycache__' \
  /path/to/Almuhasib/ user@YOUR_VPS_IP:/opt/almuhasib/

ssh user@YOUR_VPS_IP "sudo systemctl restart almuhasib"
```
