"""Una entrada por fuente: qué lee, qué filas del catálogo reemplaza y cuántas necesita para darse por buena."""
import json
import re
from datetime import datetime, timedelta

from bs4 import BeautifulSoup

from comun import (DEBUG, DATA, LIMA, a_fila, bajar, casar_local, fechas, hoy_lima, leer_json, leer_tarjeta,
                   locales_conocidos, norm, precios, tarjetas)

RESTRICCION = re.compile(r'no aplica|no v[aá]lid|solo |s[oó]lo |v[aá]lid|m[aá]x|stock|excepto|delivery|sal[oó]n|llevar|'
                         r'lunes|martes|mi[eé]rcoles|jueves|viernes|s[aá]bado|domingo|horario|hasta agotar', re.I)


def nota_de(t, defecto):
    partes = [l for l in t['lineas'] if RESTRICCION.search(l)]
    return (' · '.join(dict.fromkeys(partes))[:180]) or defecto


def nombre_local(t, conocidos, fijo=None):
    if fijo:
        return fijo
    return (casar_local(' '.join([t['alt'], t['titulo'], t['texto']]), conocidos)
            or t['alt'] or t['titulo'] or t['lineas'][0])[:60]


def desde_html(url, debug, *, medio, programa, defecto, local=None, ciudad='', ciudad_si_lima=False, extras=None):
    html = bajar(url, debug)
    conocidos = locales_conocidos()
    filas = []
    for el in tarjetas(html):
        t = leer_tarjeta(el)
        nombre = nombre_local(t, conocidos, local)
        c = ciudad
        if ciudad_si_lima:
            c = 'AQP' if 'arequipa' in norm(t['texto']) else (conocidos.get(nombre) or 'Lima')
        f = a_fila(t, local=nombre, medio=medio, programa=programa, nota=nota_de(t, defecto), ciudad=c, extras=extras)
        if f:
            filas.append(f)
    return filas


# ── Interbank: primero busca datos JSON dentro de la página; si no hay, lee las tarjetas del HTML ──
CLAVES_MARCA = ('marca', 'brand', 'comercio', 'partner', 'store', 'tienda', 'establecimiento')
CLAVES_TITULO = ('title', 'titulo', 'nombre', 'name', 'descripcion', 'description', 'detalle')


def _json_embebidos(html):
    soup = BeautifulSoup(html, 'html.parser')
    for s in soup.find_all('script'):
        txt = s.string or ''
        if not txt.strip():
            continue
        candidatos = [txt]
        if s.get('type') not in ('application/json', 'application/ld+json') and s.get('id') != '__NEXT_DATA__':
            candidatos = re.findall(r'=\s*(\{.*\}|\[.*\])\s*;?\s*$', txt, re.S)
        for c in candidatos:
            try:
                yield json.loads(c)
            except (ValueError, TypeError):
                pass


def _recorrer(o):
    if isinstance(o, dict):
        yield o
        for v in o.values():
            yield from _recorrer(v)
    elif isinstance(o, list):
        for v in o:
            yield from _recorrer(v)


def _valor(d, pistas):
    for k, v in d.items():
        kl = k.lower()
        if any(p in kl for p in pistas) and isinstance(v, (str, int, float)) and str(v).strip():
            return v
    return None


def _num(v):
    ps = precios('S/' + str(v)) if not isinstance(v, (int, float)) else [float(v)]
    return ps[0] if ps else None


def interbank_json(html, conocidos):
    filas = []
    for raiz in _json_embebidos(html):
        for d in _recorrer(raiz):
            promo = _valor(d, ('preciopromo', 'promoprice', 'precio_promo', 'precioplin', 'saleprice', 'offerprice'))
            regular = _valor(d, ('precioregular', 'regularprice', 'precio_regular', 'normalprice', 'oldprice', 'listprice'))
            if promo is None:
                promo = _valor(d, ('precio', 'price'))
            if promo is None or _num(promo) is None:
                continue
            marca = _valor(d, CLAVES_MARCA)
            titulo = _valor(d, CLAVES_TITULO) or ''
            texto = f'{marca or ""} {titulo}'
            local = casar_local(texto, conocidos) or (str(marca) if marca else None)
            if not local:
                continue
            fin = _valor(d, ('fechafin', 'enddate', 'hasta', 'vence', 'vigenciafin', 'fin'))
            ini = _valor(d, ('fechainicio', 'startdate', 'desde', 'inicio'))
            fv = fechas(str(fin)) if fin else []
            fi = fechas(str(ini)) if ini else []
            e = {'conf': 'of'}
            st = _valor(d, ('stock',))
            mx = _valor(d, ('max', 'limite'))
            if st and str(st).isdigit():
                e['stock'] = int(st)
            if mx and str(mx).isdigit():
                e['max'] = int(mx)
            filas.append([local, 'Plin Interbank', 'precio', _num(promo), _num(regular) or 0,
                          fi[0].isoformat() if fi else '', fv[-1].isoformat() if fv else '',
                          str(titulo)[:140], 'Leído de la web de Interbank', 'Plin Interbank', e])
    return filas


def leer_interbank():
    url = 'https://interbank.pe/promociones/descuentos/plinpromos'
    html = bajar(url, 'interbank.html')
    conocidos = locales_conocidos()
    filas = interbank_json(html, conocidos)
    if len(filas) >= 20:
        return filas
    filas = []
    for el in tarjetas(html):
        t = leer_tarjeta(el)
        f = a_fila(t, local=nombre_local(t, conocidos), medio='Plin Interbank', programa='Plin Interbank',
                   nota=nota_de(t, 'Pagando con QR Plin en el local'), ciudad=conocidos.get(nombre_local(t, conocidos), ''))
        if f:
            filas.append(f)
    return filas


# ── BBVA: PDF de provincias, sección Arequipa. La marca sale del logo (tabla de hashes) o del combo ──
POR_COMBO = [(r'\broyal\b|\bcheese\b|queso tocino', 'Bembos'), (r'whopper', 'Burger King'),
             (r'avocado chicken bowl', 'Chili’s'), (r'donut', 'Dunkin'), (r'nuggets?.*piezas|piezas.*nuggets?', 'KFC')]
CIUDADES = ['AREQUIPA', 'CUSCO', 'TRUJILLO', 'CHICLAYO', 'PIURA', 'ICA', 'HUANCAYO', 'TACNA', 'PUNO', 'CAJAMARCA',
            'IQUITOS', 'PUCALLPA', 'TARAPOTO', 'AYACUCHO', 'HUÁNUCO', 'HUANUCO', 'CHIMBOTE', 'JULIACA', 'MOQUEGUA',
            'TUMBES', 'LIMA']


def huella(im):
    """Forma (phash) + color promedio: dos logos iguales de forma pero de otro color no se confunden."""
    import imagehash
    r, g, b = im.resize((1, 1)).getpixel((0, 0))
    return f'{imagehash.phash(im)}-{r:02x}{g:02x}{b:02x}'


def parecidos(a, b):
    import imagehash
    fa, ca = a.split('-')
    fb, cb = b.split('-')
    color = sum(abs(int(ca[i:i + 2], 16) - int(cb[i:i + 2], 16)) for i in (0, 2, 4))
    return imagehash.hex_to_hash(fa) - imagehash.hex_to_hash(fb) <= 4 and color <= 45


def leer_bbva():
    import fitz
    from PIL import Image

    url = ('https://www.bbva.pe/content/dam/public-web/peru/documents/personas/catalogo-promociones/'
           'Catalogo-provincias.pdf')
    pdf = fitz.open(stream=bajar(url, 'bbva.pdf', binario=True), filetype='pdf')
    logos = leer_json(DATA / 'logos_bbva.json', {})
    (DEBUG / 'logos').mkdir(parents=True, exist_ok=True)
    filas, en_aqp = [], False
    for pagina in pdf:
        texto = pagina.get_text()
        encabezados = [c for c in CIUDADES if re.search(r'(^|\n)\s*' + c + r'\s*(\n|$)', texto)]
        if encabezados:
            en_aqp = 'AREQUIPA' in encabezados
        if not en_aqp:
            continue
        imagenes = []
        for img in pagina.get_images(full=True):
            for rect in pagina.get_image_rects(img[0]):
                if 20 < rect.width < pagina.rect.width * 0.6:
                    imagenes.append(rect)
        for x0, y0, x1, y1, bloque, *_ in pagina.get_text('blocks'):
            if not (precios(bloque) or re.search(r'\d{1,2}\s*%', bloque)):
                continue
            t = {'lineas': [l.strip() for l in bloque.split('\n') if l.strip()], 'texto': ' '.join(bloque.split()),
                 'alt': '', 'titulo': '', 'href': ''}
            local, conf = None, 'of'
            if imagenes:
                cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
                rect = min(imagenes, key=lambda r: ((r.x0 + r.x1) / 2 - cx) ** 2 + ((r.y0 + r.y1) / 2 - cy) ** 2)
                pix = pagina.get_pixmap(clip=rect, dpi=72, colorspace=fitz.csRGB, alpha=False)
                im = Image.frombytes('RGB', (pix.width, pix.height), pix.samples)
                h = huella(im)
                local = next((m for k, m in logos.items() if parecidos(k, h)), None)
                if not local:
                    pix.save(str(DEBUG / 'logos' / f'{h}.png'))
            nota = 'Pagando con tarjeta BBVA en Arequipa'
            if not local:
                for patron, marca in POR_COMBO:
                    if re.search(patron, t['texto'], re.I):
                        local, conf, nota = marca, 'rep', 'Marca deducida del combo, no confirmada por el logo'
                        break
            f = a_fila(t, local=local or 'Restaurantes BBVA Arequipa', medio='Tarjeta BBVA', programa='Tarjeta BBVA',
                       nota=nota, ciudad='AQP', extras={'conf': conf})
            if f:
                filas.append(f)
    return filas


# ── Telegram: ofertas relámpago de hoy y ayer ──
TIENDAS_EXTRA = ['Ripley', 'Plaza Vea', 'Tottus', 'Wong', 'Promart', 'Sodimac', 'Real Plaza', 'Hiraoka', 'Coolbox',
                 'Estilos', 'Mercado Libre', 'Amazon', 'Temu', 'AliExpress', 'Shein', 'Adidas', 'Nike', 'Puma',
                 'Juntoz', 'Bata', 'Viale', 'Samsung', 'Xiaomi', 'Lenovo', 'Vivanda', 'Mass', 'Efe', 'La Curacao',
                 'Carsa', 'Saga', 'Paris', 'Linio', 'Joinnus', 'Teleticket', 'Pedidos Ya']
NO_OFERTA = re.compile(r'sorteo|giveaway|gana un|participa|únete al canal|unete al canal|invita a tus', re.I)
SI_OFERTA = re.compile(r'S/\.?\s*\d|\d{1,2}\s*%|oferta|descuento|dscto|cup[oó]n|c[oó]digo|promo|remate|2x1|gratis|liquidaci', re.I)


def leer_telegram():
    html = bajar('https://t.me/s/concuponperu', 'telegram.html')
    soup = BeautifulSoup(html, 'html.parser')
    mensajes = soup.select('.tgme_widget_message')
    if not mensajes:
        raise RuntimeError('La vista web del canal no trajo mensajes (¿cambió o se restringió?)')
    tiendas = list(locales_conocidos()) + TIENDAS_EXTRA
    hoy = hoy_lima()
    salida = []
    for m in mensajes:
        cuerpo = m.select_one('.tgme_widget_message_text')
        cuando = m.select_one('time[datetime]')
        if not cuerpo or not cuando:
            continue
        f = datetime.fromisoformat(cuando['datetime']).astimezone(LIMA).date()
        if (hoy - f).days > 1:
            continue
        lineas = [l.strip() for l in cuerpo.get_text('\n').split('\n') if l.strip()]
        texto = ' '.join(lineas)
        if NO_OFERTA.search(texto) or not SI_OFERTA.search(texto):
            continue
        tienda = casar_local(texto, tiendas) or 'Concupón'
        ps = precios(texto)
        reg = re.findall(r'(?:antes|regular|normal)\D{0,12}S/\.?\s*([\d.,]+)', texto, re.I)
        p = ps[0] if ps else 0
        r = precios('S/' + reg[0])[0] if reg else (max(ps) if len(ps) > 1 and max(ps) > p else 0)
        oferta = next((l for l in lineas if len(re.sub(r'\W', '', l)) > 8), lineas[0])
        resto = [l for l in lineas if l != oferta and not l.startswith('http')]
        post = m.get('data-post', '')
        salida.append({'f': f.isoformat(), 't': tienda, 'o': oferta[:110], 'p': p, 'r': r,
                       'n': ' · '.join(resto)[:200], 'u': f'https://t.me/{post}' if post else ''})
    return salida


def es(local=None, programa=None, ciudad=None):
    def f(fila):
        return ((local is None or fila[0] == local) and (programa is None or fila[9] in programa)
                and (ciudad is None or (fila[10] or {}).get('ciudad') == ciudad))
    return f


FUENTES = [
    {'id': 'interbank', 'leer': leer_interbank, 'minimo': 40, 'clave': True,
     'propias': es(programa={'Plin Interbank'}), 'ver': ['Plin Interbank']},
    {'id': 'telegram', 'leer': leer_telegram, 'minimo': 0, 'relampago': True, 'propias': None, 'ver': []},
    {'id': 'bbva', 'leer': leer_bbva, 'minimo': 5, 'propias': es(programa={'Tarjeta BBVA'}, ciudad='AQP'), 'ver': ['Tarjeta BBVA']},
    {'id': 'caja_arequipa', 'minimo': 4, 'propias': es(programa={'Tarjeta Caja Arequipa'}), 'ver': ['Tarjeta Caja Arequipa'],
     'leer': lambda: desde_html('https://www.cajaarequipa.pe/programa-de-beneficios/', 'caja.html',
                                medio='Tarjeta Caja Arequipa', programa='Tarjeta Caja Arequipa',
                                defecto='Pagando con tarjeta de débito VISA de Caja Arequipa', ciudad='AQP')},
    {'id': 'cuponatic', 'minimo': 5, 'propias': es(programa={'Cuponatic'}), 'ver': ['Cuponatic'],
     'leer': lambda: desde_html('https://www.cuponatic.com.pe/', 'cuponatic.html', medio='Cuponatic',
                                programa='Cuponatic', defecto='Compra el cupón en Cuponatic', ciudad_si_lima=True)},
    {'id': 'cuponidad', 'minimo': 5, 'propias': es(programa={'Cuponidad'}), 'ver': ['Cuponidad'],
     'leer': lambda: desde_html('https://cuponidad.pe/', 'cuponidad.html', medio='Cuponidad', programa='Cuponidad',
                                defecto='Compra el cupón en Cuponidad', ciudad_si_lima=True)},
    {'id': 'papajohns', 'minimo': 2, 'propias': es('Papa Johns', {'Web/app de la marca'}), 'ver': ['Web/app de la marca'],
     'leer': lambda: desde_html('https://www.papajohns.com.pe/menu/promociones', 'papajohns.html',
                                medio='Web/app de la marca', programa='Web/app de la marca', local='Papa Johns',
                                defecto='Promo de la web y app de Papa Johns', extras={'canal': 'A'})},
    {'id': 'nutripoint', 'minimo': 2, 'propias': es('NutriPoint', {'Promo del local'}), 'ver': [],
     'leer': lambda: desde_html('https://www.nutripoint.com.pe/promociones/', 'nutripoint.html',
                                medio='Promo del local', programa='Promo del local', local='NutriPoint',
                                defecto='Precio de la tienda NutriPoint', extras={'canal': 'A'})},
    {'id': 'cencosud', 'minimo': 1, 'propias': es(programa={'Tarjeta Cencosud'}), 'ver': ['Tarjeta Cencosud'],
     'leer': lambda: desde_html('https://www.tarjetacencosud.pe/promotion/boticas-y-salud/', 'cencosud.html',
                                medio='Tarjeta Cencosud', programa='Tarjeta Cencosud',
                                defecto='Pide el descuento en caja con tu Tarjeta Cencosud')},
    {'id': 'starperu', 'minimo': 1, 'propias': es('Star Perú', {'Diners Club'}), 'ver': [],
     'leer': lambda: desde_html('https://www.starperu.com/es/promociones/marca/diners_club', 'starperu.html',
                                medio='Diners Club', programa='Diners Club', local='Star Perú',
                                defecto='Pagando con Diners Club en starperu.com', extras={'canal': 'APP'})},
]
