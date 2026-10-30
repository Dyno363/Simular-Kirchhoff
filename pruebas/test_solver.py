"""Pruebas del modelo (circuito + solver) con unittest.

Ejecutar desde la carpeta simulador_kirchhoff:
    python -m unittest discover -s pruebas -v
"""

import os
import sys
import unittest

import numpy as np

# Permite ejecutar este archivo directamente sin instalar nada.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from controlador.controlador_circuito import EJEMPLO  # noqa: E402
from modelo.circuito import Circuito, ErrorCircuito  # noqa: E402
from modelo.solver_kirchhoff import (  # noqa: E402
    ErrorSistemaSingular, SolverKirchhoff)


def circuito_base():
    """Fuente de 12 V con R1 = 2 Ω en serie con R2 = 6 Ω ∥ R3 = 3 Ω."""
    c = Circuito(2)
    c.agregar_rama(1, 2, 2, 12)  # R1 + fuente: de 1 hacia 2
    c.agregar_rama(2, 1, 6, 0)   # R2: de 2 hacia 1
    c.agregar_rama(2, 1, 3, 0)   # R3: de 2 hacia 1
    return c


class PruebasSolver(unittest.TestCase):

    def setUp(self):
        self.solver = SolverKirchhoff()

    # -- caso base del enunciado ----------------------------------------
    def test_caso_base(self):
        r = self.solver.resolver(circuito_base())
        i1, i2, i3 = (x.corriente for x in r.ramas)
        self.assertAlmostEqual(i1, 3.0)
        self.assertAlmostEqual(i2, 1.0)
        self.assertAlmostEqual(i3, 2.0)
        # Vab = voltaje entre los extremos del paralelo (nodo 2 respecto al 1)
        self.assertAlmostEqual(r.diferencia_potencial(2, 1), 6.0)
        # Voltaje en cada resistencia: R * I
        self.assertAlmostEqual(r.ramas[0].voltaje_resistencia, 6.0)
        self.assertAlmostEqual(r.ramas[1].voltaje_resistencia, 6.0)
        self.assertAlmostEqual(r.ramas[2].voltaje_resistencia, 6.0)

    def test_caso_base_cumple_kcl_y_kvl(self):
        r = self.solver.resolver(circuito_base())
        self.assertTrue(r.kcl_se_cumple)
        self.assertLess(r.residuo_kvl, 1e-9)
        self.assertEqual(r.num_ecuaciones_kcl, 1)
        self.assertEqual(r.num_lazos, 2)

    # -- signo de la corriente -----------------------------------------
    def test_corriente_negativa_si_la_rama_se_dibuja_al_reves(self):
        c = Circuito(2)
        c.agregar_rama(1, 2, 2, 12)
        c.agregar_rama(1, 2, 6, 0)  # R2 dibujada de 1 a 2: opuesta al caso base
        c.agregar_rama(2, 1, 3, 0)
        r = self.solver.resolver(c)
        self.assertAlmostEqual(r.ramas[1].corriente, -1.0)
        self.assertFalse(r.ramas[1].en_sentido_dibujado)
        self.assertTrue(r.ramas[0].en_sentido_dibujado)
        self.assertAlmostEqual(r.ramas[0].corriente, 3.0)

    def test_fuente_invertida_invierte_todas_las_corrientes(self):
        c = Circuito(2)
        c.agregar_rama(1, 2, 2, -12)
        c.agregar_rama(2, 1, 6, 0)
        c.agregar_rama(2, 1, 3, 0)
        r = self.solver.resolver(c)
        self.assertAlmostEqual(r.ramas[0].corriente, -3.0)
        self.assertAlmostEqual(r.ramas[1].corriente, -1.0)
        self.assertAlmostEqual(r.ramas[2].corriente, -2.0)

    # -- otros circuitos ------------------------------------------------
    def test_malla_simple_dos_fuentes(self):
        # Malla de 3 nodos: 10 V y 4 V opuestas, resistencias 1, 2 y 3 Ω.
        c = Circuito(3)
        c.agregar_rama(1, 2, 1, 10)
        c.agregar_rama(2, 3, 2, 0)
        c.agregar_rama(3, 1, 3, -4)
        r = self.solver.resolver(c)
        esperada = (10 - 4) / (1 + 2 + 3)
        for x in r.ramas:
            self.assertAlmostEqual(x.corriente, esperada)

    def test_puente_de_wheatstone_equilibrado(self):
        c = Circuito(4)
        c.agregar_rama(1, 2, 1, 10)   # fuente + resistencia interna
        c.agregar_rama(2, 3, 10)
        c.agregar_rama(2, 4, 10)
        c.agregar_rama(3, 1, 10)
        c.agregar_rama(4, 1, 10)
        c.agregar_rama(3, 4, 5)       # rama del puente
        r = self.solver.resolver(c)
        self.assertAlmostEqual(r.ramas[5].corriente, 0.0)
        self.assertAlmostEqual(r.ramas[0].corriente, 10 / 11)
        self.assertTrue(r.kcl_se_cumple)
        self.assertLess(r.residuo_kvl, 1e-9)

    def test_puente_desequilibrado_cumple_las_leyes(self):
        c = Circuito(4)
        c.agregar_rama(1, 2, 1, 9)
        c.agregar_rama(2, 3, 4)
        c.agregar_rama(2, 4, 10)
        c.agregar_rama(3, 1, 7)
        c.agregar_rama(4, 1, 3)
        c.agregar_rama(3, 4, 5)
        r = self.solver.resolver(c)
        self.assertEqual(r.num_lazos, 3)
        self.assertTrue(r.kcl_se_cumple)
        self.assertLess(r.residuo_kvl, 1e-9)
        self.assertNotAlmostEqual(r.ramas[5].corriente, 0.0)

    # -- validaciones ---------------------------------------------------
    def test_resistencia_debe_ser_positiva(self):
        c = Circuito(2)
        for malo in (0, -5, float("nan"), float("inf")):
            with self.assertRaises(ErrorCircuito):
                c.agregar_rama(1, 2, malo, 5)
        self.assertEqual(len(c.ramas), 0)

    def test_nodo_inexistente(self):
        c = Circuito(2)
        with self.assertRaisesRegex(ErrorCircuito, "no existe"):
            c.agregar_rama(1, 3, 5, 0)
        with self.assertRaises(ErrorCircuito):
            c.agregar_rama(0, 1, 5, 0)

    def test_nodos_iguales(self):
        with self.assertRaises(ErrorCircuito):
            Circuito(2).agregar_rama(2, 2, 5, 0)

    def test_voltaje_debe_ser_finito(self):
        with self.assertRaises(ErrorCircuito):
            Circuito(2).agregar_rama(1, 2, 5, float("nan"))

    def test_circuito_sin_ramas(self):
        with self.assertRaisesRegex(ErrorCircuito, "no tiene ramas"):
            self.solver.resolver(Circuito(2))

    def test_circuito_no_conexo(self):
        c = Circuito(4)
        c.agregar_rama(1, 2, 5, 10)
        c.agregar_rama(3, 4, 5, 0)
        with self.assertRaisesRegex(ErrorCircuito, "no es conexo"):
            self.solver.resolver(c)

    def test_nodo_sin_ramas_no_es_conexo(self):
        c = Circuito(3)
        c.agregar_rama(1, 2, 5, 10)
        self.assertFalse(c.es_conexo())
        self.assertEqual(c.nodos_inalcanzables(), [3])

    def test_sistema_singular(self):
        singular = np.array([[1.0, 2.0], [2.0, 4.0]])
        with self.assertRaises(ErrorSistemaSingular):
            SolverKirchhoff.resolver_sistema(singular, np.array([1.0, 2.0]))

    def test_no_se_reducen_nodos_en_uso(self):
        c = Circuito(3)
        c.agregar_rama(1, 3, 5, 0)
        with self.assertRaises(ErrorCircuito):
            c.establecer_num_nodos(2)
        self.assertEqual(c.nodos, (1, 2, 3))

    def test_eliminar_y_limpiar(self):
        c = circuito_base()
        c.eliminar_rama(0)
        self.assertEqual(len(c.ramas), 2)
        with self.assertRaises(ErrorCircuito):
            c.eliminar_rama(5)
        c.limpiar()
        self.assertEqual(c.ramas, ())


def circuito_cuatro_nodos():
    """Puente de 4 nodos con una fuente de 9 V (nodos A, B, C, D = 1, 2, 3, 4)."""
    c = Circuito(4)
    c.agregar_rama(1, 2, 1, 9)   # R1 + fuente
    c.agregar_rama(2, 3, 4)      # R2
    c.agregar_rama(2, 4, 10)     # R3
    c.agregar_rama(3, 1, 7)      # R4
    c.agregar_rama(4, 1, 3)      # R5
    c.agregar_rama(3, 4, 5)      # R6 (puente)
    return c


def corrientes_por_nodos(circuito):
    """Resuelve el mismo circuito con análisis nodal, como comprobación independiente.

    Con V_b − V_a = ε − R·I se tiene I = (ε + V_a − V_b) / R. Se aplica KCL
    en los nodos 2..N y el nodo 1 queda a 0 V.
    """
    n = len(circuito.nodos)
    a = np.zeros((n - 1, n - 1))
    b = np.zeros(n - 1)
    for rama in circuito.ramas:
        g = 1.0 / rama.resistencia
        for nodo, saliente in ((rama.nodo_a, True), (rama.nodo_b, False)):
            if nodo == 1:
                continue
            fila = nodo - 2
            signo = 1.0 if saliente else -1.0          # I sale de a, entra en b
            # I = g·(ε + V_a − V_b)
            b[fila] -= signo * g * rama.voltaje
            for otro, coef in ((rama.nodo_a, +g), (rama.nodo_b, -g)):
                if otro != 1:
                    a[fila, otro - 2] += signo * coef
    tensiones = np.concatenate(([0.0], np.linalg.solve(a, b)))
    return [(r.voltaje + tensiones[r.nodo_a - 1] - tensiones[r.nodo_b - 1]) / r.resistencia
            for r in circuito.ramas]


class PruebasVerificaciones(unittest.TestCase):
    """Caso base (el ejemplo que carga la interfaz) y circuito de 4 nodos."""

    def setUp(self):
        self.solver = SolverKirchhoff()

    def test_ejemplo_de_la_interfaz(self):
        # Mismo circuito que «Cargar ejemplo»: B → A con 12 V + R1, y R2, R3 de A a B.
        c = Circuito(2)
        for nodo_a, nodo_b, r, v in EJEMPLO:
            c.agregar_rama(nodo_a, nodo_b, r, v)
        res = self.solver.resolver(c)
        for esperada, rama in zip((3.0, 1.0, 2.0), res.ramas):
            self.assertAlmostEqual(rama.corriente, esperada)
            self.assertTrue(rama.en_sentido_dibujado)
        self.assertAlmostEqual(res.diferencia_potencial(1, 2), 6.0)  # Vab = V_A − V_B

    def test_caso_base_kvl_por_lazo(self):
        res = self.solver.resolver(circuito_base())
        self.assertEqual(len(res.lazos), 2)
        for lazo in res.lazos:
            self.assertTrue(lazo.cumple)
            self.assertAlmostEqual(lazo.suma, 0.0)
            # Σ fuentes = Σ R·I en cada lazo (12 V = 2·3 + 6·1)
            self.assertAlmostEqual(lazo.suma_fuentes, 12.0)
            self.assertAlmostEqual(lazo.suma_caidas, 12.0)
        self.assertTrue(res.kvl_se_cumple)

    def test_caso_base_balance_de_potencia(self):
        res = self.solver.resolver(circuito_base())
        self.assertAlmostEqual(res.potencia_entregada, 36.0)   # 12 V · 3 A
        self.assertAlmostEqual(res.potencia_disipada, 36.0)    # 2·9 + 6·1 + 3·4
        self.assertTrue(res.potencia_balanceada)

    def test_cuatro_nodos_coincide_con_analisis_nodal(self):
        c = circuito_cuatro_nodos()
        res = self.solver.resolver(c)
        for obtenida, esperada in zip((r.corriente for r in res.ramas),
                                      corrientes_por_nodos(c)):
            self.assertAlmostEqual(obtenida, esperada, places=9)

    def test_cuatro_nodos_valores_conocidos(self):
        res = self.solver.resolver(circuito_cuatro_nodos())
        valores = [r.corriente for r in res.ramas]
        for obtenida, esperada in zip(valores, (1.4020, 0.8898, 0.5123, 0.5770,
                                                0.8250, 0.3128)):
            self.assertAlmostEqual(obtenida, esperada, places=4)

    def test_cuatro_nodos_kcl_kvl_y_potencia(self):
        res = self.solver.resolver(circuito_cuatro_nodos())
        self.assertEqual(len(res.nodos), 4)
        self.assertTrue(res.kcl_se_cumple)
        self.assertEqual(len(res.lazos), 3)
        self.assertTrue(res.kvl_se_cumple)
        self.assertTrue(all(abs(lazo.suma) < 1e-9 for lazo in res.lazos))
        self.assertTrue(res.potencia_balanceada)
        self.assertAlmostEqual(res.potencia_entregada, 9 * res.ramas[0].corriente)

    def test_fuente_que_absorbe_potencia_sigue_balanceando(self):
        # Dos fuentes opuestas: la de 4 V recibe energía (potencia neta negativa).
        c = Circuito(3)
        c.agregar_rama(1, 2, 1, 10)
        c.agregar_rama(2, 3, 2, 0)
        c.agregar_rama(3, 1, 3, -4)
        res = self.solver.resolver(c)
        self.assertTrue(res.potencia_balanceada)
        self.assertTrue(res.kvl_se_cumple)


if __name__ == "__main__":
    unittest.main()
