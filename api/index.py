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
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            raw = urllib.request.urlopen(req, timeout=8, context=ctx).read()
            
            html = raw.decode('cp1251', errors='ignore')
            if 'Предмет' not in html and '4ЭС' not in html:
                html = raw.decode('cp866', errors='ignore')
            if 'Предмет' not in html and '4ЭС' not in html:
                html = raw.decode('utf-8', errors='ignore')

            if '4ЭС' in html or 'ЭС-4' in html or 'ЭС 4' in html:
                idx = html.find('4ЭС')
                if idx == -1:
                    idx = html.find('ЭС')
                snippet = re.sub(r'\s+', ' ', html[max(0, idx-50):idx+600])
                ans = 'НАШЕЛ КУСОК: ' + snippet
            else:
                snippet = re.sub(r'\s+', ' ', html[len(html)//2 : len(html)//2 + 400])
                ans = 'НЕ НАШЕЛ 4ЭС. СЕРЕДИНА ФАЙЛА: ' + snippet
        except Exception as e:
            ans = 'ОШИБКА: ' + str(e)

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
