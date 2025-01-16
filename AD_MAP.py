from colorama import init, Fore

class AD_MAP:
    def __init__(self, ancho=20, alto=20):
        self.ancho = ancho
        self.alto = alto
        self.map = [[[] for _ in range(self.ancho)] for _ in range(self.alto)]

    
    def pushDrone(self, drone,estado, row, column):
        dron = estado + str(drone)
        self.map[row][column].append(dron)

    def dropDrone(self, drone, row, column):
        lista = self.map[row][column]
        
        for dron in lista:
            idDron = int(dron[1:])
            if drone == int(idDron):
                self.map[row][column].remove(dron)
                break
    def mapaVacio(self):
        for row,fila in enumerate(self.map):
            for column,coordenada in enumerate(fila):
                if row != 0 or column != 0:
                    if len(self.map[row][column]) != 0:
                        return False
        return True
                
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
                            mapa += f"{self.map[i][j][dron]} "
                        else:
                            mapa += f"{self.map[i][j][dron]},"

            mapa += "\n"
        return mapa
    
    def __str__(self):
        mapa = ""
        for i in range(self.alto):
            for j in range(self.ancho):
                if len(self.map[i][j]) == 0:
                    mapa += Fore.RESET +"-\t"
                else:
                    numDrons = len(self.map[i][j])
                    
                    if numDrons > 0:                        
                        if self.map[i][j][0][0] == "F":
                            drone = Fore.GREEN + f"{self.map[i][j][0][1:]}\t"
                            mapa += drone
                        else:
                            drone = Fore.RED + f"{self.map[i][j][0][1:]}\t"
                            mapa += drone
                            

            mapa += "\n"
        return mapa
    
    def getLista(self):
	    return self.map
    
    def stringToMap(self, mapa_string):
        mapa_objeto = AD_MAP()
        filas = mapa_string.strip().split('\n')
        for i, fila in enumerate(filas):
            columnas = fila.strip().split(' ')
            for j, columna in enumerate(columnas):
                if columna != "-":
                    drones = columna.split(',')
                    for dron in drones:
                        if dron[len(dron) - 1] == " ":
                            dron = dron[:len(dron) - 1]
                        estadoDron = dron[0]
                        idDron = int(dron[1:])
                        mapa_objeto.pushDrone(idDron, estadoDron, i, j)
        return mapa_objeto
    

