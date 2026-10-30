"""Modelo: el circuito (nodos y ramas) y todas sus validaciones."""

import math
from collections import deque
from numbers import Integral, Real

from modelo.rama import Rama

MIN_NODOS = 2
MAX_NODOS = 12


class ErrorCircuito(ValueError):
    """Error de validación con un mensaje pensado para mostrarse al usuario."""


class Circuito:
    """Conjunto de nodos (numerados 1..N) y de ramas que los conectan.

    No sabe nada de la interfaz gráfica ni resuelve ecuaciones: solo guarda
    los datos y comprueba que sean válidos.
    """

    def __init__(self, num_nodos=MIN_NODOS):
        self._num_nodos = MIN_NODOS
        self._ramas = []
        self.establecer_num_nodos(num_nodos)

    # ------------------------------------------------------------------
    # Consulta
    # ------------------------------------------------------------------
    @property
    def nodos(self):
        """Tupla con los identificadores de los nodos: (1, 2, ..., N)."""
        return tuple(range(1, self._num_nodos + 1))

    @property
    def ramas(self):
        """Tupla (solo lectura) con las ramas, en el orden en que se agregaron."""
        return tuple(self._ramas)

    def existe_nodo(self, nodo):
        return isinstance(nodo, Integral) and not isinstance(nodo, bool) \
            and 1 <= nodo <= self._num_nodos

    # ------------------------------------------------------------------
    # Modificación
    # ------------------------------------------------------------------
    def establecer_num_nodos(self, cantidad):
        """Define cuántos nodos tiene el circuito (entre MIN_NODOS y MAX_NODOS)."""
        if not isinstance(cantidad, Integral) or isinstance(cantidad, bool):
            raise ErrorCircuito("El número de nodos debe ser un entero.")
        if not MIN_NODOS <= cantidad <= MAX_NODOS:
            raise ErrorCircuito(
                f"El número de nodos debe estar entre {MIN_NODOS} y {MAX_NODOS}.")
        # No se puede dejar una rama apuntando a un nodo que dejaría de existir.
        for i, rama in enumerate(self._ramas, start=1):
            mayor = max(rama.nodo_a, rama.nodo_b)
            if mayor > cantidad:
                raise ErrorCircuito(
                    f"No se puede reducir a {cantidad} nodos: la rama {i} "
                    f"usa el nodo {mayor}. Elimínala primero.")
        self._num_nodos = int(cantidad)

    def agregar_rama(self, nodo_a, nodo_b, resistencia, voltaje=0.0):
        """Valida los datos y agrega una rama. Devuelve la ``Rama`` creada."""
        for nombre, nodo in (("inicial", nodo_a), ("final", nodo_b)):
            if not isinstance(nodo, Integral) or isinstance(nodo, bool):
                raise ErrorCircuito(f"El nodo {nombre} debe ser un número entero.")
            if not self.existe_nodo(nodo):
                raise ErrorCircuito(
                    f"El nodo {nombre} ({nodo}) no existe: el circuito tiene "
                    f"los nodos 1 a {self._num_nodos}.")
        if nodo_a == nodo_b:
            raise ErrorCircuito(
                "El nodo inicial y el final deben ser distintos "
                "(una rama no puede empezar y terminar en el mismo nodo).")

        if not self._es_real_finito(resistencia):
            raise ErrorCircuito("La resistencia debe ser un número real finito.")
        if resistencia <= 0:
            raise ErrorCircuito(
                f"La resistencia debe ser mayor que 0 Ω (se recibió {resistencia:g} Ω).")
        if not self._es_real_finito(voltaje):
            raise ErrorCircuito("El voltaje de la fuente debe ser un número real finito.")

        rama = Rama(int(nodo_a), int(nodo_b), float(resistencia), float(voltaje))
        self._ramas.append(rama)
        return rama

    def eliminar_rama(self, indice):
        """Elimina la rama en la posición ``indice`` (empezando en 0)."""
        if not isinstance(indice, Integral) or not 0 <= indice < len(self._ramas):
            raise ErrorCircuito("La rama que se quiere eliminar no existe.")
        return self._ramas.pop(indice)

    def limpiar(self):
        """Borra todas las ramas y vuelve al número mínimo de nodos."""
        self._ramas.clear()
        self._num_nodos = MIN_NODOS

    # ------------------------------------------------------------------
    # Validaciones previas al cálculo
    # ------------------------------------------------------------------
    def nodos_inalcanzables(self):
        """Nodos que no se pueden alcanzar desde el nodo 1 siguiendo las ramas."""
        vecinos = {n: [] for n in self.nodos}
        for rama in self._ramas:
            vecinos[rama.nodo_a].append(rama.nodo_b)
            vecinos[rama.nodo_b].append(rama.nodo_a)
        visitados = {1}
        cola = deque([1])
        while cola:
            actual = cola.popleft()
            for vecino in vecinos[actual]:
                if vecino not in visitados:
                    visitados.add(vecino)
                    cola.append(vecino)
        return [n for n in self.nodos if n not in visitados]

    def es_conexo(self):
        return not self.nodos_inalcanzables()

    def validar_para_resolver(self):
        """Lanza ``ErrorCircuito`` si el circuito aún no se puede resolver."""
        if not self._ramas:
            raise ErrorCircuito("El circuito no tiene ramas. Agrega al menos una.")
        sueltos = self.nodos_inalcanzables()
        if sueltos:
            lista = ", ".join(str(n) for n in sueltos)
            raise ErrorCircuito(
                f"El circuito no es conexo: el/los nodo(s) {lista} no están "
                "conectados con el resto. Une cada nodo con una rama o reduce "
                "el número de nodos.")

    @staticmethod
    def _es_real_finito(valor):
        return isinstance(valor, Real) and not isinstance(valor, bool) \
            and math.isfinite(valor)
