---
name: misterio-medallon
description: Cómo trabajar en El Misterio del Medallón sin romperlo. Usar al modificar este repo: orientarse, reutilizar, validar por microfases y Git seguro.
---

# El Misterio del Medallón — Cómo trabajar aquí

Juego multijugador de deducción (FastAPI + WebSocket + Canvas). Se trabaja por
**microfases**: un cambio mínimo → tests → validación humana → checkpoint Git.

## 0. SEARCH BEFORE CREATE

Antes de crear CSS, componentes, helpers, modales, funciones, estructuras,
tests o recursos, **busca si ya existe una solución reutilizable** y úsala.
Crear un sistema paralelo sin justificarlo es un defecto, no una mejora.

Ejemplos reales que ya existen — no duplicar:

- Familia visual de botones `.medallon` (`.medallon-primario`,
  `.medallon-secundario`, `.medallon-fantasma`, `.medallon-compacto`)
  en `app/static/css/estilos.css`. No crear una segunda familia de botones.
- Sistema de modales `.modal` / `.modal-caja` en `estilos.css` + `sala.html`.
  Los popups de Inicio lo reutilizan (`portada-modal-caja`).
- Helpers de cartas visuales en `app/static/js/sala.js`
  (renders de sospecha/resolver/hoja). Reutilizar antes de inventar.

## 1. Fuente de verdad (consultar, no memorizar)

| Pregunta | Dónde mirar |
|---|---|
| Reglas del juego | `app/motor/sala.py` + `tests/test_*.py` |
| Tablero/topología | `app/motor/tablero.py` (canónico) + `tests/test_tablero*.py` |
| Cartas canónicas | `app/datos/jarandilla.py` |
| Recursos visuales | `GET /api/recursos` y `app/datos/recursos.py` |
| Frontend | `app/templates/*.html` + `app/static/js/*.js` + `estilos.css` actuales |
| Comportamiento esperado | `tests/*.py` y `tests/*.cjs` (harnesses Node del flujo real) |
| Estado de la microfase | `git status --short` + `git log --oneline -5` + código actual |

Si documentación (p. ej. `README.md`) y código discrepan: **no adivinar**.
El código + tests mandan. Señalar la discrepancia.
(Caso conocido: el README describe topología antigua; la autoridad es
`app/motor/tablero.py`.)

## 2. Invariantes (no romper accidentalmente)

- Sin sospecha gratuita: para sospechar hay que ENTRAR en un lugar ese turno
  (`formular_sospecha` exige `estado_jugada` + ubicación actual en modo
  tablero). Aplica a Vera aunque empiece en el Parador.
- `CENTRO_ID = "parador"`. Pasadizos: Plaza Constitución ↔ Ntra. Sra. de la
  Torre; Ermita de Sopetrán ↔ Puente Parral (`PAREJAS_PASADIZOS`).
- Cada camino directo tiene exactamente 3 nodos intermedios (c1–c3).
- El misterio nunca sale del servidor; la refutación solo la ve su
  investigador; el conocimiento privado PNJ no se expone.
- Resolver exige doble confirmación: CONTINUAR no envía; solo la
  confirmación final (`modal-confirmar-resolver`) resuelve.
- TABLERO es el modo normal. RÁPIDO es infraestructura de pruebas/dev:
  oculto en la interfaz (solo `Ctrl+Alt+D`, sin persistencia). El frontend
  siempre envía `modo` explícito (`POST /api/partidas`).

Detalle completo: código y tests. Esta lista no es exhaustiva.

## 3. Cambios visuales (procedimiento)

1. Localizar el componente existente (template + JS + CSS).
2. Buscar estilos/helpers reutilizables (§0).
3. Comprobar qué pantallas heredan ese CSS (un cambio compartido puede
   afectar a otras: verificar alcance antes de tocar).
4. Preservar contratos JS/backend (IDs, endpoints, payloads).
5. Hacer el cambio mínimo.
6. Validación visual humana antes del checkpoint. Un test verde no sustituye
   ver la pantalla cuando el cambio es visual.

## 4. Horizontal-first en vistas de juego

- Referencia canónica: desktop/tablet apaisado. Aprovechar el ancho antes
  de crecer en alto; evitar scroll del documento en el viewport de juego.
- En vistas inmersivas/protagonistas resolver la geometría de fuera hacia
  dentro: **viewport → contenedor limitado → controles con su mínimo →
  protagonista ocupando todo el espacio restante**. Aplica a portada, tablero
  y futuro fullscreen: el mismo patrón, con más viewport.
- El viewport limita al contenedor, nunca el tamaño intrínseco del contenido.
  Usar alturas computables en padres y revisar `min-height: 0` / `min-width: 0`
  en flex/grid; no compensar con alturas mágicas del protagonista.
- En desktop/apaisado, evitar scroll del documento sin esconder una geometría
  incorrecta con `overflow: hidden`. En móvil/vertical se puede reorganizar y
  admitir scroll natural.
- Si una medición headless contradice la captura, validar en navegador real.
- Preferir filas/distribuciones horizontales con ancho suficiente.
- El responsive puede hacer wrap en viewports estrechos, pero el móvil
  vertical no condiciona la composición canónica.
- No resolver layout empequeñeciendo toda la UI. Los modales pueden
  gestionar su propio overflow.

## 5. Microfases

`INSPECCIONAR → CAMBIO MÍNIMO → TESTS → VALIDACIÓN HUMANA → CHECKPOINT GIT`.
No mezclar mejoras independientes en una microfase; lo que aparezca de más
se anota para después.

## 6. Validación (herramientas existentes primero)

- `python -m pytest tests/<zona>.py -q`, luego suite completa si corresponde.
- `node tests/*.cjs` (harnesses del flujo real de portada/modo/tablero).
- `node --check app/static/js/<fichero>.js`.
- `git diff --check`.
- No crear harness/script temporal si uno existente cubre el caso; y si se
  crea uno puntual, fuera del repo (p. ej. dir temporal) y eliminarlo después.
- No dejar archivos temporales ni de análisis dentro del repositorio.

## 7. Git seguro (obligatorio)

- Prohibido `git add .` / `git add -A`. Staging explícito por archivo.
- Antes de staging: `git status --short`, `git diff --check`, `git diff`.
- **Un cambio preexistente que no es de tu tarea no es tuyo**: no tocarlo,
  no restaurarlo, no borrarlo, no incluirlo (aplica a recursos/carteles del
  usuario u otros untracked/modificados ajenos).
- Sin commit/tag hasta validación humana cuando la fase lo exija.
- Sin push salvo instrucción explícita.

## 8. Economía de contexto

Búsquedas dirigidas (`grep`/`glob`), no lectura indiscriminada. Orden:
instrucciones → archivos de la zona → referencias por búsqueda → tests.
Ampliar solo si hace falta.
