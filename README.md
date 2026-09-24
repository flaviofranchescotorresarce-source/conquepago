# ¿Con qué pago? — promos que se actualizan solas, gratis

Cada mañana a las 6:17 (hora de Perú), GitHub Actions lee las páginas oficiales, copia los precios tal como aparecen (sin IA) y publica la página en GitHub Pages. Todo gratis porque el repositorio es público.

## Puesta en marcha (una sola vez)

1. **Pages:** Settings → Pages → Source: **GitHub Actions**.
2. **Primera corrida:** pestaña Actions → «Refrescar promos» → **Run workflow**.
3. La página queda en `https://<tu-usuario>.github.io/conquepago/`.
4. **Reporte diario:** se crea un issue llamado «Reporte diario de promos» y cada mañana llega ahí un comentario con lo nuevo, lo que cambió de precio, lo que salió y lo que vence en 3 días. GitHub te lo manda por correo.

## Qué hace cada archivo

| Archivo | Para qué |
|---|---|
| `data/base.json` | Catálogo base. Las promos sin script (Yape, BCP, Scotiabank, Falabella, operadores…) se editan a mano aquí |
| `data/fuentes/*.json` | Lo último bueno que leyó cada script |
| `data/estado.json` | Qué fuente respondió y cuál falló |
| `data/logos_bbva.json` | Tabla logo → marca para el PDF de BBVA |
| `scripts/fuentes.py` | Un lector por fuente |
| `scripts/refrescar.py` | Corre los lectores y guarda solo lo que pasa los controles |
| `scripts/build.py` | Une todo y aplica el freno de seguridad |
| `web/index.html` | La página |

## Controles de precisión

- Una fuente se guarda solo si trae su mínimo de filas, no cae a menos de la mitad de lo que tenía y, en Interbank, al menos la mitad de las filas corresponden a locales conocidos.
- Si una fuente falla, se mantienen sus datos anteriores y el reporte lo dice.
- Si el catálogo quedaría con menos de 210 promos, no se publica nada y el workflow falla (GitHub te manda un correo).

## Tareas de mantenimiento

**Etiquetar logos de BBVA (unos minutos al mes).** En la corrida de Actions, descarga el archivo «paginas-descargadas» y abre `logos/`. Cada imagen se llama como su huella. Agrega a `data/logos_bbva.json` una línea por marca:

```json
{"8f3c1e0a9b2d4c6e-c81e2a": "Bembos"}
```

**Si una web cambió y su lector falla.** El reporte dice cuál. En «paginas-descargadas» está la página tal como llegó, para ajustar su lector en `scripts/fuentes.py`.

**Si una web bloquea a GitHub.** Corre esa fuente desde tu PC y súbela:

```powershell
py -m pip install -r requirements.txt
py scripts/refrescar.py interbank
git add data; git commit -m "Interbank desde la PC"; git push
```

El push vuelve a publicar la página con esos datos.
