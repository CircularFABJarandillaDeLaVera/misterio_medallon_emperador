# El Misterio del Medallón

Juego web multijugador de investigación y deducción ambientado en Jarandilla
de la Vera, desarrollado en Circular FAB Jarandilla.

El objetivo es descubrir quién escondió el medallón, en qué lugar de la
localidad lo hizo y dentro de qué objeto lo ocultó. La partida combina
personajes originales, lugares reconocibles de Jarandilla de la Vera y una
investigación privada para cada participante.

## Cómo se juega

- Una persona crea una sala y comparte su código `JARA-XXXX`.
- De una a seis personas pueden entrar desde sus navegadores y elegir personaje.
- Los puestos libres se completan con personajes controlados por PNJ.
- Durante cada turno se recorre el tablero, se formulan sospechas y otros
  participantes pueden refutarlas mostrando una única carta en privado.
- Para ganar hay que resolver correctamente las tres partes del misterio:
  personaje, lugar y objeto.
- Una resolución incorrecta elimina al participante como investigador, pero
  conserva sus cartas y puede continuar refutando manualmente o en automático.
- Al finalizar, el anfitrión puede iniciar una revancha en la misma sala.

El servidor es la fuente de verdad. El misterio, las manos y las hojas de
investigación privadas no se revelan a otros participantes.

## Tecnología

- Python y FastAPI para API, estado de salas y reglas del juego.
- WebSockets para sincronización multijugador en tiempo real.
- HTML, CSS y JavaScript sin framework para la interfaz.
- Canvas para representar el tablero, las fichas y el movimiento.
- Pytest y harnesses Node.js para validar servidor e interfaz.
- Docker Compose como alternativa de ejecución local.

## Proyecto educativo y creativo

El Misterio del Medallón es también una experiencia de creación y aprendizaje
en Circular FAB Jarandilla. El proyecto combina programación, diseño,
fabricación digital, creatividad e inteligencia artificial para construir una
experiencia jugable vinculada al entorno local.

## Requisitos

- Python 3.12 o posterior.
- Node.js para ejecutar los harnesses de interfaz.
- Docker y Docker Compose, opcionales.

## Ejecución local

```powershell
git clone <URL_DEL_REPOSITORIO>
cd misterio-medallon
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

No se incluye una URL de GitHub concreta porque no está configurada en este
repositorio local. Una vez iniciado el servidor, abre
<http://localhost:8000>.

También puede ejecutarse con Docker:

```powershell
docker compose up --build
```

Para jugar desde otros dispositivos de la misma red, abre en ellos
`http://IP_DEL_EQUIPO:8000` y permite el puerto 8000 en el firewall si fuera
necesario.

## Pruebas

Suite del servidor:

```powershell
python -m pytest -q
```

Harnesses principales de interfaz:

```powershell
node tests/resolver_confirm_check.cjs
node tests/audio_fondo_check.cjs
node tests/hoja_render_check.cjs
node tests/interfaz_panel_check.cjs
node tests/modo_seleccion_check.cjs
node tests/movimiento_render_check.cjs
node tests/tablero_canvas_check.cjs
node tests/tablero_montaje_real_check.cjs
```

Comprobación sintáctica del JavaScript principal:

```powershell
node --check app/static/js/sala.js
node --check app/static/js/audio.js
```

## Estructura

```text
misterio-medallon/
├── app/
│   ├── main.py                 # FastAPI, API y WebSockets
│   ├── motor/                  # Reglas, salas y tablero canónico
│   ├── datos/                  # Cartas y manifiestos de recursos
│   ├── static/                 # CSS, JavaScript, imágenes y audio web
│   └── templates/              # Portada y sala de juego
├── recursos/                   # Materiales gráficos y fuentes originales
├── tests/                      # Pytest y harnesses Node.js
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── LICENSE
```

## Estado actual

El proyecto se encuentra en preparación para su primera publicación. Incluye
lobby multijugador, salas por código, participantes humanos y PNJ, tablero con
movimiento y pasadizos, sospechas y refutaciones privadas, hoja de
investigación, resolución final, eliminación individual, refutación automática,
revancha en la misma sala, audio y soporte de pantalla completa.

Las salas viven en memoria del proceso. Reiniciar el servidor elimina las
partidas activas y todavía no existe persistencia mediante base de datos.

## Licencia

El código fuente se distribuye bajo la licencia MIT. Consulta [LICENSE](LICENSE).

Los recursos gráficos, fotografías, ilustraciones y otros materiales incluidos
en `recursos/` pueden estar sujetos a condiciones distintas y no se consideran
automáticamente licenciados bajo MIT salvo que se indique expresamente.
