# ad_map_gui.py
import tkinter as tk
import threading
import time
from AD_MAP import AD_MAP  # Importar la clase AD_MAP desde el otro archivo

class AD_MAP_GUI(AD_MAP):
    def __init__(self, ancho=20, alto=20):
        super().__init__(ancho, alto)
        self.root = tk.Tk()
        self.canvas = tk.Canvas(self.root, width=20 * 20, height=20 * 20, bg="white")
        self.canvas.pack()

        # Calcular las dimensiones de cada celda
        self.celda_width = self.canvas.winfo_reqwidth() // ancho
        self.celda_height = self.canvas.winfo_reqheight() // alto

        # Crear drones

        self.draw_map()

    def draw_map(self):
        self.canvas.delete("all")  # Limpiar el canvas antes de redibujar
        for i in range(self.alto):
            for j in range(self.ancho):
                x1 = j * self.celda_width
                y1 = i * self.celda_height
                x2 = (j + 1) * self.celda_width
                y2 = (i + 1) * self.celda_height

                # Dibujar el borde de la celda
                self.canvas.create_rectangle(x1, y1, x2, y2, outline="black")

                # Dibujar los drones en la celda
                for drone_info in self.map[i][j]:
                    estado = drone_info[0]
                    color = "green" if estado == "F" else "red"
                    self.canvas.create_rectangle(x1 + 1, y1 + 1, x2 - 1, y2 - 1, fill=color)

                    # Mostrar la ID del dron en blanco si es "F" y en negro si es "R"
                    id_dron = drone_info[1:]
                    id_color = "black" if estado == "R" else "white"
                    self.canvas.create_text((x1 + x2) // 2, (y1 + y2) // 2, text=str(id_dron), fill=id_color)

    def pushDrone(self, drone, estado, row, column):
        return super().pushDrone(drone, estado, row, column)

    def dropDrone(self, drone, row, column):
        return super().dropDrone(drone, row, column)
    
    def run(self):
        self.root.mainloop()

