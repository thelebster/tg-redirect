import asyncio
import pathlib
import aiohttp
from aiohttp import web
import aiohttp_jinja2
import jinja2
import os
from urllib.parse import urlparse, parse_qs
import logging
import re
from bs4 import BeautifulSoup

logging.basicConfig(format='%(asctime)s - %(levelname)s - %(name)s - %(message)s', level=logging.DEBUG)
logger = logging.getLogger(__file__)

TEMPLATES_ROOT = pathlib.Path(__file__).parent / 'templates'
DOMAIN_NAME = os.getenv('DOMAIN_NAME')
DEVELOPMENT = os.getenv('DEVELOPMENT', 'False')
USE_PARSER = os.getenv('USE_PARSER', 'True')
IMAGES_DIR = os.getenv('IMAGES_DIR', '/tmp/files/img')
BLACKLIST = os.getenv('BLACKLIST', '')

BLACKLIST_FILE = os.getenv('BLACKLIST_FILE', '/config/blacklist.txt')
if os.path.exists(BLACKLIST_FILE) and os.path.isfile(BLACKLIST_FILE):
    with open(BLACKLIST_FILE) as blacklist_file:
        lines = blacklist_file.readlines()
        if len(lines) > 0:
            lines.append(BLACKLIST)
            BLACKLIST = ','.join(lines)
            logger.debug(f'Blacklisted channels: {BLACKLIST}')

WHITELIST = ''
WHITELIST_FILE = os.getenv('WHITELIST_FILE', '/config/whitelist.txt')
if os.path.exists(WHITELIST_FILE) and os.path.isfile(WHITELIST_FILE):
    with open(WHITELIST_FILE) as whitelist_file:
        lines = whitelist_file.readlines()
        if len(lines) > 0:
            lines.append(WHITELIST)
            WHITELIST = ','.join(lines)
            logger.debug(f'Whitelisted channels: {WHITELIST}')


def setup_jinja(app):
    loader = jinja2.FileSystemLoader(str(TEMPLATES_ROOT))
    jinja_env = aiohttp_jinja2.setup(app, loader=loader)
    return jinja_env


@aiohttp_jinja2.template('index.html')
async def index(request):
    if request.method == 'GET':
        return {}

    if request.method == 'POST' and request.can_read_body:
        redirect_hostname = DOMAIN_NAME if not DOMAIN_NAME.strip() else request.host
        redirect_scheme = 'https'
        try:
            data = await request.post()
            source_url = data.get('url')
            if source_url is None or not source_url.strip():
                return {}

            url = urlparse(source_url)
            query_string = url.query
            query_string_dict = parse_qs(url.query)
            default_scheme = 'https://'
            default_hostname = 't.me/'
            path = url.path.replace(default_hostname, '').strip("/")
            url = ''.join([default_scheme, default_hostname, path])
            url = urlparse(url)
            if url.netloc != 't.me':
                raise Exception('Указан неверный адрес.')

            path = url.path.split('/')
            path.pop(0)

            redirect_path = f'{path[0]}'
            if re.match(r'^[a-zA-Z0-9_]{5,}$', redirect_path) is None:
                raise Exception('Имя пользователя может содержать буквы латинского алфавита (a–z), цифры (0–9) и символ подчеркивания (_). Минимальная длина 5 символов.')

            fixed_paths = ['joinchat', 'addstickers']
            if len(path) == 2:
                redirect_path = f'{path[0]}/{path[1]}'
                if path[0] not in fixed_paths and not path[1].isnumeric():
                    raise Exception('Номер сообщения должен быть числом.')

            if redirect_path == 'proxy' and len(query_string_dict) == 3:
                server = query_string_dict.get('server', None)[0]
                port = query_string_dict.get('port', None)[0]
                secret = query_string_dict.get('secret', None)[0]
                try:
                    validate_proxy(server, port, secret)
                except Exception as err:
                    raise err

                redirect_url = f'{redirect_scheme}://{redirect_hostname}/{redirect_path}?{query_string}'
                return {
                    'source_url': source_url,
                    'redirect_url': redirect_url,
                }

            if blacklisted(redirect_path):
                raise Exception('Канал заблокирован.')

            err = None
            if not whitelisted(redirect_path):
                err = 'Перед тем как использовать ссылку, напишите администратору.'

            redirect_url = f'{redirect_scheme}://{redirect_hostname}/{redirect_path}'
            return {
                'source_url': source_url,
                'redirect_url': redirect_url,
                'error': err,
            }
        except Exception as err:
            logger.error(err)
            return {
                'source_url': source_url,
                'error': str(err),
            }
    else:
        return {}


async def download_profile_image(url, name):
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            chunk_size = 10
            img_filename = f'{IMAGES_DIR}/{name}.jpg'
            with open(img_filename, 'wb') as f:
                while True:
                    chunk = await response.content.read(chunk_size)
                    if not chunk:
                        break
                    f.write(chunk)


# Parse t.me because the API access for bot users is restricted for private channels.
async def parse_channel_info(url):
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            html = await response.text()
            soup = BeautifulSoup(html, 'html.parser')
            page_photo_image = soup.find(name='img', attrs={'class': 'tgme_page_photo_image'})
            profile_image = page_photo_image.get('src', None) if page_photo_image is not None else None

            page_title = soup.find(name='div', attrs={'class': 'tgme_page_title'})
            profile_name = page_title.contents[0].strip() if page_title is not None else ''

            page_description = soup.find(name='div', attrs={'class': 'tgme_page_description'})
            profile_status = page_description.decode_contents(formatter="html") if page_description is not None else ''

            page_extra = soup.find(name='div', attrs={'class': 'tgme_page_extra'})
            profile_extra = page_extra.decode_contents(formatter="html") if page_extra is not None else ''
            return profile_name, profile_status, profile_image, profile_extra


async def parse_embed(url):
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            html = await response.text()
            soup = BeautifulSoup(html, 'html.parser')
            widget_message_text = soup.find(name='div', attrs={'class': 'tgme_widget_message_text'})
            message_text = widget_message_text.decode_contents(formatter="html")
            return message_text


def blacklisted(path):
    # If blacklist is empty, skip.
    if not BLACKLIST.strip():
        return False

    blacklist = list(map(lambda str: str.strip().lower(), BLACKLIST.split(',')))
    if path.lower() in blacklist:
        return True

    # If channel is blocked, probably every post also should be blocked.
    path = path.split('/')[0]
    if path.lower() not in ['joinchat', 'addstickers'] and path.lower() in blacklist:
        return True
    return False


def whitelisted(path):
    # If whitelist is empty, skip.
    if not WHITELIST.strip():
        return True

    whitelist = list(map(lambda str: str.strip().lower(), WHITELIST.split(',')))
    if path.lower() in whitelist:
        return True

    # If channel is whitelisted, probably every post also should be whitelisted, except cases when link in blacklist.
    path = path.split('/')[0]
    if path.lower() not in ['joinchat', 'addstickers'] and path.lower() in whitelist:
        return True
    return False


def validate_proxy(server=None, port=None, secret=None):
    if None in [server, port, secret]:
        raise Exception('Указан неверный адрес.')
    regex_port_number = r'^()([1-9]|[1-5]?[0-9]{2,4}|6[1-4][0-9]{3}|65[1-4][0-9]{2}|655[1-2][0-9]|6553[1-5])$'
    if not port.isnumeric() or re.match(regex_port_number, port) is None:
        raise Exception('Порт должен быть числом в диапазоне 1-65535.')
    if re.match(r'[0-9A-Fa-f]{32}', secret) is None:
        raise Exception('Плохой секрет.')
    regex_server_name = r'^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$|^(([a-zA-Z0-9]|[a-zA-Z0-9][a-zA-Z0-9\-]*[a-zA-Z0-9])\.)+([A-Za-z]|[A-Za-z][A-Za-z0-9\-]*[A-Za-z0-9])$'
    if re.match(regex_server_name, server) is None:
        raise Exception('Неверно указано имя сервера.')


@aiohttp_jinja2.template('redirect.html')
async def redirect(request):
    route_name = request.match_info.route.name
    redirect_hostname = DOMAIN_NAME if not DOMAIN_NAME.strip() else request.host
    redirect_scheme = 'https'
    if route_name == 'account':
        name = request.match_info.get('name')
        if blacklisted(name):
            return web.Response(status=451)
        if not whitelisted(name):
            return web.Response(status=404)
        location = f'tg://resolve?domain={name}'
        tme_url = f'https://t.me/{name}'

    if route_name == 'joinchat':
        code = request.match_info.get('code')
        if blacklisted(f'joinchat/{code}'):
            return web.Response(status=451)
        if not whitelisted(f'joinchat/{code}'):
            return web.Response(status=404)
        location = f'tg://join?invite={code}'
        tme_url = f'https://t.me/joinchat/{code}'

    if route_name == 'addstickers':
        name = request.match_info.get('name')
        if blacklisted(f'addstickers/{name}'):
            return web.Response(status=451)
        if not whitelisted(f'addstickers/{name}'):
            return web.Response(status=404)
        location = f'tg://addstickers?set={name}'
        tme_url = f'https://t.me/addstickers/{name}'

    if route_name == 'proxy':
        server = request.query.get('server', None)
        port = request.query.get('port', None)
        secret = request.query.get('secret', None)
        try:
            validate_proxy(server, port, secret)
        except Exception as err:
            logger.error(err)
            return web.Response(status=400)
        location = f'tg://proxy?server={server}&port={port}&secret={secret}'
        tme_url = f'https://t.me/proxy?server={server}&port={port}&secret={secret}'

    if route_name == 'post':
        name = request.match_info.get('name')
        post = request.match_info.get('post')
        if not post.isnumeric():
            return {}
        if blacklisted(f'{name}/{post}'):
            return web.Response(status=451)
        if not whitelisted(f'{name}/{post}'):
            return web.Response(status=404)
        location = f'tg://resolve?domain={name}&post={post}'
        tme_url = f'https://t.me/{name}'
        tme_post_url = f'https://t.me/{name}/{post}?embed=1'

    if location is None:
        return web.Response(status=404)
    else:
        response = {
            'location': location,
            'base_path': f'{redirect_scheme}://{redirect_hostname}',
            'route_name': route_name,
        }

        if USE_PARSER == 'True':
            try:
                profile_info = await parse_channel_info(tme_url)
                profile_name, profile_status, profile_image, profile_extra = profile_info
                response['profile_name'] = profile_name
                response['profile_status'] = profile_status
                response['profile_image'] = profile_image
                if profile_image is not None:
                    try:
                        name
                    except NameError:
                        name = code
                    await download_profile_image(profile_image, name)
                    response['local_profile_image'] = f'{name}.jpg'

                try:
                    tme_post_url
                except NameError as err:
                    tme_post_url = None

                if tme_post_url is not None:
                    try:
                        message_text = await parse_embed(tme_post_url)
                        response['message_text'] = message_text
                    except Exception as err:
                        logger.error(err)

                if profile_extra.strip():
                    response['profile_extra'] = profile_extra

                return response
            except Exception as err:
                logger.error(err)
                return response

        return response


app = web.Application()
routes = [
    web.get('/', index, name='index'),
    web.post('/', index, name='index'),
    web.get('/proxy', redirect, name='proxy'),
    web.get(r'/{name:[a-zA-Z0-9_]{5,}}', redirect, name='account'),
    web.get('/joinchat/{code}', redirect, name='joinchat'),
    web.get('/addstickers/{name}', redirect, name='addstickers'),
    web.get(r'/{name:[a-zA-Z0-9_]{5,}}/{post:\d+}', redirect, name='post'),
]

if DEVELOPMENT == 'True':
    routes.append(web.static('/static/', pathlib.Path(__file__).parent / 'static', name='static'))
    routes.append(web.static('/files/img/', IMAGES_DIR, name='img'))

app.add_routes(routes)
setup_jinja(app)

if __name__ == '__main__':
    web.run_app(app)
