import socket
from pymongo import *
import json
import threading
import AD_WEATHER
import AD_DRONE
from AD_MAP import *
import AD_REGISTRY
import time
from kafka import KafkaConsumer, KafkaProducer
import tkinter
from tkinter import *
from tkinter.simpledialog import *
from tkinter import messagebox as MessageBox
from confluent_kafka import Producer, Consumer, KafkaError

FORMAT = 'utf-8'
HEADER = 64
localhost = socket.gethostbyname(socket.gethostname())
KAFKA_BROKER = localhost + ":9092"
#DATOS_KAFKA = "MOVIMIENTOS#MAPA#DESTINOS#" + KAFKA_BROKER 
DATOS_KAFKA = "prueba24#prueba23#prueba22#" + KAFKA_BROKER
DATOS_CLIMA = localhost + "::5050"
ENQ = "<ENQ>"
ACK = "1"
NACK = "-1"
STX = "<STX>"
ETX = "<ETX>"
EOT = "<EOT>"


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

class AD_ENGINE:
    def __init__(self,puerto_escucha,max_drones,datos_kafka,datos_clima,datos_drones):
        self.puerto_escucha = puerto_escucha
        self.max_drones = max_drones
        self.datos_kafka = separaDatos(datos_kafka)
        self.datos_clima = separa(datos_clima)
        self.datos_drones = datos_drones
        self.positionsDrones = [[0,0]] * max_drones
        self.estadosDron = [] * max_drones
        #kafka
        
    
    def consulta_weather(self):
        motor = socket.socket(socket.AF_INET,socket.SOCK_STREAM)
        ADDR = self.datos_clima
        # print(ADDR) Descomentar el dia de correccion
        temperatura = 100
        try:
            motor.connect(ADDR)
            motor.send("<ENQ>".encode(FORMAT))
            ack = motor.recv(2).decode(FORMAT)
            if bool(ack):
                mensaje = motor.recv(HEADER).decode('utf-8')
                if compruebaMensaje(mensaje):
                    motor.send("1".encode(FORMAT))
                    temperatura = int(mensaje[mensaje.find("<STX>") + len("<STX>") : mensaje.find("<ETX>")])
                    print(f"Temperatura = {temperatura}")
                    eot = motor.recv(HEADER).decode(FORMAT)
                    if eot == "<EOT>":
                        motor.send(eot.encode(FORMAT))
                else:
                    print("Mensaje inválido")
            else:
                print("No se ha recibido confirmación del mensaje")
        except Exception as e:
            print("Se ha perdido la conexión con el servidor Weather")
        finally:
            motor.close()
            return temperatura

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


    def handle_drone(self,conn,addr):
        print(f"Nueva conexión: {addr} conectado.")
        connected = True
        try:
            while connected:
                token = conn.recv(128).decode(FORMAT)
                if compruebaMensaje(token):
                    conn.send(ACK.encode(FORMAT))
                    token = token[len(STX):token.find(ETX)]
                    datos = self.compruebaTokenDatabase(token)
                    mensaje = STX + datos + ETX + str(calculaLrc(datos))
                    conn.send(mensaje.encode(FORMAT))
                    mensaje = conn.recv(2).decode(FORMAT)
                    if mensaje == ACK:
                        mensaje = conn.recv(len(EOT)).decode(FORMAT)
                        conn.send(EOT.encode(FORMAT))
                        if mensaje == EOT:
                            connected = False
                        else:
                            conn.send(NACK.encode(FORMAT))
                            connected = False
                else:
                    conn.send(NACK.encode(FORMAT))
                    connected = False
            
        except Exception as e:
            print("Se ha perdido la conexión con el Dron y no se ha podido autenticar correctamente.")
            connected = False
        finally:
            conn.close()

    def autentica_dron(self):
        motor = socket.socket(socket.AF_INET,socket.SOCK_STREAM)
        ADDR = (socket.gethostbyname(socket.gethostname()),self.puerto_escucha)
        motor.bind(ADDR)
        print(f"Engine a la escucha en {motor}")
        motor.listen()
        CONEX_ACTIVAS = threading.active_count() - 1
        while True:
            conn, addr = motor.accept()
            mensaje = conn.recv(len(ENQ)).decode(FORMAT)
            if mensaje == ENQ:
                conn.send(ACK.encode(FORMAT))
                CONEX_ACTIVAS = threading.active_count()
                if CONEX_ACTIVAS <= self.max_drones:
                    thread = threading.Thread(target=self.handle_drone,args=(conn,addr))
                    thread.start()
            else:
                conn.send(NACK.encode(FORMAT))
            option = input("¿Quieres autenticar más drones? (S/N): ")
            if option != "S" and option != "s":
                break
        motor.close()
            

    def consulta_drones(self,buscaDrones=0,datos = [],primeraFigura = None):
        MONGO_URI = self.datos_drones
        cliente = MongoClient(MONGO_URI)
        database = cliente["dbREGISTRY"]
        collection = database['REGISTRY']
        if buscaDrones == 0 and len(datos) == 0:
            for dron in collection.find():
                print(f"ID: {dron['ID']} Coordenadas: ({dron['POS']})")
        else:
            self.producer = self.configure_kafka_producer()
            for dron in range(buscaDrones):
                filter = {"ID" : dron}
                newValues = {"$set" : {"POS" : datos[dron]['POS']}}
                collection.update_one(filter,newValues)
                mensaje = str(dron) + "." + datos[dron]['POS']
                self.producer.send(self.datos_kafka[2],value=mensaje.encode(FORMAT))
                if primeraFigura:
                    self.mapa.pushDrone(dron+1,0,0)
            primeraFigura = False

    def leerFicheroJSON(self,fichero):
        try:
            with open(fichero) as figuras:
                datos = json.load(figuras)
        except Exception as e:
            print("No existe el archivo " + fichero + " en el directorio")
            datos = []
        return datos

    
    def empezarEspectaculo(self):
        fichero = input("Introduce el nombre del fichero JSON: ")
        fichero += ".json"
        datos = motor.leerFicheroJSON(fichero)
        primeraFigura = True
        if len(datos) > 0:
            for numFiguras,figura in enumerate(datos['figuras']):
                print(f"Dibujo: {figura['Nombre']}")
                print("Comprobando que hay drones registrados para realizar la figura...")
                self.mapa = AD_MAP()
                drones = figura['Drones']
                self.consulta_drones(len(drones),drones,primeraFigura)
                time.sleep(6)
                temp = ""
                terminado = False
                #self.positionsDrones = [(0,0)] * len(drones)
                while True:
                    self.enviaMapa(temp)
                    if terminado:
                        print("CONDICIONES CLIMÁTICAS ADVERSAS. ESPECTÁCULO FINALIZADO.")
                        self.producer.close()
                        break
                    else:
                        print("Mapa enviado")
                        self.producer.close()
                        self.movimientos = []
                        print("Voy a consumir los movimientos")
                        
                        self.recibeMovimientos(len(drones))
                        
                        print("Movimientos recibidos")
                        print(self.movimientos)
                        self.procesaMovimientos()
                        print(self.mapa)

                        temperatura = self.consulta_weather()
                        if temperatura == 100 or temperatura < 0:
                            print("Se ha terminado el espectáculo")
                            terminado = True
                            temp = "F"
                            self.producer = self.configure_kafka_producer()
                self.estadosDron = [] * self.max_drones
                if numFiguras + 1 == len(datos['figuras']) or terminado:
                    print("Ha terminado el espectáculo")
                    break
                else:
                    print("Descansando mientras los drones vuelven a base...")
                    time.sleep(60)
                    

#kafka

    #Crea al engine productor
    # El engine es productor cuando produce el mapa y se lo envía al dron, y cuando le envía a los drones sus posiciones finales
    def enviaMapa(self,temp):
        mapastr = self.mapa.mapToString()
        mensaje = temp + mapastr
        mensaje = mensaje.encode(FORMAT)
        self.producer.send(self.datos_kafka[1],value=mensaje)


    def recibeMovimientos(self,drones):
        self.consumer = self.configure_kafka_consumer_movs()
        cuenta = 0
        for mensaje in self.consumer:
            self.movimientos.append(mensaje.value.decode(FORMAT))
            cuenta += 1
            print(f"Mensaje recibido: {mensaje.value.decode(FORMAT)}")
            if cuenta == drones:
                break
        self.consumer.close()
        
        
        
    def procesaMovimientos(self):
        movimientos = self.movimientos
        for movs in movimientos:
            
            id = int(movs[1:movs.find(".")])
            estadoDron = movs[0]
            self.estadosDron[id-1] = estadoDron
            movimientos = movs[movs.find(".")+1:len(movs)]
            coordX = movimientos[:movimientos.find(",")]
            coordY = movimientos[movimientos.find(",")+1:]
            movimientos = (int(coordX),int(coordY))
            self.mapa.dropDrone(id,self.positionsDrones[id-1][0],self.positionsDrones[id-1][1])
            self.mapa.pushDrone(id,movimientos[0],movimientos[1])
            self.positionsDrones[id-1][0] = movimientos[0]
            self.positionsDrones[id-1][1] = movimientos[1]

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

        


def mostrarMenu():
    option = ""
    while True:
        print("Menú del Engine:")
        print("1. Empezar espectáculo.")
        print("2. Consultar drones registrados.")
        print("3. Autenticar dron")
        print("4. Consultar clima")
        print("5. Salir")
        option = input("Introduce una opción: ")
        if option == "1" or option == "2" or option == "3" or option == "4" or option == "5":
            break
        else:
            print("Introduce una opción correcta")
    return option

if __name__ == "__main__":
    motor = AD_ENGINE(8080,30,DATOS_KAFKA,DATOS_CLIMA,"mongodb://localhost:27017")
    contador = 0
    while True:
        option = mostrarMenu()
        if option == "1":
            motor.empezarEspectaculo()
        elif option == "2":
            motor.consulta_drones()
        elif option == "4":
            motor.consulta_weather()
        elif option == "3":
            motor.autentica_dron()
        else:
            print("Has salido con éxito")
            break
