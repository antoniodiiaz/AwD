from flask import Flask
from flask import request
from flask import render_template
import requests
from AD_MAP import *
import sys
from flask_socketio import SocketIO, emit
from threading import Thread

mapa_global=AD_MAP()
auditoria_global=None
tiempo_global=None
#api_key = "d0c92f36da1722f367bdf7e5d0fe7e40"

app = Flask(__name__)

socketio = SocketIO(app)

API_ENGINE_KEY = "http://apiengine:"

def read_city_name():
    ciudad = None  # Inicializamos la variable ciudad con None por defecto
    try:
        with open("temperatura\ciudad.txt", "r") as file:
            ciudad = file.read().strip()
    except FileNotFoundError:
        pass  # Dejamos ciudad como None si el archivo no existe
    return ciudad

def read_api_key():
    key = None  # Inicializamos la variable ciudad con None por defecto
    try:
        with open("temperatura\key.txt", "r") as file:
            key = file.read().strip()
    except FileNotFoundError:
        pass  # Dejamos ciudad como None si el archivo no existe
    return key

@app.route('/')
def home():
    ciudad = read_city_name()
    key=read_api_key()
    if ciudad is None:
        ciudad = "Ciudad Desconocida"  # Valor predeterminado si no se puede leer la ciudad

    try:
        weather_url = f"http://api.openweathermap.org/data/2.5/weather?q={ciudad}&appid={key}&units=metric"
        response = requests.get(weather_url)

        if response.status_code == 200:
            weather_data = response.json()
            temp = weather_data['main']['temp']
        else:
            temp = "N/A"

    except Exception as e:
        print(f"Fallo: {e}")
        temp = "No se ha podido leer la temperatura"

    return render_template('home.html', temperatura=temp, ciudad=ciudad)



def background_thread():
    while True:
        socketio.sleep(5)  # Actualiza cada 5 segundos

def coger_mapa():
    while True:
        url = API_ENGINE_KEY + "/drones/1"
        response = requests.get(url)#verify="certificados\certificado_apiengine_CA.crt")
        new_mapa=AD_MAP()
        contenido = response.content
        diccionario = response.json()
        mapa_espectaculo = diccionario['data'][0]['Mapa']
        mapa_global=new_mapa.stringToMap(mapa_espectaculo).getLista()
        socketio.emit('update', {'mapa_data': mapa_global})
        socketio.sleep(0.5)


def coger_mapa_inicial():
    url = API_ENGINE_KEY + "/drones/1"
    response = requests.get(url)#verify="certificados\certificado_apiengine_CA.crt")
    new_mapa=AD_MAP()
    contenido = response.content
    diccionario = response.json()
    mapa_espectaculo = diccionario['data'][0]['Mapa']
    new_mapa2=new_mapa.stringToMap(mapa_espectaculo).getLista()
    return new_mapa2

@socketio.on('connect')
def handle_connect():
    print("Cliente conectado")

@app.route('/mapa')
def mapa():

    ciudad = read_city_name()
    key= read_api_key()
    
    if ciudad is None:
        ciudad = "Ciudad Desconocida"  # Valor predeterminado si no se puede leer la ciudad

    try:
        weather_url = f"http://api.openweathermap.org/data/2.5/weather?q={ciudad}&appid={key}&units=metric"
        response = requests.get(weather_url)

        if response.status_code == 200:
            weather_data = response.json()
            temp = weather_data['main']['temp']
        else:
            temp = "N/A"

    except Exception as e:
        print(f"Fallo: {e}")
        temp = "No se ha podido leer la temperatura"

    try:
        e=None
        mapa_global= coger_mapa_inicial()
        
    except Exception as e:
        print(f"Fallo: {e}")

    return render_template('mapa.html', mapa_del_dron=mapa_global, temperatura=temp, ciudad=ciudad, drone_error_message=e)

@app.route('/drones')
def drones():
    try:
        url = API_ENGINE_KEY + "/drones"
        response = requests.get(url)

        if response.status_code == 200:
            drones_data = response.json()
        else:
            drones_data = []

    except Exception as e:
        print(f"Fallo: {e}")
        drones_data = []

    return render_template('drones.html', drones=drones_data)

def obtener_auditoria():
    global auditoria_global  # Indicar que estamos usando la variable global
    while True:
        try:
            url = API_ENGINE_KEY + "/auditoria"
            response = requests.get(url)

            if response.status_code == 200:
                auditoria_data = response.json()
                socketio.emit('update_auditoria', {'auditoria_data': auditoria_data})
                auditoria_global = auditoria_data  # Actualizar la variable global
            else:
                print("Error al obtener auditoría:", response.status_code)

        except Exception as e:
            print(f"Fallo al obtener auditoría: {e}")

        socketio.sleep(5)  # Actualizar cada 5 segundos

def coger_auditoria_inicial():
    global auditoria_global  # Indicar que estamos usando la variable global
    url = API_ENGINE_KEY + "/auditoria"
    response = requests.get(url)
    diccionario = response.json()
    auditoria_espectaculo = diccionario['data'][0]
    auditoria_global = auditoria_espectaculo.getLista()  # Actualizar la variable global
    return auditoria_global

def coger_auditoria():
    while True:
        try:
            url = API_ENGINE_KEY + "/auditoria"
            response = requests.get(url)

            if response.status_code == 200:
                auditoria_data = response.json()
                socketio.emit('update_auditoria', {'auditoria_data': auditoria_data})
            else:
                print("Error al obtener auditoría:", response.status_code)

        except Exception as e:
            print(f"Fallo al obtener auditoría: {e}")

        socketio.sleep(5)  # Actualizar cada 5 segundos

@app.route('/auditoria')
def auditoria():
    global auditoria_global  # Indicar que estamos usando la variable global
    try:
        e = None
        auditoria_global = coger_auditoria_inicial()

    except Exception as e:
        print(f"Fallo: {e}")

    return render_template('auditoria.html', auditoria=auditoria_global)



if __name__ == '__main__':
    if len(sys.argv) != 3:
        print("Introduce la siguiente lÃ­nea de argumentos: python Front.py puertoEscucha puertoAPIENGINE")  
    else:
        #thread = Thread(target=coger_mapa)
        #thread.daemon = True
        #thread.start()
        API_ENGINE_KEY = API_ENGINE_KEY + sys.argv[2]
        puertoEscucha = int(sys.argv[1])
        puertoAPIENGINE = int(sys.argv[2])
        #app.run(host="front",port=puertoEscucha, debug=True, ssl_context=('certificados\certificado_front.crt', 'certificados\clave_privada_front.pem'))
        socketio.start_background_task(coger_mapa)
        socketio.start_background_task(coger_auditoria)
        socketio.run(app, host="front", port=puertoEscucha, debug=True)
