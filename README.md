# CLUEDO JARANDILLA — El misterio del medallón imperial
## Sprint 4

La partida permite formular una sospecha y busca automáticamente al primer
refutador según el orden de turnos. Si tiene varias coincidencias, elige en
privado; la carta seleccionada llega solo al investigador, se marca
automáticamente como `VISTA` en su hoja y el turno avanza una posición. La
refutación pendiente se conserva al reconectar.

Todavía no existen la acusación final ni el tablero o movimiento.

Proyecto cultural de Circular FAB. Juego multijugador inspirado en lugares
y personajes de Jarandilla de la Vera.

## Flujo de uso (estado actual)

1. Abrir la aplicación.
2. Crear una nueva partida (genera un código tipo `JARA-XXXX`).
3. Desde otro dispositivo, introducir código + alias y unirse.
4. Cada jugador elige su personaje en el lobby (3 a 6 jugadores).
5. Cuando todos tienen personaje, el anfitrión pulsa "Comenzar partida".
6. El servidor crea el misterio en secreto, reparte las 18 cartas
   restantes, sortea el orden de turnos y cada jugador ve únicamente
   sus cartas ("EL MISTERIO COMIENZA") junto a su hoja de
   investigación privada ("🔎 HOJA DE INVESTIGACIÓN").

## Sprint 1: lobby multijugador

Creación de salas, alias, anfitrión y sincronización del lobby
por WebSocket. Estado en memoria; el servidor es la fuente de verdad.

## Sprint 2: misterio secreto + mazo + reparto privado

Al comenzar, el servidor crea en secreto el misterio (1 sospechoso +
1 lugar + 1 objeto), baraja las 18 cartas restantes y las reparte de
forma equilibrada (3 jug.: 6/6/6; 4 jug.: 5/5/4/4; 5 jug.: 4/4/4/3/3;
6 jug.: 3/3/3/3/3/3).

- Cada jugador ve únicamente sus propias cartas, agrupadas en
  SOSPECHOSOS / LUGARES / OBJETOS.
- El misterio nunca sale del servidor: no viaja por WebSocket, API,
  HTML, JS ni logs. Cada conexión recibe solo su estado privado.
- El estado público incluye recuentos de cartas, personajes elegidos,
  orden de turnos y turno actual (nada de esto es secreto).
- Si un jugador recarga o pierde la WiFi tras comenzar, conserva su
  mano y la recupera al reconectar con su `jugador_id` (sessionStorage).
  En el lobby (sin empezar), salir sí elimina al jugador.

## Sprint 3: personajes + sorteo de turnos

- En el lobby cada jugador elige un personaje (los 6 sospechosos
  canónicos). La elección es libre pero exclusiva: un personaje solo
  puede tenerlo un jugador; se puede cambiar hasta que empiece la partida.
- Sin personaje para todos no se puede comenzar (validado en backend).
- Al comenzar se sortea una sola vez el orden de todos los jugadores
  (`turno_actual = 0`); todos ven el mismo "ORDEN DE JUEGO" y el mismo
  turno ("ES TU TURNO" / "TURNO DE …"). Recargar no vuelve a sortear.
- Todavía no hay acciones de turno (llegarán con las jugadas posteriores).

## Microfase 3B: hoja de investigación privada

- Cada jugador tiene una hoja privada con las 21 cartas canónicas
  (6 SOSPECHOSOS / 9 LUGARES / 6 OBJETOS, terminología OBJETOS).
- Sus cartas aparecen automarcadas como LA TENGO (derivado de la mano,
  no almacenable ni modificable); el resto alterna entre
  SIN INFORMACIÓN y DESCARTADA con un toque.
- El estado VISTA está reservado para Sprint 4 (sin lógica aún) y no
  puede marcarse manualmente.
- La hoja vive en memoria del servidor y sobrevive a recarga y
  reconexión (`jugador_id`); nunca viaja en `estado_publico()` ni a
  otros jugadores, y no sabe nada del misterio.

## Requisitos

- Python 3.12+
- (Opcional) Docker

## 1. Ejecutar directamente con Python

```powershell
pip install -r requirements.txt
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Abrir en el PC: http://localhost:8000

## 2. Ejecutar con Docker

```powershell
docker compose up --build
```

Abrir en el PC: http://localhost:8000

## 3. Averiguar la IP local del PC (Windows)

```powershell
ipconfig
```

Buscar el apartado del WiFi, línea `Dirección IPv4`, por ejemplo `192.168.1.50`.

## 4. Acceder desde otro dispositivo (móvil en la misma WiFi)

En el móvil, abrir el navegador y entrar en:

```
http://IP_DEL_PC:8000
```

Ejemplo: `http://192.168.1.50:8000`

El móvil debe estar conectado a la misma red WiFi que el PC.
Si no carga, revisar el firewall de Windows (permitir Python / puerto 8000).

## Pruebas

```powershell
pytest -v
```

Cubren: creación de sala, sala inexistente, alias vacío,
alias duplicado, lista de jugadores, solo el anfitrión puede iniciar,
mínimo de 3 y máximo de 6 jugadores, datos canónicos (6+9+6=21),
composición del misterio, reparto completo sin duplicados ni cartas del
 misterio, equilibrio del reparto (3/4/5/6), privacidad de manos y
 misterio por WebSocket y API pública, desconexión/reconexión
 conservando la mano, elección y exclusividad de personajes (incluido
 intento simultáneo), bloqueo tras comenzar, condición de personajes
 completos para iniciar, sorteo único de orden y turno, persistencia
 de orden/turno/personaje al reconectar, y hoja de investigación
 privada (21 canónicas, LA TENGO automático, descartes manuales,
 privacidad y persistencia de marcas).

## Estructura

```
cluedo-jarandilla/
├── app/
│   ├── main.py              # FastAPI: páginas, API REST y WebSocket
│   ├── motor/sala.py        # Lobby, personajes, misterio, reparto y turnos
│   ├── datos/jarandilla.py  # 21 cartas canónicas (sospechoso/lugar/objeto)
│   ├── static/
│   │   ├── css/estilos.css
│   │   └── js/
│   │       ├── inicio.js
│   │       └── sala.js      # Renderiza solo el estado privado propio
│   └── templates/
│       ├── inicio.html
│       └── sala.html        # Lobby + pantalla "EL MISTERIO COMIENZA"
├── recursos/                # Materiales originales (fuente, no runtime web)
├── tests/
│   ├── test_lobby.py
│   ├── test_misterio.py
│   ├── test_personajes.py
│   └── test_investigacion.py
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── .gitignore
└── README.md
```
