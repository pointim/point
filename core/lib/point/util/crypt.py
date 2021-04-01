from Crypto.Cipher import AES
from Crypto import Random
from hashlib import md5
import json
import base64
#from geweb import log

import settings

aes_key = md5(settings.secret).digest()
_bs = AES.block_size


print aes_key

def _pad(s):
    return s + (_bs - len(s) % _bs) * chr(_bs - len(s) % _bs)

def _unpad(s):
    return s[:-ord(s[len(s)-1:])]

def aes_encrypt(data):
    iv = Random.new().read(16)
    cipher = AES.new(aes_key, AES.MODE_CBC, iv)
    return base64.b64encode(iv + cipher.encrypt(_pad(json.dumps(data))))

def aes_decrypt(data):
    data = base64.b64decode(data)
    iv = data[:_bs]
    cipher = AES.new(aes_key, AES.MODE_CBC, iv)
    return json.loads(_unpad(cipher.decrypt(data[_bs:])))
