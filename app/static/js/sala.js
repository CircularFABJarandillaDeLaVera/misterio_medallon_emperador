/* Sala: sincronización en tiempo real por WebSocket (Microfase 4B).
   Cada conexión recibe solo su estado privado: nunca ve las
   cartas ni la hoja de investigación de otros jugadores,
   ni el misterio secreto. */
"use strict";

const codigo = document.getElementById("codigo").textContent.trim();
const jugadorId = sessionStorage.getItem("jugador_id") || "";

const lista = document.getElementById("jugadores");
const estado = document.getElementById("estado");
const error = document.getElementById("error");
const btnComenzar = document.getElementById("btn-comenzar");
const lobbyPersonajes = document.getElementById("lobby-personajes");
const personajesDiv = document.getElementById("personajes");
const partida = document.getElementById("partida");
const turnoP = document.getElementById("turno");
const ordenOl = document.getElementById("orden");
const cartasDiv = document.getElementById("mis-cartas");
const total = document.getElementById("total");
const modalCartas = document.getElementById("modal-cartas");
const modalHoja = document.getElementById("modal-hoja");
const hojaDiv = document.getElementById("hoja");
const errorHoja = document.getElementById("error-hoja");
const btnVerHoja = document.getElementById("btn-ver-hoja");
const btnVerCartas = document.getElementById("btn-ver-cartas");
const btnCerrarHoja = document.getElementById("btn-cerrar-hoja");
const btnCerrarCartas = document.getElementById("btn-cerrar-cartas");
const jugadaDiv = document.getElementById("jugada");
const btnSospecha = document.getElementById("btn-sospecha");
const modalSospecha = document.getElementById("modal-sospecha");
const modalRefutacion = document.getElementById("modal-refutacion");
const opcionesRefutacion = document.getElementById("opciones-refutacion");
const selectSospechoso = document.getElementById("sospecha-sospechoso");
const selectLugar = document.getElementById("sospecha-lugar");
const selectObjeto = document.getElementById("sospecha-objeto");

if (!jugadorId) {
  window.location.href = "/";
}

let PERSONAJES = [];
fetch("/api/personajes")
  .then((r) => r.json())
  .then((datos) => {
    PERSONAJES = datos.personajes;
    if (ultimaSala) {
      pintarPersonajes(ultimaSala);
    }
  });

let ultimaSala = null;

const protocolo = window.location.protocol === "https:" ? "wss" : "ws";
const ws = new WebSocket(
  `${protocolo}://${window.location.host}/ws/${encodeURIComponent(codigo)}/${encodeURIComponent(jugadorId)}`
);

ws.onmessage = (evento) => {
  const mensaje = JSON.parse(evento.data);
  if (mensaje.tipo === "estado_privado") {
    ultimaSala = mensaje.sala;
    pintarSala(mensaje.sala);
  } else if (mensaje.tipo === "error") {
    error.textContent = mensaje.detalle;
  }
};

ws.onclose = () => {
  estado.textContent = "Conexión perdida. Recarga la página para reintentar.";
};

const TITULOS = {
  sospechoso: "SOSPECHOSOS",
  lugar: "LUGARES",
  objeto: "OBJETOS",
};

const ETIQUETA_ESTADO = {
  sin_informacion: "SIN INFORMACIÓN",
  la_tengo: "LA TENGO",
  descartada: "DESCARTADA",
  vista: "VISTA",
};

function aliasDePersonaje(sala, personajeId) {
  const j = sala.jugadores.find((x) => x.personaje_id === personajeId);
  return j ? j.alias : null;
}

function pintarPersonajes(sala) {
  personajesDiv.innerHTML = "";
  PERSONAJES.forEach((p) => {
    const tarjeta = document.createElement("button");
    tarjeta.type = "button";
    tarjeta.className = "personaje";
    const ocupante = aliasDePersonaje(sala, p.id);
    const esMio = sala.personaje_id === p.id;

    const nombre = document.createElement("strong");
    nombre.textContent = p.nombre;
    tarjeta.appendChild(nombre);
    const detalle = document.createElement("span");
    detalle.textContent = `${p.color} · ${p.simbolo}`;
    tarjeta.appendChild(detalle);

    const situacion = document.createElement("span");
    if (esMio) {
      tarjeta.classList.add("mio");
      situacion.textContent = "TU PERSONAJE";
    } else if (ocupante) {
      tarjeta.classList.add("ocupado");
      tarjeta.disabled = true;
      situacion.textContent = `Elegido por ${ocupante}`;
    } else {
      situacion.textContent = "DISPONIBLE";
      tarjeta.addEventListener("click", () => {
        error.textContent = "";
        ws.send(JSON.stringify({ accion: "elegir_personaje", personaje_id: p.id }));
      });
    }
    tarjeta.appendChild(situacion);
    personajesDiv.appendChild(tarjeta);
  });
}

function pintarSala(sala) {
  error.textContent = "";
  lista.innerHTML = "";
  sala.jugadores.forEach((j) => {
    const li = document.createElement("li");
    let texto = j.alias;
    if (j.personaje) {
      texto += ` — ${j.personaje}`;
    }
    if (sala.estado === "iniciada") {
      texto += ` · ${j.num_cartas} cartas`;
      texto += j.tipo === "pnj" ? " · PNJ" : " · HUMANO";
    }
    li.textContent = texto;
    if (j.es_anfitrion) {
      const etiqueta = document.createElement("span");
      etiqueta.className = "etiqueta-anfitrion";
      etiqueta.textContent = "anfitrión";
      li.appendChild(etiqueta);
    }
    lista.appendChild(li);
  });

  if (sala.estado === "iniciada") {
    estado.textContent = "";
    btnComenzar.style.display = "none";
    lobbyPersonajes.style.display = "none";
    partida.hidden = false;
    pintarTurno(sala);
    pintarCartas(sala.mis_cartas);
    pintarHoja(sala.investigacion || []);
    pintarJugada(sala);
    const repartidas = sala.jugadores.reduce((n, j) => n + j.num_cartas, 0);
    total.textContent = `${repartidas} cartas han sido repartidas.`;
  } else {
    partida.hidden = true;
    btnComenzar.style.display = "";
    lobbyPersonajes.style.display = "";
    pintarPersonajes(sala);
    btnComenzar.disabled = !sala.es_anfitrion;
    const sinPersonaje = sala.jugadores.filter((j) => !j.personaje_id).length;
    if (sinPersonaje > 0) {
      estado.textContent =
        "Todos los jugadores deben elegir un personaje antes de comenzar.";
    } else if (!sala.es_anfitrion) {
      estado.textContent = "Esperando a que el anfitrión comience…";
    } else {
      estado.textContent = "Todo listo. ¡Puedes comenzar!";
    }
  }
}

function pintarTurno(sala) {
  ordenOl.innerHTML = "";
  sala.orden.forEach((entrada, i) => {
    const li = document.createElement("li");
    li.textContent = `${entrada.alias} — ${entrada.personaje} · ${entrada.tipo === "pnj" ? "PNJ" : "HUMANO"}`;
    if (entrada.alias === sala.turno_alias) {
      li.classList.add("en-turno");
    }
    ordenOl.appendChild(li);
  });
  if (sala.pnj_pensando_alias) {
    turnoP.textContent = `${sala.pnj_pensando_alias} ESTÁ PENSANDO...`;
  } else if (sala.es_mi_turno) {
    turnoP.textContent = "ES TU TURNO";
  } else {
    turnoP.textContent = `TURNO DE ${(sala.turno_alias || "").toUpperCase()}`;
  }
}

function llenarSelect(select, cartas, categoria) {
  select.innerHTML = '<option value="">-- Selecciona --</option>';
  cartas.filter((c) => c.categoria === categoria).forEach((c) => {
    const opcion = document.createElement("option");
    opcion.value = c.id;
    opcion.textContent = c.nombre;
    select.appendChild(opcion);
  });
}

function pintarJugada(sala) {
  const jugada = sala.jugada || {};
  jugadaDiv.innerHTML = "";
  const puedeSospechar = sala.es_mi_turno && jugada.estado === "esperando_sospecha";
  btnSospecha.hidden = !puedeSospechar;
  if (jugada.sospecha) {
    const titulo = document.createElement("strong");
    titulo.textContent = `${jugada.investigador_alias} HA FORMULADO UNA SOSPECHA`;
    jugadaDiv.appendChild(titulo);
    ["sospechoso", "lugar", "objeto"].forEach((categoria) => {
      const linea = document.createElement("p");
      linea.textContent = `${TITULOS[categoria]}: ${jugada.sospecha[`${categoria}_id`].nombre}`;
      jugadaDiv.appendChild(linea);
    });
  }
  const resultado = document.createElement("p");
  if (jugada.resultado === "sin_refutacion") {
    resultado.textContent = "NADIE HA PODIDO REFUTAR LA SOSPECHA";
  } else if (jugada.resultado === "refutada") {
    resultado.textContent = `SOSPECHA REFUTADA POR ${jugada.refutador_alias}`;
  } else if (jugada.esperando_resolucion) {
    resultado.textContent = "ESPERANDO RESPUESTA...";
  } else if (jugada.resultado === "pendiente") {
    resultado.textContent = "RESOLVIENDO SOSPECHA...";
  }
  if (jugada.carta_mostrada) {
    resultado.textContent += ` ${jugada.refutador_alias} TE HA MOSTRADO: ${jugada.carta_mostrada.nombre}`;
  }
  jugadaDiv.appendChild(resultado);

  const opciones = Array.isArray(jugada.opciones_refutacion)
    ? jugada.opciones_refutacion : [];
  modalRefutacion.hidden = opciones.length === 0;
  opcionesRefutacion.innerHTML = "";
  opciones.forEach((carta) => {
    const boton = document.createElement("button");
    boton.type = "button";
    boton.textContent = carta.nombre;
    boton.addEventListener("click", () => {
      boton.disabled = true;
      ws.send(JSON.stringify({ accion: "mostrar_carta", carta_id: carta.id }));
    });
    opcionesRefutacion.appendChild(boton);
  });
}

function pintarCartas(misCartas) {
  if (!cartasDiv) {
    return;
  }
  cartasDiv.innerHTML = "";
  const lista = Array.isArray(misCartas) ? misCartas : [];
  ["sospechoso", "lugar", "objeto"].forEach((categoria) => {
    const mias = lista.filter((c) => c.categoria === categoria);
    if (mias.length === 0) {
      return;
    }
    const grupo = document.createElement("div");
    grupo.className = "grupo-cartas";
    const titulo = document.createElement("h3");
    titulo.textContent = `${TITULOS[categoria]} (${mias.length})`;
    grupo.appendChild(titulo);
    const ul = document.createElement("ul");
    mias.forEach((carta) => {
      const li = document.createElement("li");
      li.textContent = carta.nombre;
      ul.appendChild(li);
    });
    grupo.appendChild(ul);
    cartasDiv.appendChild(grupo);
  });
}

btnComenzar.addEventListener("click", () => {
  error.textContent = "";
  ws.send(JSON.stringify({ accion: "iniciar" }));
});

function filaHoja(entrada) {
  const fila = document.createElement("button");
  fila.type = "button";
  fila.className = `hoja-fila estado-${entrada.estado}`;
  const nombre = document.createElement("span");
  nombre.className = "hoja-nombre";
  nombre.textContent = entrada.nombre;
  fila.appendChild(nombre);
  const marca = document.createElement("span");
  marca.className = "hoja-estado";
  marca.textContent = ETIQUETA_ESTADO[entrada.estado] || entrada.estado;
  fila.appendChild(marca);
  if (entrada.estado === "la_tengo" || entrada.estado === "vista") {
    fila.disabled = true;
    fila.title =
      entrada.estado === "la_tengo"
        ? "Es una de tus cartas: no se puede modificar."
        : "Carta vista: se conserva automáticamente.";
  } else {
    fila.addEventListener("click", () => {
      if (errorHoja) {
        errorHoja.textContent = "";
      }
      ws.send(
        JSON.stringify({
          accion: "marcar_investigacion",
          carta_id: entrada.id,
          estado:
            entrada.estado === "descartada" ? "sin_informacion" : "descartada",
        })
      );
    });
  }
  return fila;
}

const CATEGORIAS_HOJA = ["sospechoso", "lugar", "objeto"];
// Grupos independientes: plegar uno nunca cierra los otros.
const GRUPO_ABIERTO = { sospechoso: true, lugar: true, objeto: true };

function categoriaDe(entrada) {
  return String((entrada && entrada.categoria) || "")
    .trim()
    .toLowerCase();
}

function pintarHoja(investigacion) {
  if (!hojaDiv) {
    return;
  }
  hojaDiv.innerHTML = "";
  if (errorHoja) {
    errorHoja.textContent = "";
  }
  const lista = Array.isArray(investigacion) ? investigacion : [];
  if (lista.length === 0) {
    // Nunca mostrar los tres títulos vacíos en silencio: avisar.
    const aviso = document.createElement("p");
    aviso.className = "estado";
    aviso.textContent =
      "Cargando tu hoja de investigación… si las cartas no aparecen, recarga la página.";
    hojaDiv.appendChild(aviso);
    return;
  }
  CATEGORIAS_HOJA.forEach((categoria) => {
    const entradas = lista.filter((e) => categoriaDe(e) === categoria);
    const grupo = document.createElement("div");
    grupo.className = "grupo-cartas grupo-hoja";
    const cabecera = document.createElement("button");
    cabecera.type = "button";
    cabecera.className = "hoja-cabecera";
    const titulo = document.createElement("span");
    titulo.textContent = `${TITULOS[categoria]} (${entradas.length})`;
    cabecera.appendChild(titulo);
    const flecha = document.createElement("span");
    flecha.className = "hoja-flecha";
    flecha.textContent = GRUPO_ABIERTO[categoria] ? "▾" : "▸";
    cabecera.appendChild(flecha);
    cabecera.setAttribute(
      "aria-expanded",
      GRUPO_ABIERTO[categoria] ? "true" : "false"
    );
    const cuerpo = document.createElement("div");
    cuerpo.className = "hoja-cuerpo";
    cuerpo.hidden = !GRUPO_ABIERTO[categoria];
    entradas.forEach((entrada) => {
      cuerpo.appendChild(filaHoja(entrada));
    });
    cabecera.addEventListener("click", () => {
      GRUPO_ABIERTO[categoria] = !GRUPO_ABIERTO[categoria];
      cuerpo.hidden = !GRUPO_ABIERTO[categoria];
      flecha.textContent = GRUPO_ABIERTO[categoria] ? "▾" : "▸";
      cabecera.setAttribute(
        "aria-expanded",
        GRUPO_ABIERTO[categoria] ? "true" : "false"
      );
    });
    grupo.appendChild(cabecera);
    grupo.appendChild(cuerpo);
    hojaDiv.appendChild(grupo);
  });
  // Entradas con categoría inesperada: mostrarlas, nunca ocultarlas.
  const resto = lista.filter((e) => !CATEGORIAS_HOJA.includes(categoriaDe(e)));
  if (resto.length > 0) {
    const grupo = document.createElement("div");
    grupo.className = "grupo-cartas grupo-hoja";
    const titulo = document.createElement("h3");
    titulo.textContent = `OTRAS (${resto.length})`;
    grupo.appendChild(titulo);
    resto.forEach((entrada) => {
      grupo.appendChild(filaHoja(entrada));
    });
    hojaDiv.appendChild(grupo);
  }
}

function abrirHoja() {
  if (modalHoja) {
    modalHoja.hidden = false;
  }
}

function cerrarHoja() {
  if (modalHoja) {
    modalHoja.hidden = true;
  }
}

function abrirCartas() {
  if (modalCartas) {
    modalCartas.hidden = false;
  }
}

function cerrarCartas() {
  if (modalCartas) {
    modalCartas.hidden = true;
  }
}

if (btnVerHoja) {
  btnVerHoja.addEventListener("click", abrirHoja);
}
if (btnVerCartas) {
  btnVerCartas.addEventListener("click", abrirCartas);
}
if (btnCerrarHoja) {
  btnCerrarHoja.addEventListener("click", cerrarHoja);
}
if (btnCerrarCartas) {
  btnCerrarCartas.addEventListener("click", cerrarCartas);
}

btnSospecha.addEventListener("click", () => {
  const cartas = (ultimaSala && ultimaSala.investigacion) || [];
  llenarSelect(selectSospechoso, cartas, "sospechoso");
  llenarSelect(selectLugar, cartas, "lugar");
  llenarSelect(selectObjeto, cartas, "objeto");
  modalSospecha.hidden = false;
});
document.getElementById("btn-cancelar-sospecha").addEventListener("click", () => {
  modalSospecha.hidden = true;
});
document.getElementById("btn-confirmar-sospecha").addEventListener("click", () => {
  if (!selectSospechoso.value || !selectLugar.value || !selectObjeto.value) {
    error.textContent = "Selecciona sospechoso, lugar y objeto.";
    return;
  }
  ws.send(JSON.stringify({
    accion: "formular_sospecha",
    sospechoso_id: selectSospechoso.value,
    lugar_id: selectLugar.value,
    objeto_id: selectObjeto.value,
  }));
  modalSospecha.hidden = true;
});
