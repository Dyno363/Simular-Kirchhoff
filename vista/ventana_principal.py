"""Vista: ventana principal con el formulario, la lista de ramas y los paneles.

La vista no importa el modelo ni calcula nada: solo muestra datos y avisa al
controlador cuando el usuario pulsa un botón (mediante funciones que el
controlador registra en ``conectar``).
"""

import tkinter as tk
from tkinter import messagebox, ttk

from vista.panel_circuito import PanelCircuito, nombre_nodo
from vista.panel_resultados import PanelResultados


class VentanaPrincipal:

    def __init__(self, raiz):
        self._raiz = raiz
        self._acciones = {}
        raiz.title("Simulador de circuitos – Leyes de Kirchhoff (Física II)")
        raiz.geometry("1180x840")
        raiz.minsize(960, 680)

        self._var_num_nodos = tk.StringVar(value="2")
        self._var_a = tk.StringVar(value="A")
        self._var_b = tk.StringVar(value="B")
        self._var_r = tk.StringVar()
        self._var_v = tk.StringVar(value="0")
        self._var_mensaje = tk.StringVar(value="Listo.")

        self._construir()

    # ------------------------------------------------------------------
    # Conexión con el controlador
    # ------------------------------------------------------------------
    def conectar(self, **acciones):
        """Registra las funciones del controlador (agregar, eliminar, ...)."""
        self._acciones = acciones

    def _llamar(self, nombre, *argumentos):
        accion = self._acciones.get(nombre)
        if accion is not None:
            accion(*argumentos)

    def configurar_limites_nodos(self, minimo, maximo):
        self._spin_nodos.configure(from_=minimo, to=maximo)

    # ------------------------------------------------------------------
    # Construcción de la interfaz
    # ------------------------------------------------------------------
    def _construir(self):
        principal = ttk.Frame(self._raiz, padding=8)
        principal.pack(fill="both", expand=True)
        principal.columnconfigure(1, weight=1)
        principal.rowconfigure(0, weight=1)

        izquierda = ttk.Frame(principal)
        izquierda.grid(row=0, column=0, sticky="ns", padx=(0, 8))
        self._construir_formulario(izquierda)
        self._construir_lista_ramas(izquierda)
        self._construir_botones(izquierda)

        derecha = ttk.PanedWindow(principal, orient="vertical")
        derecha.grid(row=0, column=1, sticky="nsew")
        self._panel_circuito = PanelCircuito(derecha)
        self._panel_resultados = PanelResultados(derecha)
        derecha.add(self._panel_circuito, weight=3)
        derecha.add(self._panel_resultados, weight=2)

        ttk.Label(principal, textvariable=self._var_mensaje, relief="sunken",
                  anchor="w", padding=(6, 2)).grid(row=1, column=0, columnspan=2,
                                                   sticky="ew", pady=(8, 0))
        self._panel_resultados.limpiar()

    def _construir_formulario(self, padre):
        marco = ttk.LabelFrame(padre, text="Nueva rama", padding=8)
        marco.pack(fill="x")

        ttk.Label(marco, text="Número de nodos:").grid(row=0, column=0, sticky="w", pady=2)
        self._spin_nodos = ttk.Spinbox(
            marco, from_=2, to=12, width=6, textvariable=self._var_num_nodos,
            command=self._al_cambiar_nodos)
        self._spin_nodos.grid(row=0, column=1, sticky="w", pady=2)
        self._spin_nodos.bind("<Return>", lambda _e: self._al_cambiar_nodos())
        self._spin_nodos.bind("<FocusOut>", lambda _e: self._al_cambiar_nodos())

        ttk.Label(marco, text="Nodo inicial:").grid(row=1, column=0, sticky="w", pady=2)
        self._combo_a = ttk.Combobox(marco, width=6, textvariable=self._var_a)
        self._combo_a.grid(row=1, column=1, sticky="w", pady=2)

        ttk.Label(marco, text="Nodo final:").grid(row=2, column=0, sticky="w", pady=2)
        self._combo_b = ttk.Combobox(marco, width=6, textvariable=self._var_b)
        self._combo_b.grid(row=2, column=1, sticky="w", pady=2)

        ttk.Label(marco, text="Resistencia (Ω):").grid(row=3, column=0, sticky="w", pady=2)
        entrada_r = ttk.Entry(marco, width=10, textvariable=self._var_r)
        entrada_r.grid(row=3, column=1, sticky="w", pady=2)

        ttk.Label(marco, text="Fuente (V):").grid(row=4, column=0, sticky="w", pady=2)
        entrada_v = ttk.Entry(marco, width=10, textvariable=self._var_v)
        entrada_v.grid(row=4, column=1, sticky="w", pady=2)

        ttk.Label(marco, text="La corriente es positiva de nodo inicial a final.\n"
                              "Una fuente positiva sube el potencial hacia el nodo final.\n"
                              "Fuente 0 = rama sin fuente.",
                  foreground="#555555", justify="left", wraplength=250
                  ).grid(row=5, column=0, columnspan=2, sticky="w", pady=(6, 4))

        ttk.Button(marco, text="Agregar rama", command=self._al_agregar
                   ).grid(row=6, column=0, columnspan=2, sticky="ew")
        for entrada in (entrada_r, entrada_v):
            entrada.bind("<Return>", lambda _e: self._al_agregar())

    def _construir_lista_ramas(self, padre):
        marco = ttk.LabelFrame(padre, text="Ramas del circuito", padding=6)
        marco.pack(fill="both", expand=True, pady=8)
        columnas = ("rama", "a", "b", "r", "v")
        self._lista = ttk.Treeview(marco, columns=columnas, show="headings",
                                   height=10, selectmode="browse")
        for clave, titulo, ancho in (("rama", "Rama", 45), ("a", "Inicial", 52),
                                     ("b", "Final", 48), ("r", "R (Ω)", 60),
                                     ("v", "Fuente (V)", 70)):
            self._lista.heading(clave, text=titulo)
            self._lista.column(clave, width=ancho, anchor="center")
        self._lista.pack(fill="both", expand=True)
        self._lista.bind("<Delete>", lambda _e: self._al_eliminar())
        ttk.Button(marco, text="Eliminar rama seleccionada",
                   command=self._al_eliminar).pack(fill="x", pady=(6, 0))

    def _construir_botones(self, padre):
        marco = ttk.Frame(padre)
        marco.pack(fill="x")
        ttk.Button(marco, text="Calcular", command=lambda: self._llamar("calcular")
                   ).pack(fill="x", pady=2)
        ttk.Button(marco, text="Cargar ejemplo", command=lambda: self._llamar("ejemplo")
                   ).pack(fill="x", pady=2)
        ttk.Button(marco, text="Limpiar todo", command=lambda: self._llamar("limpiar")
                   ).pack(fill="x", pady=2)

    # ------------------------------------------------------------------
    # Eventos de la interfaz -> controlador
    # ------------------------------------------------------------------
    def _al_agregar(self):
        self._llamar("agregar", self._var_a.get(), self._var_b.get(),
                     self._var_r.get(), self._var_v.get())

    def _al_eliminar(self):
        seleccion = self._lista.selection()
        self._llamar("eliminar", int(seleccion[0]) if seleccion else None)

    def _al_cambiar_nodos(self):
        self._llamar("cambiar_nodos", self._var_num_nodos.get())

    # ------------------------------------------------------------------
    # Órdenes del controlador -> vista
    # ------------------------------------------------------------------
    def actualizar_circuito(self, nodos, ramas, disposicion=None):
        """Refresca la lista de ramas, los selectores de nodo y el dibujo.

        ``disposicion`` (opcional) fija dónde se dibuja cada nodo; con un
        diccionario vacío el esquema vuelve a la disposición automática.
        """
        self._var_num_nodos.set(str(len(nodos)))
        valores = [nombre_nodo(n) for n in nodos]
        self._combo_a.configure(values=valores)
        self._combo_b.configure(values=valores)

        self._lista.delete(*self._lista.get_children())
        for indice, rama in enumerate(ramas):
            self._lista.insert("", "end", iid=str(indice), values=(
                f"R{indice + 1}", nombre_nodo(rama.nodo_a), nombre_nodo(rama.nodo_b),
                f"{rama.resistencia:g}", f"{rama.voltaje:g}"))
        self._panel_circuito.dibujar(nodos, ramas, disposicion=disposicion)
        self._panel_resultados.limpiar()

    def mostrar_resultados(self, nodos, ramas, resultado):
        self._panel_circuito.dibujar(nodos, ramas, resultado.ramas)
        self._panel_resultados.mostrar(resultado)

    def mostrar_mensaje(self, texto):
        self._var_mensaje.set(texto)

    def mostrar_error(self, texto):
        self._var_mensaje.set("⚠ " + texto)
        messagebox.showwarning("Dato no válido", texto, parent=self._raiz)
