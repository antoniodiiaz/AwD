import socket
from pymongo import *
import random
import threading

MAX_CONEXIONES = 50
ENQ = "<ENQ>"
ACK = "1"
NACK = "-1"
STX = "<STX>"
ETX = "<ETX>"
EOT = "<EOT>"

FORMAT = 'utf-8'

def calculaLrc(cadena):
    suma = 0
    for caracter in cadena:
        suma += ord(caracter)
    lrc = (suma & 0xFF) ^ 0xFF
    return lrc + 1

def comprobarLrc(cadena,lrc):
    return lrc == calculaLrc(cadena)

class AD_WEATHER:
    def __init__(self,puerto):
        self.puerto = puerto
    
    def handle_engine(self,conn,addr):
        print(f"Nueva conexión: {addr} conectado.")
        connected = True
        try:
            while connected:
                
                temperatura = self.consulta_clima()
                mensaje = STX + temperatura + ETX + str(calculaLrc(temperatura))
                conn.send(mensaje.encode(FORMAT))
                mensaje = bool(conn.recv(2).decode(FORMAT))
                
                if mensaje:
                    conn.send(EOT.encode(FORMAT))
                    mensaje = conn.recv(len(EOT)).decode(FORMAT)
                    if mensaje == EOT:
                        conn.close()
                        connected = False
                else:
                    print("No se ha enviado el mensaje correctamente")
                    conn.close()
            conn.close()
        except Exception as e:
            print("Se ha perdido la conexión con el servidor")
            connected = False
        finally:
            conn.close()
            
    
    def start(self):
        try:
            print("Servidor inicializándose")
            SOCKET = socket.gethostbyname(socket.gethostname())
            ADDR = (SOCKET,self.puerto)
            weather = socket.socket(socket.AF_INET,socket.SOCK_STREAM)
            print(f"Nueva conexión en {ADDR}")
            weather.bind(ADDR)
            print(f"Servidor a la escucha en {weather}")
            weather.listen()
            CONEX_ACTIVAS = threading.active_count() - 1
            while True:
                conn, addr = weather.accept()
                mensaje = conn.recv(len(ENQ.encode(FORMAT))).decode(FORMAT)
                if mensaje == ENQ:
                    conn.send(ACK.encode(FORMAT))
                    CONEX_ACTIVAS = threading.active_count()
                    if CONEX_ACTIVAS <= MAX_CONEXIONES:
                        thread = threading.Thread(target=self.handle_engine,args = (conn,addr))
                        thread.start()
                else:
                    conn.send(NACK.encode(FORMAT))
        except Exception as e:
            print("Ya hay un servidor WEATHER escuhando")
        
        

    def databaseVacia(self,collection):
        return collection.count_documents({}) == 0
    
   
    def consulta_clima(self):
        MONGO_URI = "mongodb://localhost:27017"
        cliente =  MongoClient(MONGO_URI)
        database = cliente["dbWEATHER"]
        collection = database["WEATHER"]
        if self.databaseVacia(collection):
            temperatura = int(input("Introduce la nueva temperatura: "))
            collection.insert_one({
                "Temperatura" : temperatura,
                "Ciudad" : "Nueva York"
            })
        else:
            temperatura = collection.find_one()["Temperatura"]
            newTemperatura = int(input("Introduce la nueva temperatura: "))
            filter = {"Temperatura" : temperatura}
            newValues = {"$set" : {"Temperatura" : newTemperatura}}
            collection.update_one(filter,newValues)
            temperatura = newTemperatura
     
        return str(temperatura)

if __name__ == "__main__":
    clima = AD_WEATHER(5050)
    clima.start()