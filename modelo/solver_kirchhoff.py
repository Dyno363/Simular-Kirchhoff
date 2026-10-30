"""Modelo: arma y resuelve el sistema de ecuaciones de Kirchhoff.

Incógnitas: la corriente de cada una de las m ramas.
Ecuaciones (m en total):
  * KCL en n-1 nodos (el nodo de referencia sale sobrante).
  * KVL en los m-(n-1) lazos independientes (un lazo por cada rama que no
    pertenece a un árbol de expansión del circuito).
"""

from collections import deque
from dataclasses import dataclass
from typing import NamedTuple

import numpy as np

from modelo.circuito import ErrorCircuito
from modelo.rama import Rama

# Una corriente menor que esto es ruido numérico y se muestra como 0.
UMBRAL_CERO = 1e-12
# Tolerancia relativa para dar por cumplida la KCL en un nodo.
TOLERANCIA_RELATIVA = 1e-9
# Si la matriz está peor condicionada que esto se considera singular.
LIMITE_CONDICION = 1e13


class ErrorSistemaSingular(ErrorCircuito):
    """El sistema de ecuaciones no tiene una solución única."""


# ----------------------------------------------------------------------
# Resultados
# ----------------------------------------------------------------------
@dataclass(frozen=True)
class ResultadoRama:
    indice: int                 # número de rama (empieza en 1)
    rama: Rama
    corriente: float            # A; negativa => va de nodo_b a nodo_a
    voltaje_resistencia: float  # V en la resistencia = R * I (de a hacia b)

    @property
    def en_sentido_dibujado(self):
        return self.corriente >= 0


@dataclass(frozen=True)
class BalanceNodo:
    nodo: int
    corriente_entra: float  # suma de las corrientes que llegan al nodo (A)
    corriente_sale: float   # suma de las corrientes que salen del nodo (A)
    neto: float             # entra - sale; debe ser ~0 (KCL)
    potencial: float        # V respecto al nodo de referencia
    cumple: bool


@dataclass(frozen=True)
class ResultadoLazo:
    """Verificación de la KVL en un lazo independiente."""
    numero: int
    terminos: tuple         # ((índice de rama, signo), ...); +1 = recorrida de a hacia b
    suma_fuentes: float     # Σ s·ε   (V)
    suma_caidas: float      # Σ s·R·I (V)
    suma: float             # Σ s·(ε − R·I); debe ser ~0 (KVL)
    cumple: bool


@dataclass(frozen=True)
class ResultadoKirchhoff:
    ramas: tuple
    nodos: tuple
    nodo_referencia: int
    num_lazos: int
    tolerancia: float
    residuo_kvl: float  # mayor error al comprobar V_b - V_a = E - R*I en las ramas
    lazos: tuple              # un ResultadoLazo por lazo independiente
    potencia_entregada: float  # Σ ε·I  (W), neta de las fuentes
    potencia_disipada: float   # Σ R·I² (W), en las resistencias
    tolerancia_potencia: float

    @property
    def num_ecuaciones_kcl(self):
        return len(self.nodos) - 1

    @property
    def kcl_se_cumple(self):
        return all(balance.cumple for balance in self.nodos)

    @property
    def kvl_se_cumple(self):
        return all(lazo.cumple for lazo in self.lazos)

    @property
    def potencia_balanceada(self):
        return abs(self.potencia_entregada - self.potencia_disipada) \
            <= self.tolerancia_potencia

    def potencial(self, nodo):
        for balance in self.nodos:
            if balance.nodo == nodo:
                return balance.potencial
        raise ErrorCircuito(f"El nodo {nodo} no existe.")

    def diferencia_potencial(self, nodo_a, nodo_b):
        """V(nodo_a) - V(nodo_b)."""
        return self.potencial(nodo_a) - self.potencial(nodo_b)


class _Arbol(NamedTuple):
    """Árbol de expansión del circuito, recorrido desde el nodo de referencia."""
    orden: list    # nodos en el orden en que se visitaron
    padre: dict    # nodo -> nodo del que se llegó
    camino: dict   # nodo -> [(índice_rama, signo)] desde la referencia hasta él
    ramas: set     # índices de las ramas que forman el árbol


# ----------------------------------------------------------------------
# Solver
# ----------------------------------------------------------------------
class SolverKirchhoff:
    """Resuelve un ``Circuito`` aplicando las leyes de Kirchhoff."""

    def resolver(self, circuito):
        circuito.validar_para_resolver()
        ramas = circuito.ramas
        nodos = circuito.nodos
        referencia = nodos[0]

        arbol = self._construir_arbol(nodos, ramas, referencia)
        matriz, independientes, lazos = self._armar_sistema(
            nodos, ramas, referencia, arbol)
        corrientes = self.resolver_sistema(matriz, independientes)
        corrientes = np.where(np.abs(corrientes) < UMBRAL_CERO, 0.0, corrientes)

        return self._empaquetar(nodos, ramas, referencia, arbol, corrientes, lazos)

    # -- paso 1: estructura del grafo ----------------------------------
    @staticmethod
    def _construir_arbol(nodos, ramas, referencia):
        """Recorrido en anchura desde la referencia.

        El signo de cada paso vale +1 si se recorre la rama de a hacia b y
        -1 si se recorre de b hacia a.
        """
        vecinos = {n: [] for n in nodos}
        for k, rama in enumerate(ramas):
            vecinos[rama.nodo_a].append((rama.nodo_b, k, +1))
            vecinos[rama.nodo_b].append((rama.nodo_a, k, -1))

        camino = {referencia: []}
        padre = {}
        orden = [referencia]
        en_arbol = set()
        cola = deque([referencia])
        while cola:
            actual = cola.popleft()
            for vecino, k, signo in vecinos[actual]:
                if vecino not in camino:
                    camino[vecino] = camino[actual] + [(k, signo)]
                    padre[vecino] = actual
                    orden.append(vecino)
                    en_arbol.add(k)
                    cola.append(vecino)
        return _Arbol(orden, padre, camino, en_arbol)

    # -- paso 2: sistema A·I = b ---------------------------------------
    @staticmethod
    def _armar_sistema(nodos, ramas, referencia, arbol):
        m = len(ramas)
        resistencias = np.array([r.resistencia for r in ramas])
        fuentes = np.array([r.voltaje for r in ramas])
        matriz = np.zeros((m, m))
        independientes = np.zeros(m)

        # KCL en cada nodo salvo la referencia:
        #   (corrientes que salen) - (corrientes que entran) = 0
        fila = 0
        for nodo in nodos:
            if nodo == referencia:
                continue
            for k, rama in enumerate(ramas):
                if rama.nodo_a == nodo:
                    matriz[fila, k] += 1.0
                if rama.nodo_b == nodo:
                    matriz[fila, k] -= 1.0
            fila += 1

        # KVL en el lazo fundamental de cada cuerda (rama fuera del árbol).
        # El lazo es: la cuerda de a hacia b, luego el camino por el árbol de
        # b hasta la referencia y de la referencia hasta a. Los tramos comunes
        # se recorren en ambos sentidos y se cancelan solos al sumar signos.
        # Suma de subidas de potencial = 0  =>  Σ s·R·I = Σ s·E
        lazos = []  # signos de cada lazo, para poder verificarlo después
        for k_cuerda, cuerda in enumerate(ramas):
            if k_cuerda in arbol.ramas:
                continue
            signos = np.zeros(m)
            signos[k_cuerda] += 1.0
            for k, signo in arbol.camino[cuerda.nodo_b]:
                signos[k] -= signo      # b -> referencia: se recorre al revés
            for k, signo in arbol.camino[cuerda.nodo_a]:
                signos[k] += signo      # referencia -> a
            matriz[fila] = signos * resistencias
            independientes[fila] = signos @ fuentes
            lazos.append(signos)
            fila += 1

        return matriz, independientes, lazos

    # -- paso 3: resolver ----------------------------------------------
    @staticmethod
    def resolver_sistema(matriz, independientes):
        """Resuelve A·x = b con ``numpy.linalg.solve`` detectando singularidad."""
        mensaje = ("El sistema de ecuaciones es singular (no tiene una solución "
                   "única). Revisa que las ramas estén bien conectadas.")
        try:
            condicion = np.linalg.cond(matriz)
            if not np.isfinite(condicion) or condicion > LIMITE_CONDICION:
                raise ErrorSistemaSingular(mensaje)
            solucion = np.linalg.solve(matriz, independientes)
        except np.linalg.LinAlgError as error:
            raise ErrorSistemaSingular(mensaje) from error
        if not np.all(np.isfinite(solucion)):
            raise ErrorSistemaSingular(mensaje)
        return solucion

    # -- paso 4: voltajes, verificación KCL y resultado -----------------
    @staticmethod
    def _empaquetar(nodos, ramas, referencia, arbol, corrientes, lazos):
        # Voltaje en cada resistencia (de a hacia b): V = R * I
        voltajes_r = [r.resistencia * i for r, i in zip(ramas, corrientes)]

        # Potenciales: V_b = V_a + E - R*I, recorriendo el árbol de expansión.
        potenciales = {referencia: 0.0}
        for nodo in arbol.orden[1:]:
            k, signo = arbol.camino[nodo][-1]
            salto = ramas[k].voltaje - voltajes_r[k]
            potenciales[nodo] = potenciales[arbol.padre[nodo]] + signo * salto

        # Comprobación de la KVL en todas las ramas (incluidas las cuerdas).
        residuo = max(
            abs(potenciales[r.nodo_b] - potenciales[r.nodo_a] - (r.voltaje - v))
            for r, v in zip(ramas, voltajes_r))

        # Verificación de la KCL: se suma lo que realmente entra y sale de
        # cada nodo según el sentido físico de cada corriente.
        entra = {n: 0.0 for n in nodos}
        sale = {n: 0.0 for n in nodos}
        for rama, i in zip(ramas, corrientes):
            origen, destino = ((rama.nodo_a, rama.nodo_b) if i >= 0
                               else (rama.nodo_b, rama.nodo_a))
            sale[origen] += abs(i)
            entra[destino] += abs(i)

        escala = max(1.0, float(np.max(np.abs(corrientes))))
        tolerancia = TOLERANCIA_RELATIVA * escala
        balances = tuple(
            BalanceNodo(n, entra[n], sale[n], entra[n] - sale[n], potenciales[n],
                        abs(entra[n] - sale[n]) <= tolerancia)
            for n in nodos)

        resultados = tuple(
            ResultadoRama(k + 1, r, float(i), float(v))
            for k, (r, i, v) in enumerate(zip(ramas, corrientes, voltajes_r)))
        num_lazos = len(ramas) - (len(nodos) - 1)

        # Verificación de la KVL lazo por lazo: Σ s·(ε − R·I) debe ser 0.
        fuentes = np.array([r.voltaje for r in ramas])
        caidas = np.array(voltajes_r)
        escala_v = max(1.0, float(np.max(np.abs(fuentes))), float(np.max(np.abs(caidas))))
        tolerancia_v = TOLERANCIA_RELATIVA * escala_v
        verificacion_lazos = []
        for numero, signos in enumerate(lazos, start=1):
            suma_fuentes = float(signos @ fuentes)
            suma_caidas = float(signos @ caidas)
            suma = suma_fuentes - suma_caidas
            terminos = tuple((k + 1, int(s)) for k, s in enumerate(signos) if s != 0)
            verificacion_lazos.append(ResultadoLazo(
                numero, terminos, suma_fuentes, suma_caidas, suma,
                abs(suma) <= tolerancia_v))

        # Balance de potencia: lo que entregan las fuentes se disipa en las R.
        entregada = float(np.sum(fuentes * corrientes))
        disipada = float(np.sum(np.array([r.resistencia for r in ramas]) * corrientes ** 2))
        tolerancia_p = TOLERANCIA_RELATIVA * max(1.0, abs(entregada), disipada)

        return ResultadoKirchhoff(resultados, balances, referencia, num_lazos,
                                  tolerancia, float(residuo), tuple(verificacion_lazos),
                                  entregada, disipada, tolerancia_p)
