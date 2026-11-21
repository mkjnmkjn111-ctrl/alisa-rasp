from http.server import BaseHTTPRequestHandler
from datetime import datetime, timedelta, timezone
from concurrent.futures import ThreadPoolExecutor
import urllib.request
import html as htmllib
import ssl
import json
import time
import re

CACHE = {'ts': 0, 'ans': ''}

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

BELLS_WEEKDAY = {
    1: ((8, 15), (9, 0), (9, 10), (9, 55)),
    2: ((10, 5), (10, 50), (11, 35), (12, 20)),
    3: ((12, 30), (13, 15), (13, 25), (14, 10)),
    4: ((14, 20), (15, 5), (15, 15), (16, 0)),
    5: ((16, 20), (17, 5), (17, 15), (18, 0)),
    6: ((18, 10), (18, 55), (19, 0), (19, 45))
}

BELLS_SATURDAY = {
    1: ((8, 15), (9, 0), (9, 10), (9, 55)),
    2: ((10, 5), (10, 50), (11, 0), (11, 45)),
    3: ((11, 55), (12, 40), (12, 50), (13, 35)),
    4: ((13, 45), (14, 30), (14, 40), (15, 25)),
    5: ((15, 35), (16, 20), (16, 30), (17, 15)),
    6: ((17, 25), (18, 10), (18, 20), (19, 5))
}

SUBJECT_MAP = (
    ('физ', 'Физкультура', 'физкультуры'),
    ('рус яз', 'Русский язык', 'русского языка'),
    ('рус лит', 'Русская литература', 'русской литературы'),
    ('бел яз', 'Белорусский язык', 'белорусского языка'),
    ('бел лит', 'Белорусская литература', 'белорусской литературы'),
    ('иностр', 'Иностранный язык', 'иностранного языка'),
    ('англ', 'Английский язык', 'английского языка'),
    ('нем', 'Немецкий язык', 'немецкого языка'),
    ('матем', 'Математика', 'математики'),
    ('физик', 'Физика', 'физики'),
    ('хими', 'Химия', 'химии'),
    ('биолог', 'Биология', 'биологии'),
    ('географ', 'География', 'географии'),
    ('информ час', 'Информационный час', 'информационного часа'),
    ('инф час', 'Информационный час', 'информационного часа'),
    ('информ', 'Информатика', 'информатики'),
    ('обществ', 'Обществоведение', 'обществоведения'),
    ('ист бел', 'История Беларуси', 'истории Беларуси'),
    ('всем ист', 'Всемирная история', 'всемирной истории'),
    ('астроном', 'Астрономия', 'астрономии'),
    ('дпю', 'Допризывная подготовка', 'допризывной подготовки'),
    ('мед подготов', 'Медицинская подготовка', 'медицинской подготовки'),
    ('мгп', 'Международное гуманитарное право', 'международного гуманитарного права'),
    ('черчен', 'Черчение', 'черчения'),
    ('инж граф', 'Инженерная графика', 'инженерной графики'),
    ('тех мех', 'Техническая механика', 'технической механики'),
    ('электротех', 'Электротехника', 'электротехники'),
    ('материалов', 'Материаловедение', 'материаловедения'),
    ('факультат', 'Факультатив', 'факультатива'),
    ('куратор', 'Кураторский час', 'кураторского часа')
)

def expand_subject(raw_subj):
    s = re.sub(r'\s+[лп]$', '', raw_subj.strip(), flags=re.I)
    low = s.lower().replace('.', ' ')
    low = re.sub(r'\s+', ' ', low).strip()
    for key, nom, gen in SUBJECT_MAP:
        if key in low:
            return nom, gen
    return s, s.lower()

def num_to_words(n, female=False):
    ones_m = ('ноль', 'один', 'два', 'три', 'четыре', 'пять', 'шесть', 'семь', 'восемь', 'девять')
    ones_f = ('ноль', 'одна', 'две', 'три', 'четыре', 'пять', 'шесть', 'семь', 'восемь', 'девять')
    teens = ('десять', 'одиннадцать', 'двенадцать', 'тринадцать', 'четырнадцать',
             'пятнадцать', 'шестнадцать', 'семнадцать', 'восемнадцать', 'девятнадцать')
    tens = ('', '', 'двадцать', 'тридцать', 'сорок', 'пятьдесят')
    ones = ones_f if female else ones_m
    if n < 10:
        return ones.__getitem__(n)
    if n < 20:
        return teens.__getitem__(n - 10)
    t = n // 10
    o = n % 10
    if o == 0:
        return tens.__getitem__(t)
    return f'{tens.__getitem__(t)} {ones.__getitem__(o)}'

def time_to_words(hm):
    h, m = hm
    h_word = num_to_words(h, female=False)
    if m == 0:
        return f'{h_word} ноль ноль'
    if m < 10:
        return f'{h_word} ноль {num_to_words(m, female=True)}'
    return f'{h_word} {num_to_words(m, female=True)}'

def minutes_word(n):
    word = num_to_words(n, female=True)
    if 11 <= (n % 100) <= 14:
        suffix = 'минут'
    elif n % 10 == 1:
        suffix = 'минута'
    elif 2 <= (n % 10) <= 4:
        suffix = 'минуты'
    else:
        suffix = 'минут'
    return f'{word} {suffix}'

def to_mins(hm):
    return hm.__getitem__(0) * 60 + hm.__getitem__(1)

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

def fetch_page(num):
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    url = 'https://mgak1.by' + f'/assets/site/raspisanie/{num}.htm'
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    raw = urllib.request.urlopen(req, timeout=2.5, context=ctx).read()
    page = raw.decode('cp1251', errors='ignore')
    page = re.sub(r'[\r\n]+', ' ', page)
    page = re.sub(r'<p\b[^>]*>', '\n', page, flags=re.I)
    page = re.sub(r'<[^>]+>', '', page)
    return htmllib.unescape(page)

def parse_schedule(page):
    lines = page.splitlines()
    raw_pairs = list()
    current_pair = None
    capture = False
    cleaning = False

    for line in lines:
        low_line = line.lower()
        clean_line_grp = low_line.replace(' ', '').replace('-', '')
        if 'уборк' in low_line and ('4эс' in clean_line_grp or 'эс4' in clean_line_grp):
            cleaning = True

        if '│' not in line:
            if capture and 'уборк' in low_line:
                cleaning = True
            if capture and ('─' in line or '┴' in line or '┼' in line):
                capture = False
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
            if 'уборк' in low_line:
                cleaning = True
                continue
            pair_num = parts.__getitem__(2)
            subj = parts.__getitem__(3)
            room = parts.__getitem__(4)
            if pair_num.isdigit():
                current_pair = int(pair_num)
                raw_pairs.append((current_pair, list()))
            if current_pair is not None and subj:
                nom, gen = expand_subject(subj)
                corpus = get_corpus_phrase(room)
                entries = raw_pairs.__getitem__(-1).__getitem__(1)
                if not any(e.__getitem__(0) == nom and e.__getitem__(2) == corpus for e in entries):
                    entries.append((nom, gen, corpus))

    pairs = list()
    for p_num, entries in raw_pairs:
        if entries:
            pairs.append((p_num, entries))

    return pairs, cleaning

def format_lessons_list(pairs):
    items = list()
    for idx, (p_num, entries) in enumerate(pairs):
        p_word = ORDINALS_NOM.get(str(p_num), str(p_num))
        if idx == 0:
            p_word = p_word.capitalize()
        if len(entries) >= 2:
            e1 = entries.__getitem__(0)
            e2 = entries.__getitem__(1)
            part1 = f'первая половина {e1.__getitem__(0)} {e1.__getitem__(2)}'.strip()
            part2 = f'вторая половина {e2.__getitem__(0)} {e2.__getitem__(2)}'.strip()
            items.append(f'{p_word} пара разделена. {part1.capitalize()}, {part2}')
        else:
            e1 = entries.__getitem__(0)
            phrase = f'{p_word} пара {e1.__getitem__(0)} {e1.__getitem__(2)}'.strip()
            items.append(phrase)
    return ', '.join(items) + '.'

def build_today_status(pairs, now_minsk, is_saturday):
    if not pairs:
        return ''
    bells = BELLS_SATURDAY if is_saturday else BELLS_WEEKDAY
    now_m = now_minsk.hour * 60 + now_minsk.minute

    first_p_num = pairs.__getitem__(0).__getitem__(0)
    last_p_num = pairs.__getitem__(-1).__getitem__(0)
    first_gen = ORDINALS_GEN.get(str(first_p_num), str(first_p_num))
    prep = 'ко' if first_p_num == 2 else 'к'

    first_bell = bells.get(first_p_num)
    last_bell = bells.get(last_p_num)
    if not first_bell or not last_bell:
        return f'Сегодня {prep} {first_gen} паре.'

    start_day_m = to_mins(first_bell.__getitem__(0))
    end_day_m = to_mins(last_bell.__getitem__(3))

    if now_m < start_day_m:
        t_words = time_to_words(first_bell.__getitem__(0))
        return f'Сегодня {prep} {first_gen} паре, начало в {t_words}.'

    if now_m >= end_day_m:
        return f'Сегодня надо было {prep} {first_gen} паре.'

    for idx, (p_num, entries) in enumerate(pairs):
        b = bells.get(p_num)
        if not b:
            continue
        s1 = to_mins(b.__getitem__(0))
        e1 = to_mins(b.__getitem__(1))
        s2 = to_mins(b.__getitem__(2))
        e2 = to_mins(b.__getitem__(3))

        p_gen = ORDINALS_GEN.get(str(p_num), str(p_num))
        e1_gen = entries.__getitem__(0).__getitem__(1)
        e2_gen = entries.__getitem__(1).__getitem__(1) if len(entries) >= 2 else e1_gen

        if s1 <= now_m < e1:
            rem = minutes_word(e1 - now_m)
            return f'Сейчас идет первая половина {p_gen} пары {e1_gen}, до конца осталось {rem}. Сегодня надо было идти {prep} {first_gen} паре.'

        if e1 <= now_m < s2:
            rem = minutes_word(s2 - now_m)
            if p_num == 2 and not is_saturday:
                if len(entries) >= 2 and e1_gen != e2_gen:
                    return f'Сейчас обед, то есть середина второй пары {e1_gen} и {e2_gen}, до конца обеда осталось {rem}. После обеда будет половина пары {e2_gen}. Сегодня надо было идти {prep} {first_gen} паре.'
                return f'Сейчас обед, то есть середина второй пары {e1_gen}, до конца обеда осталось {rem}. Сегодня надо было идти {prep} {first_gen} паре.'
            return f'Сейчас перемена перед второй половиной {p_gen} пары {e2_gen}, до звонка осталось {rem}. Сегодня надо было идти {prep} {first_gen} паре.'

        if s2 <= now_m < e2:
            rem = minutes_word(e2 - now_m)
            return f'Сейчас идет вторая половина {p_gen} пары {e2_gen}, до конца осталось {rem}. Сегодня надо было идти {prep} {first_gen} паре.'

        if idx + 1 < len(pairs):
            next_p_num, next_entries = pairs.__getitem__(idx + 1)
            nb = bells.get(next_p_num)
            if nb:
                ns1 = to_mins(nb.__getitem__(0))
                if e2 <= now_m < ns1:
                    rem = minutes_word(ns1 - now_m)
                    np_gen = ORDINALS_GEN.get(str(next_p_num), str(next_p_num))
                    ne_gen = next_entries.__getitem__(0).__getitem__(1)
                    return f'Сейчас перемена перед {np_gen} парой {ne_gen}, до начала осталось {rem}. Сегодня надо было идти {prep} {first_gen} паре.'

    return f'Сегодня надо было {prep} {first_gen} паре.'

def format_full_day(sched_date, pairs, cleaning, now_minsk):
    today_date = now_minsk.date()
    tomorrow_date = today_date + timedelta(days=1)
    lessons_text = format_lessons_list(pairs)

    if sched_date == today_date:
        is_sat = (sched_date.weekday() == 5)
        header = build_today_status(pairs, now_minsk, is_sat)
        res = f'{header} {lessons_text}'
        if cleaning:
            res = f'{res} Так же сегодня у вас уборка территории.'
        return res

    first_p_num = pairs.__getitem__(0).__getitem__(0)
    first_gen = ORDINALS_GEN.get(str(first_p_num), str(first_p_num))
    prep = 'ко' if first_p_num == 2 else 'к'

    if sched_date == tomorrow_date or sched_date is None:
        res = f'Завтра {prep} {first_gen} паре. {lessons_text}'
        if cleaning:
            res = f'{res} Так же завтра у вас уборка территории.'
        return res

    wd = sched_date.weekday()
    day_acc = DAYS_ACC.get(wd, '')
    day_clean = DAYS_CLEAN.get(wd, 'в этот день')
    res = f'Расписание на {day_acc}: {prep} {first_gen} паре. {lessons_text}'
    if cleaning:
        res = f'{res} Так же {day_clean} у вас уборка территории.'
    return res

def build_answer():
    now_ts = time.time()
    if CACHE['ans'] and (now_ts - CACHE['ts']) < 180:
        return CACHE['ans']

    tz_minsk = timezone(timedelta(hours=3))
    now_minsk = datetime.now(tz_minsk)
    today_date = now_minsk.date()

    pages = list()
    with ThreadPoolExecutor(max_workers=2) as ex:
        futures = [ex.submit(fetch_page, '1'), ex.submit(fetch_page, '2')]
        for f in futures:
            try:
                pages.append(f.result(timeout=2.6))
            except Exception:
                pass

    valid_items = list()
    for page in pages:
        sched_date = extract_schedule_date(page)
        pairs, cl = parse_schedule(page)
        if pairs:
            if sched_date is None or sched_date >= today_date:
                valid_items.append((sched_date, pairs, cl))

    valid_items.sort(key=lambda x: x.__getitem__(0) or today_date)

    if len(valid_items) >= 2:
        blocks = list()
        for sched_date, pairs, cl in valid_items:
            if sched_date == today_date:
                blocks.append(format_full_day(sched_date, pairs, cl, now_minsk))
            else:
                wd = sched_date.weekday() if sched_date else 0
                day_acc = DAYS_ACC.get(wd, '')
                day_clean = DAYS_CLEAN.get(wd, 'в этот день')
                first_p = pairs.__getitem__(0).__getitem__(0)
                first_gen = ORDINALS_GEN.get(str(first_p), str(first_p))
                prep = 'ко' if first_p == 2 else 'к'
                lessons_text = format_lessons_list(pairs)
                b = f'Расписание на {day_acc}: {prep} {first_gen} паре. {lessons_text}'
                if cl:
                    b = f'{b} Так же {day_clean} у вас уборка территории.'
                blocks.append(b)
        ans = ' '.join(blocks)
    elif len(valid_items) == 1:
        sched_date, pairs, cl = valid_items.__getitem__(0)
        ans = format_full_day(sched_date, pairs, cl, now_minsk)
    else:
        ans = 'Актуальное расписание для группы 4ЭС пока не выложено.'

    if ans and 'пока не выложено' not in ans:
        CACHE['ts'] = now_ts
        CACHE['ans'] = ans
    return ans

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

        try:
            ans = build_answer()
        except Exception:
            ans = 'Сайт колледжа отвечает слишком долго, попробуй еще раз.'

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
