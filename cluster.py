import subprocess
import threading

def run_update():
    subprocess.run(["python3", "update.py"])

def run_gunicorn():
    subprocess.run(["gunicorn", "--workers=4", "--bind=0.0.0.0:8000", "--log-level=info", "--access-logfile=-", "--error-logfile=-", "run:app"])

def run_supervisord():
    subprocess.run(["/usr/bin/supervisord", "-n", "-c", "/etc/supervisor/supervisord.conf"])

def run_worker():
    subprocess.run(["python3", "worker.py"])

def run_ping_server():
    subprocess.run(["python3", "ping_server.py"])


if __name__ == "__main__":
    update_thread = threading.Thread(target=run_update)
    gunicorn_thread = threading.Thread(target=run_gunicorn)
    supervisord_thread = threading.Thread(target=run_supervisord)
    worker_thread = threading.Thread(target=run_worker)
    ping_server_thread = threading.Thread(target=run_ping_server)

    update_thread.start()
    gunicorn_thread.start()
    supervisord_thread.start()
    worker_thread.start()
    ping_server_thread.start()

    update_thread.join()
    gunicorn_thread.join()
    supervisord_thread.join()
    worker_thread.join()
    ping_server_thread.join()
