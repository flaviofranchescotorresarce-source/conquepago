"""TEMPORAL: imprime en el log cómo vienen las páginas, para ajustar los lectores. Se borra antes de mergear."""
import re
import sys

from bs4 import BeautifulSoup

from comun import bajar, leer_tarjeta, tarjetas

sys.stdout.reconfigure(line_buffering=True)


def corto(s, n):
    s = ' '.join(str(s).split())
    return s if len(s) <= n else s[:n] + '…'


def estructura(el, n=2500):
    """HTML de la tarjeta sin atributos largos, para ver dónde está la marca."""
    el = BeautifulSoup(str(el), 'html.parser')
    for t in el.find_all(True):
        for a in list(t.attrs):
            if a not in ('class', 'src', 'alt', 'href', 'title', 'data-src', 'id') and not a.startswith('data-'):
                del t.attrs[a]
    return corto(str(el), n)


def interbank():
    print('\n######## INTERBANK ########')
    html = bajar('https://interbank.pe/promociones/descuentos/plinpromos', 'interbank.html')
    print('tamaño', len(html), '| scripts JSON:', len(re.findall(r'__NEXT_DATA__|application/json|application/ld\+json', html)))
    cards = tarjetas(html)
    print('tarjetas:', len(cards))
    for el in cards[:3]:
        print('--- ejemplo de tarjeta ---')
        print(estructura(el, 4000))
    print('--- resumen de cada tarjeta: imgs | título | texto ---')
    for i, el in enumerate(cards):
        imgs = [(im.get('src') or im.get('data-src') or '').split('/')[-1][:60] + '~' + (im.get('alt') or '')[:30]
                for im in el.find_all('img')]
        t = leer_tarjeta(el)
        print(f'{i:3} {imgs} | {corto(t["titulo"], 50)} | {corto(t["texto"], 160)}')
    print('--- texto completo de tarjetas con varias promos ---')
    k = 0
    for el in cards:
        t = leer_tarjeta(el)
        if len(re.findall(r'\ba\s+S/', t['texto'])) >= 2 or re.search(r'caesars|donuts|tallar', t['texto'], re.I):
            print('>>>', estructura(el, 3000))
            print('   LINEAS:', t['lineas'])
            k += 1
            if k >= 8:
                break


def sondear(nombre, url):
    print(f'\n######## {nombre}: {url}')
    try:
        html = bajar(url, re.sub(r'\W', '_', nombre) + '.html')
    except Exception as e:  # noqa: BLE001
        print('   ERROR', corto(e, 200))
        return
    soup = BeautifulSoup(html, 'html.parser')
    texto = soup.get_text(' ', strip=True)
    print('   tamaño', len(html), '| texto visible', len(texto), '| precios S/', len(re.findall(r'S/\.?\s*\d', texto)),
          '| %', len(re.findall(r'\d{1,2}\s*%', texto)))
    print('   json embebido:', [s.get('id') or s.get('type') for s in soup.find_all('script')
                                if s.get('type') in ('application/json', 'application/ld+json') or s.get('id') == '__NEXT_DATA__'][:5])
    apis = sorted(set(re.findall(r'https?://[^"\'\s<>]*(?:api|graphql|contentful|promoc|benefic|cupon)[^"\'\s<>]*', html, re.I)))
    print('   urls tipo api:', [corto(a, 120) for a in apis[:12]])
    cards = tarjetas(html)
    print('   tarjetas:', len(cards))
    for el in cards[:6]:
        t = leer_tarjeta(el)
        print('     -', corto(t['alt'], 30), '|', corto(t['titulo'], 50), '|', corto(t['texto'], 170))
    if cards:
        print('   ejemplo:', estructura(cards[0], 1500))
    elif len(texto) < 3000:
        print('   texto:', corto(texto, 600))


if __name__ == '__main__':
    interbank()
    for nombre, url in [
        ('falabella_cuponera', 'https://www.bancofalabella.pe/promociones/detalle/cuponera-de-ous-1'),
        ('falabella', 'https://www.bancofalabella.pe/promociones'),
        ('bbva_plin', 'https://www.bbva.pe/personas/servicios-digitales/plin/descuentos.html'),
        ('scotiabank', 'https://www.scotiabank.com.pe/Personas/beneficios/promociones'),
        ('bcp', 'https://www.viabcp.com/beneficios'),
        ('diners', 'https://dinersclub.pe/promociones'),
        ('yape', 'https://www.yape.com.pe/productos/yape-promos'),
        ('interbank_tarjeta', 'https://interbank.pe/promociones/descuentos/rappi'),
        ('pedidosya', 'https://www.pedidosya.com.pe/promociones'),
        ('claro', 'https://www.claro.com.pe/personas/beneficios/claro-club/'),
        ('movistar', 'https://www.movistar.com.pe/club-movistar'),
        ('entel', 'https://www.entel.pe/beneficios'),
        ('oh', 'https://www.beneficios.tarjetaoh.pe/ohfarmas/'),
        ('amex', 'https://www.americanexpress.com/es-pe/network/beneficios/'),
    ]:
        sondear(nombre, url)
    print('\nFIN')
