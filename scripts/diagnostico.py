"""TEMPORAL: corre los lectores con las páginas reales y compara con lo publicado. Se borra antes de mergear."""
import sys

from comun import DATA, leer_json, locales_conocidos
from fuentes import FUENTES
from refrescar import limpiar, revisar

sys.stdout.reconfigure(line_buffering=True)


def corto(s, n):
    s = ' '.join(str(s).split())
    return s if len(s) <= n else s[:n] + '…'


def linea(f):
    e = {k: v for k, v in (f[10] or {}).items() if k != 'conf'}
    return f'{f[0][:24]:24} {f[2][:5]:5} {f[3]:>7} {f[4]:>7} {f[5]:10} {f[6]:10} {e} | {corto(f[7], 70)} | {corto(f[8], 35)}'


if __name__ == '__main__':
    conocidos = locales_conocidos()
    for fuente in FUENTES:
        if fuente['id'] in ('bbva', 'starperu', 'telegram'):
            continue
        print(f'\n######## {fuente["id"]} ########')
        previo = leer_json(DATA / 'fuentes' / f'{fuente["id"]}.json')
        filas = []
        try:
            filas = limpiar(fuente['leer']())
            revisar(fuente, filas, previo, [len(filas)])
            veredicto = 'PASA LOS CONTROLES'
        except Exception as e:  # noqa: BLE001
            veredicto = f'NO PASA: {e}'
        antes = previo['filas'] if previo else []
        print(f'antes {len(antes)} filas → ahora {len(filas)} | {veredicto}')
        print('locales conocidos:', sum(1 for f in filas if f[0] in conocidos), '| con días:',
              sum(1 for f in filas if (f[10] or {}).get('dias')))
        claves_antes = {(f[0], f[7]): f for f in antes}
        cambios = [(claves_antes[(f[0], f[7])], f) for f in filas if (f[0], f[7]) in claves_antes
                   and (claves_antes[(f[0], f[7])][2:7]) != f[2:7]]
        print('mismas promos con otro tipo/precio/fecha:', len(cambios))
        for a, b in cambios[:15]:
            print(f'   {a[0][:20]:20} {a[2:7]} → {b[2:7]} | {corto(b[7], 60)}')
        limite = 400 if fuente['id'] in ('interbank', 'cencosud') else 25
        for f in filas[:limite]:
            print(linea(f))
    print('\nFIN')
