import subprocess
import threading

def run_app():
    subprocess.run(["python3", "app.py"])

def run_ping_server():
    subprocess.run(["python3", "ping_server.py"])

def run_worker():
    subprocess.run(["python3", "worker.py"])

def run_supervisord():
    subprocess.run(["/usr/bin/supervisord", "-n", "-c", "/etc/supervisor/supervisord.conf"])

if __name__ == "__main__":
    supervisord_thread = threading.Thread(target=run_supervisord)
    app_thread = threading.Thread(target=run_app)
    ping_server_thread = threading.Thread(target=run_ping_server)
    worker_thread = threading.Thread(target=run_worker)

    supervisord_thread.start()
    app_thread.start()
    ping_server_thread.start()
    worker_thread.start()

    supervisord_thread.join()
    app_thread.join()
    ping_server_thread.join()
    worker_thread.join()
