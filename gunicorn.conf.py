import os
import multiprocessing

# Worker class
#worker_class = "eventlet"

# Server socket
PORT = os.getenv("PORT", "5000")
bind = f"0.0.0.0:{PORT}"
backlog = 2048

# Worker processes
workers = 4
worker_class = 'sync'
worker_connections = 1000
timeout = 60
keepalive = 2
reload = True

# Logging
accesslog = '-'
errorlog = '-'
loglevel = 'info'

# Process naming
proc_name = 'gunicorn_flask'

# Server mechanics
daemon = False
sendfile = False
pidfile = None
umask = 0
user = None
group = None
tmp_upload_dir = None

# SSL
keyfile = None
certfile = None
