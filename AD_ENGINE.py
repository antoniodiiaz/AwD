import socket
from pymongo import *
import json
import logging
import threading
from AD_MAP import *
import time
from kafka import KafkaConsumer, KafkaProducer
import sys
import tkinter as tk
from tkinter import ttk
from colorama import init, Fore
from concurrent.futures import ThreadPoolExecutor
from AD_MAP_GUI import *
import requests
from AD_EVENT import *
import datetime
from AES import *
import csv
from flask import Flask, request, jsonify

FORMAT = 'utf-8'
HEADER = 64
ENQ = "<ENQ>"
ACK = "1"
NACK = "-1"
STX = "<STX>"
ETX = "<ETX>"
EOT = "<EOT>"

AUTENTICACION = "Autenticación correcta"
INTENTO_FALLIDO = "Intentos de autenticación fallidos"
CAMBIO_CLIMA = "Cambio de clima"
ERRORES = "Errores"
INCIDENCIAS = "Incidencias durante el espectáculo"
DATOS_DATABASE = "mongodb://localhost:27017"
HOST = socket.gethostbyname(socket.gethostname())

running = False
# MOVIMIENTOS#MAPA#DESTINOS#bootstrap_servers
# topic1#topic2#topic3#bootstrap_servers -> [topic1,topic2,topic3,bootstrap_servers]
def separaDatos(datos) -> list[str]:
    res = []
    cuantos = 0
    for i,d in enumerate(datos):
        if d == "#":
            if cuantos == 0:
                res.append(datos[:i])
                j = i
            
            elif cuantos > 0 or cuantos < 3:
                res.append(datos[j + 1 : i])
                j = i
            cuantos += 1
            if cuantos == 3:
                res.append(datos[i+1:])
                break
    return res


def calculaLrc(cadena):
    suma = 0
    for caracter in cadena:
        suma += ord(caracter)
    lrc = (suma & 0xFF) ^ 0xFF
    return lrc + 1

def comprobarLrc(cadena,lrc):
    return lrc == calculaLrc(cadena)

def compruebaMensaje(mensaje : str) -> bool:
    stx = "<STX>"
    etx = "<ETX>"
    indSTX = mensaje.find(stx)
    if indSTX == -1:
        return False
    indETX = mensaje.find(etx)
    if indETX == -1:
        return False
    if len(mensaje) == (indETX + (len(etx))):
        return False
    lrc = mensaje[indETX + (len(etx)):]
    datos = mensaje[indSTX+len(stx):indETX]
    if comprobarLrc(datos,int(lrc)):
        if len(datos) == 0:
            return False
        return True
    else:
        return False
    
#IP:PUERTO#
def separa(datos):
    return (datos[:datos.find(":")],int(datos[datos.find("::")+2:len(datos)]))



def existeClave(id):
    try:
        archivo = "claves\clavesEngine.txt"
        with open(archivo, 'r') as file:
            lineas = file.readlines()

        for linea in lineas:
            if linea[:linea.find(":")] == id and linea.find(":") != -1:
                return True
        return False
    
    except FileNotFoundError:
        print(f"El archivo {archivo} no fue encontrado.")
    except Exception as e:
        print(f"Ocurrió un error: {e}")
def guardar_claves_en_archivo(claveAES,id=None):
    
    with open("claves\clavesEngine.txt", "a") as file:
        if id:
            guardar = str(id) + ":" + claveAES
            if existeClave(str(id)):
                buscarCoincidencias(guardar)
            else:
                file.write(guardar + "\n")
        else:            
            file.write(claveAES.getClave().hex() + "\n")


api_key = "d0c92f36da1722f367bdf7e5d0fe7e40"


def kelvinAcelsius(kelvin):
    temp = kelvin - 273.15
    return temp

def read_file(file_path):
    with open(file_path, 'r') as file:
        return file.read().strip()
    
class WeatherAPI:
    def __init__(self, api_key):
        self.api_key = api_key
        self.base_url = "https://api.openweathermap.org/data/2.5/weather"

    def get_weather(self, city):
        url = f"{self.base_url}?q={city}&appid={self.api_key}"
        response = requests.get(url)

        if response.status_code == 200:
            data = response.json()
            return data
        else:
            print(f"Error {response.status_code}: Unable to fetch weather data.")
            return None

def obtenerFecha():
    fecha_hora = datetime.datetime.now()
    fecha = fecha_hora.strftime("%Y-%m-%d")
    hora = fecha_hora.strftime("%H:%M:%S")
    return fecha,hora



claveEngine = AES()
claveMapa = AES()


def escribir(evento : AD_EVENT):
    with open('auditoria_engine.csv', 'a', newline='') as csvfile:
        spamwriter = csv.writer(csvfile, delimiter='\t')
        spamwriter.writerow([evento.fecha, evento.hora, evento.ipEvento, evento.accion, evento.descripcion])

def vaciar_csv(archivo_csv):
    # Abre el archivo CSV en modo escritura ('w') para vaciar su contenido
    with open(archivo_csv, 'w', newline='') as csvfile:
        # Crea un objeto escritor de CSV
        csv_writer = csv.writer(csvfile)

        # Escribe una fila vacía para vaciar el contenido
        csv_writer.writerow([])

def buscarCoincidencias(cadena_a_buscar):
    try:
        archivo = "claves\clavesEngine.txt"
        with open(archivo, 'r') as file:
            lineas = file.readlines()

        id = cadena_a_buscar[:cadena_a_buscar.find(":")]
        
        nuevas_lineas = [linea for linea in lineas if id != linea[:linea.find(":")] or linea.find(":") == -1]
        
        # Agregar la cadena de búsqueda al final del archivo
        nuevas_lineas.append(cadena_a_buscar + '\n')

        # Escribir las líneas actualizadas en el archivo
        with open(archivo, 'w') as file:
            file.writelines(nuevas_lineas)
    except FileNotFoundError:
        print(f"El archivo {archivo} no fue encontrado.")
    except Exception as e:
        print(f"Ocurrió un error: {e}")

class AD_ENGINE:
    def __init__(self,puerto_escucha,max_drones,datos_kafka,datos_drones):
        self.puerto_escucha = puerto_escucha
        self.max_drones = max_drones
        self.datos_kafka = separaDatos(datos_kafka)
        self.datos_drones = datos_drones
        self.positionsDrones = [[0, 0] for _ in range(max_drones)]
        self.estadosDron = [None for _ in range(max_drones)]
        self.destinosDrones = [str(i) + "." + "0,0" for i in range(1,max_drones+1)]
        self.numDrons = []
        self.terminado = False
        self.producerMap = self.configure_kafka_producer()
        self.consumer = self.configure_kafka_consumer_movs()
        self.producerDestinos = self.configure_kafka_producer()
        self.figuras = []
        self.temp = ""
        self.mapa = AD_MAP()
        self.mostrar = True
        self.stop = False
        self.stop_event_flag = threading.Event()
        self.running_thread = None
        self.mapaInterface = AD_MAP_GUI()
        self.connectedDrones = [True for _ in range(self.max_drones)] 
        self.datosDrone = [None for _ in range(self.max_drones)]
        self.figura = 1
        self.jsonHecho = False
        self.jsonIntroducido = False
        self.start = False
        self.city = None
        self.semaforo = threading.Semaphore()
        self.miClavePublica = None
        self.claveMapa = None
        
        self.clavePublicaDrones = [None for _ in range(self.max_drones)]
        self.lista = []
        self.movimientosDrones = [0 for _ in range(self.max_drones)]
        self.noHayDrones = False
        self.registrar = False
        limpiaAuditoria()
        with open('auditoria_engine.csv', 'a', newline='') as csvfile:
            spamwriter = csv.writer(csvfile, delimiter='\t')
            spamwriter.writerow(["Fecha", "Hora", "Ip del evento", "Accion", "Descripcion"])
    
    # 1. Hilo principal que pedirá START o STOP
    # Si se introduce START -> se creará el segundo hilo 
    def run(self):
        self.resetearMapa()
        hiloStart = threading.Thread(target=self.empieza)
        hiloFichero = threading.Thread(target=self.leerFicheroJSON)
        hiloMandarPos = threading.Thread(target=self.producePos)
        hiloRecibeMov = threading.Thread(target=self.recibeMovimientos)
        hiloConsultaClima = threading.Thread(target=self.consulta_weather)
        hiloFicheroClaves = threading.Thread(target=self.leeClaves)
        hiloStart.start()
        hiloFicheroClaves.start()
        hiloFichero.start()
        hiloMandarPos.start()
        hiloRecibeMov.start()
        hiloConsultaClima.start()
        

    
    def empieza(self):
        while not self.stop:
            opcion = input("Introduce una instrucción: ")
            if opcion.upper() == "START":
                if not self.start:
                    fecha, hora = obtenerFecha()
                    evento = AD_EVENT(fecha,hora,HOST,"Inicio","Comienza el espectaculo")
                    self.semaforo.acquire()
                    escribir(evento)
                    registraEventos(evento)
                    self.semaforo.release()                
                    self.start = True                
            elif opcion.upper() == "STOP":
                if self.start:
                    self.start = False 
                self.stop = True  
                fecha, hora = obtenerFecha()
                evento = AD_EVENT(fecha,hora,HOST,"STOP","Se ha parado el Engine")                
                self.semaforo.acquire()
                escribir(evento)
                registraEventos(evento)
                self.semaforo.release()            
                
                time.sleep(20)
                break
            time.sleep(20)
        print("Se ha terminado el programa")
        
    
    
    # Función que comprueba el token de la base de datos
    def compruebaTokenDatabase(self,token):
        MONGO_URI = "mongodb://localhost:27017"
        cliente =  MongoClient(MONGO_URI)
        database = cliente["dbREGISTRY"]
        collection = database["REGISTRY"]
        consulta = {"Token" : token}
        datosDron = -1
        try:
            query = collection.find(consulta)
            for x in query:
                datosDron = x["ID"]
                break
        except Exception as e:
            datosDron = -1
        return str(datosDron)
    

    # Hilo 2.2 que esperará ficheros JSON y cuando se introduzca uno se realizarán sus figuras.
    def leerFicheroJSON(self):
        while True:
            if self.start:
                procesoJSON = True
                try:
                    self.fichero = input("Introduce el fichero JSON: ")                                
                    self.fichero += ".json"
                    with open(self.fichero) as figuras:
                        datos = json.load(figuras)
                        if len(datos) > 0:
                            for figura in datos['figuras']:
                                for drones in figura['Drones']:
                                    posiciones = str(drones['ID']) + "." + drones['POS']                            
                                    self.destinosDrones[drones['ID'] - 1] = posiciones                            
                                copia = self.destinosDrones.copy()
                                numDrones = len(figura['Drones'])
                                
                                self.figuras.append(copia[:numDrones])
                                self.numDrons.append(numDrones)
                                self.destinosDrones = [str(i) + "." + "0,0" for i in range(1,self.max_drones + 1)]

                            for i in range(len(self.figuras)):
                                if i - 1 >= 0 and i < len(self.figuras):
                                    if len(self.figuras[i-1]) > len(self.figuras[i]):
                                        diferencia = len(self.figuras[i-1]) - len(self.figuras[i])
                                        for j in range(diferencia):                                            
                                            posicion = str(len(self.figuras[i]) + 1) + "." + "0,0"
                                            self.figuras[i].append(posicion)
                    self.jsonIntroducido = True
                    
                    fecha, hora = obtenerFecha()
                    evento = AD_EVENT(fecha,hora,HOST,"Lectura JSON",f"Fichero {self.fichero} JSON leido")
                    self.semaforo.acquire()
                    escribir(evento)
                    registraEventos(evento)
                    self.semaforo.release()

                except Exception as e:
                    print("No existe el archivo " + self.fichero + " en el directorio")
                    self.termina = True
                    fecha, hora = obtenerFecha()
                    evento = AD_EVENT(fecha,hora,HOST,"Error",f"No se ha leido el fichero JSON: {self.fichero}")
                    self.semaforo.acquire()
                    escribir(evento)
                    registraEventos(evento)
                    self.semaforo.release()
                    break
                while True:
                    if self.jsonHecho:
                        self.jsonIntroducido = False
                        if not self.terminado:
                            print("Se han realizado todas las figuras")
                        self.jsonHecho = False
                        break
                    if self.stop:
                        break
                    time.sleep(10)
            if self.stop:
                print("Función leerFicheroJSON terminada")
                break


    # Hilo 2.3 que cuando el fichero JSON haya leído las figuras irá publicando los destinos por KAFKA
    def producePos(self):
        while True:
            if self.start:                
                if self.jsonIntroducido:
                    if not self.terminado:
                        self.registrar = True
                        self.finalizado = False
                        self.figuraAcabada = False
                        while not self.stop:
                            if not self.terminado and not self.stop and not self.finalizado:
                                while True:
                                    if self.figura > len(self.figuras):                                    
                                        break

                                    elif self.registrar:
                                        self.enviarKafka(posFigura=True,registrar=True)                                     
                                        self.registrar = False

                                    elif self.terminado:
                                        break
                                    elif self.noHayDrones:
                                        break
                                    else:
                                        while True:                                                    
                                            self.enviarKafka(posFigura=True)
                                            
                                            if self.figuraAcabada:
                                                self.figuraAcabada = False
                                                self.registrar = False
                                                break

                                            if self.stop:
                                                break
                                            if self.finalizado:
                                                break
                                            
                                            time.sleep(2)
                                        if self.terminado or self.finalizado or self.stop:
                                            break

                            if self.stop:
                                break
                        
                            if self.finalizado or self.terminado or self.noHayDrones:
                                print("Ahora los drones vuelven a base")
                                self.enviarKafka(volverBase=True)
                                break
                            
                            else:                            
                                break
            if self.stop:
                print("Función producePos terminada")
                break

    def comprobarDronesCaidos(self):
        try:
            n = len(self.figuras[self.figura-1])
            dronesFigura = self.connectedDrones[:n]

            drones = list(filter(lambda x: x == True,dronesFigura))
        
            if len(drones) < n:
                print("Hay drones caídos, esperando 60 segundos para su reintegro a la figura")
                time.sleep(60)
                return self.figuraRealizada()
            else:
                return False
        except:
            return False
        
    # Función que envía las posiciones a KAFKA
    def enviarKafka(self,volverBase=False,posFigura=False,registrar=False):
        if volverBase:
            n = len(self.figuras[self.figura-2])
            print(n)
            volverABase = []
            for dron in range(n):
                pos = str(dron + 1) + ".0,0" 
                volverABase.append(pos)
            while True:
                for dron, dest in enumerate(volverABase):     
                    if self.clavePublicaDrones[dron]:
                        mensajeEncriptado = self.clavePublicaDrones[dron].encriptar(dest)
                        self.producerDestinos.send(self.datos_kafka[2],value=mensajeEncriptado.encode(FORMAT))   
                        self.producerDestinos.flush()
                
                if self.mapa.mapaVacio():
                    print("Han vuelto todos los drones a base")
                    print(self.mapa)
                    self.meterBaseDatos()
                    break
                time.sleep(4)
                        
                    
        if posFigura:
            try:
                n = len(self.figuras[self.figura-1])
                if registrar:
                    for dron,dest in enumerate(self.figuras[self.figura-1]):
                        self.registraDron(dron,dest,self.figura-1)  
                else:
                    for dron,dest in reversed(list(enumerate(self.figuras[self.figura-1]))):
                        if dest != None: 
                            if self.clavePublicaDrones[dron]:
                                mensajeEncriptado = self.clavePublicaDrones[dron].encriptar(dest)                   
                                self.producerDestinos.send(self.datos_kafka[2],value=mensajeEncriptado.encode(FORMAT))
                                self.producerDestinos.flush()    

                    time.sleep(8)
            except Exception as e:
                print("No hay más figuras")

    # Funcion que realiza la conexión a base de datos y registra sus posiciones en ella para el dron.
    def registraDron(self,id,pos,figura):
        MONGO_URI = self.datos_drones
        cliente = MongoClient(MONGO_URI)
        database = cliente["dbREGISTRY"]
        collection = database['REGISTRY']
        filter = {"ID" : id+1}
        newValues = {"$set" : {"POS" : pos} }
        collection.update_one(filter,newValues)
        if figura == 0:
            self.mapa.pushDrone(id+1,"R",0,0)
            self.meterBaseDatos()
    

    # Hilo 2.4. que se encarga de recibir los movimientos de kafka
    def recibeMovimientos(self):   
        while True:
            if self.start:                
                muestra = False
                while not self.stop:
                    for mensaje in self.consumer.poll(1).values():  
                        
                        if mensaje is None:
                            break
                        for movimiento in mensaje:
                            if muestra:
                                self.iniciaFiguras()        
                                self.enviaMapa()
                                muestra = False
                            movsCifrado = movimiento.value.decode(FORMAT)   
                            try:
                                movs = self.miClavePublica.desencriptar(movsCifrado)
                                self.colocaDron(movs)      
                            except:
                                fecha,hora = obtenerFecha()
                                evento = AD_EVENT(fecha,hora,HOST,"Mensajes Indescifrables", "No es posible conectarse con los drones")
                                self.semaforo.acquire()
                                escribir(evento)
                                registraEventos(evento)
                                self.semaforo.release()
                                print("Imposible conectarse con los drones. Mensajes indescifrables.")
                                self.stop = True
                            
                            if self.stop:
                                break
            if self.stop:
                print("Función recibeMovimientos terminada")
                break
        

    # Función que colocará el dron en el mapa o realizará el movimiento
    def colocaDron(self,movs):
        
        id = int(movs[1:movs.find(".")])
        estadoDron = movs[0]
        
        self.estadosDron[id-1] = estadoDron
        self.connectedDrones[id-1] = True
        movimientos = movs[movs.find(".")+1:]
        coordX = movimientos[:movimientos.find(",")]
        coordY = movimientos[movimientos.find(",")+1:]
        movimientos = (int(coordX), int(coordY))
                        
        self.mapa.dropDrone(id, self.positionsDrones[id-1][1], self.positionsDrones[id-1][0])
        self.mapaInterface.dropDrone(id,self.positionsDrones[id-1][1],self.positionsDrones[id-1][0])

        
        if movimientos[0] > 0 or movimientos[1] > 0:            
            self.mapa.pushDrone(id, estadoDron, movimientos[1], movimientos[0])
            self.mapaInterface.pushDrone(id,estadoDron,movimientos[1],movimientos[0])
        
        self.positionsDrones[id-1][0] = movimientos[0]
        self.positionsDrones[id-1][1] = movimientos[1]
        
        
        if not self.mapa.mapaVacio():
            if self.mostrarMapa(id):
                self.comprobarActivos()   
                self.lista = []
                self.lista.append(id)                
                self.meterBaseDatos()
                self.enviaMapa()
                if self.figuraRealizada():
                    if self.comprobarDronesCaidos():
                        self.noHayDrones = True
                    else:
                        print("Se ha realizado la figura ",self.figura)
                        print(f"Tiempo en {self.city}: {self.temperatura:.2f}º")    
                        print(self.mapa)
                        self.figura += 1
                        if self.figura > len(self.figuras):
                            self.finalizado = True
                            self.jsonIntroducido = False
                            self.jsonHecho = True
                            
                            print("No hay más figuras")     
                            fecha, hora = obtenerFecha()
                            evento = AD_EVENT(fecha,hora,HOST,"Figuras terminadas", f"Se han terminado todas las figuras del fichero: {self.fichero}")
                            self.semaforo.acquire()
                            escribir(evento)
                            registraEventos(evento)
                            self.semaforo.release()                                    
                            time.sleep(10)             
                        else:
                            self.registrar = True
                            
                            self.figuraAcabada = True
                            fecha, hora = obtenerFecha()
                            evento = AD_EVENT(fecha,hora,HOST,"Figura terminada", f"Se ha terminado la figura {self.figura-1}")
                            self.semaforo.acquire()
                            escribir(evento)
                            registraEventos(evento)
                            n = len(self.figuras[self.figura-2])
                            for i in range(n):
                                self.estadosDron[i] = None
                            
                            self.semaforo.release()
                            time.sleep(5)
                else:
                    print(f"Tiempo en {self.city}: {self.temperatura:.2f}º")
                    print(self.mapa)

    def comprobarEstadosDrones(self):

        dronesActivos = list(filter(lambda x : x == "F",self.estadosDron))
        
        if self.figura > len(self.figuras):
            return len(dronesActivos) == len(self.figuras[self.figura-2])
        else:
            return len(dronesActivos) == len(self.figuras[self.figura-1])
    
    
    def comprobarActivos(self):
        if len(self.figuras) > self.figura:
            try:
                n = len(self.figuras[self.figura-1])
                for dron in range(self.max_drones):
                    idDron = dron + 1
                    if idDron <= n:
                        if idDron in self.lista:   
                            self.movimientosDrones[dron] = 0
                        else:
                            if self.estadosDron[dron] == "R":
                                self.movimientosDrones[dron] += 1
                                if self.movimientosDrones[dron] == 3:
                                    print(f"El dron {idDron} no está operativo")
                                    fecha,hora = obtenerFecha()
                                    self.semaforo.acquire()
                                    evento = AD_EVENT(fecha,hora,HOST,"Desconexión", f"El dron {idDron} se ha desconectado del espectáculo.")
                                    registraEventos(evento)
                                    self.semaforo.release()
                                    self.connectedDrones[dron] = False
                                    try:
                                        self.mapa.dropDrone(idDron, self.positionsDrones[idDron-1][1], self.positionsDrones[idDron-1][0])
                                    except:
                                        pass
            except:
                print("No hay más figuras (comprobarActivos)")

                    


    def meterBaseDatos(self):
        collection = obtenerBaseDatos()
        for dron,estado in enumerate(self.estadosDron):
            filtro = {"ID" : dron+ 1}
            actualizacion = {"$set" : {"Mapa" : self.mapa.mapToString(),"Estado" : self.estadosDron[dron]}}
            collection.update_one(filtro,actualizacion)
            
            
        
            
    
    def mostrarMapa(self,id):
        if id in self.lista:
            return True
        else:
            self.lista.append(id)
            return False or self.comprobarEstadosDrones()
    
    #Método que coloca a los drones en la posición 0,0
    def iniciaFiguras(self):
        for f,s in enumerate(self.figuras[0]):
            self.mapaInterface.pushDrone(f,"R",0,0)
            self.mapaInterface.root.after(1,self.mapaInterface.draw_map)
    
    # Método que enviará el mapa cada vez que recibe "x" movimientos
    def enviaMapa(self):
        mapastr = self.mapa.mapToString()
        mensaje = self.temp + mapastr
        mensajeCifrado = self.claveMapa.encriptar(mensaje)
        self.producerMap.send(self.datos_kafka[1],value=mensajeCifrado.encode(FORMAT))
        self.producerMap.flush()
        time.sleep(0.2)
            
            
    # Hilo 2.5. que consultará al AD_WEATHER y pedirá su clima.

    def consulta_weather(self):
        while True:
            if self.start:
                if self.jsonIntroducido:
                    if not self.terminado:
                        while True:
                            self.city = read_file("temperatura\ciudad.txt")
                            api_key = read_file("temperatura\key.txt")
                            try:
                                weather_api = WeatherAPI(api_key)
                                weather_data = weather_api.get_weather(self.city)
                                if weather_data:
                                    temperature_kelvin = weather_data['main']['temp']
                                    self.temperatura = kelvinAcelsius(temperature_kelvin)
                            except:
                                print("No se puede acceder al servidor OPENWEATHER. Se procede a clausurar el espectáculo.")
                                self.temperatura = -1
                            
                            if self.temperatura < 0 or self.temperatura == 100 or self.stop:
                                if self.stop:
                                    self.temp = "S"
                                    mapastr = self.mapa.mapToString()
                                    mensaje = self.temp + mapastr
                                    mensaje = mensaje.encode(FORMAT)
                                    self.producerMap.send(self.datos_kafka[1],value=mensaje)
                                else:
                                    self.terminado = True
                                    self.temp = "W"        
                                    self.jsonIntroducido = False
                                    self.jsonHecho = True
                                    mapastr = self.mapa.mapToString()
                                    mensaje = self.temp + mapastr             
                                    print(mensaje)                   
                                    mensajeEncriptado = self.claveMapa.encriptar(mensaje)
                                    self.producerMap.send(self.datos_kafka[1],value=mensaje.encode(FORMAT))
                                    self.producerMap.flush()
                                    print("CONDICIONES CLIMÁTICAS ADVERSAS. ESPECTÁCULO FINALIZADO.")
                                    fecha, hora = obtenerFecha()
                                    evento = AD_EVENT(fecha,hora,HOST,"CONDICIONES CLIMÁTICAS ADVERSAS", f"Se ha finalizado el espectáculo por temperatura en {self.city} = {self.temperatura}")
                                    self.semaforo.acquire()
                                    escribir(evento)
                                    registraEventos(evento)
                                    self.semaforo.release()
                                    break
                            time.sleep(5)
                    time.sleep(5)
            if self.stop:
                print("Función consultaClima terminada.")
                break

    def leeClaves(self):
        while True:
            try:
                with open("claves\clavesEngine.txt", 'r') as archivo:
                    for fila,linea in enumerate(archivo):
                        if fila <= 1:
                            if fila == 0:
                                
                                self.miClavePublica = AES(llave=bytes.fromhex(linea))


                            else:
                                
                                self.claveMapa = AES(llave=bytes.fromhex(linea))
                        else:

                            partes = linea.strip().split(':')
                            dron = int(partes[0])
                            claveDron = partes[1]
                            
                            self.clavePublicaDrones[dron-1] = AES(llave=bytes.fromhex(claveDron))
                            #print(f"El dron {dron} tiene la siguiente clave: {self.clavePublicaDrones[dron-1].getClave()}")
                    time.sleep(10)
            except FileNotFoundError:
                print(f"El archivo clavesEngine.txt no fue encontrado.")
        
            except Exception as e:
                print(f"Ocurrió un error: {e}")  
            time.sleep(8)     

    def figuraRealizada(self):
        if not self.figuraAcabada and not self.finalizado:
            n = self.numDrons[self.figura-1]
            
            lista0 = list(filter(lambda conectado : conectado == True,self.connectedDrones))
            lista1 = list(filter(lambda estado : estado != None, self.estadosDron[:n]))
            
            if len(lista1) < n:
                return False
            lista01 = lista0[:len(lista1)]
            if len(lista1) == 0:
                return False
            lista2 = list(filter(lambda estado : estado == "F",lista1))
            resultado = len(lista2) == len(lista1) and len(lista01) <= len(lista1)
            
            return resultado
        return False
    

    
    


    def configure_kafka_producer(self):
        try:
            producer = KafkaProducer(bootstrap_servers=self.datos_kafka[3])
            return producer
        except Exception as e:
            print("No se ha podido crear el productor Engine")


    #Crea al engine consumidor
    # El engine es consumidor cuando recibe los movimientos de los drones en el mapa
    def configure_kafka_consumer_movs(self):
        try:
            consumer = KafkaConsumer(self.datos_kafka[0],bootstrap_servers=self.datos_kafka[3])
            return consumer
        except Exception as e:
            print("No se ha podido configurar el engine consumidor de movimientos")
    
    def resetearMapa(self):
        collection = obtenerBaseDatos()
        actualizacion = {
            "$set" : {"Mapa" : self.mapa.mapToString(),
                      "Estado" : "N"},
        }
        collection.update_many({},actualizacion)
    
def registraEventos(evento):
    MONGO_URI = DATOS_DATABASE
    cliente = MongoClient(MONGO_URI)
    database = cliente["dbREGISTRY"]
    collection = database["AUDITORIA"]

    insertar = {
        "Fecha" : evento.fecha,
        "Hora" : evento.hora,
        "IP" : evento.ipEvento,
        "Accion" : evento.accion,
        "Descripcion" : evento.descripcion
    }
    collection.insert_one(insertar)
    
def limpiaAuditoria():
    MONGO_URI = DATOS_DATABASE
    cliente = MongoClient(MONGO_URI)
    database = cliente["dbREGISTRY"]
    collection = database["AUDITORIA"]
    collection.drop()


 
def vaciarFichero():
    with open("claves\clavesEngine.txt", "w"):
        pass

def mostrarMenu():
    print("1. Empezar espectáculo")
    print("2. Autenticar drones")
    option = input("Introduce una opción: ")
    return option

app = Flask(__name__)


log = logging.getLogger('werkzeug')
log.disabled = True


def obtenerBaseDatos():
    cliente = MongoClient(DATOS_DATABASE)
    database = cliente["dbREGISTRY"]
    collection = database["REGISTRY"]
    return collection


@app.route('/obtenerdatos',methods=['GET'])
def obtenerDrones():
    try:
        if request.method == "GET":
            #obtener todos los drones de la base de datos
           
            collection = obtenerBaseDatos()
            registros = list(collection.find({}, {'_id': False}))
            
            for registro in registros:
                registro['Clave Simetrica'] = ""
            response = {
                'data' : registros,
                'error' : False,
                'message' : 'Objetos cogidos satisfactoriamente',
                'clave Engine' : claveEngine.getClave().hex(),
                'clave Mapa' : claveMapa.getClave().hex()
            }
            return jsonify(response), 200
        
    except Exception as e:
        response = {
            'error' : False,
            'message' : f'Ha ocurrido el error: {e}',
            'data' : None
        }
        return jsonify(response),500


@app.route('/autenticacion',methods=['POST'])
def autenticar():
    try:
        datas = request.get_json()
        
        for data in datas:
            
            # Insertar dron en la base de datos
            
            id = data['ID']
            token = data['Token']
            collection = obtenerBaseDatos()
            registro = collection.find({"ID" : id})
            
            iguales = False
            for r in registro:
                if r['Token'] == token:
                    iguales = True
            if iguales:     
                fecha,hora = obtenerFecha()
                evento = AD_EVENT(fecha,hora,request.host,"Autenticacion",f"Autenticacion correcta del Dron {id}")
                registraEventos(evento)
                escribir(evento)      
                response = {
                    'error' : False,
                    'message' : f'Dron {id} autenticado correctamente',
                    'data' : data
                }
                return jsonify(response),201
            else:
                response = {
                    'error': True,
                    'message': f'El token {token} no es correcto',
                    'data' : data
                }        

                return jsonify(response), 401
    
    except Exception as e:
        response = {
            'error': True,
            'message': f'Ha ocurrido el siguiente error {e}',
            'data' : None
        }
        print(e)
        return jsonify(response), 500

@app.route('/recibirclaves',methods=['POST'])
def recibirClaves():
    try:
        datas = request.get_json()
        
        for data in datas:
            
            # Insertar dron en la base de datos
            
            id = data['ID']
            claveDron = data['Clave']
            
            guardar_claves_en_archivo(claveDron,id=id)

            response = {
                'error' : False,
                'message' : f'Se ha almacenado la clave del drone {id}',
                'data' : claveDron
            }
            return jsonify(response),201
    
    except Exception as e:
        response = {
            'error': True,
            'message': f'Ha ocurrido el siguiente error {e}',
            'data' : None
        }
        print(e)
        return jsonify(response), 500


@app.route('/')
def index():
    return "API_REST ENGINE-DRONES"

if __name__ == '__main__':
    if len(sys.argv) != 4:
        print("Introduce los argumentos: AD_ENGINE.py puertoAPI maxDrones bootstrapServerKafka")
    else:
        vaciarFichero()
        #topics = "MOVIMIENTOS#MAPA#DESTINOS#"
        topics = "prueba3#prueba2#prueba1#"
        
        
        if sys.argv[3] == "localhost":
            DATOS_KAFKA = topics + socket.gethostbyname(socket.gethostname()) + ":9092"
        else:
            DATOS_KAFKA = topics + sys.argv[3] + ":9092"
        puertoEscucha = int(sys.argv[1])
        MAX_DRONES = int(sys.argv[2])
        
        
        vaciar_csv("auditoria_engine.csv")
        
        motor = AD_ENGINE(puertoEscucha,MAX_DRONES,DATOS_KAFKA,DATOS_DATABASE)
        guardar_claves_en_archivo(claveEngine)
        guardar_claves_en_archivo(claveMapa)
        
        hiloEngine = threading.Thread(target=motor.run)
        hiloEngine.start()
        
        app.run(host="engine",debug = False,port=puertoEscucha,ssl_context=('certificados\certificado_engine.crt','certificados\clave_privada_engine.pem'))
        
        
      