import socket
from pymongo import *
import AD_REGISTRY
import json
from AD_MAP import *
from kafka import KafkaConsumer,KafkaProducer, TopicPartition
import time

HEADER = 128
FORMAT = "utf-8"

localhost = socket.gethostbyname(socket.gethostname())
KAFKA_BROKER = localhost + ":9092"
#DATOS_KAFKA = "MOVIMIENTOS#MAPA#DESTINOS#" + KAFKA_BROKER 
DATOS_KAFKA = "prueba24#prueba23#prueba22#" + KAFKA_BROKER 

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
    
    #IP::PORT
def obtenerDatos(datos : str) -> tuple[str,int]:
    indice = datos.find("::")
    empezar = indice + 2
    ip = datos[0:indice]
    port = datos[empezar:]
    return (ip,int(port))
    
def send(datos : str,cliente) -> str:
    enviar = datos.encode(FORMAT)
    datos_length = len(enviar)
    send_length = str(datos_length).encode(FORMAT)
    length = STX + str(send_length) + ETX + str(calculaLrc(str(send_length)))
    cliente.send(length.encode(FORMAT))
    mensaje = cliente.recv(2).decode(FORMAT)
    if mensaje == ACK:
        cliente.send(enviar)
        mensaje = cliente.recv(2).decode(FORMAT)
        if mensaje == ACK:
            datos_drone = cliente.recv(HEADER).decode(FORMAT)
            if compruebaMensaje(datos_drone):
                cliente.send(ACK.encode(FORMAT))
                cliente.send(EOT.encode(FORMAT))
                mensaje = cliente.recv(len(EOT)).decode(FORMAT)
                if mensaje == EOT:
                    print("Se va a cerrar la conexión")
                    cliente.close()
                    return datos_drone
        else:
            return NACK
    else:
        return NACK

#ID_TOKEN
def organizaDatosDatabase(datos : str) -> tuple[int,str]:
    indSTX = datos.find(STX)
    indETX = datos.find(ETX)
    indice = datos.find("_")
    empezar = indice + 1
    id = datos[indSTX+len(STX):indice]
    token = datos[empezar:indETX]
    return (int(id),token)



class AD_DRONE:
    def __init__(self,datos_engine : str,datos_kafka: str,datos_registry : str):
        self.id = -1
        self.token = ""
        self.datos_engine = datos_engine
        self.datos_kafka = separaDatos(datos_kafka)
        self.datos_registry = datos_registry
        self.coordenadaX = 0
        self.coordenadaY = 0
        self.mapa = AD_MAP()
        self.posActual = [0,0]
        self.colocado = False
        self.finalizar = False
        #kafka
        
        
        
        
    def getId(self):
        return self.id

    def register_drone(self):
        client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        ADDR = obtenerDatos(self.datos_registry)
        try:
            client.connect(ADDR)
            client.send(ENQ.encode(FORMAT))
            mensaje = client.recv(2).decode(FORMAT)
            if mensaje == ACK: 
                print(f"Conexión establecida en {ADDR}")
                datos_drone = str(self.id) + "_0_0"
                mensaje = STX + datos_drone + ETX + str(calculaLrc(datos_drone))
                datosDroneDatabase = send(mensaje,client)
                self.id,self.token = organizaDatosDatabase(datosDroneDatabase)
                
                """
                #kafka
                drone_message = f"Drone registrado con ID: {self.id}"
                send_to_kafka("drones_topic", drone_message, self.producer)
                """
            else:
                print("No se ha establecido la conexión correectamente")
        
        except Exception as e:
            print("Se ha perdido la conexión con el AD_REGISTRY, no se pudo registrar el DRON")
        finally:
            client.close()
            
    def iniciarSesion(self):
        while True:
            token = input("Introduce el token del dron: ")
            if len(token) == 9:
                break
        client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        ADDR = obtenerDatos(self.datos_registry)
        noSesion = False
        try:
            client.connect(ADDR)
            client.send(ENQ.encode(FORMAT))
            mensaje = client.recv(2).decode(FORMAT)
            if mensaje == ACK: 
                print(f"Conexión establecida en {ADDR}")
                mensaje = STX + token + ETX + str(calculaLrc(token))
                client.send(mensaje.encode(FORMAT))
                mensaje = client.recv(2).decode(FORMAT)
                if mensaje == ACK:
                    datosDrone = client.recv(100).decode(FORMAT)
                    if compruebaMensaje(datosDrone):
                        client.send(ACK.encode(FORMAT))
                        client.send(EOT.encode(FORMAT))
                        mensaje = client.recv(len(EOT)).decode(FORMAT)
                        if mensaje == EOT:
                            datosDrone = datosDrone[len(STX):datosDrone.find(ETX)]
                            if datosDrone == "-1":
                                print("Token incorrecto")
                            else:
                                print(f"Inicio de sesión correcto.\n Bienvenido dron con ID {datosDrone}")
                                self.id = int(datosDrone)
                                self.token = token
                            print("Se va a cerrar la conexión con el Engine")
                            client.close()
                        else:
                            print("No se ha enviado el EOT")
                    else:
                        client.send(NACK.encode(FORMAT))
                else:
                    print("El mensaje no ha llegado bien")
                    client.close()
            else:
                print("No se ha establecido la conexión correctamente")
        except Exception as e:
            print("No se ha podido iniciar sesión ya que el Engine no se encuentra disponible ahora mismo")
            noSesion = True
        finally:
            client.close()
        if not noSesion:
            while True:
                try:
                    while True:
                        self.esperarRespuestaEngine()
                        if self.colocado or self.finalizar:
                            break
                    if self.colocado:
                        print("El dron ya está en su sitio")
                    elif self.finalizar:
                        self.posActual[0] = 0
                        self.posActual[1] = 0
                        print("CONDICIONES CLIMATICAS ADVERSAS. ESPECTACULO FINALIZADO")
                except Exception as e:
                    print("No se encuentra kafka en servicio")
            
    
    def drope_drone(self):
        print("Eliminar Dron")
    
    def __str__(self) -> str:
        if self.coordenadaX == 0 and self.coordenadaY == 0:
            return f"Drone con ID = {self.id} y token = {self.token}"
        else:
            return f"Drone con ID = {self.id} y token = {self.token} cuya posicion es ({self.coordenadaX},{self.coordenadaY})"
    #kafka

    
    # Crea el Dron Producto
    # El dron es productor cuando produce los movimientos y se mueve por el mapa
    def configure_kafka_producer(self):
        try:
            producer = KafkaProducer(bootstrap_servers=self.datos_kafka[3])
            return producer
        except Exception as e:
            print("No se ha podido configurar el kafka productor del dron")
        


    # Crea el Dron Consumidor
    # El dron es consumidor cuando recibe las posiciones finales y cuando recibe el mapa
    def configure_kafka_consumer_dest(self):
        try:
            consumer = KafkaConsumer(self.datos_kafka[2],bootstrap_servers=self.datos_kafka[3],group_id=None,partition_assignment_strategy='roundrobin')
            return consumer
        except Exception as e:
            print("No se ha podido configurar el kafka consumidor del destino del dron")
        

    def configure_kafka_consumer_map(self):
        try:
            consumer = KafkaConsumer(self.datos_kafka[1],bootstrap_servers=self.datos_kafka[3])            
            return consumer
        except Exception as e:
            print("No se ha podido configurar el kafka consumidor del mapa del dron")
        
    
    def calculaDirecciones(self):
        positions = (int(self.pos[self.pos.find(".")+1:self.pos.find(",")]),int(self.pos[self.pos.find(",")+1:]))
        x,y = self.posActual[0],self.posActual[1]
        if self.posActual[0] == positions[0] and self.posActual[1] == positions[1]:
            self.colocado = True
        elif x < positions[0]:
            x += 1
            self.posActual[0] = x
        elif x > positions[0]:
            x -= 1
            self.posActual[0] = x
        elif y < positions[0]:
            y += 1
            self.posActual[1] = y
        else:
            y -= 1
            self.posActual[1] = y
        
    
    def recibeMapa(self):
        self.consumerMap = self.configure_kafka_consumer_map()
        mapa = AD_MAP()
        for mensaje in self.consumerMap:
            message = mensaje.value.decode(FORMAT)
            if message[0] == "F":
                self.finalizar = True
            else:
                self.mapa = mapa.stringToMap(mensaje.value.decode(FORMAT))
            break
        self.consumerMap.close()
        print("Mapa recibido")

    def enviaMovimientos(self,movimientos):
        self.producer.send(self.datos_kafka[0],value=movimientos.encode(FORMAT))
        print("Movimientos enviados")
        self.producer.close()

    def recibePos(self):
        self.consumerDest = self.configure_kafka_consumer_dest()
        for mensaje in self.consumerDest:
            #ID.X,Y
            datos = mensaje.value.decode(FORMAT)
            ident = int(datos[:datos.find(".")])
            if self.id - 1 == ident:
                self.pos = datos[datos.find(".")+1:]
                break
        self.consumerDest.close()
        
    
    def esperarRespuestaEngine(self):
        self.finalizar = False
        primeraFigura = True
        while True:
            print("Esperando información del Engine")
            if primeraFigura:
                self.recibePos()
                primeraFigura = False
                print("Desde el Engine hemos recibido las posiciones ", self.pos)
            self.recibeMapa()
            if self.finalizar:
                break
            print("Recibiendo mapa")
            print("Desde el engine hemos recibido el mapa")
            print(self.mapa)
            
            print("Calculando direcciones")
            self.calculaDirecciones()
            
            time.sleep(5)
            if not self.colocado:
                mensaje = "R" + str(self.id) + "." + str(self.posActual[0]) + "," + str(self.posActual[1])
                print(mensaje)
            else:
                mensaje = "F" + str(self.id) + "." + str(self.posActual[0]) + "," + str(self.posActual[1])
                print(mensaje)
                primeraFigura = False
            self.producer = self.configure_kafka_producer()
            self.enviaMovimientos(mensaje)

def muestra_menu():
    option = ""
    while True:
        print("Menú de Drones:")
        print("1. Registrar Dron.")
        print("2. Esperar órdenes desde Engine")
        print("3. Iniciar sesión.")
        print("4. Ver datos Dron")
        print("5. Salir.")
        option = input("Introduce una opción: ")
        if option == "1" or option == "2" or option == "3" or option == "4" or option == "5":
            break
        else:
            print("Introduce una opción correcta")
    return option


if __name__ == "__main__":
    ip = socket.gethostbyname(socket.gethostname())
    puerto = 8000
    ADDR_Registry = ip + "::" + str(8000)
    ADDR_Engine = ip + "::" + str(8080)
    dron = AD_DRONE(ADDR_Registry,DATOS_KAFKA,ADDR_Engine)
    while True:
        option = muestra_menu()
        if option == "1":
            if dron.getId() != -1:
                print("El dron ya está registrado")
            else:
                dron.register_drone()
        elif option == "2":
            dron.esperarRespuestaEngine()
        elif option == "3":
            dron.iniciarSesion()
        elif option == "4":
            print(dron)
            
        elif option == "5":
            print("Has salido con éxito")
            break
        else:
            print("Se ha finalizado el programa")
