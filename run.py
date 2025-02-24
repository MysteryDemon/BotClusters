import eventlet
eventlet.monkey_patch()

import os
import logging
from app import app
from flask_socketio import SocketIO, emit
from app.routes import parse_supervisor_status, run_supervisor_command

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

@socketio.on('connect')
def handle_connect():
    """Handle client connection."""
    logger.info("Client connected")
    emit('connected', {'data': 'Connected'})
    broadcast_status_update()

@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnection."""
    logger.info("Client disconnected")

@socketio.on('request_status')
def handle_status_request():
    """Handle WebSocket request for process status updates."""
    try:
        status = run_supervisor_command("status")
        if status["status"] == "success":
            processes = []
            for proc in status["message"].splitlines():
                parsed_proc = parse_supervisor_status(proc)
                if parsed_proc:
                    processes.append(parsed_proc)
            
            if not processes:
                logger.warning("No processes found in supervisor status")
                
            emit('status_update', {
                "status": "success",
                "processes": processes,
                "timestamp": datetime.utcnow().isoformat()
            })
        else:
            logger.error(f"Error getting supervisor status: {status['message']}")
            emit('status_update', {
                "status": "error",
                "message": status["message"],
                "processes": []
            })
    except Exception as e:
        logger.error(f"Error in handle_status_request: {str(e)}")
        emit('status_update', {
            "status": "error",
            "message": str(e),
            "processes": []
        })

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
