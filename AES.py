from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import padding
from base64 import b64encode, b64decode
import secrets

FORMAT = 'utf-8'

def pad(data):
    padder = padding.PKCS7(128).padder()
    padded_data = padder.update(data) + padder.finalize()
    return padded_data

def unpad(data):
    unpadder = padding.PKCS7(128).unpadder()
    unpadded_data = unpadder.update(data) + unpadder.finalize()
    return unpadded_data


class AES:
    def __init__(self,key_length=256,llave=None):
        if llave is None:
            llave = self.generarClave(key_length)
        self.key = llave.ljust(32)
        

    def generarClave(self,key_length):
        return secrets.token_bytes(key_length // 8)
        
    def encriptar(self, data):
          
        data = pad(data.encode('utf-8'))

        cipher = Cipher(algorithms.AES(self.key), modes.ECB(), backend=default_backend())
        encryptor = cipher.encryptor()

        ciphertext = encryptor.update(data) + encryptor.finalize()
        return b64encode(ciphertext).decode('utf-8')

    def desencriptar(self, ciphertext):    
        try:
            ciphertext = b64decode(ciphertext)
            cipher = Cipher(algorithms.AES(self.key), modes.ECB(), backend=default_backend())
            decryptor = cipher.decryptor()
            decrypted_data = decryptor.update(ciphertext) + decryptor.finalize()        
            textoPlano = unpad(decrypted_data).decode('utf-8')
        except:
            return ""
        return textoPlano

    def getClave(self):
        return self.key

