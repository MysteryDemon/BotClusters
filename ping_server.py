from time import sleep
from os import environ
from logging import error as logerror

from requests import get as rget

BASE_URL = environ.get('BASE_URL', "http://0.0.0.0").rstrip("/")
PORT = environ.get('PORT', None)

if PORT is not None:
    while 1:
        try:
            rget(BASE_URL).status_code
            sleep(600)
        except Exception as e:
            logerror(f"alive.py: {e}")
            sleep(600)
            continue
