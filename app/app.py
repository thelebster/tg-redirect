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
from telethon import TelegramClient, connection
import logging
import uuid

logging.basicConfig(format='%(asctime)s - %(levelname)s - %(name)s - %(message)s', level=logging.DEBUG)
logger = logging.getLogger(__file__)

TEMPLATES_ROOT = pathlib.Path(__file__).parent / 'templates'

DOMAIN_NAME = os.getenv('DOMAIN_NAME')

# Get your own api_id and api_hash from https://my.telegram.org, under API Development.
TELEGRAM_API_ID = os.getenv('TELEGRAM_API_ID')
TELEGRAM_API_HASH = os.getenv('TELEGRAM_API_HASH')
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')

MTPROXY_HOST = os.getenv('MTPROXY_HOST')
MTPROXY_PORT = os.getenv('MTPROXY_PORT')
MTPROXY_SECRET = os.getenv('MTPROXY_SECRET')

SHOW_INFO = os.getenv('SHOW_INFO', 'False')


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

            redirect_url = f'https://{DOMAIN_NAME}/{path[0]}'
            if len(path) == 2:
                redirect_url = f'https://{DOMAIN_NAME}/{path[0]}/{path[1]}'
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

        if name is not None and SHOW_INFO == 'True':
            try:
                session_id = str(uuid.uuid1())
                client = TelegramClient(
                    f'/tmp/sessions/{session_id}',
                    TELEGRAM_API_ID,
                    TELEGRAM_API_HASH,
                    # Use one of the available connection modes.
                    # Normally, this one works with most proxies.
                    connection=connection.ConnectionTcpMTProxyRandomizedIntermediate,
                    # Then, pass the proxy details as a tuple:
                    #     (host name, port, proxy secret)
                    #
                    # If the proxy has no secret, the secret must be:
                    #     '00000000000000000000000000000000'
                    proxy=(MTPROXY_HOST, int(MTPROXY_PORT), MTPROXY_SECRET)
                )
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

                profile_photo = await client.download_profile_photo(name, f'/tmp/files/img/{name}.jpg', download_big=False)
                return {
                    'profile_photo': f'{name}.jpg',
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
                web.get('/{name}/{post}', redirect, name='post')])

setup_jinja(app)

if __name__ == '__main__':
    web.run_app(app)
