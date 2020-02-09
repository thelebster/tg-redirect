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
from telethon import TelegramClient
import logging
import uuid

logging.basicConfig(format='%(asctime)s - %(levelname)s - %(name)s - %(message)s', level=logging.DEBUG)
logger = logging.getLogger(__file__)

TEMPLATES_ROOT = pathlib.Path(__file__).parent / 'templates'
STATIC_ROOT = pathlib.Path(__file__).parent / 'static'
DOWNLOADS_ROOT = pathlib.Path(__file__).parent / 'dl'

# Get your own api_id and api_hash from https://my.telegram.org, under API Development.
TELEGRAM_API_ID = os.getenv('TELEGRAM_API_ID')
TELEGRAM_API_HASH = os.getenv('TELEGRAM_API_HASH')
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')


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
            logger.error(err)
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
        try:
            name
        except NameError:
            name = None

        try:
            post
        except NameError:
            post = None

        if name is not None:
            try:
                session_id = str(uuid.uuid1())
                client = TelegramClient(session_id, TELEGRAM_API_ID, TELEGRAM_API_HASH)
                await client.start(bot_token=TELEGRAM_BOT_TOKEN)
                profile = await client.get_entity(name)
                if hasattr(profile, 'broadcast'):
                    # This is channel or chat.
                    profile_name = profile.title
                else:
                    # This is user or bot.
                    profile_name = ' '.join(list(filter(None, (profile.first_name, profile.last_name))))
                    if not profile_name.strip():
                        profile_name = profile.username

                profile_photo = await client.download_profile_photo(name, f'/tmp/dl/img/{name}.jpg', download_big=False)
                # Fix file permissions.
                os.chmod(profile_photo, 0o777)
                return {
                    'profile_photo': f'img/{name}.jpg',
                    'profile_name': profile_name,
                    'location': location,
                }
            except Exception as err:
                logger.error(err)

        return {
            'location': location,
        }


app = web.Application()
app.add_routes([web.get('/', index, name='index'),
                web.post('/', index, name='index'),
                web.get('/{name}', redirect, name='account'),
                web.get('/joinchat/{code}', redirect, name='joinchat'),
                web.get('/{name}/{post}', redirect, name='post'),
                web.static('/static/', path=str(STATIC_ROOT), name='static'),
                web.static('/dl/', path=str(DOWNLOADS_ROOT), name='dl')])

setup_jinja(app)

if __name__ == '__main__':
    web.run_app(app)
