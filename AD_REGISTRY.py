import pymongo
import threading
import sys
import random
import time
from flask import Flask, request, jsonify
from AD_MAP import *

MAX_CONEXIONES = 50
HEADER = 128
FORMAT = "utf-8"


ENQ = "<ENQ>"
ACK = "1"
NACK = "-1"
STX = "<STX>"
ETX = "<ETX>"
EOT = "<EOT>"

DATOS_DATABASE = "mongodb://localhost:27017"
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

def generaToken():
    cadena = ""
    for i in range(9):
        num = random.randint(97,122)
        cadena += str(chr(num))
    return cadena


def obtenerBaseDatos():
    cliente = pymongo.MongoClient(DATOS_DATABASE)
    database = cliente["dbREGISTRY"]
    collection = database["REGISTRY"]
    return collection

def limpiaToken(id):
    time.sleep(20)
    collection = obtenerBaseDatos()
    filtro = {'ID' : id}
    actualizacion = {'$set' : {'Token' : ""}}
    collection.update_one(filtro,actualizacion)
    print("Se ha limpiado el token de la base de datos")


# API_REST
app = Flask(__name__)

@app.route('/generarToken/<int:id>',methods=['PUT'])
def actualizarToken(id):
    try:
        datas = request.get_json()

        id = datas['ID']

        collection = obtenerBaseDatos()
        token = generaToken()
        filtro = {'ID' : id}
        actualizacion = {'$set' : {'Token' : token}}
        collection.update_one(filtro,actualizacion)
        response = {
            'error' : False,
            'message' : 'Se ha generado el token (válido solo 20 segundos)',
            'data' : {'Token' : token}
        }
        limpiarToken = threading.Thread(target=limpiaToken,args=(id,))
        limpiarToken.start()
        return jsonify(response),201

    except Exception as e:
        response = {
            'error' : True,
            'message' : f'Error: {e}',
            'data' : None
        }
        print(f"Fallo {e}")
        return jsonify(response), 500


@app.route('/obtenerdatos',methods=['GET'])
def obtenerDrones():
    try:
        if request.method == "GET":
            #obtener todos los drones de la base de datos
           
            collection = obtenerBaseDatos()
            registros = list(collection.find({}, {'_id': False}))
           
            response = {
                'data' : registros,
                'error' : False,
                'message' : 'Objetos cogidos satisfactoriamente'
            }
            return jsonify(response), 200
        
    except Exception as e:
        response = {
            'error' : False,
            'message' : f'Ha ocurrido el error: {e}',
            'data' : None
        }
        return jsonify(response),500
    

@app.route('/registrardron',methods=['POST'])
def anyadirDrones():
    try:
        datas = request.get_json()
        
        for data in datas:

            # Insertar dron en la base de datos
            alias = data['Alias']
            id = data['ID']
            pos = data['POS']
            token = data['Token']
            insertar = {
                "ID" : id,
                "Alias" : alias,
                "POS": pos,
                "Token" : token,
		"Mapa" : AD_MAP().mapToString(),
		"Estado" : "N"
            }
            collection = obtenerBaseDatos()
            collection.insert_one(insertar)
            print(f"<API_REST> Dron con ID: {id} registrado correctamente en la Base de Datos")

            response = {
                'error' : False,
                'message' : 'Item Added Successfully',
                'data' : data
            }

        return jsonify(response), 201
    
    except Exception as e:
        response = {
            'error': True,
            'message': f'Ha ocurrido el siguiente error {e}',
            'data' : None
        }
        return jsonify(response), 500
    
@app.route('/')
def index():
    return "API_REST REGISTRY-DRONES"


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Introduce la siguiente línea de argumentos: python AD_REGISTRY.py puertoEscuchaAPI")
    else:
        puertoEscuchaAPI = int(sys.argv[1])        
        app.run(host="registry",debug = False,port=puertoEscuchaAPI,ssl_context=('certificados\certificado_registry.crt','certificados\clave_privada_registry.pem'))
        
