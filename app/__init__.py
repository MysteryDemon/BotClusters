import eventlet
eventlet.monkey_patch()

from flask import Flask
from asgiref.wsgi import WsgiToAsgi

app = Flask(__name__)

asgi_app = WsgiToAsgi(app)

from app import routes
