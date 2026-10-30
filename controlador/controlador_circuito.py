"""Controlador: conecta la vista con el modelo.

Recibe los textos que escribió el usuario, los convierte en números, se los
pasa al modelo y le ordena a la vista qué mostrar. Es el único que conoce a
las dos partes.
"""

import math

from modelo.circuito import MAX_NODOS, MIN_NODOS, ErrorCircuito

# Ejemplo del curso: fuente de 12 V con R1 = 2 Ω en serie con R2 = 6 Ω ∥ R3 = 3 Ω
# entre los nodos A (arriba, nodo 1) y B (abajo, nodo 2).
# Cada tupla es (nodo inicial, nodo final, resistencia, fuente).
EJEMPLO = (
    (2, 1, 2, 12),  # R1 + fuente: sube de B a A
    (1, 2, 6, 0),   # R2: baja de A a B
    (1, 2, 3, 0),   # R3: baja de A a B
)
# Dónde se dibuja cada nodo del ejemplo (fracción del ancho y del alto del lienzo).
EJEMPLO_DISPOSICION = {1: (0.5, 0.2), 2: (0.5, 0.8)}


class ControladorCircuito:

    def __init__(self, circuito, solver, vista):
        self._circuito = circuito
        self._solver = solver
        self._vista = vista

        vista.configurar_limites_nodos(MIN_NODOS, MAX_NODOS)
        vista.conectar(agregar=self.agregar_rama, eliminar=self.eliminar_rama,
                       calcular=self.calcular, limpiar=self.limpiar,
                       ejemplo=self.cargar_ejemplo, cambiar_nodos=self.cambiar_nodos)
        self._refrescar()

    # ------------------------------------------------------------------
    # Acciones de la interfaz
    # ------------------------------------------------------------------
    def agregar_rama(self, texto_a, texto_b, texto_r, texto_v):
        try:
            nodo_a = self._leer_nodo(texto_a, "nodo inicial")
            nodo_b = self._leer_nodo(texto_b, "nodo final")
            resistencia = self._leer_real(texto_r, "resistencia")
            voltaje = self._leer_real(texto_v, "voltaje de la fuente", vacio_es_cero=True)
            self._circuito.agregar_rama(nodo_a, nodo_b, resistencia, voltaje)
        except ErrorCircuito as error:
            self._vista.mostrar_error(str(error))
            return
        self._refrescar()
        self._vista.mostrar_mensaje(f"Rama {len(self._circuito.ramas)} agregada.")

    def eliminar_rama(self, indice):
        if indice is None:
            self._vista.mostrar_error("Selecciona primero una rama de la lista.")
            return
        try:
            self._circuito.eliminar_rama(indice)
        except ErrorCircuito as error:
            self._vista.mostrar_error(str(error))
            return
        self._refrescar()
        self._vista.mostrar_mensaje("Rama eliminada.")

    def cambiar_nodos(self, texto):
        try:
            cantidad = self._leer_entero(texto, "número de nodos")
            if cantidad != len(self._circuito.nodos):
                self._circuito.establecer_num_nodos(cantidad)
            else:
                return
        except ErrorCircuito as error:
            self._vista.mostrar_error(str(error))
        # Se refresca siempre: si hubo error, la vista vuelve al valor real.
        self._refrescar()

    def calcular(self):
        try:
            resultado = self._solver.resolver(self._circuito)
        except ErrorCircuito as error:  # incluye circuito no conexo y sistema singular
            self._vista.mostrar_error(str(error))
            return
        self._vista.mostrar_resultados(
            self._circuito.nodos, self._circuito.ramas, resultado)
        self._vista.mostrar_mensaje(
            "Cálculo terminado." if resultado.kcl_se_cumple
            else "Cálculo terminado, pero la KCL no se cumple: revisa los datos.")

    def limpiar(self):
        self._circuito.limpiar()
        self._refrescar(disposicion={})  # vuelve a la disposición automática
        self._vista.mostrar_mensaje("Circuito vaciado.")

    def cargar_ejemplo(self):
        self._circuito.limpiar()
        self._circuito.establecer_num_nodos(2)
        for nodo_a, nodo_b, resistencia, voltaje in EJEMPLO:
            self._circuito.agregar_rama(nodo_a, nodo_b, resistencia, voltaje)
        self._refrescar(disposicion=EJEMPLO_DISPOSICION)
        self._vista.mostrar_mensaje(
            "Ejemplo cargado: 12 V, R1 = 2 Ω en serie con R2 = 6 Ω ∥ R3 = 3 Ω. "
            "Presiona «Calcular».")

    # ------------------------------------------------------------------
    # Utilidades
    # ------------------------------------------------------------------
    def _refrescar(self, disposicion=None):
        self._vista.actualizar_circuito(self._circuito.nodos, self._circuito.ramas,
                                        disposicion)

    @staticmethod
    def _leer_nodo(texto, nombre):
        """Acepta el nodo como letra (A, B, C...) o como número (1, 2, 3...)."""
        limpio = str(texto).strip().upper()
        if len(limpio) == 1 and "A" <= limpio <= "Z":
            return ord(limpio) - ord("A") + 1
        try:
            return int(limpio)
        except ValueError:
            raise ErrorCircuito(
                f"El {nombre} debe ser una letra (A, B, C...) o un número "
                f"(se escribió «{texto}»).") from None

    @staticmethod
    def _leer_entero(texto, nombre):
        try:
            return int(str(texto).strip())
        except ValueError:
            raise ErrorCircuito(
                f"El {nombre} debe ser un número entero (se escribió «{texto}»).") from None

    @staticmethod
    def _leer_real(texto, nombre, vacio_es_cero=False):
        limpio = str(texto).strip().replace(",", ".")  # acepta coma decimal
        if not limpio:
            if vacio_es_cero:
                return 0.0
            raise ErrorCircuito(f"Falta indicar la {nombre}.")
        try:
            valor = float(limpio)
        except ValueError:
            raise ErrorCircuito(
                f"La {nombre} debe ser un número (se escribió «{texto}»).") from None
        if not math.isfinite(valor):
            raise ErrorCircuito(f"La {nombre} debe ser un número finito.")
        return valor
