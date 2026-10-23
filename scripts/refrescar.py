"""Lee cada fuente y guarda data/fuentes/<id>.json solo si el resultado pasa los controles.

Uso: python scripts/refrescar.py            (todas)
     python scripts/refrescar.py interbank  (solo algunas, p. ej. desde la PC)
"""
import sys

from comun import DATA, ahora_lima_iso, guardar_json, leer_json, locales_conocidos
from fuentes import FUENTES


def limpiar(filas):
    vistas, salida = set(), []
    for f in filas:
        clave = (f[0], f[2], f[3], f[7])
        if clave in vistas:
            continue
        vistas.add(clave)
        salida.append(f)
    return salida


def revisar(fuente, filas, previo, historial):
    n = len(filas)
    if n < fuente['minimo']:
        raise RuntimeError(f'solo {n} filas (mínimo {fuente["minimo"]})')
    if fuente.get('relampago'):
        return
    antes = len(previo['filas']) if previo else sum(
        1 for r in leer_json(DATA / 'base.json')['filas'] if fuente['propias'](r))
    # Si 3 de las últimas 5 lecturas coinciden, esa es la cantidad normal de la página hoy: así una sola
    # lectura inflada no deja la fuente congelada para siempre, y una caída de un par de días sigue frenándose.
    if len(historial) >= 3:
        antes = sorted(historial)[len(historial) // 2]
    if antes >= 8 and n < antes * 0.5:
        raise RuntimeError(f'bajó de {antes} a {n} filas: probablemente cambió la página')
    if fuente.get('clave'):
        conocidos = locales_conocidos()
        ok = sum(1 for f in filas if f[0] in conocidos)
        if ok < n * 0.5:
            raise RuntimeError(f'solo {ok} de {n} filas corresponden a locales conocidos: la lectura no es confiable')


def main(solo):
    estado = leer_json(DATA / 'estado.json', {})
    ahora = ahora_lima_iso()
    for fuente in FUENTES:
        if solo and fuente['id'] not in solo:
            continue
        ruta = DATA / 'fuentes' / f'{fuente["id"]}.json'
        previo = leer_json(ruta)
        antes = estado.get(fuente['id'], {})
        historial = antes.get('historial', [])  # cuántas filas trajo cada lectura reciente, aunque se haya rechazado
        try:
            filas = fuente['leer']()
            if not fuente.get('relampago'):
                filas = limpiar(filas)
            historial = (historial + [len(filas)])[-5:]
            revisar(fuente, filas, previo, historial)
            guardar_json(ruta, {'id': fuente['id'], 'leido': ahora, 'filas': filas})
            estado[fuente['id']] = {'ok': True, 'filas': len(filas), 'leido': ahora, 'error': '',
                                    'historial': historial}
            print(f'✔ {fuente["id"]}: {len(filas)} filas')
        except Exception as e:  # una fuente caída no debe tumbar a las demás
            estado[fuente['id']] = {'ok': False, 'filas': antes.get('filas', 0), 'leido': antes.get('leido', ''),
                                    'intento': ahora, 'error': str(e)[:300], 'historial': historial}
            print(f'✘ {fuente["id"]}: {e}')
    guardar_json(DATA / 'estado.json', estado)


if __name__ == '__main__':
    main(set(sys.argv[1:]))
