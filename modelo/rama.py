"""Modelo: una rama del circuito (resistencia en serie con una fuente opcional)."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Rama:
    """Rama dirigida que une dos nodos.

    Convenciones (todo el programa las respeta):
      * La corriente I de la rama es positiva si va de ``nodo_a`` hacia ``nodo_b``.
      * ``voltaje`` es la fuerza electromotriz de la rama: si es positiva, el
        potencial *sube* al recorrer la rama de ``nodo_a`` a ``nodo_b``.
      * Relación de la rama:  V_b - V_a = voltaje - resistencia * I
    """

    nodo_a: int          # nodo inicial
    nodo_b: int          # nodo final
    resistencia: float   # en ohmios (Ω), siempre > 0
    voltaje: float = 0.0  # fuente en voltios (V); 0 si la rama no tiene fuente
