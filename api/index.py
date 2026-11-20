from http.server import BaseHTTPRequestHandler
import urllib.request
import ssl
import json
import re

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

        ans = ''
        try:
            url = 'https://mgak1.by' + '/assets/site/raspisanie/1.htm'
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})
            raw = urllib.request.urlopen(req, timeout=8, context=ctx).read()
            
            html = raw.decode('cp1251', errors='ignore')
            if '│' not in html:
                html = raw.decode('cp866', errors='ignore')
                
            text = re.sub(r'<[^>]+>', '', html)
            lines = text.splitlines()
            
            lessons = list()
            first_pair = None
            capture = False
            found_groups = list()
            
            for line in lines:
                if '│' not in line:
                    continue
                parts = tuple(p.strip() for p in line.split('│'))
                if len(parts) < 5:
                    continue
                    
                raw_grp = parts.__getitem__(1)
                if raw_grp and raw_grp not in found_groups:
                    found_groups.append(raw_grp)
                    
                grp = raw_grp.lower().replace(' ', '').replace('-', '')
                if grp in ('эс4', '4эс', '4с', 'с4'):
                    capture = True
                elif grp != '' and capture:
                    break
                    
                if capture:
                    pair_num = parts.__getitem__(2)
                    subj = parts.__getitem__(3)
                    room = parts.__getitem__(4)
                    if pair_num:
                        if first_pair is None:
                            first_pair = pair_num
                        lessons.append(f'{pair_num} пара {subj} кабинет {room}')
                    elif subj:
                        lessons.append(f'также {subj} кабинет {room}')

            if lessons:
                prep = 'ко' if str(first_pair) == '2' else 'к'
                ans = f'Завтра {prep} {first_pair} паре ' + ' '.join(lessons)
            else:
                ans = 'Не найдено. Группы в файле: ' + ', '.join(found_groups) + ' | Кусок текста: ' + text[:150].strip()
        except Exception as e:
            ans = f'Ошибка сети: {str(e)}'

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
