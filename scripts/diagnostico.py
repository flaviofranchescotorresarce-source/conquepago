"""TEMPORAL: abre la web de beneficios de BCP con un navegador y anota de dónde salen los datos. Se borra antes de mergear."""
import json
import re
import sys

from playwright.sync_api import sync_playwright

sys.stdout.reconfigure(line_buffering=True)


def corto(s, n):
    s = ' '.join(str(s).split())
    return s if len(s) <= n else s[:n] + '…'


URLS = [
    'https://www.viabcp.com/beneficios/todos-los-beneficios?rfid=beneficios:promociones-descuentos:mundo-cuenta-sueldo:card',
    'https://www.viabcp.com/cuenta-sueldo-bcp',
    'https://www.viabcp.com/beneficiostarjetabcp',
]

with sync_playwright() as p:
    nav = p.chromium.launch()
    pag = nav.new_page(locale='es-PE', user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                                                  '(KHTML, like Gecko) Chrome/128.0 Safari/537.36')
    for url in URLS:
        print(f'\n######## {url}')
        respuestas = []

        def anotar(r):
            tipo = r.headers.get('content-type', '')
            if 'json' in tipo or re.search(r'api|benefic|promo|wcm/connect', r.url, re.I) and 'image' not in tipo \
                    and not re.search(r'\.(js|css|woff2?|svg|png|jpe?g|webp)(\?|$)', r.url):
                try:
                    cuerpo = r.text()
                except Exception:  # noqa: BLE001
                    cuerpo = ''
                respuestas.append((r.status, tipo, r.url, cuerpo))
        pag.on('response', anotar)
        try:
            r = pag.goto(url, wait_until='networkidle', timeout=60000)
            print('   estado', r.status if r else None, '| url final', pag.url)
            pag.wait_for_timeout(5000)
            for _ in range(6):  # baja para que carguen las tarjetas perezosas
                pag.mouse.wheel(0, 3000)
                pag.wait_for_timeout(800)
        except Exception as e:  # noqa: BLE001
            print('   ERROR', corto(e, 200))
        texto = pag.inner_text('body') if pag.url else ''
        print('   texto visible', len(texto), '| "alma":', len(re.findall(r'alma', texto, re.I)), '| %:', len(re.findall(r'\d{1,2}\s*%', texto)))
        for m in list(re.finditer(r'alma', texto, re.I))[:5]:
            print('   alma>', corto(texto[max(0, m.start() - 300):m.end() + 300], 600))
        print('   primeras líneas:', corto(texto, 1500))
        print('   respuestas de datos:', len(respuestas))
        for st, tipo, u, cuerpo in respuestas[:40]:
            marca = ' <<< ALMA' if re.search(r'alma', cuerpo, re.I) else ''
            print(f'     {st} {corto(tipo, 30)} {len(cuerpo):>7} {corto(u, 200)}{marca}')
        for st, tipo, u, cuerpo in respuestas:
            if re.search(r'alma', cuerpo, re.I):
                i = re.search(r'alma', cuerpo, re.I).start()
                print('   >>> ', corto(u, 200))
                print('       ', corto(cuerpo[max(0, i - 1500):i + 1500], 3000))
                break
        pag.remove_listener('response', anotar)
    nav.close()
print('\nFIN')
