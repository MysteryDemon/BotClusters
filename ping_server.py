import requests
import time

TIME = 120
starttime = time.time()

while True:
    try:
        requests.get('http://0.0.0.0')
    except:
        pass
    time.sleep(TIME - ((time.time() - starttime) % TIME))
