"""Utilidades compartidas: descarga, lectura de precios y fechas, y el extractor genérico de tarjetas de promo."""
import json
import re
import time
import unicodedata
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup

RAIZ = Path(__file__).resolve().parent.parent
DATA = RAIZ / 'data'
DEBUG = RAIZ / 'debug'
LIMA = timezone(timedelta(hours=-5))

UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/128.0 Safari/537.36')


def hoy_lima():
    return datetime.now(LIMA).date()


def ahora_lima_iso():
    return datetime.now(LIMA).strftime('%Y-%m-%dT%H:%M')


def bajar(url, nombre_debug, binario=False, intentos=3):
    ultimo = None
    for i in range(intentos):
        try:
            r = requests.get(url, headers={'User-Agent': UA, 'Accept-Language': 'es-PE,es;q=0.9'}, timeout=40)
            r.raise_for_status()
            DEBUG.mkdir(exist_ok=True)
            destino = DEBUG / nombre_debug
            if binario:
                destino.write_bytes(r.content)
                return r.content
            r.encoding = r.encoding if r.encoding and r.encoding.lower() != 'iso-8859-1' else 'utf-8'
            destino.write_text(r.text, encoding='utf-8')
            return r.text
        except requests.RequestException as e:
            ultimo = e
            time.sleep(3 * (i + 1))
    raise RuntimeError(f'No se pudo descargar {url}: {ultimo}')


# ── números y fechas ──
PRECIO = re.compile(r'S/\.?\s*(\d{1,3}(?:[.,\s]\d{3})*(?:[.,]\d{1,2})?|\d+(?:[.,]\d{1,2})?)', re.I)
PCT = re.compile(r'(\d{1,2})\s*%')
MESES = {'enero': 1, 'febrero': 2, 'marzo': 3, 'abril': 4, 'mayo': 5, 'junio': 6, 'julio': 7, 'agosto': 8,
         'septiembre': 9, 'setiembre': 9, 'octubre': 10, 'noviembre': 11, 'diciembre': 12}


def num(s):
    s = s.replace(' ', '')
    if ',' in s and '.' in s:
        s = s.replace(',', '') if s.rfind('.') > s.rfind(',') else s.replace('.', '').replace(',', '.')
    elif ',' in s:
        s = s.replace(',', '.') if len(s.split(',')[-1]) <= 2 else s.replace(',', '')
    elif s.count('.') == 1 and len(s.split('.')[-1]) == 3:
        s = s.replace('.', '')
    return round(float(s), 2)


def precios(texto):
    return [num(m) for m in PRECIO.findall(texto)]


def fechas(texto, ref=None):
    ref = ref or hoy_lima()
    out = []
    for d, m, a in re.findall(r'\b(\d{1,2})/(\d{1,2})/(\d{2,4})\b', texto):
        a = int(a) + (2000 if len(a) == 2 else 0)
        try:
            out.append(date(a, int(m), int(d)))
        except ValueError:
            pass
    patron = r'\b(\d{1,2})\s+de\s+(' + '|'.join(MESES) + r')(?:\s+(?:de|del)\s+(\d{4}))?'
    for d, m, a in re.findall(patron, texto.lower()):
        anio = int(a) if a else ref.year
        try:
            f = date(anio, MESES[m], int(d))
        except ValueError:
            continue
        if not a and f < ref - timedelta(days=180):
            f = date(anio + 1, MESES[m], int(d))
        out.append(f)
    return sorted(set(out))


def norm(s):
    s = re.sub(r"['’`´]", '', s)
    s = unicodedata.normalize('NFKD', s).encode('ascii', 'ignore').decode().lower()
    return re.sub(r'[^a-z0-9]+', ' ', s).strip()


def locales_conocidos():
    return json.loads((DATA / 'locales.json').read_text(encoding='utf-8'))


def casar_local(texto, conocidos):
    """Devuelve el nombre del local tal como está en el catálogo si aparece en el texto."""
    t = ' ' + norm(texto) + ' '
    mejor = None
    for nombre in conocidos:
        n = norm(nombre)
        if n and (' ' + n + ' ') in t and (not mejor or len(n) > len(norm(mejor))):
            mejor = nombre
    return mejor


# ── extractor genérico de tarjetas ──
RUIDO = ['script', 'style', 'noscript', 'svg', 'nav', 'footer', 'header', 'form']
DISPARADOR = re.compile(r'S/\.?\s*\d|\d{1,2}\s*%|2\s*x\s*1', re.I)


def _firma(el):
    return el.name, tuple(sorted(el.get('class') or []))


def _texto_sin_precios(el):
    t = el.get_text(' ', strip=True)
    return len(DISPARADOR.sub('', PRECIO.sub('', t)).strip())


def tarjetas(html):
    """Encuentra los bloques repetidos de la página que contienen un precio o un %.

    Sube desde cada precio hasta el primer ancestro que tiene al menos 3 hermanos con la misma
    etiqueta y clases (la "tarjeta" de la grilla) y que además trae texto propio, no solo el precio.
    """
    soup = BeautifulSoup(html, 'html.parser')
    for t in soup(RUIDO):
        t.decompose()
    vistas, salida = set(), []
    for nodo in soup.find_all(string=DISPARADOR):
        cur = nodo.parent
        elegido = None
        while cur is not None and cur.parent is not None and cur.name not in ('body', 'html', 'main'):
            sig = _firma(cur)
            hermanos = [c for c in cur.parent.find_all(recursive=False) if _firma(c) == sig]
            if len(hermanos) >= 3 and _texto_sin_precios(cur) >= 12:
                elegido = cur
                break
            cur = cur.parent
        if elegido is not None and id(elegido) not in vistas:
            vistas.add(id(elegido))
            salida.append(elegido)
    # si una tarjeta contiene a otra, se queda la de adentro
    return [c for c in salida if not any(o is not c and any(p is c for p in o.parents) for o in salida)]


def leer_tarjeta(el):
    lineas = [l.strip() for l in el.get_text('\n').split('\n') if l.strip()]
    texto = ' '.join(lineas)
    img = el.find('img', alt=True)
    titulo = el.find(['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'strong', 'b'])
    enlace = el.find('a', href=True)
    return {
        'lineas': lineas,
        'texto': texto,
        'alt': (img.get('alt') or '').strip() if img else '',
        'titulo': titulo.get_text(' ', strip=True) if titulo else '',
        'href': enlace['href'] if enlace else '',
    }


REGULAR = re.compile(r'(?:antes|regular|normal|precio\s+de\s+lista|valor)\D{0,15}S/\.?\s*([\d.,]+)', re.I)
STOCK = re.compile(r'stock[^\d]{0,25}(\d[\d .,]*)', re.I)
VIGENCIA = re.compile(r'v[aá]lid[oa]\s+(?:hasta|del|desde)|vigencia|^\s*(?:del|hasta el)\s+\d|\d{1,2}/\d{1,2}/\d{2,4}', re.I)
MAXIMO = re.compile(r'm[aá]x(?:imo)?\.?\s*(?:de\s+)?(\d{1,2})', re.I)


def a_fila(t, *, local, medio, programa, nota, extras=None, ciudad=''):
    """Convierte una tarjeta leída en una fila del catálogo. Todo número sale literal del texto."""
    texto = t['texto']
    ps = precios(texto)
    reg = [num(x) for x in REGULAR.findall(texto)]
    pct = [int(x) for x in PCT.findall(texto)]
    fs = fechas(texto)
    e = {'conf': 'of'}
    if ciudad:
        e['ciudad'] = ciudad
    if extras:
        e.update(extras)
    m = STOCK.search(texto)
    if m:
        e['stock'] = int(re.sub(r'\D', '', m.group(1)) or 0)
    m = MAXIMO.search(texto)
    if m:
        e['max'] = int(m.group(1))
    if re.search(r'2\s*x\s*1', texto, re.I):
        tipo, valor, regular = '2x1', 0, 0
    elif ps:
        regular = reg[0] if reg else (max(ps) if len(ps) > 1 and max(ps) > min(ps) else 0)
        candidatos = [p for p in ps if p != regular] or ps
        valor = min(candidatos)
        tipo = 'precio'
        if re.search(r'S/\.?\s*[\d.,]+\s*(?:de\s+)?(?:descuento|dscto|dcto)', texto, re.I):
            tipo, regular = 'monto', 0
    elif pct:
        tipo, valor, regular = 'porcentaje', max(pct), 0
    else:
        return None
    if tipo == 'precio' and (valor <= 0 or valor > 20000):
        return None
    if regular and regular <= valor:
        regular = 0
    utiles = [l for l in t['lineas'] if norm(l) != norm(local) and not VIGENCIA.search(l)]
    detalle = max([l for l in utiles if not DISPARADOR.search(l)] or utiles or [t['titulo'] or texto], key=len)[:140]
    desde = fs[0].isoformat() if len(fs) > 1 else ''
    vence = fs[-1].isoformat() if fs else ''
    return [local, medio, tipo, valor, regular, desde, vence, detalle, nota, programa, e]


def guardar_json(ruta, datos):
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(json.dumps(datos, ensure_ascii=False, indent=1), encoding='utf-8')


def leer_json(ruta, defecto=None):
    try:
        return json.loads(ruta.read_text(encoding='utf-8'))
    except FileNotFoundError:
        return defecto
