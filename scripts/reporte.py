"""Compara el promos.json nuevo con el publicado ayer y escribe reporte.md en español."""
import os
from datetime import date, timedelta

from comun import DATA, RAIZ, guardar_json, hoy_lima, leer_json


def clave(r):
    return (r[0], r[9], r[7].strip().lower())


def precio(r):
    if r[2] == 'porcentaje':
        return f'{r[3]:g} %'
    if r[2] in ('precio', 'monto'):
        return f'S/ {r[3]:.2f}'
    return r[2]


def main():
    nuevo = leer_json(RAIZ / '_site' / 'promos.json')
    viejo = leer_json(DATA / 'publicado.json', {'filas': []})
    a = {clave(r): r for r in viejo['filas']}
    b = {clave(r): r for r in nuevo['filas']}
    hoy = hoy_lima()
    en3 = hoy + timedelta(days=3)

    entraron = [b[k] for k in b if k not in a]
    salieron = [a[k] for k in a if k not in b]
    cambiaron = [(a[k], b[k]) for k in b if k in a and (a[k][3], a[k][4]) != (b[k][3], b[k][4])]
    vencen = sorted((r for r in nuevo['filas'] if r[6] and hoy <= date.fromisoformat(r[6]) <= en3), key=lambda r: r[6])
    rel_hoy = [r for r in nuevo['relampago'] if r['f'] == hoy.isoformat()]

    L = [f'## Promos del {hoy.strftime("%d/%m/%Y")}', '',
         f'**{len(nuevo["filas"])} promos** en el catálogo · ofertas relámpago de hoy: {len(rel_hoy)}.', '']
    fallas = {k: v for k, v in nuevo['estado'].items() if not v.get('ok')}
    if fallas:
        L += ['### ⚠️ Fuentes que no se pudieron leer (se mantienen sus datos anteriores)']
        L += [f'- **{k}**: {v.get("error", "")} · último dato bueno: {v.get("leido") or "nunca"}' for k, v in fallas.items()]
        L += ['']
    if not (entraron or salieron or cambiaron):
        L += ['Sin cambios en el catálogo.', '']
    if rel_hoy:
        L += ['### Relámpago de hoy'] + [f'- {r["t"]}: {r["o"]}' + (f' — S/ {r["p"]:.2f}' if r['p'] else '') for r in rel_hoy] + ['']
    if entraron:
        L += [f'### Nuevas ({len(entraron)})'] + [f'- {r[0]} · {r[7]} · {precio(r)} ({r[9]})' for r in entraron[:60]] + ['']
    if cambiaron:
        L += [f'### Cambiaron de precio ({len(cambiaron)})'] + [f'- {n[0]} · {n[7]}: {precio(v)} → {precio(n)}' for v, n in cambiaron[:60]] + ['']
    if salieron:
        L += [f'### Ya no aparecen ({len(salieron)})'] + [f'- {r[0]} · {r[7]} ({r[9]})' for r in salieron[:60]] + ['']
    if vencen:
        L += ['### Vencen en los próximos 3 días'] + [f'- {r[6]} · {r[0]} · {r[7]} · {precio(r)}' for r in vencen[:60]] + ['']

    texto = '\n'.join(L)
    (RAIZ / 'reporte.md').write_text(texto, encoding='utf-8')
    if os.environ.get('GITHUB_STEP_SUMMARY'):
        with open(os.environ['GITHUB_STEP_SUMMARY'], 'a', encoding='utf-8') as f:
            f.write(texto)
    guardar_json(DATA / 'publicado.json', nuevo)
    print(texto)


if __name__ == '__main__':
    main()
