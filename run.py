import eventlet
eventlet.monkey_patch()

import os
import logging
from app import app
from flask_socketio import SocketIO, emit

SUPERVISOR_LOG_DIR = "/var/log/supervisor"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

socketio = SocketIO(
    app,
    async_mode='eventlet',
    cors_allowed_origins="*",
    ping_timeout=60,
    ping_interval=25
)

if __name__ == "__main__":
    try:
        os.makedirs(SUPERVISOR_LOG_DIR, exist_ok=True)
        port = int(os.environ.get("PORT", 5000))
        socketio.run(
            app,
            host="0.0.0.0",
            port=port,
            debug=True,    
            use_reloader=False
        )

    except Exception as e:
        logger.error(f"Failed to start application: {str(e)}", exc_info=True)
        raise
