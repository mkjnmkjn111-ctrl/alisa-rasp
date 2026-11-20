from http.server import BaseHTTPRequestHandler
from datetime import datetime, timedelta, timezone
import urllib.request
import html as htmllib
import ssl
import json
import re

ORDINALS_GEN = {
    '1': 'первой',
    '2': 'второй',
    '3': 'третьей',
    '4': 'четвертой',
    '5': 'пятой',
    '6': 'шестой'
}

ORDINALS_NOM = {
    '1': 'первая',
    '2': 'вторая',
    '3': 'третья',
    '4': 'четвертая',
    '5': 'пятая',
    '6': 'шестая'
}

def get_corpus_phrase(room_str):
    nums = re.findall(r'\d+', room_str)
    if not nums:
        return ''
    room_num = int(nums.__getitem__(0))
    if room_num <= 100:
        return 'во втором корпусе'
    return 'в первом корпусе'

def fetch_page(num, ctx):
    url = 'https://mgak1.by' + f'/assets/site/raspisanie/{num}.htm'
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    raw = urllib.request.urlopen(req, timeout=8, context=ctx).read()
    page = raw.decode('cp1251', errors='ignore')
    page = re.sub(r'[\r\n]+', ' ', page)
    page = re.sub(r'<p\b[^>]*>', '\n', page, flags=re.I)
    page = re.sub(r'<[^>]+>', '', page)
    return htmllib.unescape(page)

def parse_schedule(page):
    lines = page.splitlines()
    lessons = list()
    first_pair = None
    capture = False
    cleaning = False
    group_lines = list()

    for line in lines:
        low_line = line.lower()
        if 'уборк' in low_line and ('4эс' in low_line.replace(' ', '').replace('-', '') or 'эс4' in low_line.replace(' ', '').replace('-', '')):
            cleaning = True

        if '│' not in line:
            continue
        parts = tuple(re.sub(r'\s+', ' ', p).strip() for p in line.split('│'))
        if len(parts) < 5:
            continue

        grp = parts.__getitem__(1).lower().replace(' ', '').replace('-', '')
        if grp in ('4эс', 'эс4', '4с', 'с4'):
            capture = True
        elif grp != '' and capture:
            capture = False

        if capture:
            group_lines.append(line.lower())
            pair_num = parts.__getitem__(2)
            subj = parts.__getitem__(3)
            room = parts.__getitem__(4)
            
            if 'уборк' in subj.lower() or 'уборк' in room.lower():
                cleaning = True
                continue

            corpus = get_corpus_phrase(room)
            if pair_num.isdigit():
                if first_pair is None:
                    first_pair = pair_num
                p_word = ORDINALS_NOM.get(pair_num, pair_num)
                if len(lessons) == 0:
                    p_word = p_word.capitalize()
                item = f'{p_word} пара {subj}'
                if corpus:
                    item = f'{item} {corpus}'
                lessons.append(item)
            elif subj:
                item = f'также {subj}'
                if corpus:
                    item = f'{item} {corpus}'
                lessons.append(item)

    if any('уборк' in gl for gl in group_lines):
        cleaning = True

    return first_pair, lessons, cleaning

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.process()

    def do_POST(self):
        self.process()

    def process(self):
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length) if content_length > 0 else b'{}'
            data = json.loads(body.decode('utf-8'))
        except Exception:
            data = dict()

        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

        tz_minsk = timezone(timedelta(hours=3))
        tomorrow = datetime.now(tz_minsk) + timedelta(days=1)
        target_dd_mm = tomorrow.strftime('%d.%m')

        ans = ''
        try:
            pages = list()
            for num in ('1', '2'):
                try:
                    pages.append(fetch_page(num, ctx))
                except Exception:
                    pass

            chosen_page = None
            for p in pages:
                if target_dd_mm in p:
                    chosen_page = p
                    break
            if chosen_page is None and pages:
                chosen_page = pages.__getitem__(0)

            if chosen_page:
                first_pair, lessons, cleaning = parse_schedule(chosen_page)
                if lessons:
                    prep = 'ко' if str(first_pair) == '2' else 'к'
                    first_gen = ORDINALS_GEN.get(str(first_pair), str(first_pair))
                    ans = f'Завтра {prep} {first_gen} паре. ' + ', '.join(lessons) + '.'
                    if cleaning:
                        ans = ans + ' Так же завтра у вас уборка территории.'
                else:
                    ans = 'Расписание для группы 4ЭС на завтра пока не найдено.'
            else:
                ans = 'Не удалось загрузить расписание с сайта колледжа.'
        except Exception as e:
            ans = f'Ошибка загрузки {str(e)}'

        res = {
            'version': data.get('version', '1.0'),
            'session': data.get('session', dict()),
            'response': {
                'text': ans,
                'end_session': True
            }
        }

        self.send_response(200)
        self.send_header('Content-type', 'application/json; charset=utf-8')
        self.end_headers()
        self.wfile.write(json.dumps(res, ensure_ascii=False).encode('utf-8'))
