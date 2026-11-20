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
        found_groups = list()
        
        for num in ('1', '2', '3'):
            try:
                url = 'https://mgak1.by' + f'/assets/site/raspisanie/{num}.htm'
                req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
                raw = urllib.request.urlopen(req, timeout=8, context=ctx).read()
                
                html = raw.decode('cp1251', errors='ignore')
                if 'charset=utf-8' in html.lower() or 'encoding="utf-8"' in html.lower():
                    html = raw.decode('utf-8', errors='ignore')

                rows = re.findall(r'<tr[^>]*>(.*?)</tr>', html, flags=re.S | re.I)
                
                lessons = list()
                first_pair = None
                capture = False
                
                for r in rows:
                    cells = re.findall(r'<td[^>]*>(.*?)</td>', r, flags=re.S | re.I)
                    clean = list()
                    for c in cells:
                        t = re.sub(r'<[^>]+>', ' ', c)
                        t = t.replace('&nbsp;', ' ')
                        t = re.sub(r'\s+', ' ', t).strip()
                        clean.append(t)
                        
                    if not any(clean):
                        continue
                        
                    raw_grp = clean.__getitem__(0)
                    if raw_grp and len(raw_grp) <= 10 and any(ch.isdigit() for ch in raw_grp):
                        if raw_grp not in found_groups:
                            found_groups.append(raw_grp)
                            
                    grp = raw_grp.lower().replace(' ', '').replace('-', '')
                    if grp in ('эс4', '4эс', '4с', 'с4'):
                        capture = True
                    elif grp != '' and any(ch.isdigit() for ch in grp) and capture:
                        break
                        
                    if capture and len(clean) >= 4:
                        pair_num = clean.__getitem__(1)
                        subj = clean.__getitem__(2)
                        room = clean.__getitem__(3)
                        if pair_num.isdigit():
                            if first_pair is None:
                                first_pair = pair_num
                            lessons.append(f'{pair_num} пара {subj} кабинет {room}')
                        elif subj:
                            lessons.append(f'также {subj} кабинет {room}')

                if lessons:
                    prep = 'ко' if str(first_pair) == '2' else 'к'
                    ans = f'Завтра {prep} {first_pair} паре ' + ' '.join(lessons)
                    break
            except Exception:
                continue

        if not ans:
            ans = 'Группа не найдена. Найденные группы: ' + ', '.join(found_groups)

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
