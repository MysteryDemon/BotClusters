import eventlet
eventlet.monkey_patch()
import os
import logging
from app import app
from app.routes.routes import socketio, schedule_cronjobs

SUPERVISOR_LOG_DIR = "/var/log/supervisor"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

if __name__ == "__main__":
    try:
        os.makedirs(SUPERVISOR_LOG_DIR, exist_ok=True)
        schedule_cronjobs()
        port = int(os.environ.get("PORT", 5000))
        socketio.run(
            app,
            host="0.0.0.0",
            port=port,
            debug=False,    
            use_reloader=False,
            allow_unsafe_werkzeug=True
        )

    except Exception as e:
        logger.error(f"Failed to start application: {str(e)}", exc_info=True)
        raise
