"""TEMPORAL: busca dónde publica BCP sus beneficios de Cuenta Sueldo. Se borra antes de mergear."""
import re
import sys
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from comun import bajar, leer_tarjeta, tarjetas

sys.stdout.reconfigure(line_buffering=True)


def corto(s, n):
    s = ' '.join(str(s).split())
    return s if len(s) <= n else s[:n] + '…'


def sondear(url, detalle=True):
    print(f'\n######## {url}')
    try:
        html = bajar(url, 'bcp.html')
    except Exception as e:  # noqa: BLE001
        print('   ERROR', corto(e, 200))
        return ''
    soup = BeautifulSoup(html, 'html.parser')
    texto = soup.get_text(' ', strip=True)
    print('   tamaño', len(html), '| texto', len(texto), '| %', len(re.findall(r'\d{1,2}\s*%', texto)),
          '| "alma" en html:', len(re.findall(r'alma', html, re.I)))
    for m in list(re.finditer(r'alma', html, re.I))[:8]:
        print('   alma>', corto(html[max(0, m.start() - 200):m.end() + 300], 500))
    if detalle:
        enlaces = sorted({urljoin(url, a['href']) for a in soup.find_all('a', href=True)
                          if re.search(r'benefic|sueldo|descuent|promoc|restaur', a['href'], re.I)})
        print('   enlaces:', len(enlaces))
        for e in enlaces[:80]:
            print('     ', corto(e, 160))
        print('   scripts:', [corto(s.get('src'), 120) for s in soup.find_all('script', src=True)][:25])
        print('   urls json/api:', sorted({corto(u, 160) for u in re.findall(r'[\w/.:-]*(?:\.json|/api/|wcm/connect/[^"\'\s]*?(?:json|JSON))[^"\'\s<>]*', html)})[:20])
    cards = tarjetas(html)
    print('   tarjetas:', len(cards))
    for el in cards[:15]:
        t = leer_tarjeta(el)
        print('     -', corto(t['alt'], 30), '|', corto(t['titulo'], 40), '|', corto(t['texto'], 150))
    return html


if __name__ == '__main__':
    for u in ['https://www.viabcp.com/beneficios',
              'https://www.viabcp.com/beneficios/todos-los-beneficios?rfid=beneficios:promociones-descuentos:mundo-cuenta-sueldo:card',
              'https://www.viabcp.com/beneficios/todos-los-beneficios',
              'https://www.viabcp.com/cuenta-sueldo',
              'https://www.viabcp.com/beneficios/cuenta-sueldo']:
        sondear(u)
    print('\nFIN')
