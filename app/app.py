import asyncio
import logging
import pathlib
import aiohttp
from aiohttp import web
import aiohttp_jinja2
import jinja2
import os
import json
from urllib.parse import urlparse

TEMPLATES_ROOT = pathlib.Path(__file__).parent / 'templates'
STATIC_ROOT = pathlib.Path(__file__).parent / 'static'


def setup_jinja(app):
    loader = jinja2.FileSystemLoader(str(TEMPLATES_ROOT))
    jinja_env = aiohttp_jinja2.setup(app, loader=loader)
    return jinja_env


@aiohttp_jinja2.template('index.html')
async def index(request):
    if request.method == 'GET':
        return {}

    if request.method == 'POST' and request.can_read_body:
        try:
            data = await request.post()
            source_url = data.get('url')
            if source_url is None or not source_url.strip():
                return {}

            url = urlparse(source_url)
            if url.netloc != 't.me':
                raise Exception('Указан неверный адрес.')

            path = url.path.split('/')
            path.pop(0)

            redirect_url = f'https://tg.nnm.guru/{path[0]}'
            if len(path) == 2:
                redirect_url = f'https://tg.nnm.guru/{path[0]}/{path[1]}'
                if path[0] != 'joinchat' and not path[1].isnumeric():
                    raise Exception('Номер сообщения должен быть числом.')

            return {
                'source_url': source_url,
                'redirect_url': redirect_url,
            }
        except Exception as err:
            return {
                'source_url': source_url,
                'error': str(err),
            }
    else:
        return {}


@aiohttp_jinja2.template('redirect.html')
async def redirect(request):
    route_name = request.match_info.route.name
    if route_name == 'account':
        name = request.match_info.get('name')
        location = f'tg://resolve?domain={name}'

    if route_name == 'joinchat':
        code = request.match_info.get('code')
        location = f'tg://join?invite={code}'

    if route_name == 'post':
        name = request.match_info.get('name')
        post = request.match_info.get('post')
        if not post.isnumeric():
            return {}

        location = f'tg://resolve?domain={name}&post={post}'

    if location is None:
        return {}
    else:
        return {
            'location': location,
        }


app = web.Application()
app.add_routes([web.get('/', index, name='index'),
                web.post('/', index, name='index'),
                web.get('/{name}', redirect, name='account'),
                web.get('/joinchat/{code}', redirect, name='joinchat'),
                web.get('/{name}/{post}', redirect, name='post'),
                web.static('/static/', path=str(STATIC_ROOT), name='static')])

setup_jinja(app)

if __name__ == '__main__':
    web.run_app(app)
