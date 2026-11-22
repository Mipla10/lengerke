# Expedición Caminos de Lengerke

**Publicada en: https://mipla10.github.io/lengerke/**

Página estática (sin backend) con la ruta del trekking: mapa 3D animado, pestañas por día, perfil de elevación sincronizado y tips.

```
index.html              la página
data/route.json         datos calculados (no editar a mano)
og-image.png            vista previa para WhatsApp (1200×630)
gpx/                    tracks originales de Wikiloc (solo en local, no se suben)
scripts/build_route.py  GPX → data/route.json
scripts/og-image.html   plantilla de og-image.png
```

## Regenerar datos

```bash
python3 scripts/build_route.py
```

Usa solo la librería estándar de Python. Los tiempos, noches y costos del itinerario están en `ITINERARY` dentro del script.

## Regenerar la imagen de vista previa

```bash
python3 -m http.server 8765
chromium --headless=new --window-size=1200,630 --hide-scrollbars \
  --virtual-time-budget=5000 --screenshot=og-image.png \
  http://127.0.0.1:8765/scripts/og-image.html
```

## Probar en local

`index.html` carga `data/route.json` con `fetch`, así que hay que servirla (abrirla con doble clic no funciona):

```bash
python3 -m http.server 8765    # y abrir http://127.0.0.1:8765
```

## Llave de MapTiler

Al inicio del `<script>` de `index.html`:

```js
const MAPTILER_KEY = "PEGAR_AQUI";
```

Crea una cuenta gratis en https://cloud.maptiler.com, copia tu API key y pégala ahí. Recomendado: en MapTiler, en la configuración de la llave, restringe los orígenes permitidos a `https://TU-USUARIO.github.io` (la llave queda visible en el código de la página).

Sin llave, la página usa alternativas gratuitas (satélite de Esri y relieve de Mapzen/AWS), así que funciona igual mientras tanto.

## Publicar gratis en GitHub Pages

1. Crea una cuenta en https://github.com si no tienes.
2. Crea un repositorio nuevo **público** llamado `lengerke` (botón **New** → nombre `lengerke` → **Create repository**). No marques "Add a README".
3. Antes de subir, reemplaza `TU-USUARIO` por tu usuario de GitHub en las etiquetas `og:url` y `og:image` de `index.html`. WhatsApp necesita la URL completa de la imagen.
4. Sube los archivos. Opción fácil, desde la web: en el repo vacío, clic en **uploading an existing file**, arrastra `index.html`, `og-image.png`, `README.md` y las carpetas `data`, `gpx` y `scripts`, y luego **Commit changes**.
   Opción con terminal, desde esta carpeta:
   ```bash
   git init -b main
   git add .
   git commit -m "Expedición Caminos de Lengerke"
   git remote add origin https://github.com/TU-USUARIO/lengerke.git
   git push -u origin main
   ```
5. En el repo: **Settings → Pages**. En *Build and deployment*, en *Source* elige **Deploy from a branch**, en *Branch* elige **main** y carpeta **/ (root)**, y luego **Save**.
6. Espera uno o dos minutos y recarga esa página de Settings. Aparece el link: `https://TU-USUARIO.github.io/lengerke/`.
7. Revisa la vista previa pegando el link en https://www.opengraph.xyz antes de mandarlo por WhatsApp. Si WhatsApp ya guardó una vista previa vieja, agrega `?v=2` al final del link.

Cada vez que cambies algo, sube los archivos de nuevo (o `git commit` + `git push`) y Pages se actualiza solo en un par de minutos.

## Créditos

Tracks GPS de Wikiloc: "Camino real Los Santos - Jordan - Villanueva - Barichara" por *El ultimo kogui scout* y "Barichara - Guane - Zapatoca (camino real Lengerke)" por *jacortex*.
