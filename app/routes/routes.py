import eventlet
eventlet.monkey_patch()

import os
import json
import signal
import subprocess
import re
from datetime import datetime
from functools import wraps
from pathlib import Path
import logging
import time
import threading
import configparser
from collections import defaultdict

from app import app
from flask import (
    Flask, render_template, request, jsonify, Response,
    send_file, abort, redirect, url_for, session, flash, stream_with_context
)
from flask_socketio import SocketIO, emit

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename='app.log'
)
logger = logging.getLogger(__name__)
logging.getLogger('socketio').setLevel(logging.DEBUG)
logging.getLogger('engineio').setLevel(logging.DEBUG)

app.config['SECRET_KEY'] = os.urandom(24)

socketio = SocketIO(
    app,
    async_mode='eventlet',
    cors_allowed_origins="*",
    ping_timeout=60,
    ping_interval=25
)

SUPERVISOR_LOG_DIR = "/var/log/supervisor"
SUPERVISORD_CONF_DIR = "/etc/supervisor/conf.d"
STATUS_CHECK_INTERVAL = 2
MAX_STATUS_CHECK_ATTEMPTS = 10
TEMP_SUPERVISOR_CONFIGS = {}

# Track consecutive failures per process for auto-pause
FAILURE_COUNTS = defaultdict(int)
MAX_FAILURES_BEFORE_PAUSE = 5
PAUSED_BY_SYSTEM = set()

# Cronjob restart interval (in hours), 0 = disabled
CRON_RESTART_INTERVAL = int(os.environ.get('CRON_RESTART_HOURS', 0))
_cron_thread = None

def parse_supervisor_status(status_line):
    try:
        parts = status_line.strip().split()
        if len(parts) >= 2:
            name = parts[0]
            status = parts[1]
            pid_match = re.search(r'pid (\d+)', status_line)
            uptime_match = re.search(r'uptime ([\d:]+)', status_line)
            pid = pid_match.group(1) if pid_match else None
            paused = False
            
            if pid and is_process_paused(pid):
                paused = True
            
            return {
                "name": name,
                "status": status,
                "pid": pid_match.group(1) if pid_match else None,
                "uptime": uptime_match.group(1) if uptime_match else "0:00:00",
                "paused": paused
            }
    except Exception as e:
        logger.error(f"Error parsing supervisor status line: {e}")
    return None

def pause_process(process_name):
    result = run_supervisor_command("status", process_name)
    if result["status"] == "success":
        proc = parse_supervisor_status(result["message"])
        if proc and proc["pid"]:
            try:
                os.kill(int(proc["pid"]), signal.SIGSTOP)
                return {"status": "success", "message": f"Paused process {process_name}"}
            except Exception as e:
                logger.error(f"Error pausing process {process_name}: {e}")
                return {"status": "error", "message": str(e)}
    return {"status": "error", "message": "Process not running or PID not found"}

@app.route('/supervisor/pause/<process_name>', methods=['POST'])
def pause_supervisor_process(process_name):
    logger.info(f"Received pause request for process: {process_name}")
    result = pause_process(process_name)
    if result["status"] == "success":
        broadcast_status_update()
        return jsonify(result), 200
    else:
        return jsonify(result), 500

@app.route('/supervisor/resume/<process_name>', methods=['POST'])
def resume_supervisor_process(process_name):
    logger.info(f"Received resume request for process: {process_name}")
    result = resume_process(process_name)
    if result["status"] == "success":
        broadcast_status_update()
        return jsonify(result), 200
    else:
        return jsonify(result), 500

def is_process_paused(pid):
    try:
        with open(f"/proc/{pid}/status") as f:
            for line in f:
                if line.startswith("State:") and "\tT" in line:
                    return True
    except Exception:
        pass
    return False

def resume_process(process_name):
    result = run_supervisor_command("status", process_name)
    if result["status"] == "success":
        proc = parse_supervisor_status(result["message"])
        if proc and proc["pid"]:
            try:
                os.kill(int(proc["pid"]), signal.SIGCONT)
                return {"status": "success", "message": f"Resumed process {process_name}"}
            except Exception as e:
                logger.error(f"Error resuming process {process_name}: {e}")
                return {"status": "error", "message": str(e)}
    return {"status": "error", "message": "Process not running or PID not found"}

def run_supervisor_command(command, process_name=None, timeout=30):
    try:
        cmd = ["supervisorctl"]
        if command:
            cmd.append(command)
        if process_name:
            cmd.append(process_name)

        logger.info(f"Executing supervisor command: {' '.join(cmd)}")
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout
        )

        if result.stdout:
            logger.info(f"Command output: {result.stdout.strip()}")
        if result.stderr:
            logger.error(f"Command error: {result.stderr.strip()}")

        if result.returncode == 0:
            return {"status": "success", "message": result.stdout.strip()}
        else:
            return {"status": "error", "message": result.stderr.strip()}

    except subprocess.TimeoutExpired:
        logger.error(f"Command timed out after {timeout} seconds")
        return {"status": "error", "message": f"Command timed out after {timeout} seconds"}
    except Exception as e:
        logger.error(f"Error executing supervisor command: {str(e)}")
        return {"status": "error", "message": str(e)}

def verify_process_status(process_name, expected_status=None):
    try:
        result = run_supervisor_command("status", process_name)
        if result["status"] == "success":
            if expected_status:
                return expected_status in result["message"]
            return result["message"]
        return None
    except Exception as e:
        logger.error(f"Error verifying process status: {str(e)}")
        return None
        
def broadcast_status_update():
    try:
        with app.app_context():
            status = run_supervisor_command("status")
            if status["status"] == "success":
                processes = []
                for proc_line in status["message"].splitlines():
                    parsed = parse_supervisor_status(proc_line)
                    if parsed:
                        # Track failures: if FATAL or BACKOFF, increment counter
                        pname = parsed["name"]
                        if parsed["status"] in ("FATAL", "BACKOFF", "EXITED"):
                            FAILURE_COUNTS[pname] += 1
                            if FAILURE_COUNTS[pname] >= MAX_FAILURES_BEFORE_PAUSE and pname not in PAUSED_BY_SYSTEM:
                                logger.warning(f"Process {pname} has failed {FAILURE_COUNTS[pname]} times, auto-pausing")
                                PAUSED_BY_SYSTEM.add(pname)
                                parsed["auto_paused"] = True
                            elif pname in PAUSED_BY_SYSTEM:
                                parsed["auto_paused"] = True
                            else:
                                parsed["auto_paused"] = False
                        else:
                            # Reset failure count on healthy status
                            if parsed["status"] == "RUNNING":
                                FAILURE_COUNTS[pname] = 0
                                if pname in PAUSED_BY_SYSTEM:
                                    PAUSED_BY_SYSTEM.discard(pname)
                            parsed["auto_paused"] = pname in PAUSED_BY_SYSTEM
                        processes.append(parsed)
                
                socketio.emit('status_update', {
                    "status": "success",
                    "processes": processes,
                    "timestamp": datetime.utcnow().isoformat()
                }, broadcast=True)
                
                return True
    except Exception as e:
        logger.error(f"Error broadcasting status update: {str(e)}")
        return False

def update_process_code(process_name, config_content=None):
    try:
        if config_content:
            config = configparser.ConfigParser()
            config.read_string(config_content)
            section = 'program:' + process_name
            if section in config:
                directory = config[section].get('directory')
                if directory and Path(directory).exists():
                    subprocess.run(['git', 'pull'], cwd=directory, check=True)
                    logger.info(f"Updated code for {process_name} in {directory}")
                else:
                    logger.warning(f"No valid directory found for {process_name}")
        else:
            config_path = Path(SUPERVISORD_CONF_DIR) / f"{process_name.replace(' ', '_')}.conf"
            if config_path.exists():
                config = configparser.ConfigParser()
                config.read(config_path)
                section = 'program:' + process_name
                if section in config:
                    directory = config[section].get('directory')
                    if directory and Path(directory).exists():
                        subprocess.run(['git', 'pull'], cwd=directory, check=True)
                        logger.info(f"Updated code for {process_name} in {directory}")
                    else:
                        logger.warning(f"No valid directory found for {process_name}")
    except Exception as e:
        logger.error(f"Error updating code for {process_name}: {str(e)}")

users = {
    "admin": "password123",
    "newuser": "newpassword"
}

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        if username in users and users[username] == password:
            session['logged_in'] = True
            return redirect(url_for('cluster'))
        else:
            flash('Invalid credentials. Please try again.')
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    return redirect(url_for('login'))

@app.route('/')
@login_required
def cluster():
    return render_template('cluster.html')

@app.route('/supervisor/status', methods=['GET'])
def list_supervisor_processes():
    status = run_supervisor_command("status")
    if status["status"] == "success":
        processes = []
        for line in status["message"].splitlines():
            process = parse_supervisor_status(line)
            if process:
                processes.append(process)
        return jsonify({"status": "success", "processes": processes}), 200
    return jsonify(status), 500

@socketio.on('connect')
def handle_connect():
    logger.info("Client connected")
    emit('connected', {'data': 'Connected'})
    broadcast_status_update()

@socketio.on('disconnect')
def handle_disconnect():
    logger.info("Client disconnected")

@socketio.on('request_status')
def handle_status_request():
    try:
        status = run_supervisor_command("status")
        if status["status"] == "success":
            processes = []
            for proc in status["message"].splitlines():
                parsed_proc = parse_supervisor_status(proc)
                if parsed_proc:
                    pname = parsed_proc["name"]
                    if parsed_proc["status"] in ("FATAL", "BACKOFF", "EXITED"):
                        FAILURE_COUNTS[pname] += 1
                        if FAILURE_COUNTS[pname] >= MAX_FAILURES_BEFORE_PAUSE:
                            PAUSED_BY_SYSTEM.add(pname)
                        parsed_proc["auto_paused"] = pname in PAUSED_BY_SYSTEM
                    else:
                        if parsed_proc["status"] == "RUNNING":
                            FAILURE_COUNTS[pname] = 0
                            PAUSED_BY_SYSTEM.discard(pname)
                        parsed_proc["auto_paused"] = pname in PAUSED_BY_SYSTEM
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

@app.route('/supervisor/<action>/<process_name>', methods=['POST'])
def manage_supervisor_process(action, process_name):
    logger.info(f"Received {action} request for process: {process_name}")
    
    if action not in ["start", "stop", "restart"]:
        return jsonify({"status": "error", "message": "Invalid action"}), 400
    
    if not re.match(r'^[a-zA-Z0-9_\- ]+$', process_name):
        return jsonify({"status": "error", "message": "Invalid process name"}), 400
    
    try:
        initial_status = verify_process_status(process_name)
        if initial_status is None:
            return jsonify({
                "status": "error", 
                "message": f"Process {process_name} not found"
            }), 404
        
        config_path = Path(SUPERVISORD_CONF_DIR) / f"{process_name.replace(' ', '_')}.conf"
        
        if action == "stop":
            if "RUNNING" not in initial_status:
                return jsonify({
                    "status": "error",
                    "message": f"Process {process_name} is not running"
                }), 400
                
            result = run_supervisor_command("stop", process_name)
            expected_status = "STOPPED"
            
            if result["status"] == "success":
                try:
                    if config_path.exists():
                        with open(config_path, 'r') as f:
                            TEMP_SUPERVISOR_CONFIGS[process_name] = f.read()
                            
                        config_path.unlink()
                        logger.info(f"Saved and removed supervisor config for {process_name}")
                        subprocess.run(["supervisorctl", "reread"], check=True)
                        subprocess.run(["supervisorctl", "update"], check=True)
                        
                except Exception as e:
                    logger.error(f"Error handling supervisor config for {process_name}: {e}")
            
        elif action == "start":
            try:
                if process_name in TEMP_SUPERVISOR_CONFIGS:
                    config_content = TEMP_SUPERVISOR_CONFIGS[process_name]
                    update_process_code(process_name, config_content)
                    with open(config_path, 'w') as f:
                        f.write(config_content)
                    subprocess.run(["supervisorctl", "reread"], check=True)
                    subprocess.run(["supervisorctl", "update"], check=True)
                    del TEMP_SUPERVISOR_CONFIGS[process_name]
                else:
                    update_process_code(process_name)
                
                result = run_supervisor_command("start", process_name)
                expected_status = "RUNNING"
                
            except Exception as e:
                logger.error(f"Error restoring supervisor config for {process_name}: {e}")
                return jsonify({
                    "status": "error",
                    "message": f"Error restoring configuration: {str(e)}"
                }), 500
            
        elif action == "restart":
            try:
                thoroughly_cleanup(process_name)
                delete_supervisor_logs(process_name)
                if config_path.exists():
                    with open(config_path, 'r') as f:
                        config_content = f.read()
                    
                    result = run_supervisor_command("stop", process_name)
                    if result["status"] == "success":
                        config_path.unlink()
                        subprocess.run(["supervisorctl", "reread"], check=True)
                        subprocess.run(["supervisorctl", "update"], check=True)
                        time.sleep(2)
                        update_process_code(process_name, config_content)
                        with open(config_path, 'w') as f:
                            f.write(config_content)
                        subprocess.run(["supervisorctl", "reread"], check=True)
                        subprocess.run(["supervisorctl", "update"], check=True)
                        result = run_supervisor_command("start", process_name)
                        expected_status = "RUNNING"
                        
                else:
                    return jsonify({
                        "status": "error",
                        "message": f"Config file not found for {process_name}"
                    }), 404
                    
            except Exception as e:
                logger.error(f"Error during restart process for {process_name}: {e}")
                return jsonify({
                    "status": "error",
                    "message": f"Error during restart: {str(e)}"
                }), 500
        
        if result["status"] != "success":
            return jsonify(result), 500
        for _ in range(MAX_STATUS_CHECK_ATTEMPTS):
            time.sleep(STATUS_CHECK_INTERVAL)
            current_status = verify_process_status(process_name)
            
            if action == "stop" and current_status is None:
                broadcast_status_update()
                return jsonify({
                    "status": "success",
                    "message": f"Successfully stopped {process_name}"
                }), 200
            
            if current_status and expected_status in current_status:
                broadcast_status_update()
                return jsonify({
                    "status": "success",
                    "message": f"Successfully {action}ed {process_name}"
                }), 200
                
        return jsonify({
            "status": "error",
            "message": f"Process did not reach {expected_status} state after {action}"
        }), 500
            
    except Exception as e:
        logger.error(f"Error managing process {process_name}: {str(e)}")
        return jsonify({
            "status": "error",
            "message": f"Error managing process: {str(e)}"
        }), 500

@app.route('/supervisor/log/<process_name>', methods=['GET'])
def download_supervisor_log(process_name):
    try:
        if not re.match(r'^[a-zA-Z0-9_\- ]+$', process_name):
            return jsonify({"status": "error", "message": "Invalid process name"}), 400
        
        stdout_log = Path(SUPERVISOR_LOG_DIR) / f"{process_name}_out.log"
        stderr_log = Path(SUPERVISOR_LOG_DIR) / f"{process_name}_err.log"
        combined_log = Path(SUPERVISOR_LOG_DIR) / f"{process_name}_combined.log"
        
        if stdout_log.exists() or stderr_log.exists():
            with combined_log.open('w') as outfile:
                outfile.write(f"=== Combined logs for {process_name} ===\n")
                outfile.write(f"Generated at: {datetime.utcnow().isoformat()}\n\n")
                
                if stdout_log.exists():
                    outfile.write("=== STDOUT LOG ===\n")
                    with stdout_log.open('r') as f:
                        outfile.write(f.read())
                    outfile.write("\n\n")
                
                if stderr_log.exists():
                    outfile.write("=== STDERR LOG ===\n")
                    with stderr_log.open('r') as f:
                        outfile.write(f.read())
            
            return send_file(
                str(combined_log),
                mimetype='text/plain',
                as_attachment=True,
                download_name=f"{process_name}_combined.log"
            )
        else:
            return jsonify({
                "status": "error",
                "message": "No log files found for this process"
            }), 404
            
    except Exception as e:
        logger.error(f"Error accessing log files for {process_name}: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.errorhandler(Exception)
def handle_error(e):
    logger.error(f"Unhandled error: {str(e)}")
    return jsonify({
        "status": "error",
        "message": "An internal server error occurred"
    }), 500

def delete_supervisor_logs(process_name):
    try:
        stdout_log = Path(SUPERVISOR_LOG_DIR) / f"{process_name}_out.log"
        stderr_log = Path(SUPERVISOR_LOG_DIR) / f"{process_name}_err.log"
        combined_log = Path(SUPERVISOR_LOG_DIR) / f"{process_name}_combined.log"
        for log_file in [stdout_log, stderr_log, combined_log]:
            if log_file.exists():
                log_file.unlink()
                logger.info(f"Deleted log file: {log_file}")
    except Exception as e:
        logger.error(f"Error deleting logs for {process_name}: {e}")

def thoroughly_cleanup(process_name):
    subprocess.run(f"pkill -f {process_name}", shell=True)
    directory = None
    config_path = Path(SUPERVISORD_CONF_DIR) / f"{process_name.replace(' ', '_')}.conf"
    if config_path.exists():
        config = configparser.ConfigParser()
        config.read(config_path)
        section = 'program:' + process_name
        if section in config:
            directory = config[section].get('directory')
    if directory and Path(directory).exists():
        for root, dirs, files in os.walk(directory):
            for d in dirs:
                if d == '__pycache__':
                    pycache_dir = Path(root) / d
                    for file in pycache_dir.glob('*.pyc'):
                        file.unlink()
                    pycache_dir.rmdir()
            for f in files:
                if f.endswith('.pyc'):
                    (Path(root) / f).unlink()


# ── Log Stream ──────────────────────────────────────────────────
@app.route('/logstream')
@login_required
def logstream_page():
    return render_template('logstream.html')


@app.route('/logstream/stream')
@login_required
def logstream_sse():
    """Stream all supervisor stdout/stderr logs as Server-Sent Events."""
    def generate():
        log_dir = Path(SUPERVISOR_LOG_DIR)
        # Track file positions
        positions = {}
        while True:
            for log_file in sorted(log_dir.glob("*.log")):
                if '_combined' in log_file.name:
                    continue
                try:
                    pos = positions.get(log_file.name, 0)
                    size = log_file.stat().st_size
                    if size < pos:
                        pos = 0  # file was truncated / rotated
                    if size > pos:
                        with log_file.open('r', errors='replace') as fh:
                            fh.seek(pos)
                            new_data = fh.read()
                            positions[log_file.name] = fh.tell()
                        if new_data.strip():
                            payload = json.dumps({
                                "file": log_file.name,
                                "data": new_data
                            })
                            yield f"data: {payload}\n\n"
                except Exception:
                    pass
            eventlet.sleep(1)

    return Response(
        stream_with_context(generate()),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no',
        }
    )


# ── Cronjob Restart Config ──────────────────────────────────────
@app.route('/config/cron', methods=['GET', 'POST'])
@login_required
def config_cron():
    global CRON_RESTART_INTERVAL, _cron_thread
    if request.method == 'POST':
        data = request.get_json(silent=True) or {}
        hours = int(data.get('hours', 0))
        CRON_RESTART_INTERVAL = max(0, hours)
        os.environ['CRON_RESTART_HOURS'] = str(CRON_RESTART_INTERVAL)
        # Restart the cron thread with new interval
        _start_cron_thread()
        return jsonify({"status": "success", "hours": CRON_RESTART_INTERVAL})
    return jsonify({"status": "success", "hours": CRON_RESTART_INTERVAL})


@app.route('/supervisor/clear_failure/<process_name>', methods=['POST'])
@login_required
def clear_failure(process_name):
    """Clear the auto-pause / failure state for a process so it can run again."""
    FAILURE_COUNTS[process_name] = 0
    PAUSED_BY_SYSTEM.discard(process_name)
    # Attempt to start it again via supervisor
    run_supervisor_command("start", process_name)
    broadcast_status_update()
    return jsonify({"status": "success", "message": f"Cleared failure state for {process_name}"})


def _cron_restart_loop():
    """Background loop that restarts all supervisor processes on schedule."""
    while True:
        interval = CRON_RESTART_INTERVAL
        if interval <= 0:
            eventlet.sleep(60)  # check back every minute
            continue
        logger.info(f"Cron restart: sleeping for {interval} hours")
        eventlet.sleep(interval * 3600)
        if CRON_RESTART_INTERVAL <= 0:
            continue
        logger.info("Cron restart: restarting all processes")
        try:
            run_supervisor_command("restart", "all")
            broadcast_status_update()
        except Exception as e:
            logger.error(f"Cron restart error: {e}")


def _start_cron_thread():
    global _cron_thread
    if _cron_thread is None or not _cron_thread:
        _cron_thread = eventlet.spawn(_cron_restart_loop)


def _auto_delete_logs_loop():
    """Background loop that deletes all supervisor logs every 24 hours."""
    while True:
        eventlet.sleep(24 * 3600)
        logger.info("Auto log cleanup: deleting all supervisor logs")
        try:
            log_dir = Path(SUPERVISOR_LOG_DIR)
            deleted = 0
            for log_file in log_dir.glob("*.log"):
                try:
                    log_file.unlink()
                    deleted += 1
                except Exception as e:
                    logger.error(f"Failed to delete {log_file}: {e}")
            logger.info(f"Auto log cleanup: deleted {deleted} log files")
        except Exception as e:
            logger.error(f"Auto log cleanup error: {e}")


_log_cleanup_thread = None

def _start_log_cleanup_thread():
    global _log_cleanup_thread
    if _log_cleanup_thread is None or not _log_cleanup_thread:
        _log_cleanup_thread = eventlet.spawn(_auto_delete_logs_loop)


# Start background threads on import
_start_cron_thread()
_start_log_cleanup_thread()
