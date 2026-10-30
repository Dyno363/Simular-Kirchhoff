"""Punto de entrada: crea el modelo, la vista y el controlador y arranca la app."""

import tkinter as tk

from controlador.controlador_circuito import ControladorCircuito
from modelo.circuito import Circuito
from modelo.solver_kirchhoff import SolverKirchhoff
from vista.ventana_principal import VentanaPrincipal


def main():
    raiz = tk.Tk()
    vista = VentanaPrincipal(raiz)
    # El controlador une las tres piezas; el modelo y la vista no se conocen.
    ControladorCircuito(Circuito(), SolverKirchhoff(), vista)
    raiz.mainloop()


if __name__ == "__main__":
    main()
