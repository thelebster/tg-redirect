# Переадресация Телеграм

Сервис позволяет обойти блокировку и дать рабочую ссылку на Телеграм аккаунт, канал или чат.

### Build and deploy

```
docker-compose -f docker-compose.yml up --build -d
```

### Run local env

```
mkdir -p $PWD/app/dl
ln -s $PWD/app/dl /tmp/
```

```
TELEGRAM_API_ID=012345 \
TELEGRAM_API_HASH=abcdefghijklmnopqrstuvwxyz012345 \
TELEGRAM_BOT_TOKEN=012345678:ABCDefghIJKLmnopQRSTuvwxYZ012345678 \ 
python3 app/app.py
```
