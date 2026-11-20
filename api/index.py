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

DAYS_ACC = {
    0: 'понедельник',
    1: 'вторник',
    2: 'среду',
    3: 'четверг',
    4: 'пятницу',
    5: 'субботу',
    6: 'воскресенье'
}

DAYS_CLEAN = {
    0: 'в понедельник',
    1: 'во вторник',
    2: 'в среду',
    3: 'в четверг',
    4: 'в пятницу',
    5: 'в субботу',
    6: 'в воскресенье'
}

def get_corpus_phrase(room_str):
    low_room = room_str.lower()
    if 'с/з' in low_room or 'с.з' in low_room or 'спорт' in low_room:
        return 'в спортивном зале'
    if 'общ' in low_room:
        return 'в общежитии'
    nums = re.findall(r'\d+', room_str)
    if not nums:
        return ''
    room_num = int(nums.__getitem__(0))
    if room_num <= 100:
        return 'во втором корпусе'
    return 'в первом корпусе'

def clean_subject(subj):
    low = subj.lower()
    if 'физ' in low and ('здоров' in low or 'культ' in low):
        return 'Физкультура'
    return subj

def extract_schedule_date(page):
    m = re.search(r'(\d{2})\.(\d{2})\.(\d{2,4})', page)
    if not m:
        return None
    d = int(m.group(1))
    mo = int(m.group(2))
    y = int(m.group(3))
    if y < 100:
        y += 2000
    try:
        return datetime(y, mo, d).date()
    except Exception:
        return None

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
            nice_subj = clean_subject(subj)
            if pair_num.isdigit():
                if first_pair is None:
                    first_pair = pair_num
                p_word = ORDINALS_NOM.get(pair_num, pair_num)
                if len(lessons) == 0:
                    p_word = p_word.capitalize()
                item = f'{p_word} пара {nice_subj}'
                if corpus:
                    item = f'{item} {corpus}'
                lessons.append(item)
            elif subj:
                item = f'также {nice_subj}'
                if corpus:
                    item = f'{item} {corpus}'
                lessons.append(item)

    if any('уборк' in gl for gl in group_lines):
        cleaning = True

    return first_pair, lessons, cleaning

def format_day_block(prefix, first_pair, lessons, cleaning, clean_day_word):
    if not lessons:
        return ''
    prep = 'ко' if str(first_pair) == '2' else 'к'
    first_gen = ORDINALS_GEN.get(str(first_pair), str(first_pair))
    text = f'{prefix} {prep} {first_gen} паре. ' + ', '.join(lessons) + '.'
    if cleaning:
        text = text + f' Так же {clean_day_word} у вас уборка территории.'
    return text

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
        today_date = datetime.now(tz_minsk).date()
        tomorrow_date = today_date + timedelta(days=1)

        ans = ''
        try:
            valid_items = list()
            for num in ('1', '2'):
                try:
                    page = fetch_page(num, ctx)
                    sched_date = extract_schedule_date(page)
                    fp, les, cl = parse_schedule(page)
                    if les:
                        if sched_date is None or sched_date >= today_date:
                            valid_items.append((sched_date, fp, les, cl))
                except Exception:
                    pass

            valid_items.sort(key=lambda x: x.__getitem__(0) or today_date)

            if len(valid_items) >= 2:
                blocks = list()
                for sched_date, fp, les, cl in valid_items:
                    if sched_date:
                        wd = sched_date.weekday()
                        prefix = f'Расписание на {DAYS_ACC.get(wd, "")}:'
                        clean_w = DAYS_CLEAN.get(wd, 'в этот день')
                    else:
                        prefix = 'Расписание:'
                        clean_w = 'в этот день'
                    b = format_day_block(prefix, fp, les, cl, clean_w)
                    if b:
                        blocks.append(b)
                ans = ' '.join(blocks)
            elif len(valid_items) == 1:
                sched_date, fp, les, cl = valid_items.__getitem__(0)
                if sched_date == today_date:
                    ans = format_day_block('Сегодня', fp, les, cl, 'сегодня')
                elif sched_date == tomorrow_date or sched_date is None:
                    ans = format_day_block('Завтра', fp, les, cl, 'завтра')
                else:
                    wd = sched_date.weekday()
                    prefix = f'Расписание на {DAYS_ACC.get(wd, "")}:'
                    clean_w = DAYS_CLEAN.get(wd, 'в этот день')
                    ans = format_day_block(prefix, fp, les, cl, clean_w)
            else:
                ans = 'Актуальное расписание для группы 4ЭС пока не выложено.'
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
