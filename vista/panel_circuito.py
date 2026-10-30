"""Vista: esquema eléctrico del circuito, dibujado como en un libro de texto.

Cables ortogonales, resistencias como rectángulos, fuentes como baterías,
nodos como puntos con letra (A, B, C...) y flechas de corriente. Los nodos se
colocan solos en una cuadrícula y se pueden arrastrar con el mouse.

Este panel solo dibuja lo que recibe; no calcula ninguna magnitud eléctrica.
"""

import math
import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk

COLOR_FONDO = "white"
COLOR_CABLE = "#3a3a3a"
COLOR_TEXTO = "#222222"
COLOR_TEXTO_SUAVE = "#666666"
COLOR_NEGATIVO = "#c0392b"

GROSOR_CABLE = 1.5
RADIO_NODO = 4
RESISTENCIA_LARGO = 40
RESISTENCIA_ALTO = 14
SEMI_PLACA_LARGA = 12
SEMI_PLACA_CORTA = 7
SEPARACION_PLACAS = 4      # distancia del centro de la batería a cada placa
RADIO_SALTO = 6            # radio del salto semicircular en un cruce
DESVIO_MIN, DESVIO_MAX = 70, 130  # separación de ramas paralelas (px)


def nombre_nodo(nodo):
    """Nodo 1 -> 'A', 2 -> 'B', ... (la vista nombra los nodos con letras)."""
    return chr(64 + nodo) if 1 <= nodo <= 26 else str(nodo)


# ----------------------------------------------------------------------
# Piezas geométricas
# ----------------------------------------------------------------------
class _Segmento:
    """Tramo recto de un cable, recorrido en el sentido de la corriente (a → b)."""

    def __init__(self, p, q):
        self.x1, self.y1 = p
        self.x2, self.y2 = q
        self.largo = math.hypot(self.x2 - self.x1, self.y2 - self.y1)
        self.ux = (self.x2 - self.x1) / self.largo
        self.uy = (self.y2 - self.y1) / self.largo
        self.horizontal = abs(self.y2 - self.y1) < 0.5
        self.cruces = []    # distancias desde el inicio donde otro cable lo cruza
        self.saltos = []    # los cruces donde este cable salta por encima
        self.simbolos = []  # (distancia del centro, semilongitud) de cada símbolo

    def punto(self, s):
        return self.x1 + self.ux * s, self.y1 + self.uy * s

    def caja(self, margen):
        return (min(self.x1, self.x2) - margen, min(self.y1, self.y2) - margen,
                max(self.x1, self.x2) + margen, max(self.y1, self.y2) + margen)


class _Simbolo:
    """Resistencia o fuente colocada sobre un segmento."""

    def __init__(self, tipo, segmento, s):
        self.tipo = tipo
        self.segmento = segmento
        self.s = s
        cx, cy = segmento.punto(s)
        self.centro = (cx, cy)
        a = RESISTENCIA_LARGO / 2 if tipo == "resistencia" else SEPARACION_PLACAS + 2
        p = RESISTENCIA_ALTO / 2 if tipo == "resistencia" else SEMI_PLACA_LARGA
        if not segmento.horizontal:
            a, p = p, a
        self.caja = (cx - a, cy - p, cx + a, cy + p)


class _Ocupacion:
    """Cajas ya ocupadas del lienzo; sirve para colocar etiquetas sin encimarlas."""

    SEPARACION_ETIQUETAS = 6  # aire mínimo entre dos etiquetas

    def __init__(self, ancho, alto):
        self.ancho, self.alto = ancho, alto
        self.cajas = []      # cables, símbolos y nodos
        self.etiquetas = []  # etiquetas ya colocadas

    def choques(self, caja):
        x0, y0, x1, y1 = caja
        total = 0
        if x0 < 2 or y0 < 2 or x1 > self.ancho - 2 or y1 > self.alto - 2:
            total += 3  # etiqueta cortada por el borde
        for a, b, c, d in self.cajas:
            if x0 < c - 0.5 and x1 > a + 0.5 and y0 < d - 0.5 and y1 > b + 0.5:
                total += 1
        m = self.SEPARACION_ETIQUETAS
        for a, b, c, d in self.etiquetas:
            if x0 - m < c and x1 + m > a and y0 - m < d and y1 + m > b:
                total += 1
        return total

    def elegir(self, candidatos):
        """Devuelve el dato del primer candidato sin choques (o el que menos choca)."""
        mejor = None
        for caja, dato in candidatos:
            choques = self.choques(caja)
            if mejor is None or choques < mejor[0]:
                mejor = (choques, caja, dato)
            if choques == 0:
                break
        self.etiquetas.append(mejor[1])
        return mejor[2]


def _unir(a, b):
    return min(a[0], b[0]), min(a[1], b[1]), max(a[2], b[2]), max(a[3], b[3])


# ----------------------------------------------------------------------
# Panel
# ----------------------------------------------------------------------
class PanelCircuito(ttk.Frame):

    def __init__(self, padre):
        super().__init__(padre)
        self._canvas = tk.Canvas(self, bg=COLOR_FONDO, highlightthickness=1,
                                 highlightbackground="#999999", height=300)
        self._canvas.pack(fill="both", expand=True)
        self._fuente = tkfont.Font(family="Segoe UI", size=9)
        self._fuente_nodo = tkfont.Font(family="Segoe UI", size=10, weight="bold")
        self._fuente_pie = tkfont.Font(family="Segoe UI", size=8)

        self._nodos = ()
        self._ramas = ()
        self._resultados = None
        self._posiciones = {}   # nodo -> (x, y) como fracción del lienzo (0..1)
        self._pos_px = {}
        self._arrastrando = None
        self._ancho = self._alto = 1

        self._canvas.bind("<Configure>", lambda _e: self._redibujar())
        self._canvas.bind("<ButtonPress-1>", self._al_presionar)
        self._canvas.bind("<B1-Motion>", self._al_arrastrar)
        self._canvas.bind("<ButtonRelease-1>", self._al_soltar)
        self._canvas.bind("<Motion>", self._al_mover)

    # ------------------------------------------------------------------
    # API pública (la usa la ventana principal)
    # ------------------------------------------------------------------
    def dibujar(self, nodos, ramas, resultados=None, disposicion=None):
        """Guarda lo que hay que dibujar y lo pinta.

        ``resultados``: si viene, se escribe la corriente de cada rama.
        ``disposicion``: {nodo: (x, y)} con fracciones 0..1 del lienzo; un
        diccionario vacío vuelve a la cuadrícula automática. Si es None se
        conservan las posiciones actuales (salvo que cambie el número de nodos).
        """
        nodos = tuple(nodos)
        if disposicion is not None or len(nodos) != len(self._nodos):
            self._posiciones = dict(disposicion or {})
        self._nodos = nodos
        self._ramas = tuple(ramas)
        self._resultados = tuple(resultados) if resultados else None
        self._redibujar()

    # ------------------------------------------------------------------
    # Arrastre de nodos
    # ------------------------------------------------------------------
    def _nodo_en(self, x, y):
        for nodo, (nx, ny) in self._pos_px.items():
            if math.hypot(x - nx, y - ny) <= 12:
                return nodo
        return None

    def _al_presionar(self, evento):
        self._arrastrando = self._nodo_en(evento.x, evento.y)

    def _al_arrastrar(self, evento):
        if self._arrastrando is None:
            return
        fx = min(max(evento.x / self._ancho, 0.03), 0.97)
        fy = min(max(evento.y / self._alto, 0.05), 0.95)
        self._posiciones[self._arrastrando] = (fx, fy)
        self._redibujar()

    def _al_soltar(self, _evento):
        self._arrastrando = None

    def _al_mover(self, evento):
        sobre_nodo = self._nodo_en(evento.x, evento.y) is not None
        self._canvas.configure(cursor="fleur" if sobre_nodo else "")

    # ------------------------------------------------------------------
    # Posiciones de los nodos
    # ------------------------------------------------------------------
    @staticmethod
    def _posicion_por_defecto(indice, total):
        """Disposición automática: 2 en vertical, 3 en triángulo, 4 en rombo, y cuadrícula."""
        if total == 2:
            return ((0.5, 0.2), (0.5, 0.8))[indice]
        if total == 3:
            return ((0.5, 0.18), (0.2, 0.82), (0.8, 0.82))[indice]
        if total == 4:
            return ((0.5, 0.15), (0.82, 0.5), (0.5, 0.85), (0.18, 0.5))[indice]
        columnas = math.ceil(math.sqrt(total))
        filas = math.ceil(total / columnas)
        c, f = indice % columnas, indice // columnas
        fx = 0.5 if columnas == 1 else 0.15 + 0.7 * c / (columnas - 1)
        fy = 0.5 if filas == 1 else 0.15 + 0.7 * f / (filas - 1)
        return fx, fy

    def _calcular_posiciones(self, ancho, alto):
        for indice, nodo in enumerate(self._nodos):
            if nodo not in self._posiciones:
                self._posiciones[nodo] = self._posicion_por_defecto(indice, len(self._nodos))
        return {n: (self._posiciones[n][0] * ancho, self._posiciones[n][1] * alto)
                for n in self._nodos}

    # ------------------------------------------------------------------
    # Rutas ortogonales de los cables
    # ------------------------------------------------------------------
    def _calcular_rutas(self, pos, ancho):
        """Devuelve {índice de rama: [segmentos]} con cables rectos u ortogonales."""
        grupos = {}
        for i, rama in enumerate(self._ramas):
            clave = (min(rama.nodo_a, rama.nodo_b), max(rama.nodo_a, rama.nodo_b))
            grupos.setdefault(clave, []).append(i)

        centro = (sum(p[0] for p in pos.values()) / len(pos),
                  sum(p[1] for p in pos.values()) / len(pos))
        desvio = max(DESVIO_MIN, min(DESVIO_MAX, 0.17 * ancho))

        rutas = {}
        for (menor, mayor), indices in grupos.items():
            for ranura, i in enumerate(self._ordenar_ranuras(indices)):
                puntos = self._ruta(pos[menor], pos[mayor], ranura, desvio, centro)
                if self._ramas[i].nodo_a != menor:
                    puntos.reverse()  # la ruta siempre sigue el sentido a → b
                puntos = self._sin_repetidos(puntos)
                rutas[i] = [_Segmento(p, q) for p, q in zip(puntos, puntos[1:])]
        return rutas

    def _ordenar_ranuras(self, indices):
        """Ordena las ramas que unen el mismo par de nodos.

        La primera va recta; las demás se abren a los lados. Una rama sin
        fuente ocupa el centro y las que tienen fuente salen hacia afuera.
        """
        if len(indices) == 1:
            return indices
        sin_fuente = [i for i in indices if self._ramas[i].voltaje == 0]
        recta = sin_fuente[0] if sin_fuente else indices[0]
        resto = [i for i in indices if i != recta]
        resto.sort(key=lambda i: self._ramas[i].voltaje == 0)  # con fuente primero
        return [recta] + resto

    @staticmethod
    def _ruta(p, q, ranura, desvio, centro):
        """Puntos del cable entre p y q; ``ranura`` distingue ramas paralelas."""
        (x1, y1), (x2, y2) = p, q
        vertical = abs(x1 - x2) < 2
        horizontal = abs(y1 - y2) < 2
        if vertical or horizontal:
            if ranura == 0:
                return [p, q]
            # Rodeo en U: primero hacia la izquierda (o arriba), luego al otro lado.
            lado = (-1, 0) if vertical else (0, -1)
            nivel = (ranura + 1) // 2
            signo = 1 if ranura % 2 == 1 else -1
            dx, dy = lado[0] * signo * nivel * desvio, lado[1] * signo * nivel * desvio
            return [p, (x1 + dx, y1 + dy), (x2 + dx, y2 + dy), q]
        if ranura < 2:
            # Cable en L: se usa primero la esquina más alejada del centro del esquema.
            esquinas = [(x2, y1), (x1, y2)]
            esquinas.sort(key=lambda e: -math.hypot(e[0] - centro[0], e[1] - centro[1]))
            return [p, esquinas[ranura], q]
        nivel = (ranura - 2) // 2 + 1
        xm = (x1 + x2) / 2 + (1 if ranura % 2 == 0 else -1) * nivel * 40
        return [p, (xm, y1), (xm, y2), q]

    @staticmethod
    def _sin_repetidos(puntos):
        limpios = [puntos[0]]
        for punto in puntos[1:]:
            if math.hypot(punto[0] - limpios[-1][0], punto[1] - limpios[-1][1]) > 0.5:
                limpios.append(punto)
        return limpios

    @staticmethod
    def _calcular_cruces(rutas):
        """Marca los cruces entre cables de ramas distintas (el horizontal salta)."""
        todos = [(i, seg) for i, segs in rutas.items() for seg in segs]
        margen = RADIO_SALTO + 2
        for i, horizontal in todos:
            if not horizontal.horizontal:
                continue
            for j, vertical in todos:
                if i == j or vertical.horizontal:
                    continue
                x, y = vertical.x1, horizontal.y1
                x_min, x_max = sorted((horizontal.x1, horizontal.x2))
                y_min, y_max = sorted((vertical.y1, vertical.y2))
                if x_min + margen < x < x_max - margen and y_min + margen < y < y_max - margen:
                    s = abs(x - horizontal.x1)
                    horizontal.cruces.append(s)
                    horizontal.saltos.append(s)
                    vertical.cruces.append(abs(y - vertical.y1))

    # ------------------------------------------------------------------
    # Colocación de símbolos
    # ------------------------------------------------------------------
    def _colocar_simbolos(self, rutas):
        """Devuelve {rama: [símbolos]}. La fuente va en el tramo más largo y la
        resistencia en el siguiente (si no cabe, ambas en serie en el mismo)."""
        simbolos = {}
        for i, segs in rutas.items():
            rama = self._ramas[i]
            orden = sorted(range(len(segs)), key=lambda k: (round(segs[k].largo), k),
                           reverse=True)
            k_fuente = orden[0] if rama.voltaje != 0 else None
            if k_fuente is not None and len(orden) > 1 and segs[orden[1]].largo >= 80:
                k_res = orden[1]
            else:
                k_res = orden[0]
            juntos = k_fuente == k_res
            centro = (0.5, 0.4, 0.6, 0.3, 0.7, 0.25, 0.75, 0.2, 0.8)
            lista = []
            if k_fuente is not None:
                fracciones = (0.3, 0.2, 0.4, 0.15, 0.5) if juntos else centro
                lista.append(self._poner("fuente", segs[k_fuente], SEPARACION_PLACAS + 2,
                                         fracciones))
            fracciones = (0.7, 0.8, 0.6, 0.85, 0.5) if juntos else centro
            lista.append(self._poner("resistencia", segs[k_res], RESISTENCIA_LARGO / 2,
                                     fracciones))
            simbolos[i] = lista
        return simbolos

    @staticmethod
    def _poner(tipo, seg, mitad, fracciones):
        """Elige dónde poner un símbolo evitando cruces y otros símbolos."""
        elegido = fracciones[0] * seg.largo
        for fraccion in fracciones:
            s = fraccion * seg.largo
            if s - mitad < 8 or s + mitad > seg.largo - 8:
                continue
            if any(abs(s - otro) < mitad + m + 10 for otro, m in seg.simbolos):
                continue
            if any(abs(s - c) < mitad + RADIO_SALTO + 6 for c in seg.cruces):
                continue
            elegido = s
            break
        seg.simbolos.append((elegido, mitad))
        return _Simbolo(tipo, seg, elegido)

    # ------------------------------------------------------------------
    # Dibujo
    # ------------------------------------------------------------------
    def _redibujar(self):
        lienzo = self._canvas
        lienzo.delete("all")
        ancho = max(lienzo.winfo_width(), 320)
        alto = max(lienzo.winfo_height(), 220)
        self._ancho, self._alto = ancho, alto
        if not self._nodos:
            return

        pos = self._calcular_posiciones(ancho, alto)
        self._pos_px = pos
        rutas = self._calcular_rutas(pos, ancho)
        self._calcular_cruces(rutas)
        simbolos = self._colocar_simbolos(rutas)

        for segs in rutas.values():
            for seg in segs:
                self._dibujar_cable(seg)
        for i, lista in simbolos.items():
            for simbolo in lista:
                self._dibujar_simbolo(simbolo, self._ramas[i])

        ocupacion = _Ocupacion(ancho, alto)
        for segs in rutas.values():
            ocupacion.cajas.extend(seg.caja(2) for seg in segs)
        for lista in simbolos.values():
            ocupacion.cajas.extend(s.caja for s in lista)
        for x, y in pos.values():
            ocupacion.cajas.append((x - 6, y - 6, x + 6, y + 6))

        self._dibujar_pie(ocupacion, alto)
        self._dibujar_nodos(pos, ocupacion)
        for i, lista in simbolos.items():
            self._dibujar_etiquetas(i, self._ramas[i], lista, ocupacion)

    def _dibujar_cable(self, seg):
        """Traza el cable dejando huecos para los símbolos y saltos en los cruces."""
        eventos = [(s - m, "hueco", s + m) for s, m in seg.simbolos]
        eventos += [(s - RADIO_SALTO, "salto", s + RADIO_SALTO) for s in seg.saltos]
        cursor = 0.0
        for inicio, tipo, fin in sorted(eventos):
            self._linea(seg, cursor, inicio)
            if tipo == "salto":
                cx, cy = seg.punto((inicio + fin) / 2)
                self._canvas.create_arc(cx - RADIO_SALTO, cy - RADIO_SALTO,
                                        cx + RADIO_SALTO, cy + RADIO_SALTO, start=0,
                                        extent=180, style=tk.ARC, outline=COLOR_CABLE,
                                        width=GROSOR_CABLE)
            cursor = fin
        self._linea(seg, cursor, seg.largo)

    def _linea(self, seg, s0, s1):
        if s1 - s0 < 0.5:
            return
        x0, y0 = seg.punto(s0)
        x1, y1 = seg.punto(s1)
        self._canvas.create_line(x0, y0, x1, y1, fill=COLOR_CABLE, width=GROSOR_CABLE,
                                 capstyle=tk.PROJECTING)

    def _dibujar_simbolo(self, simbolo, rama):
        lienzo = self._canvas
        if simbolo.tipo == "resistencia":
            lienzo.create_rectangle(*simbolo.caja, outline=COLOR_CABLE,
                                    width=GROSOR_CABLE, fill="")
            return
        # Batería: placa larga = polo +, placa corta = polo −. Con voltaje
        # positivo el polo + queda del lado del nodo final de la rama.
        cx, cy = simbolo.centro
        seg = simbolo.segmento
        nx, ny = -seg.uy, seg.ux
        signo = 1 if rama.voltaje > 0 else -1
        for lado, semilargo, grosor in ((signo, SEMI_PLACA_LARGA, GROSOR_CABLE),
                                        (-signo, SEMI_PLACA_CORTA, 3.5)):
            px = cx + seg.ux * SEPARACION_PLACAS * lado
            py = cy + seg.uy * SEPARACION_PLACAS * lado
            lienzo.create_line(px - nx * semilargo, py - ny * semilargo,
                               px + nx * semilargo, py + ny * semilargo,
                               fill=COLOR_CABLE, width=grosor)

    def _dibujar_pie(self, ocupacion, alto):
        texto = ("Arrastra los nodos para reacomodar el esquema · "
                 "Corriente negativa: flecha invertida y en rojo")
        ancho_texto = self._fuente_pie.measure(texto)
        self._canvas.create_text(8, alto - 6, anchor="sw", text=texto, fill="#888888",
                                 font=self._fuente_pie)
        ocupacion.cajas.append((6, alto - 22, 10 + ancho_texto, alto))

    def _dibujar_nodos(self, pos, ocupacion):
        ancho = self._fuente_nodo.measure("M") + 4
        alto = self._fuente_nodo.metrics("linespace")
        desplazamientos = ((10, -10), (10, 10), (-10, -10), (-10, 10),
                           (0, -15), (0, 15), (15, 0), (-15, 0))
        for nodo, (x, y) in pos.items():
            self._canvas.create_oval(x - RADIO_NODO, y - RADIO_NODO, x + RADIO_NODO,
                                     y + RADIO_NODO, fill="black", outline="black")
            candidatos = []
            for dx, dy in desplazamientos:
                cx, cy = x + dx, y + dy
                caja = (cx - ancho / 2, cy - alto / 2, cx + ancho / 2, cy + alto / 2)
                candidatos.append((caja, (cx, cy)))
            cx, cy = ocupacion.elegir(candidatos)
            self._canvas.create_text(cx, cy, text=nombre_nodo(nodo), fill=COLOR_TEXTO,
                                     font=self._fuente_nodo)

    # ------------------------------------------------------------------
    # Etiquetas (nombre/valor de la resistencia, fuente y corriente)
    # ------------------------------------------------------------------
    def _medir(self, texto):
        return self._fuente.measure(texto) + 4, self._fuente.metrics("linespace") + 2

    @staticmethod
    def _normales(seg):
        """Lado preferido de las etiquetas (arriba / derecha) y su opuesto."""
        preferido = (0, -1) if seg.horizontal else (1, 0)
        return preferido, (-preferido[0], -preferido[1])

    def _candidatos_texto(self, texto, simbolo, distancia):
        """Posiciones posibles de una etiqueta junto a un símbolo, a ambos lados."""
        ancho, alto = self._medir(texto)
        seg = simbolo.segmento
        candidatos = []
        for desplazamiento in (0, 24, -24):
            s = min(max(simbolo.s + desplazamiento, 4), seg.largo - 4)
            px, py = seg.punto(s)
            for n in self._normales(seg):
                extension = alto if n[1] != 0 else ancho
                cx = px + n[0] * (distancia + extension / 2)
                cy = py + n[1] * (distancia + extension / 2)
                caja = (cx - ancho / 2, cy - alto / 2, cx + ancho / 2, cy + alto / 2)
                candidatos.append((caja, (cx, cy)))
        return candidatos

    def _candidatos_corriente(self, texto, simbolo):
        """Flecha + texto de la corriente, junto a la resistencia de la rama."""
        ancho, alto = self._medir(texto)
        seg = simbolo.segmento
        preferido, opuesto = self._normales(seg)
        candidatos = []
        for n in (opuesto, preferido):          # el lado opuesto al de la etiqueta R
            for desplazamiento in (0, 34, -34, 58, -58):
                s = simbolo.s + desplazamiento
                if s < 6 or s > seg.largo - 6:
                    continue
                qx, qy = seg.punto(s)
                ax, ay = qx + n[0] * 14, qy + n[1] * 14
                extension = alto if n[1] != 0 else ancho
                tx = qx + n[0] * (20 + extension / 2)
                ty = qy + n[1] * (20 + extension / 2)
                mitad_a = (10, 4) if seg.horizontal else (4, 10)
                caja_flecha = (ax - mitad_a[0], ay - mitad_a[1], ax + mitad_a[0], ay + mitad_a[1])
                caja_texto = (tx - ancho / 2, ty - alto / 2, tx + ancho / 2, ty + alto / 2)
                candidatos.append((_unir(caja_flecha, caja_texto), ((ax, ay), (tx, ty))))
        if not candidatos:  # tramo demasiado corto: se deja pegado al símbolo
            qx, qy = seg.punto(simbolo.s)
            candidatos.append(((qx, qy, qx, qy), ((qx, qy), (qx, qy))))
        return candidatos

    def _dibujar_etiquetas(self, i, rama, simbolos, ocupacion):
        lienzo = self._canvas
        resistencia = next(s for s in simbolos if s.tipo == "resistencia")

        texto_r = f"R{i + 1} {rama.resistencia:g} Ω"
        cx, cy = ocupacion.elegir(self._candidatos_texto(texto_r, resistencia, 11))
        lienzo.create_text(cx, cy, text=texto_r, fill=COLOR_TEXTO, font=self._fuente)

        for simbolo in simbolos:
            if simbolo.tipo == "fuente":
                texto_v = f"{abs(rama.voltaje):g} V"
                cx, cy = ocupacion.elegir(
                    self._candidatos_texto(texto_v, simbolo, SEMI_PLACA_LARGA + 3))
                lienzo.create_text(cx, cy, text=texto_v, fill=COLOR_TEXTO, font=self._fuente)

        # Corriente: la flecha apunta en el sentido dibujado (a → b) y se invierte,
        # en rojo, cuando la corriente calculada es negativa.
        corriente = None
        if self._resultados is not None and i < len(self._resultados):
            corriente = self._resultados[i].corriente
        negativa = corriente is not None and corriente < 0
        color = COLOR_NEGATIVO if negativa else (COLOR_TEXTO if corriente is not None
                                                 else COLOR_TEXTO_SUAVE)
        texto_i = f"I{i + 1}" if corriente is None \
            else f"I{i + 1} = {self._formato_corriente(corriente)} A"

        (ax, ay), (tx, ty) = ocupacion.elegir(
            self._candidatos_corriente(texto_i, resistencia))
        seg = resistencia.segmento
        sentido = -1 if negativa else 1
        fx, fy = seg.ux * sentido, seg.uy * sentido
        lienzo.create_line(ax - fx * 9, ay - fy * 9, ax + fx * 9, ay + fy * 9, fill=color,
                           width=1.5, arrow=tk.LAST, arrowshape=(7, 8, 3))
        lienzo.create_text(tx, ty, text=texto_i, fill=color, font=self._fuente)

    @staticmethod
    def _formato_corriente(valor):
        if valor == 0 or abs(valor) >= 0.01:
            return f"{valor:.2f}"
        return f"{valor:.2e}"
