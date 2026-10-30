"""Vista: tablas con las corrientes, los voltajes y las verificaciones de KCL y KVL.

Solo muestra los valores que ya calculó el modelo; no hace cálculos.
"""

import tkinter as tk
from tkinter import ttk

from vista.panel_circuito import nombre_nodo

# Por debajo de este valor una diferencia se muestra como «≈ 0» (ruido numérico).
UMBRAL_CASI_CERO = 1e-9


def _formato_diferencia(valor):
    return "≈ 0" if abs(valor) < UMBRAL_CASI_CERO else f"{valor:.2e}"


class PanelResultados(ttk.Frame):

    def __init__(self, padre):
        super().__init__(padre)
        self._tabla_ramas = self._crear_tabla(
            self, "Corrientes y voltajes por rama",
            (("rama", "Rama", 55), ("nodos", "Nodos (a → b)", 95),
             ("r", "R (Ω)", 70), ("fuente", "Fuente (V)", 80),
             ("i", "Corriente I (A)", 105), ("vr", "Voltaje en R (V)", 110),
             ("sentido", "Sentido real", 200)), altura=4)

        cuaderno = ttk.Notebook(self)
        cuaderno.pack(fill="both", expand=True, padx=6, pady=(4, 0))
        pestana_kcl = ttk.Frame(cuaderno)
        pestana_kvl = ttk.Frame(cuaderno)
        cuaderno.add(pestana_kcl, text="Verificación KCL (nodos)")
        cuaderno.add(pestana_kvl, text="Verificación KVL (lazos)")
        self._tabla_nodos = self._crear_tabla(
            pestana_kcl, None,
            (("nodo", "Nodo", 55), ("entra", "ΣI que entra (A)", 120),
             ("sale", "ΣI que sale (A)", 120), ("neto", "Entra − sale (A)", 120),
             ("potencial", "Potencial (V)", 100), ("estado", "KCL", 110)), altura=4)
        self._tabla_lazos = self._crear_tabla(
            pestana_kvl, None,
            (("lazo", "Lazo", 55), ("ramas", "Ramas recorridas", 170),
             ("fuentes", "Σ fuentes (V)", 100), ("caidas", "Σ R·I (V)", 100),
             ("suma", "Σ voltajes (V)", 110), ("estado", "KVL", 110)), altura=4)

        self._resumen = tk.StringVar()
        etiqueta = ttk.Label(self, textvariable=self._resumen, wraplength=600,
                             justify="left")
        etiqueta.pack(fill="x", padx=6, pady=(2, 6))
        # El texto se ajusta al ancho disponible para que no se corte.
        etiqueta.bind("<Configure>",
                      lambda e: etiqueta.configure(wraplength=max(e.width - 12, 200)))

    @staticmethod
    def _crear_tabla(padre, titulo, columnas, altura):
        if titulo:
            marco = ttk.LabelFrame(padre, text=titulo)
            marco.pack(fill="both", expand=True, padx=6, pady=(4, 0))
        else:
            marco = padre
        tabla = ttk.Treeview(marco, columns=[c[0] for c in columnas],
                             show="headings", height=altura, selectmode="none")
        for clave, encabezado, ancho in columnas:
            tabla.heading(clave, text=encabezado)
            tabla.column(clave, width=ancho, anchor="center")
        barra = ttk.Scrollbar(marco, orient="vertical", command=tabla.yview)
        tabla.configure(yscrollcommand=barra.set)
        tabla.pack(side="left", fill="both", expand=True)
        barra.pack(side="right", fill="y")
        return tabla

    # ------------------------------------------------------------------
    def limpiar(self):
        for tabla in (self._tabla_ramas, self._tabla_nodos, self._tabla_lazos):
            tabla.delete(*tabla.get_children())
        self._resumen.set("Presiona «Calcular» para ver los resultados.")

    def mostrar(self, resultado):
        """Llena las tablas con un ``ResultadoKirchhoff``."""
        self.limpiar()
        for res in resultado.ramas:
            a, b = nombre_nodo(res.rama.nodo_a), nombre_nodo(res.rama.nodo_b)
            sentido = (f"{a} → {b}" if res.en_sentido_dibujado
                       else f"{b} → {a} (contrario al dibujado)")
            self._tabla_ramas.insert("", "end", values=(
                f"R{res.indice}", f"{a} → {b}", f"{res.rama.resistencia:g}",
                f"{res.rama.voltaje:g}", f"{res.corriente:.4f}",
                f"{res.voltaje_resistencia:.4f}", sentido))

        for balance in resultado.nodos:
            estado = "✔ Se cumple" if balance.cumple else "✘ No se cumple"
            self._tabla_nodos.insert("", "end", values=(
                nombre_nodo(balance.nodo), f"{balance.corriente_entra:.4f}",
                f"{balance.corriente_sale:.4f}", _formato_diferencia(balance.neto),
                f"{balance.potencial:.4f}", estado))

        for lazo in resultado.lazos:
            ramas = " ".join(f"{'+' if signo > 0 else '−'}R{indice}"
                             for indice, signo in lazo.terminos)
            estado = "✔ Se cumple" if lazo.cumple else "✘ No se cumple"
            self._tabla_lazos.insert("", "end", values=(
                f"Lazo {lazo.numero}", ramas, f"{lazo.suma_fuentes:.4f}",
                f"{lazo.suma_caidas:.4f}", _formato_diferencia(lazo.suma), estado))

        kcl = "✔ KCL se cumple" if resultado.kcl_se_cumple else "✘ KCL NO se cumple"
        kvl = "✔ KVL se cumple" if resultado.kvl_se_cumple else "✘ KVL NO se cumple"
        potencia = "✔ coinciden" if resultado.potencia_balanceada else "✘ no coinciden"
        self._resumen.set(
            f"{kcl} en los {len(resultado.nodos)} nodos · {kvl} en los "
            f"{len(resultado.lazos)} lazos independientes.\n"
            f"Balance de potencia: las fuentes entregan {resultado.potencia_entregada:.4f} W "
            f"y las resistencias disipan {resultado.potencia_disipada:.4f} W ({potencia}).\n"
            f"Sistema resuelto: {resultado.num_ecuaciones_kcl} ecuaciones de KCL + "
            f"{resultado.num_lazos} de KVL. Potenciales respecto al nodo "
            f"{nombre_nodo(resultado.nodo_referencia)} (0 V). En la tabla de lazos, +/− indica "
            "si la rama se recorre a favor o en contra del sentido dibujado. Una corriente "
            "negativa va en sentido contrario al dibujado.")
