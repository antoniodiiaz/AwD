from Crypto.PublicKey import RSA as CryptoRSA
from Crypto.Cipher import PKCS1_OAEP
from base64 import b64decode, b64encode
from Crypto import Random

class RSA:
    def __init__(self, longitud=2048):
        self.generarClaves(longitud)

    def generarClaves(self,longitud):
        self.private_key = CryptoRSA.generate(longitud, Random.new().read)
        self.public_key = self.private_key.publickey()    

    def encriptar(self, mensaje):
        key = CryptoRSA.importKey(self.getClavePublica())
        cipher = PKCS1_OAEP.new(key)
        mensajeEncriptado = cipher.encrypt(mensaje.encode())
        return b64encode(mensajeEncriptado).decode("UTF-8")

    def desencriptar(self, mensajeEncriptado):
        cipher = PKCS1_OAEP.new(self.private_key)
        mensajeEncriptado = b64decode(mensajeEncriptado)
        textoPlano = cipher.decrypt(mensajeEncriptado)
        return textoPlano.decode("UTF-8")

    def getClavePrivada(self):
        return self.private_key.exportKey("PEM").decode("UTF-8")

    def getClavePublica(self):
        return self.public_key.exportKey("PEM").decode("UTF-8")

