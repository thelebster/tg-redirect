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
from telethon.tl.functions.users import GetFullUserRequest
from telethon.tl.functions.channels import GetFullChannelRequest
import logging
import uuid
import re
from bs4 import BeautifulSoup

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
MTPROXY_ENABLED = False if MTPROXY_HOST is None or MTPROXY_PORT is None or MTPROXY_SECRET is None else True

SHOW_INFO = os.getenv('SHOW_INFO', 'False')
DEVELOPMENT = os.getenv('DEVELOPMENT', 'False')

IMAGES_DIR = os.getenv('IMAGES_DIR', '/tmp/files/img')
SESSIONS_DIR = os.getenv('SESSIONS_DIR', '/tmp/sessions')
CACHE_DIR = os.getenv('CACHE_DIR', '/tmp/cache')


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
        # The API access for bot users is restricted. The method you tried to invoke cannot be executed as a bot (caused by CheckChatInviteRequest)
        # Parse t.me because to bot has no access.
        url = f'https://t.me/joinchat/{code}'
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                html = await response.text()
                soup = BeautifulSoup(html, 'html.parser')
                profile_image = soup.find(name='img', attrs={'class': 'tgme_page_photo_image'})
                profile_image_src = profile_image.attrs.get('src')
                try:
                    async with session.get(profile_image_src) as response:
                        chunk_size = 10
                        img_filename = f'{IMAGES_DIR}/{code}.jpg'
                        with open(img_filename, 'wb') as f:
                            while True:
                                chunk = await response.content.read(chunk_size)
                                if not chunk:
                                    break
                                f.write(chunk)
                except Exception as err:
                    logger.error(err)
                    pass
                page_title = soup.find(name='div', attrs={'class': 'tgme_page_title'})
                profile_name = page_title.contents[0].strip()
                page_description = soup.find(name='div', attrs={'class': 'tgme_page_description'})
                profile_status = page_description.contents[0].strip()
                return {
                    'profile_photo': f'{code}.jpg',
                    'profile_name': profile_name,
                    'profile_status': profile_status,
                    'location': location,
                    'base_path': f'https://{DOMAIN_NAME}',
                }
                pass


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
                if MTPROXY_ENABLED:
                    client = TelegramClient(
                        f'{SESSIONS_DIR}/{session_id}',
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
                else:
                    client = TelegramClient(f'{SESSIONS_DIR}/{session_id}', TELEGRAM_API_ID, TELEGRAM_API_HASH)

                await client.start(bot_token=TELEGRAM_BOT_TOKEN)
                # Enabling HTML as the default format
                client.parse_mode = 'html'

                # Try cache.
                cache_filename = f'{CACHE_DIR}/{name}.json'
                if post is not None:
                    cache_filename = f'{CACHE_DIR}/{name}-{post}.json'

                entity = {}
                if os.path.exists(cache_filename):
                    with open(cache_filename) as cache:
                        entity = json.load(cache)
                else:
                    if post is not None:
                        message_entity = await client.get_messages(name, ids=int(post))
                        logger.debug(message_entity)
                        entity['message_id'] = message_entity.id
                        if hasattr(message_entity, 'message'):
                            entity['message_text'] = message_entity.message
                        if hasattr(message_entity, 'raw_text'):
                            entity['message_raw_text'] = message_entity.raw_text
                        if hasattr(message_entity, 'text'):
                            entity['message_html'] = message_entity.text
                        if hasattr(message_entity, 'date'):
                            entity['message_date'] = str(message_entity.date)
                        if hasattr(message_entity, 'chat'):
                            entity['id'] = str(message_entity.chat.id)
                            entity['username'] = str(message_entity.chat.username)
                            if hasattr(message_entity.chat, 'broadcast'):
                                entity['broadcast'] = message_entity.chat.broadcast
                                entity['title'] = message_entity.chat.title
                    else:
                        profile_entity = await client.get_entity(name)
                        logger.debug(profile_entity)
                        if hasattr(profile_entity, 'broadcast'):
                            extended_profile_entity = await client(GetFullChannelRequest(name))
                            logger.debug(extended_profile_entity)
                        else:
                            extended_profile_entity = await client(GetFullUserRequest(name))
                            logger.debug(extended_profile_entity)

                        entity['id'] = profile_entity.id
                        if hasattr(profile_entity, 'bot'):
                            entity['bot'] = profile_entity.bot
                        entity['username'] = profile_entity.username
                        if hasattr(profile_entity, 'broadcast'):
                            entity['broadcast'] = profile_entity.broadcast
                            entity['title'] = profile_entity.title
                        if hasattr(profile_entity, 'first_name'):
                            entity['first_name'] = profile_entity.first_name
                        if hasattr(profile_entity, 'last_name'):
                            entity['last_name'] = profile_entity.last_name
                        if hasattr(extended_profile_entity, 'about'):
                            entity['about'] = extended_profile_entity.about
                        if hasattr(extended_profile_entity, 'full_chat'):
                            if hasattr(extended_profile_entity.full_chat, 'about'):
                                entity['about'] = extended_profile_entity.full_chat.about

                    with open(cache_filename, 'w') as cache:
                        json.dump(entity, cache, indent=4)

                if 'broadcast' in entity:
                    # This is channel or chat.
                    profile_name = entity.get('title', name)
                else:
                    # This is user or bot.
                    profile_name = ' '.join(list(filter(None, (entity.get('first_name', ''), entity.get('last_name', '')))))
                    if not profile_name.strip():
                        profile_name = entity.get('username', name)

                profile_status = re.sub(
                    '(^@|\s@)([a-zA-Z0-9_]+)(\s|$)',
                    ' <a href="tg://resolve?domain=\\2">@\\2</a>\\3',
                    entity.get('about', '')).strip()
                message_text = re.sub(
                    '(^@|\s@)([a-zA-Z0-9_]+)(\s|$)',
                    ' <a href="tg://resolve?domain=\\2">@\\2</a>\\3',
                    entity.get('message_html', '')).strip()

                # Try cache.
                img_filename = f'{IMAGES_DIR}/{name}.jpg'
                if not os.path.exists(img_filename):
                    profile_photo = await client.download_profile_photo(name, img_filename, download_big=False)

                return {
                    'profile_photo': f'{name}.jpg',
                    'profile_name': profile_name,
                    'profile_status': profile_status,
                    'message_text': message_text,
                    'location': location,
                    'base_path': f'https://{DOMAIN_NAME}',
                }
            except Exception as err:
                logger.error(err)

        return {
            'location': location,
            'base_path': f'https://{DOMAIN_NAME}',
        }


app = web.Application()
routes = [
    web.get('/', index, name='index'),
    web.post('/', index, name='index'),
    web.get(r'/{name:[a-zA-Z0-9_]+}', redirect, name='account'),
    web.get('/joinchat/{code}', redirect, name='joinchat'),
    web.get(r'/{name:[a-zA-Z0-9_]+}/{post:\d+}', redirect, name='post'),
]

if DEVELOPMENT == 'True':
    routes.append(web.static('/static/', pathlib.Path(__file__).parent / 'static', name='static'))
    routes.append(web.static('/files/img/', pathlib.Path(__file__).parent / '../img', name='img'))

app.add_routes(routes)
setup_jinja(app)

if __name__ == '__main__':
    web.run_app(app)
