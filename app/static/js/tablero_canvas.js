/* Renderer oficial del tablero. Solo proyecta descriptor y estado autoritativos. */
"use strict";

(function (global) {
  const TAU = Math.PI * 2;
  const RADIO_CASILLA = 1.5625;
  const RADIO_CASILLA_LEGAL = 2.25;
  const TAMANO_PEON_CASILLA = 4.5;

  // Prueba visual directa: URL PNG construida desde el ID, un solo cálculo.
  function urlTablero(nodo) {
    const nombreTablero = String((nodo && nodo.id) || "").replace(/-/g, "_");
    return `/static/img/lugares/tablero_${nombreTablero}.png`;
  }

  class TableroCanvas {
    constructor(canvas, descriptor, acciones = {}) {
      this.canvas = canvas;
      this.ctx = canvas && canvas.getContext && canvas.getContext("2d");
      if (!this.ctx) throw new Error("Canvas 2D no disponible");
      this.descriptor = descriptor;
      this.acciones = acciones;
      this.estado = null;
      this.imagenes = new Map();
      this.peonesTintados = new Map();
      this.areas = [];
      this.metricas = {};
      this._alPulsar = (evento) => this._pulsar(evento);
      canvas.addEventListener("pointerup", this._alPulsar);
      canvas.addEventListener("pointermove", (evento) => this._cursor(evento));
      this._precargar();
      this._observarTamano();
      this.redimensionar();
    }

    _observarTamano() {
      if (global.ResizeObserver) {
        this.observador = new global.ResizeObserver(() => this.redimensionar());
        this.observador.observe(this.canvas);
      } else if (global.addEventListener) {
        global.addEventListener("resize", () => this.redimensionar());
      }
    }

    _precargar() {
      this.descriptor.nodos.filter((n) => n.tipo === "ubicacion")
        .forEach((n) => this._cargarImagen(urlTablero(n)));
      this._cargarImagen(this.descriptor.peon, true);
    }

    _cargarImagen(url, esPeon = false) {
      if (!url || this.imagenes.has(url)) return;
      if (!global.Image) {
        this.imagenes.set(url, { estado: "error", imagen: null });
        return;
      }
      const registro = { estado: "cargando", imagen: new global.Image() };
      this.imagenes.set(url, registro);
      registro.imagen.onload = () => {
        registro.estado = "lista";
        if (esPeon) this.peonesTintados.clear();
        this.dibujar();
      };
      registro.imagen.onerror = () => {
        registro.estado = "error";
        this.dibujar();
      };
      registro.imagen.src = url;
    }

    actualizar(estado, descriptor = this.descriptor) {
      if (descriptor !== this.descriptor) {
        this.descriptor = descriptor;
        this._precargar();
      }
      this.estado = estado;
      this.dibujar();
    }

    redimensionar() {
      const rect = this.canvas.getBoundingClientRect();
      const lado = Math.max(1, Math.round(rect.width || this.canvas.clientWidth || 800));
      const dpr = Math.max(1, Number(global.devicePixelRatio) || 1);
      this.canvas.width = Math.round(lado * dpr);
      this.canvas.height = Math.round(lado * dpr);
      this.ladoCss = lado;
      this.dpr = dpr;
      this.dibujar();
    }

    _preparar() {
      const escala = (this.ladoCss || 1) / 100;
      this.ctx.setTransform(this.dpr * escala, 0, 0, this.dpr * escala, 0, 0);
      this.ctx.clearRect(0, 0, 100, 100);
      this.ctx.fillStyle = "#171426";
      this.ctx.fillRect(0, 0, 100, 100);
      this.areas = [];
    }

    dibujar() {
      if (!this.ladoCss || !this.descriptor) return;
      const ctx = this.ctx;
      this._preparar();
      const nodos = new Map(this.descriptor.nodos.map((n) => [n.id, n]));
      const destinos = new Set((((this.estado || {}).movimiento || {}).destinos || []).map((d) => d.id));

      ctx.lineCap = "round";
      ctx.strokeStyle = "#8d805f";
      ctx.lineWidth = 0.8;
      this.descriptor.caminos.forEach((c) => {
        const a = c.inicio || nodos.get(c.nodos[0]);
        const b = c.fin || nodos.get(c.nodos[c.nodos.length - 1]);
        ctx.beginPath(); ctx.moveTo(a.x, a.y); ctx.lineTo(b.x, b.y); ctx.stroke();
      });

      ctx.save();
      ctx.strokeStyle = "#e8c766";
      ctx.lineWidth = 0.65;
      ctx.setLineDash([2, 2]);
      this.descriptor.pasadizos.forEach((p) => {
        const a = nodos.get(p.origen); const b = nodos.get(p.destino);
        ctx.beginPath(); ctx.moveTo(a.x, a.y); ctx.lineTo(b.x, b.y); ctx.stroke();
      });
      ctx.restore();

      this.descriptor.nodos.filter((n) => n.tipo === "casilla").forEach((n) => {
        const legal = destinos.has(n.id);
        ctx.beginPath(); ctx.arc(n.x, n.y, legal ? RADIO_CASILLA_LEGAL : RADIO_CASILLA, 0, TAU);
        ctx.fillStyle = legal ? "#f4dc76" : "#312b42"; ctx.fill();
        ctx.strokeStyle = legal ? "#fff0a3" : "#776c53"; ctx.lineWidth = legal ? 0.55 : 0.35; ctx.stroke();
        this.areas.push({ tipo: "casilla", nodo: n, x: n.x, y: n.y, radio: legal ? 3.125 : 2.125, legal });
      });

      this.descriptor.nodos.filter((n) => n.tipo === "ubicacion").forEach((n) => {
        const radio = (n.diametro || 14) / 2;
        const legal = destinos.has(n.id);
        this._dibujarUbicacion(n, radio, legal);
        this.areas.push({ tipo: "ubicacion", nodo: n, x: n.x, y: n.y, radio, legal });
      });

      this._dibujarPeones(nodos);
      this.metricas = {
        dpr: this.dpr,
        ubicaciones: this.descriptor.nodos.filter((n) => n.tipo === "ubicacion").length,
        casillas: this.descriptor.nodos.filter((n) => n.tipo === "casilla").length,
        caminos: this.descriptor.caminos.length,
        pasadizos: this.descriptor.pasadizos.length,
        peones: ((this.estado || {}).jugadores || []).filter((j) => j.posicion).length,
        destinos: destinos.size,
        distribucionPeones: this.distribucionPeones || [],
        representacionesPeones: this.representacionesPeones || [],
        conteoPeones: this.conteoPeones || {},
        diametroCasilla: RADIO_CASILLA * 2,
        tamanoPeonCasilla: TAMANO_PEON_CASILLA,
      };
    }

    _dibujarUbicacion(nodo, radio, legal) {
      const ctx = this.ctx;
      ctx.save();
      ctx.beginPath(); ctx.arc(nodo.x, nodo.y, radio, 0, TAU); ctx.clip();
      // El medallón usa exclusivamente imagen_tablero; la tarjeta completa
      // (imagen_tarjeta) es solo para el modal HTML.
      const recurso = this.imagenes.get(urlTablero(nodo));
      if (recurso && recurso.estado === "lista") {
        const img = recurso.imagen;
        const lado = Math.min(img.naturalWidth || img.width, img.naturalHeight || img.height);
        const sx = ((img.naturalWidth || img.width) - lado) / 2;
        const sy = ((img.naturalHeight || img.height) - lado) / 2;
        ctx.drawImage(img, sx, sy, lado, lado, nodo.x - radio, nodo.y - radio, radio * 2, radio * 2);
      } else {
        ctx.fillStyle = "#3a334c"; ctx.fillRect(nodo.x - radio, nodo.y - radio, radio * 2, radio * 2);
        ctx.fillStyle = "#b8ad93"; ctx.beginPath(); ctx.arc(nodo.x, nodo.y, radio * 0.22, 0, TAU); ctx.fill();
      }
      ctx.restore();
      ctx.beginPath(); ctx.arc(nodo.x, nodo.y, radio, 0, TAU);
      ctx.strokeStyle = legal ? "#fff0a3" : "#8d7840"; ctx.lineWidth = legal ? 1.1 : 0.55; ctx.stroke();
    }

    _peonTintado(color) {
      const clave = String(color).trim().toLowerCase();
      if (this.peonesTintados.has(clave)) return this.peonesTintados.get(clave);
      const recurso = this.imagenes.get(this.descriptor.peon);
      if (!recurso || recurso.estado !== "lista") return null;
      try {
        const fuera = document.createElement("canvas");
        fuera.width = 64; fuera.height = 80;
        const fctx = fuera.getContext("2d");
        fctx.drawImage(recurso.imagen, 0, 0, 64, 80);
        if (fctx.getImageData) {
          const imagen = fctx.getImageData(0, 0, 64, 80);
          const pixeles = imagen.data;
          const hexadecimal = clave.match(/^#([0-9a-f]{6})$/);
          const rgb = hexadecimal ? [
            parseInt(hexadecimal[1].slice(0, 2), 16),
            parseInt(hexadecimal[1].slice(2, 4), 16),
            parseInt(hexadecimal[1].slice(4, 6), 16),
          ] : [136, 136, 136];
          let tieneContenido = false;
          for (let i = 0; i < pixeles.length; i += 4) {
            if (!pixeles[i + 3]) continue;
            tieneContenido = true;
            const esContornoClaro = pixeles[i] > 150 && pixeles[i + 1] > 140 && pixeles[i + 2] > 100;
            if (!esContornoClaro) {
              [pixeles[i], pixeles[i + 1], pixeles[i + 2]] = rgb;
            }
          }
          if (!tieneContenido) return null;
          fctx.putImageData(imagen, 0, 0);
        } else {
          fctx.globalCompositeOperation = "source-in";
          fctx.fillStyle = color; fctx.fillRect(0, 0, 64, 80);
          fctx.globalCompositeOperation = "source-over";
        }
        this.peonesTintados.set(clave, fuera);
        return fuera;
      } catch (_error) {
        return null;
      }
    }

    _dibujarPeon(x, y, color, turno, eliminado, tamano) {
      const ctx = this.ctx;
      ctx.save();
      ctx.globalAlpha = eliminado ? 0.38 : 1;
      ctx.shadowColor = turno ? "#fff0a3" : "#f4efe3";
      ctx.shadowBlur = turno ? 2.4 : 1.15;
      const tintado = this._peonTintado(color);
      if (tintado) {
        ctx.drawImage(tintado, x - tamano * 0.4, y - tamano * 0.5, tamano * 0.8, tamano);
        ctx.restore();
        return "svg";
      } else {
        ctx.fillStyle = color;
        ctx.beginPath(); ctx.arc(x, y - tamano * 0.28, tamano * 0.18, 0, TAU); ctx.fill();
        ctx.beginPath();
        ctx.moveTo(x - tamano * 0.28, y + tamano * 0.38);
        ctx.quadraticCurveTo(x, y - tamano * 0.12, x + tamano * 0.28, y + tamano * 0.38);
        ctx.closePath(); ctx.fill();
      }
      ctx.restore();
      return "fallback";
    }

    _geometriaPeones(nodo, cantidad) {
      const esUbicacion = nodo.tipo === "ubicacion";
      const diametro = nodo.diametro || 14;
      const esPlaza = esUbicacion && diametro >= 20;
      const tamano = esUbicacion ? Math.min(5, diametro * 0.34) : TAMANO_PEON_CASILLA;
      const radio = esPlaza ? 6.2 : esUbicacion ? 3.25 : 1.65;
      if (cantidad === 1) return { tamano, radio: 0, offsets: [[0, 0]] };
      if (cantidad === 2) return { tamano, radio, offsets: [[-radio, 0], [radio, 0]] };
      if (cantidad === 3) {
        return { tamano, radio, offsets: [-90, 30, 150].map((grados) => {
          const angulo = grados * Math.PI / 180;
          return [Math.cos(angulo) * radio, Math.sin(angulo) * radio];
        }) };
      }
      if (cantidad === 4) {
        const lado = radio / Math.sqrt(2);
        return { tamano, radio, offsets: [[-lado, -lado], [lado, -lado], [lado, lado], [-lado, lado]] };
      }
      return { tamano, radio, offsets: Array.from({ length: cantidad }, (_, indice) => {
        const angulo = indice * TAU / cantidad;
        return [Math.cos(angulo) * radio, Math.sin(angulo) * radio];
      }) };
    }

    _dibujarPeones(nodos) {
      const grupos = new Map();
      this.distribucionPeones = [];
      this.representacionesPeones = [];
      let solicitados = 0;
      let svgDibujados = 0;
      let fallbacksDibujados = 0;
      ((this.estado || {}).jugadores || []).forEach((j) => {
        if (!j.posicion || !nodos.has(j.posicion.id)) return;
        const grupo = grupos.get(j.posicion.id) || [];
        grupo.push(j); grupos.set(j.posicion.id, grupo);
      });
      grupos.forEach((jugadores, nodoId) => {
        const nodo = nodos.get(nodoId);
        const geometria = this._geometriaPeones(nodo, jugadores.length);
        jugadores.forEach((j, i) => {
          const offset = geometria.offsets[i];
          const color = this.descriptor.colores_personajes[j.personaje_id] || "#888";
          const x = nodo.x + offset[0];
          const y = nodo.y + offset[1];
          this.distribucionPeones.push({ nodoId, alias: j.alias, x, y, offsetX: offset[0], offsetY: offset[1], color, tamano: geometria.tamano, radio: geometria.radio });
          solicitados += 1;
          const clave = String(color).trim().toLowerCase();
          const recurso = this.imagenes.get(this.descriptor.peon);
          const resultado = this._dibujarPeon(
            x, y, color,
            j.alias === (this.estado || {}).turno_alias, !j.activo, geometria.tamano
          );
          if (resultado === "svg") svgDibujados += 1;
          else fallbacksDibujados += 1;
          this.representacionesPeones.push({
            personaje_id: j.personaje_id,
            jugador_id: j.id || j.jugador_id || j.alias,
            tipo: j.tipo,
            posicion: j.posicion.id,
            x, y, color,
            peonCacheKey: clave,
            estadoSvgTintado: this.peonesTintados.has(clave) ? "listo" : (recurso || {}).estado || "sin_recurso",
            fallbackDisponible: true,
            drawSolicitado: true,
            drawEjecutado: resultado,
          });
        });
      });
      this.conteoPeones = {
        participantesConPosicion: ((this.estado || {}).jugadores || []).filter((j) => j.posicion).length,
        peonesSolicitados: solicitados,
        peonesSvgDibujados: svgDibujados,
        fallbacksDibujados,
      };
    }

    _coordenadas(evento) {
      const rect = this.canvas.getBoundingClientRect();
      return {
        x: (evento.clientX - rect.left) * 100 / rect.width,
        y: (evento.clientY - rect.top) * 100 / rect.height,
      };
    }

    _areaEn(evento) {
      const p = this._coordenadas(evento);
      return [...this.areas].reverse().find((a) => Math.hypot(p.x - a.x, p.y - a.y) <= a.radio);
    }

    _pulsar(evento) {
      const area = this._areaEn(evento);
      if (!area) return;
      if (area.tipo === "ubicacion") {
        if (this.acciones.consultar) this.acciones.consultar(area.nodo, this.canvas);
      } else if (area.legal && this.acciones.mover) {
        this.acciones.mover(area.nodo.id, this.canvas);
      }
    }

    _cursor(evento) {
      const area = this._areaEn(evento);
      this.canvas.style.cursor = area && (area.tipo === "ubicacion" || area.legal) ? "pointer" : "default";
    }
  }

  global.TableroCanvas = TableroCanvas;
})(window);
