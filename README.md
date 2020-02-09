# Переадресация Телеграм

Сервис позволяет обойти блокировку и дать рабочую ссылку на Телеграм аккаунт, канал или чат.

### Build and deploy

```
docker-compose -f docker-compose.yml up --build -d
```

### Nginx configuration

```
upstream tg-redirect {
  server localhost:8000;
}

server {
  listen 80;
  listen [::]:80;

  error_log /var/log/nginx/error.log;
  access_log /var/log/nginx/access.log;

  location / {
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_pass http://tg-redirect;
  }

  location /files/ {
    root /srv/tg-redirect;
  }

  location /static/ {
   root /srv/tg-redirect/app;
  }
}
```
