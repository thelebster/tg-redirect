# Telegram forwarding service

On April 2018, Telegram was banned in Russia. This service allows you to share a working link to the Telegram account, channel or chat with an informative preview page.

![alt text][screenshot]

Preview page for the message from the [Oh My Py](https://t.me/ohmypy) Telegram channel.

## Build and deploy

```
docker-compose -f docker-compose.yml up --build -d
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
    sub_filter '</head>' '<!-- Yandex.Metrika counter --> <script type="text/javascript" > (function(m,e,t,r,i,k,a){m[i]=m[i]||function(){(m[i].a=m[i].a||[]).push(arguments)}; m[i].l=1*new Date();k=e.createElement(t),a=e.getElementsByTagName(t)[0],k.async=1,k.src=r,a.parentNode.insertBefore(k,a)}) (window, document, "script", "https://mc.yandex.ru/metrika/tag.js", "ym"); ym(57429748, "init", { clickmap:true, trackLinks:true, accurateTrackBounce:true }); </script> <noscript><div><img src="https://mc.yandex.ru/watch/57429748" style="position:absolute; left:-9999px;" alt="" /></div></noscript> <!-- /Yandex.Metrika counter -->'
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

  location /static/favicon.ico {
    root /srv/tg-redirect/app;
  }

  # Ignore any requests to *.php, because only a-z, 0-9, and underscores allowed.
  location ~ \.php$ {
    return 404;
  }

  location = /help {
    rewrite /help /static/help.html;

    # Attach Yandex.Metrika counter.
    sub_filter_once on;
    sub_filter '</head>' '<!-- Yandex.Metrika counter --> <script type="text/javascript" > (function(m,e,t,r,i,k,a){m[i]=m[i]||function(){(m[i].a=m[i].a||[]).push(arguments)}; m[i].l=1*new Date();k=e.createElement(t),a=e.getElementsByTagName(t)[0],k.async=1,k.src=r,a.parentNode.insertBefore(k,a)}) (window, document, "script", "https://mc.yandex.ru/metrika/tag.js", "ym"); ym(57429748, "init", { clickmap:true, trackLinks:true, accurateTrackBounce:true }); </script> <noscript><div><img src="https://mc.yandex.ru/watch/57429748" style="position:absolute; left:-9999px;" alt="" /></div></noscript> <!-- /Yandex.Metrika counter -->'
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

## Changelog

**March 7, 2020**
* Remove Telethon from dependencies.

**Feb 25, 2020**
* Add support for stickers `/addstickers` and mtproto proxy `/proxy?server=...` links.

**Feb 22, 2020**
* Parsing the t.me/username page directly to get details about the channel invitation.
* Checking if channel on a blacklist using comma separated values from the `BLACKLIST` environment variable.
* Switch to [Materialize](https://materializecss.com/) scss.

**Feb 13, 2020**
* Use Telergam API to fetch information about channel, like channel name, description and image.
* Serving static resources via Nginx.

**Feb 12, 2020** 
* Basic implementation. Show simple preview page with auto-redirect after 500 ms and a button. 

[screenshot]: common/images/ohmypy-post-screenshot.png "Page preview for Oh My Py Telegram channel (https://t.me/ohmypy)"
