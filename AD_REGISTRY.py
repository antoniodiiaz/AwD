import socket
import pymongo
import threading
import random

MAX_CONEXIONES = 50
HEADER = 128
FORMAT = "utf-8"

ENQ = "<ENQ>"
ACK = "1"
NACK = "-1"
STX = "<STX>"
ETX = "<ETX>"
EOT = "<EOT>"

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
    
def obtenerDatosDrone(lista):
    newLista= []
    newPalabra = ""
    for i,palabra in enumerate(lista):
        
        if palabra == "_":
            newLista.append(newPalabra)
            newPalabra = ""
        
        elif i +1  == len(lista):
            newPalabra += str(palabra)
            newLista.append(newPalabra)
        else:
            newPalabra += str(palabra)
    return newLista

class AD_REGISTRY:
    def __init__(self,puerto,datos_db):
        self.puerto = puerto
        self.datos_db = datos_db
    
    def generaToken(self):
        cadena = ""
        for i in range(9):
            num = random.randint(97,122)
            cadena += str(chr(num))
        return cadena

    def handle_drone(self,conn,addr):
        print(f"Nueva conexión: {addr} conectado.")
        connected = True
        try:
            while connected:
                drone_length = conn.recv(128).decode(FORMAT)
                if compruebaMensaje(drone_length):
                    conn.send(ACK.encode(FORMAT))
                    if drone_length:
                        datos = drone_length[drone_length.find(STX)+len(STX):drone_length.find(ETX)]
                        datos = datos[2:len(datos)-1]
                        drone_length = int(datos)
                        drone = conn.recv(drone_length).decode(FORMAT)
                        if compruebaMensaje(drone):
                            conn.send(ACK.encode(FORMAT))
                            indSTX = drone.find(STX)
                            indETX = drone.find(ETX)
                            drone = drone[indSTX+len(STX):indETX]
                            print(drone)
                            token = self.generaToken()
                            drone += "_" + token
                            idDrone = self.connection_database(drone)
                            datosDrone = str(idDrone) + "_" + token 
                            # ID_COORDENADAX_COORDENADAY_TOKEN
                            mensaje = STX + datosDrone + ETX + str(calculaLrc(datosDrone))
                            conn.send(mensaje.encode(FORMAT))
                            mensaje = conn.recv(2).decode(FORMAT)
                            if mensaje == ACK:
                                mensaje = conn.recv(len(EOT)).decode(FORMAT)
                                conn.send(EOT.encode(FORMAT))
                                if mensaje == EOT:
                                    connected = False
                                    print("Se va a cerrar la conexión")
                        else:
                            conn.send(NACK.encode(FORMAT))
                else:
                    conn.send(NACK.encode(FORMAT))
            
        except Exception as e:
            print("Se ha perdido la conexión con el Dron y no se ha podido registrar correctamente.")
            connected = False
        finally:
            conn.close()

    def start(self):
        print("Servidor inicializándose:")
        registry = socket.socket(socket.AF_INET,socket.SOCK_STREAM)
        ADDR = ((socket.gethostbyname(socket.gethostname())),self.puerto)
        registry.bind(ADDR)
        print(f"Servidor a la escucha en {registry}")
        registry.listen()
        CONEX_ACTIVAS = threading.active_count() - 1
        print(f"Hay {CONEX_ACTIVAS} conexiones activas")
        while True:
            conn, addr = registry.accept()
            mensaje = conn.recv(len(ENQ)).decode(FORMAT)
            if mensaje == ENQ:
                conn.send(ACK.encode(FORMAT))
                CONEX_ACTIVAS = threading.active_count()
                if CONEX_ACTIVAS <= MAX_CONEXIONES:
                    thread = threading.Thread(target=self.handle_drone,args=(conn,addr))         
                    thread.start()
            else:
                conn.send(NACK.encode(FORMAT))

    def databaseVacia(self,collection):
        return collection.count_documents({}) == 0
    
    def connection_database(self,drone):
        MONGO_URI = self.datos_db
        cliente = pymongo.MongoClient(MONGO_URI)
        database = cliente["dbREGISTRY"]
        collection = database['REGISTRY']
        newDrone = obtenerDatosDrone(list(drone))
        if self.databaseVacia(collection):
            newDrone[0] = 1
        else:
            newDrone[0] = collection.find().sort("ID",-1)[0]["ID"] + 1
        alias = "Drone_" + str(newDrone[0])
        pos = newDrone[1] + "," + newDrone[2]
        insertar = {
            "ID" : newDrone[0],
            "Alias" : alias,
            "POS": pos,
            "Token" : newDrone[3]
        }
        collection.insert_one(insertar)
        print(f"Dron con ID: {newDrone[0]} y token = {newDrone[3]} registrado correctamente en la Base de Datos")
        return newDrone[0]


if __name__ == "__main__":
    registro = AD_REGISTRY(8000,"mongodb://localhost:27017")
    registro.start()
