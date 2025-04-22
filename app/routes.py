import eventlet
eventlet.monkey_patch()

import os
import subprocess
import re
from datetime import datetime
from functools import wraps
from pathlib import Path
import logging
import time
import configparser

from app import app
from flask import (
    Flask, render_template, request, jsonify,
    send_file, abort, redirect, url_for, session, flash
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

def parse_supervisor_status(status_line):
    try:
        parts = status_line.strip().split()
        if len(parts) >= 2:
            name = parts[0]
            status = parts[1]
            pid_match = re.search(r'pid (\d+)', status_line)
            uptime_match = re.search(r'uptime ([\d:]+)', status_line)
            
            return {
                "name": name,
                "status": status,
                "pid": pid_match.group(1) if pid_match else None,
                "uptime": uptime_match.group(1) if uptime_match else "0:00:00"
            }
    except Exception as e:
        logger.error(f"Error parsing supervisor status line: {e}")
    return None

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
                processes = [
                    parse_supervisor_status(proc) 
                    for proc in status["message"].splitlines() 
                    if parse_supervisor_status(proc)
                ]
                
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
