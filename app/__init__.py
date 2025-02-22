import os
import logging
from flask import Flask
from flask_socketio import SocketIO

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename='app.log'
)
logger = logging.getLogger(__name__)

socketio = SocketIO(
    async_mode='eventlet',
    cors_allowed_origins="*",
    ping_timeout=60,
    ping_interval=25
)

def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = os.urandom(24)
    from app.routes import main
    app.register_blueprint(main)
    socketio.init_app(app)
    return app
