from flask_socketio import emit
from app import socketio
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

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
    emit('status_update', {
        "status": "success",
        "timestamp": datetime.utcnow().isoformat()
    })
