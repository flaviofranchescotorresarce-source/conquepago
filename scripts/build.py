"""Une data/base.json con lo último bueno de cada fuente y arma _site/ para GitHub Pages.

Freno de seguridad: si el catálogo queda con menos de MINIMO filas, termina con error y no se publica nada.
"""
import shutil
import sys

from comun import DATA, RAIZ, ahora_lima_iso, guardar_json, leer_json
from fuentes import FUENTES

MINIMO = 210
SITIO = RAIZ / '_site'


def armar():
    base = leer_json(DATA / 'base.json')['filas']
    estado = leer_json(DATA / 'estado.json', {})
    leidas = {f['id']: leer_json(DATA / 'fuentes' / f'{f["id"]}.json') for f in FUENTES}
    activas = [f for f in FUENTES if leidas[f['id']] and not f.get('relampago')]

    filas = [r for r in base if not any(f['propias'](r) for f in activas)]
    for f in activas:
        filas += leidas[f['id']]['filas']

    relampago = []
    for f in FUENTES:
        if f.get('relampago') and leidas[f['id']]:
            relampago = leidas[f['id']]['filas']

    ver = {}
    for f in activas:
        for programa in f['ver']:
            ver[programa] = leidas[f['id']]['leido'][:10]
    return {'actualizado': ahora_lima_iso(), 'filas': filas, 'relampago': relampago, 'ver': ver, 'estado': estado}


def main():
    datos = armar()
    n = len(datos['filas'])
    if n < MINIMO:
        print(f'FRENO: el catálogo quedaría con {n} filas (mínimo {MINIMO}). No se publica.')
        sys.exit(1)
    if SITIO.exists():
        shutil.rmtree(SITIO)
    SITIO.mkdir()
    shutil.copy(RAIZ / 'web' / 'index.html', SITIO / 'index.html')
    guardar_json(SITIO / 'promos.json', datos)
    print(f'Listo: {n} promos, {len(datos["relampago"])} ofertas relámpago')


if __name__ == '__main__':
    main()
