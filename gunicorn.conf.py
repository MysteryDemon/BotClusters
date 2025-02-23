import multiprocessing

# Worker class
worker_class = "gthread"

# Server socket
bind = '0.0.0.0:5000'
backlog = 2048

# Worker processes
workers = multiprocessing.cpu_count() * 2 + 1 
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
