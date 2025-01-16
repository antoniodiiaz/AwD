from datetime import datetime
import csv


def obtenerFecha():
    fecha_hora = datetime.now()
    fecha = fecha_hora.strftime("%Y-%m-%d")
    hora = fecha_hora.strftime("%H:%M:%S")
    return fecha, hora

class AD_EVENT:
    def __init__(self,fecha,hora,ipEvento,accion,descripcion):
        self.fecha = fecha
        self.hora = hora
        self.ipEvento = ipEvento
        self.accion = accion
        self.descripcion = descripcion

    def toDict(self):
        return {
            "Fecha": self.fecha,
            "Hora" : self.hora,
            "Ip del Evento" : self.ipEvento,
            "Accion": self.accion,
            "Descripcion": self.descripcion
        }
