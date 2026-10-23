"""TEMPORAL: prueba los lectores con las páginas reales e imprime el resultado en el log. Se borra antes de mergear."""
import re
import sys

from bs4 import BeautifulSoup

from comun import bajar, leer_tarjeta, locales_conocidos, tarjetas
from fuentes import FUENTES, _marca_ibk, _promos_ibk

sys.stdout.reconfigure(line_buffering=True)


def corto(s, n):
    s = ' '.join(str(s).split())
    return s if len(s) <= n else s[:n] + '…'


def cadena(el):
    pasos = []
    for a in [el, *el.parents][:9]:
        fuertes = [s.get_text(' ', strip=True)[:25] for s in a.find_all('strong', recursive=True)][:3]
        imgs = [(i.get('src') or '').split('/')[-1][:30] for i in a.find_all('img')][:2]
        pasos.append(f'{a.name}.{".".join(a.get("class") or [])[:40]} strongs={fuertes} imgs={imgs}')
    return '\n        '.join(pasos)


def interbank():
    print('\n######## INTERBANK: promos sin marca ########')
    html = bajar('https://interbank.pe/promociones/descuentos/plinpromos', 'interbank.html')
    sin = 0
    for el in tarjetas(html):
        items = [li for li in el.find_all('li') if re.search(r'S/|%', li.get_text())] or [el]
        for item in items:
            if _marca_ibk(item) is None and re.search(r'S/|%', item.get_text()):
                sin += 1
                if sin <= 6:
                    print('---', corto(item.get_text(' ', strip=True), 120))
                    print('        ' + cadena(item))
    print('promos sin marca:', sin)
    print('\n######## INTERBANK: filas del lector nuevo ########')
    fuente = next(f for f in FUENTES if f['id'] == 'interbank')
    filas = fuente['leer']()
    conocidos = locales_conocidos()
    print('filas:', len(filas), '| locales conocidos:', sum(1 for f in filas if f[0] in conocidos))
    for f in filas:
        print(f'{f[0][:24]:24} {f[2][:5]:5} {f[3]:>7} {f[4]:>7} {f[5]:10} {f[6]:10} | {corto(f[7], 80)} | {corto(f[8], 40)}')
    marcas = [m for m, _ in _promos_ibk(html)]
    print('segmentos:', len(marcas), '| sin marca:', marcas.count(None))


def cencosud():
    print('\n######## CENCOSUD ########')
    html = bajar('https://www.tarjetacencosud.pe/promotion/boticas-y-salud/', 'cencosud.html')
    cards = tarjetas(html)
    print('tarjetas:', len(cards))
    for el in cards[:4]:
        el = BeautifulSoup(str(el), 'html.parser')
        for t in el.find_all(True):
            for a in list(t.attrs):
                if a not in ('class', 'src', 'alt', 'href', 'title') and not a.startswith('data-'):
                    del t.attrs[a]
        print('>>>', corto(str(el), 1800))
    for el in cards[:40]:
        t = leer_tarjeta(el)
        print('  -', corto(t['alt'], 35), '|', corto(t['titulo'], 35), '|', corto(t['href'], 60), '|', corto(t['texto'], 120))


if __name__ == '__main__':
    interbank()
    cencosud()
    print('\nFIN')
