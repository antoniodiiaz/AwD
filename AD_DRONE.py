import socket
from pymongo import *
from AD_MAP import *
from kafka import KafkaConsumer,KafkaProducer, TopicPartition
import time
import threading
import sys
from colorama import init, Fore
from AES import *
import ssl
import requests
import random


HEADER = 128
FORMAT = "utf-8"

ENQ = "<ENQ>"
ACK = "1"
NACK = "-1"
STX = "<STX>"
ETX = "<ETX>"
EOT = "<EOT>"


API_REGISTRY = "https://"
API_ENGINE = "https://"



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
    if ip == "localhost":
        ip = socket.gethostbyname(socket.gethostname())
    port = datos[empezar:]
    return (ip,int(port))
   

def vaciarFichero(id):
    fichero = "claves\clavesDron_" + str(id) + ".txt"
    with open(fichero, "w"):
        pass

def guardar_claves_en_archivo(claveAES,id=None):
    if id:
        fichero = "claves\clavesDron_" + str(id) + ".txt"
    with open(fichero, "a") as file:
        file.write(claveAES.getClave().hex() + "\n")

#ID
def organizaDatosDatabase(datos : str) -> int:
    indSTX = datos.find(STX)
    indETX = datos.find(ETX)
    id = datos[indSTX+len(STX):indETX]
    return int(id)

def borrarClavesEngine(id):
    try:
        archivo = "claves\clavesDron_" + str(id) + ".txt"
        with open(archivo, 'r') as file:
            lines = file.readlines()

        # Eliminar las dos últimas líneas
        nuevas_lineas = lines[:-2]

        with open(archivo, 'w') as file:
            file.writelines(nuevas_lineas)
            
    except FileNotFoundError:
        print(f"El archivo {archivo} no fue encontrado.")
    except Exception as e:
        print(f"Ocurrió un error: {e}")

class AD_DRONE:
    def __init__(self,datos_kafka: str):
        self.id = -1
        self.token = ""
        self.datos_kafka = separaDatos(datos_kafka)
        self.coordenadaX = 0
        self.coordenadaY = 0
        self.mapa = AD_MAP()
        self.posActual = [0,0]
        self.pos = None
        self.colocado = False
        self.stop = False
        self.finalizar = False
        self.registrar = False
        self.estado = None
        self.consumerDest = self.configure_kafka_consumer_dest()
        self.producer = self.configure_kafka_producer()
        self.consumerMap = self.configure_kafka_consumer_map()
        self.miClave = AES()        
        self.claveEngine = None
        self.claveMapa = None
        self.autenticado = False
        self.tokenRecibido = False
        self.engineTieneClave = False
        self.tokenIncorrecto = True
        self.contestaEngine = False
        
    def run(self):
        dron.pideAPIRegistry()
        hiloCogeClave = threading.Thread(target=dron.claveAPI)
        hiloCogeClave.start()
        hiloSesion = threading.Thread(target= dron.consumeAPIENGINE)
        hiloSesion.start()
        hiloLeerClaves = threading.Thread(target=dron.leerClaves)
        hiloLeerClaves.start()
        hiloEspectaculo = threading.Thread(target=dron.esperarRespuestaEngine)
        hiloEspectaculo.start()
            
    def registraDronAPI(self,datosDroneanterior):
        url = API_REGISTRY + "/registrardron"
        miId = datosDroneanterior['ID'] + 1
        miAlias = "Drone_" + str(miId)
        misPos = '0,0'
        miToken = ''
        self.id = miId
        vaciarFichero(miId)
        try:
            dato_añadir=[{
                'ID' : miId,
                'Alias' : miAlias,
                'POS' : misPos,
                'Token' : miToken
            }]
            try:
                response = requests.post(url,json=dato_añadir,verify="certificados\certificado_registry_CA.crt")
            except:
                print("No se encuentra API_REGISTRY disponible")
            if response.status_code == 201:
                self.registrar = True
                vaciarFichero(self.id)
                guardar_claves_en_archivo(self.miClave,self.id)
                
        except Exception as e:
            print("Servidor AD_REGISTRY no disponible.")
        

    def registraAPIREGISTRY(self):  
        while not self.registrar:
            try:
                url = API_REGISTRY + "/obtenerdatos"
                response = requests.get(url,verify="certificados\certificado_registry_CA.crt")
                if response.status_code == 200:
                    contenido = response.content
                    diccionario = response.json()
                    drones = diccionario['data']
                    if len(drones) > 0:              
                        datosDroneanterior = drones[-1]
                    else:                            
                        datosDroneanterior = {'ID' : 0}
                    self.registraDronAPI(datosDroneanterior)
                    self.tokenIncorrecto = False
            except Exception as e:
                print("Servidor AD_REGISTRY no disponible")
            time.sleep(5)

    def pideAPIRegistry(self):
        while True:
            if not self.tokenRecibido:
                try:
                    url = API_REGISTRY + "/generarToken/" + str(self.id)
                    dato = {
                        'ID' : self.id
                    }
                    response = requests.put(url,json=dato,verify="certificados\certificado_registry_CA.crt")
                    if response.status_code == 201:
                        contenido = response.content
                        diccionario = response.json()
                        self.token = diccionario['data']['Token']
                        print("He recibido el token: ",self.token)
                        self.tokenRecibido = True
                        break
                except Exception as e:
                    response = {
                        'error' : True,
                        'message' : f'Error: {e}',
                        'data' : None
                    }
                    print("Servidor AD_REGISTRY no disponible")
                time.sleep(5)

                            

    def claveAPI(self):
        while True:
            if self.autenticado and not self.engineTieneClave:
                try:
                    url = API_ENGINE + "/obtenerdatos"
                    response = requests.get(url,verify="certificados\certificado_engine_CA.crt")
                    if response.status_code == 200:
                        contenido = response.content
                        diccionario = response.json()
                        clave_Engine = diccionario['clave Engine']                        
                        clave_Mapa = diccionario['clave Mapa']                            
                        
                        self.claveEngine = AES(llave=bytes.fromhex(clave_Engine))
                        
                        guardar_claves_en_archivo(self.claveEngine,self.id)
                        self.claveMapa = AES(llave=bytes.fromhex(clave_Mapa))
                        guardar_claves_en_archivo(self.claveMapa,self.id)
                        if not self.engineTieneClave:
                            clave = self.miClave.getClave()
                            dato_añadir = [{
                                'ID' : self.id,
                                'Clave' : clave.hex()
                            }]

                            try:
                                url = API_ENGINE  + "/recibirclaves"
                                response = requests.post(url,json=dato_añadir,verify="certificados\certificado_engine_CA.crt")
                                if response.status_code == 201:
                                    self.engineTieneClave = True
                                    print("El Engine dispone de mi clave ahora")
                            except:
                                print("No se encuentra API_ENGINE disponible")

                            
                except Exception as e:
                    #print(f"Fallo: {e}")
                    pass
            if self.autenticado and self.engineTieneClave:
                try:
                    url = API_ENGINE + "/obtenerdatos"
                    response = requests.get(url,verify="certificados\certificado_engine_CA.crt")
                    if response.status_code == 200:
                        pass
                except:
                    self.autenticado = False
                    self.engineTieneClave = False
                    borrarClavesEngine(self.id)
                time.sleep(4)
                

    def consumeAPIENGINE(self):
        while True:               
            if not self.autenticado:
                try:
                    url = API_ENGINE + "/autenticacion"
                    dato_añadir=[{
                        'ID' : self.id,
                        'Token' : self.token
                    }]
                    response = requests.post(url,json=dato_añadir,verify="certificados\certificado_engine_CA.crt")
                    if response.status_code == 201:
                        
                        self.autenticado = True
                        self.tokenIncorrecto = False
                    else:
                        self.pideAPIRegistry()
                        
                except Exception as e:
                    pass
                    #print(f"Fallo: {e}")
                
            time.sleep(1.3)  
    
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
        while True:
            if self.registrar:
                primera = True
                while not self.stop and self.autenticado:
                    
                    if self.stop:
                        print("Finalizando...")
                    
                    if self.colocado:
                        print("Dron colocado")
                        time.sleep(5)
                        
                    if self.pos is not None and not self.colocado:
                        positions = (int(self.pos[self.pos.find(".")+1:self.pos.find(",")]),int(self.pos[self.pos.find(",")+1:]))
                        
                        x,y = self.posActual[0],self.posActual[1]
                        if self.posActual[0] == 0 and self.posActual[1] == 0 and primera:
                            primera = False
                        else:
                            if x < positions[0] and y < positions[1]:
                                x += 1
                                y += 1
                                self.posActual[0] = x
                                self.posActual[1] = y
                                self.colocado = False
                            elif x > positions[0] or y > positions[1]:
                                if x > positions[0]:
                                    x -= 1
                                    self.posActual[0] = x
                                if y > positions[1]:
                                    y -= 1
                                    self.posActual[1] = y
                                self.colocado = False
                            elif y < positions[1] and x == positions[0]:
                                y += 1
                                self.posActual[1] = y
                                self.colocado = False
                            elif y == positions[1] and x < positions[0]:
                                x += 1
                                self.posActual[0] = x
                                self.colocado = False
                        if self.posActual[0] == positions[0] and self.posActual[1] == positions[1]:
                            self.colocado = True
                        if not self.colocado:
                            self.estado = "RUN"
                            if self.finalizar:
                                mensaje = "B" + "R" + str(self.id) + "." + str(self.posActual[0]) + "," + str(self.posActual[1])
                            else:
                                mensaje = "R" + str(self.id) + "." + str(self.posActual[0]) + "," + str(self.posActual[1])
                            
                            print(mensaje)
                        else:
                            self.estado = "END"
                            if self.finalizar:
                                mensaje = "B" + "F" + str(self.id) + "." + str(self.posActual[0]) + "," + str(self.posActual[1])
                            else:
                                mensaje = "F" + str(self.id) + "." + str(self.posActual[0]) + "," + str(self.posActual[1])
                            print(mensaje)
                            self.primeraFigura = False
                        self.enviaMovimientos(mensaje)
                if self.stop:
                    print("Finalizado")
                    break
                
    
    def recibeMapa(self):
        while True:
            if self.registrar:
                while not self.stop and self.autenticado:
                    mapa = AD_MAP()
                    self.mapaRecibido = False
                    for mensaje in self.consumerMap:
                        if not self.autenticado:
                            break
                       
                        try:
                            mensajeCifrado = mensaje.value.decode(FORMAT)
                            message = self.claveMapa.desencriptar(mensajeCifrado)
                            self.mapaRecibido = True
                            if message[0] == "W":
                                self.finalizar = True
                                
                            elif message[0] == "S":
                                self.stop = True    
                            else:
                                self.mapa = mapa.stringToMap(message)
                            if self.pos is not None:
                                print(self.mapa)
                            if self.stop:
                                print("Finalizando...")
                                break
                            time.sleep(2)
                        except:
                            print("No se puede descifrar el mapa.")
                            time.sleep(5)    
                            
                if self.stop:
                    print("Finalizado")
                    break

            
    def enviaMovimientos(self,movimientos):
        textoCifrado = self.claveEngine.encriptar(movimientos)
        self.producer.send(self.datos_kafka[0],value=textoCifrado.encode(FORMAT))        
        self.producer.flush() 
        print("Movimientos enviados")
        time.sleep(0.6)
    
    def recibePos(self):
        while True:
            if self.registrar:
                print("Voy a consumir posiciones")
                for mensaje in self.consumerDest:
                    #ID.X,Y
                    if self.stop:
                        print("Finalizando...")
                        break
                    
                    textoCifrado = mensaje.value.decode(FORMAT)
                    try:
                        datos = self.miClave.desencriptar(textoCifrado)            

                        if datos != "" and self.autenticado:                        
                            print(datos)
                            positions = datos[datos.find(".")+1:]
                            self.recibePos = True
                            print(f"He recibido las posiciones ",positions)
                            if self.pos is not None:
                                if self.autenticado:
                                    if positions == "0,0":   
                                        if self.pos != "0,0":                             
                                            self.pos = positions
                                            self.colocado = False
                                            #print("Volviendo a base...")
                                    else:
                                        
                                        self.colocado = False
                                        #print(f"Llendo a la posición {positions}...")
                                        self.pos = positions
                                        
                            else:
                                if positions != "0,0":
                                    #print(f"Llendo a la posición {positions}...")
                                    self.pos = positions
                            time.sleep(5)
                    except:
                        print("No es posible entender los mensajes del Engine.")
                        time.sleep(10)
                print("Finalizado")
                break
        
    def esperarRespuestaEngine(self):
        self.finalizar = False
        print("Esperando información del Engine")
        hiloRecibePos = threading.Thread(target=self.recibePos)
        hiloRecibeMapa = threading.Thread(target=self.recibeMapa)
        hiloEnviaMovimientos = threading.Thread(target=self.calculaDirecciones)
        
        hiloRecibePos.start()
        hiloRecibeMapa.start()
        hiloEnviaMovimientos.start()
        
        
    def leerClaves(self):
        while True:
            try:
                fichero = "claves\clavesDron_" + str(self.id) + ".txt"
                with open(fichero, 'r') as archivo:
                    for fila,linea in enumerate(archivo):

                        if fila == 0: #Mi clave
                                
                            
                            self.miClavePublica = AES(llave=bytes.fromhex(linea))
                        if fila == 1: #Clave Engine 
                                                    
                            self.claveEngine = AES(llave=bytes.fromhex(linea))
                        
                        if fila == 2:
                                                    
                            self.claveMapa = AES(llave=bytes.fromhex(linea))
                            
                    time.sleep(10)
            except FileNotFoundError:
                print(f"El archivo {fichero} no fue encontrado.")
            except Exception as e:
                print(f"Ocurrió un error: {e}")
            time.sleep(5)
        
        
           
            

def muestra_menu(option):
    if option == "":
        while True:
            print("Menú de Drones:")
            print("1. Registrar Dron.")
            print("2. Iniciar sesión.")
            print("3. Ver datos Dron")
            print("4. Salir.")
            option = input("Introduce una opción: ")    
            if option == "1" or option == "2" or option == "3" or option == "4":
                break
            else:
                print("Introduce una opción correcta")
    return option


if __name__ == "__main__":
    if len(sys.argv) != 5 and len(sys.argv) != 4:
        print("Introduce 5 argumentos: python AD_DRONE.py ip::puerto_Registry bootstrapServerKafka ip::puerto_Engine ipDron(Opcional)")
    else:

        #topics = "MOVIMIENTOS#MAPA#DESTINOS#"
        topics = "prueba36#prueba35#prueba34#"
        init()
        time.sleep(0.5)
        if sys.argv[2] == "localhost":
            DATOS_KAFKA = topics + socket.gethostbyname(socket.gethostname()) + ":9092"
            #DATOS_KAFKA = topics + "172.21.42.17:9092"
            
        else:
            DATOS_KAFKA = topics + sys.argv[2] + ":9092"
        ADDR_Registry = obtenerDatos(sys.argv[1])

        API_REGISTRY += ADDR_Registry[0] + ":" + str(ADDR_Registry[1])
        
        ADDR_Engine = obtenerDatos(sys.argv[3])
        API_ENGINE += ADDR_Engine[0] + ":" + str(ADDR_Engine[1])


        dron = AD_DRONE(DATOS_KAFKA)
        id = -1
        if len(sys.argv) == 5:
            id = int(sys.argv[4])
            dron.registrar = True
        #Comprobar que el id es un entero y comprobar mediante api o sockets que el dron está registrado.

        if id == -1:
            dron.registraAPIREGISTRY()                         
        else:
            dron.id = id
            vaciarFichero(dron.id)
            guardar_claves_en_archivo(dron.miClave,dron.id)

        dron.run()