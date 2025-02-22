import subprocess
import threading

def run_gunicorn():
    subprocess.run(["gunicorn", "--workers=4", "--bind=0.0.0.0:8000", "--log-level=info", "--access-logfile=-", "--error-logfile=-", "run:app"])

def run_ping_server():
    subprocess.run(["python3", "ping_server.py"])

def run_worker():
    subprocess.run(["python3", "worker.py"])

def run_supervisord():
    subprocess.run(["/usr/bin/supervisord", "-n", "-c", "/etc/supervisor/supervisord.conf"])

def run_update():
    subprocess.run(["python3", "update.py"])

if __name__ == "__main__":
    supervisord_thread = threading.Thread(target=run_supervisord)
    gunicorn_thread = threading.Thread(target=run_gunicorn)
    ping_server_thread = threading.Thread(target=run_ping_server)
    worker_thread = threading.Thread(target=run_worker)
    update_thread = threading.Thread(target=run_update)

    supervisord_thread.start()
    gunicorn_thread.start()
    ping_server_thread.start()
    worker_thread.start()
    update_thread.start()
    
    supervisord_thread.join()
    gunicorn_thread.join()
    ping_server_thread.join()
    worker_thread.join()
    update_thread.join()
