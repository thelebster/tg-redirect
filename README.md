# Telegram forwarding service

On April 2018, Telegram was banned in Russia. This service allows you to share a working link to the Telegram account, channel or chat with an informative preview page.

Сервис для переадресации Телеграм позволяет обойти блокировку и дать рабочую ссылку на Телеграм аккаунт, канал или чат.

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

  error_page 404 /404.html;

  location / {
    proxy_intercept_errors on;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_pass http://tg-redirect;
  }

  location /files/img/ {
    root /srv/tg-redirect;
  }

  location /static/ {
   root /srv/tg-redirect/app;
  }

  location /robots.txt {
    root /srv/tg-redirect/app/static;
  }

  location /favicon.ico {
    root /srv/tg-redirect/app/static;
  }

  # Ignore any requests to *.php, because only a-z, 0-9, and underscores allowed.
  location ~ \.php$ {
    return 404;
  }

  location = /404.html {
    root /srv/tg-redirect/app/static;
  }
}
```

#### Disabling MTProxy

Remove MTPROXY_* variables from .env to disable MTProxy.
