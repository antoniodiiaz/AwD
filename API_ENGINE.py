from flask import Flask, jsonify, request
from pymongo import MongoClient
import sys

DATOS_DATABASE="mongodb://localhost:27017"

app = Flask(__name__)

def obtenerBaseDatos(nameCollection):
    cliente = MongoClient(DATOS_DATABASE)
    database = cliente["dbREGISTRY"]
    collection = database[nameCollection]
    return collection


@app.route("/", methods=['GET'])
def index():
    return jsonify(message='Pagina de inicio de aplicacion de ejemplo de SD')

@app.route("/drones", methods=['GET'])
def get_drones():
    try:
        collection= obtenerBaseDatos("REGISTRY")
        registros = list(collection.find({}, {'_id': False}))
        response = {
                'data' : registros,
                'error' : False,
                'message' : 'Objetos cogidos satisfactoriamente'
            }
        return jsonify(response), 200
    except Exception as e:
        print(e)
        return jsonify(error='Error del servidor'), 500

@app.route("/drones/<int:id>", methods=['GET'])
def get_drone_by_id(id):
    try:

        collection= obtenerBaseDatos("REGISTRY")
        registro = collection.find({"ID" : id}, {'_id': False})
        busqueda=list(registro)
        existe=False
        for r in busqueda:
            if r['ID'] == id:
                existe=True
                break
        if existe:

            response = {
                'data' : busqueda,
                'error' : False,
                'message' : 'Objetos cogidos satisfactoriamente'
            }
            return jsonify(response), 200

        else:
            return jsonify(error=f'Dron con ID {id} no encontrado.'), 404

    except Exception as e:
        print(e)
        return jsonify(error='Error del servidor'), 500

@app.route("/mapa", methods=['GET'])
def get_map():
    try:
        collection = obtenerBaseDatos("REGISTRY")
        registro = collection.find({"ID": 1}, {'_id': False, 'Mapa': True})
        busqueda = list(registro)
        response = {

                'data': busqueda,
                'error': False,
                'message': 'Objetos cogidos satisfactoriamente'
            }
        return jsonify(response), 200

    except Exception as e:
        print(e)
        return jsonify(error='Error del servidor'), 500

@app.route("/auditoria",methods=['GET'])
def getAuditoria():
    try:
        collection = obtenerBaseDatos("AUDITORIA")
        auditoria = collection.find({},{'_id' : False})
        
        response = {
            'data' : list(auditoria),
            'error' : False,
            'message' : 'Información obtenida correctamente.'
        }
        return jsonify(response), 200
    except Exception as e:
        print(e)
        response = {
            'data' : None,
            'error' : True,
            'message' : f"Ha ocurrido el siguiente error: {e}"
        }
        return jsonify(response),500
    
if __name__ == "__main__":
    if len(sys.argv) != 2:
      print("Introduce la siguiente línea de argumentos: python API_ENGINE.py puertoEscucha")  
    else:
        puertoEscucha = int(sys.argv[1])
        app.run(host="apiengine", port=puertoEscucha)#, ssl_context=('certificados\certificado_apiengine.crt', 'certificados\clave_privada_apiengine.pem'))

