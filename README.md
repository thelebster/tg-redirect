# Telegram forwarding service

On April 2018, [Telegram](https://telegram.org) was banned in Russia. This service allows you to share a working link to the Telegram account, channel or chat with an informative preview page.

![alt text][screenshot]

Preview page for the message from the [Oh My Py](https://t.me/ohmypy) Telegram channel.

## Build and deploy

### Use blacklist

Copy `samplelist.txt` to `config/blacklist.txt` and add blocked channels, one per line.

```
mkdir -p config \
&& cp samplelist.txt config/blacklist.txt
```

### Use whitelist

Copy `samplelist.txt` to `config/whitelist.txt` and add allowed channels that should be resolved, one per line.

```
mkdir -p config \
&& cp samplelist.txt config/whitelist.txt
```

```
docker-compose -f docker-compose.yml up --build -d
```

## Local development environment

Run from console:

```
DOMAIN_NAME=localhost:8080 \
IMAGES_DIR=./img \
DEVELOPMENT=True \
BLACKLIST_FILE=./config/blacklist.txt \
WHITELIST_FILE=./config/whitelist.txt \
python3 ./app/app.py
```

To run from PyCharm, copy variables below and paste into the Environment variables in the active configuration.

```
DOMAIN_NAME=localhost:8080
IMAGES_DIR=../files/img
DEVELOPMENT=True
BLACKLIST_FILE=../config/blacklist.txt
WHITELIST_FILE=../config/whitelist.txt
``` 

## Nginx configuration

```
upstream tg-redirect {
  server localhost:8000;
}

server {
  listen 80;
  listen [::]:80;

  error_log /var/log/nginx/error.log;
  access_log /var/log/nginx/access.log;

  error_page 400 /400.html;
  error_page 404 /404.html;
  error_page 451 /451.html;

  # Enable gzip compression.
  gzip on;
  gzip_disable "msie6";
  gzip_vary on;
  gzip_proxied any;
  gzip_comp_level 6;
  gzip_buffers 16 8k;
  gzip_http_version 1.1;
  gzip_types text/plain text/css application/json application/x-javascript text/xml application/xml application/xml+rss text/javascript;

  location / {
    proxy_intercept_errors on;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_pass http://tg-redirect;

    # Attach Yandex.Metrika counter.
    sub_filter_once on;
    sub_filter '</head>' '<!-- Yandex.Metrika counter --> <script type="text/javascript" > (function(m,e,t,r,i,k,a){m[i]=m[i]||function(){(m[i].a=m[i].a||[]).push(arguments)}; m[i].l=1*new Date();k=e.createElement(t),a=e.getElementsByTagName(t)[0],k.async=1,k.src=r,a.parentNode.insertBefore(k,a)}) (window, document, "script", "https://mc.yandex.ru/metrika/tag.js", "ym"); ym(57429748, "init", { clickmap:true, trackLinks:true, accurateTrackBounce:true }); </script> <noscript><div><img src="https://mc.yandex.ru/watch/57429748" style="position:absolute; left:-9999px;" alt="" /></div></noscript> <!-- /Yandex.Metrika counter -->';
  }

  location /files/img/ {
    root /srv/tg-redirect;
  }

  location /static/ {
    root /srv/tg-redirect/app;
    
    # Attach Yandex.Metrika counter.
    sub_filter_once on;
    sub_filter '</head>' '<!-- Yandex.Metrika counter --> <script type="text/javascript" > (function(m,e,t,r,i,k,a){m[i]=m[i]||function(){(m[i].a=m[i].a||[]).push(arguments)}; m[i].l=1*new Date();k=e.createElement(t),a=e.getElementsByTagName(t)[0],k.async=1,k.src=r,a.parentNode.insertBefore(k,a)}) (window, document, "script", "https://mc.yandex.ru/metrika/tag.js", "ym"); ym(57429748, "init", { clickmap:true, trackLinks:true, accurateTrackBounce:true }); </script> <noscript><div><img src="https://mc.yandex.ru/watch/57429748" style="position:absolute; left:-9999px;" alt="" /></div></noscript> <!-- /Yandex.Metrika counter -->';
  }

  location /robots.txt {
    root /srv/tg-redirect/app/static;
  }

  location /static/favicon.ico {
    root /srv/tg-redirect/app;
  }

  # Ignore any requests to *.php, because only a-z, 0-9, and underscores allowed.
  location ~ \.php$ {
    return 404;
  }

  location = /help {
    rewrite /help /static/help.html;    
  }

  location = /400.html {
    root /srv/tg-redirect/app/static;
  }

  location = /404.html {
    root /srv/tg-redirect/app/static;
  }

  location = /451.html {
    root /srv/tg-redirect/app/static;
  }
}
```

## Troubleshooting

If you just added `blacklist.txt` or `whitelist.txt` file and after restart checking is not work properly, try to restart service with a command below.

```
docker-compose -f docker-compose.yml up --build -d --force
```

## Changelog

**March 8, 2020**
* Use `whitelist.txt` to provide a list of allowed channels to make validation more strict.

**March 7, 2020**
* Remove Telethon from dependencies. Telegram API is not used anymore.
* Use `blacklist.txt` to provide a list of blocked channels.

**Feb 25, 2020**
* Add support for stickers `/addstickers` and mtproto proxy `/proxy?server=...` links.

**Feb 22, 2020**
* Parsing the t.me/username page directly to get details about the channel invitation.
* Checking if channel on a blacklist using comma separated values from the `BLACKLIST` environment variable.
* Switch to [Materialize](https://materializecss.com/) scss.

**Feb 13, 2020**
* Use Telegram API to fetch information about channel, like channel name, description and image.
* Serving static resources via Nginx.

**Feb 12, 2020** 
* Basic implementation. Show simple preview page with auto-redirect after 500 ms and a button. 

[screenshot]: common/images/ohmypy-post-screenshot.png "Page preview for Oh My Py Telegram channel (https://t.me/ohmypy)"
