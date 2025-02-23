from app import app, socketio

if __name__ != "__main__":
    socketio.init_app(app)
