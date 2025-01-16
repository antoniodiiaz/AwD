
class AD_MAP:
    def __init__(self, ancho=21, alto=21):
        self.ancho = ancho
        self.alto = alto
        self.map = [[[] for _ in range(self.ancho)] for _ in range(self.alto)]

    def pushDrone(self, drone, row, column):
        self.map[row][column].append(drone)

    def dropDrone(self, drone, row, column):
        lista = self.map[row][column]
        for dron in lista:
            if dron == drone:
                self.map[row][column].remove(drone)
                break

    def mapToString(self) -> str:
        mapa = ""
        for i in range(self.alto):
            for j in range(self.ancho):
                if len(self.map[i][j]) == 0:
                    mapa += "- "
                else:
                    numDrons = len(self.map[i][j])
                    for dron in range(numDrons):
                        if dron + 1 == numDrons: 
                            mapa += f"Drone_{self.map[i][j][dron]} "
                        else:
                            mapa += f"Drone_{self.map[i][j][dron]},"

            mapa += "\n"
        return mapa
    
    def __str__(self):
        mapa = ""
        for i in range(self.alto):
            for j in range(self.ancho):
                if len(self.map[i][j]) == 0:
                    mapa += "-"
                else:
                    numDrons = len(self.map[i][j])
                    for dron in range(numDrons):
                        if dron + 1 == numDrons: 
                            mapa += f"Drone_{self.map[i][j][dron]} "
                        else:
                            mapa += f"Drone_{self.map[i][j][dron]},"

            mapa += "\n"
        return mapa
    
    def stringToMap(self,mapa_string):
        mapa_objeto = AD_MAP()
        filas = mapa_string.strip().split('\n')
        for i, fila in enumerate(filas):
            columnas = fila.strip().split(' ')
            for j, columna in enumerate(columnas):
                if columna != "":
                    drones = columna.split(',')
                    for dron in drones:
                        if dron[len(dron) - 1] == " ":
                            dron = dron[:len(dron)-1]
                        dron_id = dron.split('_')
                        if len(dron_id) > 1:
                            dron_id = int(dron_id[1])
                            mapa_objeto.pushDrone(dron_id, i, j)
        return mapa_objeto

