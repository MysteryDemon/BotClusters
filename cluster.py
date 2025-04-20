import subprocess
import threading
import time
import os

def run_update():
    subprocess.run(["python3", "update.py"])

def run_gunicorn():
    port = os.environ.get("PORT", 5000)
    subprocess.run(["gunicorn", "-w", "1", "-k", "eventlet", "-b", f"0.0.0.0:{os.environ.get('PORT', '5000')}", "run:app"], check=True)

def run_supervisord():
    subprocess.run(["supervisord", "-n", "-c", "/etc/supervisor/supervisord.conf"])

def run_worker():
    subprocess.run(["python3", "worker.py"])

def run_ping_server():
    subprocess.run(["python3", "ping_server.py"])

if __name__ == "__main__":
    update_thread = threading.Thread(target=run_update)
    update_thread.start()
    update_thread.join()
    time.sleep(2)

    gunicorn_thread = threading.Thread(target=run_gunicorn)
    supervisord_thread = threading.Thread(target=run_supervisord)
    worker_thread = threading.Thread(target=run_worker)
    ping_server_thread = threading.Thread(target=run_ping_server)

    gunicorn_thread.start()
    supervisord_thread.start()
    worker_thread.start()
    ping_server_thread.start()

    gunicorn_thread.join()
    supervisord_thread.join()
    worker_thread.join()
    ping_server_thread.join()
