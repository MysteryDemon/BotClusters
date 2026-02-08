let socket;
let updateInterval;
let reconnectAttempts = 0;
const MAX_RECONNECT_ATTEMPTS = 5;

// Keep a reference to the last known process list so cards never disappear
let lastKnownProcesses = [];

document.addEventListener('DOMContentLoaded', function () {
    socket = io({
        reconnection: true,
        reconnectionDelay: 1000,
        reconnectionDelayMax: 5000,
        reconnectionAttempts: MAX_RECONNECT_ATTEMPTS
    });

    socket.on('connect', function () {
        console.log('Connected to server');
        reconnectAttempts = 0;
        requestStatus();
        if (updateInterval) clearInterval(updateInterval);
        updateInterval = setInterval(requestStatus, 3000);
    });

    socket.on('disconnect', function () {
        console.log('Disconnected from server');
        if (updateInterval) clearInterval(updateInterval);
    });

    socket.on('connect_error', function (error) {
        console.error('Connection error:', error);
        reconnectAttempts++;
        if (reconnectAttempts >= MAX_RECONNECT_ATTEMPTS) {
            console.error('Max reconnection attempts reached');
        }
    });

    socket.on('status_update', function (data) {
        if (data.processes && Array.isArray(data.processes) && data.processes.length > 0) {
            lastKnownProcesses = data.processes;
            updateBotCards(data.processes);
        } else if (lastKnownProcesses.length > 0) {
            // Don't wipe the grid – reuse last known data
            updateBotCards(lastKnownProcesses);
        }
    });

    // Modal handling
    const modal = document.getElementById('log-modal');
    const span = modal ? modal.querySelector('.close') : null;
    if (span) {
        span.onclick = function () { modal.style.display = 'none'; };
    }
    window.onclick = function (event) {
        if (event.target === modal) modal.style.display = 'none';
        const cronModal = document.getElementById('cron-modal');
        if (event.target === cronModal) cronModal.style.display = 'none';
    };

    // Load current cron setting
    loadCronSetting();
});

function requestStatus() {
    if (socket && socket.connected) {
        socket.emit('request_status');
    } else {
        socket.connect();
    }
}

function getBotNumber(processName) {
    const match = processName.match(/bot(\d+)$/i);
    return match ? parseInt(match[1]) : null;
}

function sortProcesses(processes) {
    return processes.sort((a, b) => {
        const numA = getBotNumber(a.name) || 0;
        const numB = getBotNumber(b.name) || 0;
        return numA - numB;
    });
}

function formatBotName(processName) {
    const botNumber = getBotNumber(processName);
    return botNumber ? `Bot #${botNumber}` : processName;
}

function updateBotCards(processes) {
    const botGrid = document.getElementById('bot-grid');
    if (!botGrid) return;

    const sorted = sortProcesses(processes);

    // Stats
    let online = 0, offline = 0, paused = 0;

    botGrid.innerHTML = '';

    sorted.forEach((process) => {
        const isRunning = process.status === 'RUNNING';
        const isPaused = process.paused;
        const isAutoPaused = process.auto_paused;
        const isFatal = process.status === 'FATAL' || process.status === 'BACKOFF';

        if (isRunning && !isPaused && !isAutoPaused) online++;
        else if (isPaused || isAutoPaused) paused++;
        else offline++;

        const displayName = formatBotName(process.name);
        const now = new Date();
        const utcTime = now.toISOString().replace('T', ' ').slice(0, 19);

        let statusClass, statusLabel;
        if (isAutoPaused) {
            statusClass = 'status-fatal';
            statusLabel = 'Failed';
        } else if (isPaused) {
            statusClass = 'status-paused';
            statusLabel = 'Paused';
        } else if (isRunning) {
            statusClass = 'status-online';
            statusLabel = 'Online';
        } else {
            statusClass = 'status-offline';
            statusLabel = 'Offline';
        }

        const card = document.createElement('div');
        card.className = 'bot-card' + (isAutoPaused ? ' card-fatal' : '');

        let controlsHTML = '';
        if (isAutoPaused) {
            // Show a "Clear Failure" button for auto-paused bots
            controlsHTML = `
                <button onclick="clearFailure('${process.name}')" class="control-btn clear-btn">Clear &amp; Restart</button>
                <button onclick="viewLogs('${process.name}')" class="control-btn log-btn">Logs</button>
            `;
        } else {
            controlsHTML = `
                <button onclick="toggleBot('${process.name}', '${process.status}')"
                        class="control-btn ${isRunning ? 'stop-btn' : 'start-btn'}">
                    ${isRunning ? 'Stop' : 'Start'}
                </button>
                <button onclick="restartBot('${process.name}')"
                        class="control-btn restart-btn" ${!isRunning ? 'disabled' : ''}>
                    Restart
                </button>
                <button onclick="${isPaused ? `resumeBot('${process.name}')` : `pauseBot('${process.name}')`}"
                        class="control-btn pause-btn" ${!isRunning ? 'disabled' : ''}>
                    ${isPaused ? 'Resume' : 'Pause'}
                </button>
                <button onclick="viewLogs('${process.name}')" class="control-btn log-btn">Logs</button>
            `;
        }

        card.innerHTML = `
            <div class="bot-header">
                <h2>${displayName}</h2>
                <span class="bot-status ${statusClass}">${statusLabel}</span>
            </div>
            <div class="bot-info">
                <p><strong>Process:</strong> ${process.name}</p>
                <p><strong>Status:</strong> ${process.status}</p>
                <p><strong>PID:</strong> ${process.pid || 'N/A'}</p>
                <p><strong>Uptime:</strong> ${process.uptime || '0:00:00'}</p>
                <p><strong>Updated:</strong> ${utcTime}</p>
            </div>
            <div class="bot-controls">${controlsHTML}</div>
        `;

        botGrid.appendChild(card);
    });

    // Update header stats
    const el = (id) => document.getElementById(id);
    if (el('stat-online')) el('stat-online').textContent = online;
    if (el('stat-offline')) el('stat-offline').textContent = offline;
    if (el('stat-paused')) el('stat-paused').textContent = paused;
    if (el('bot-count-badge')) el('bot-count-badge').textContent = `${sorted.length} bot${sorted.length !== 1 ? 's' : ''}`;
}

// ── Bot actions ──────────────────────────────────────────

function toggleBot(processName, currentStatus) {
    const action = currentStatus === 'RUNNING' ? 'stop' : 'start';
    if (action === 'stop') {
        if (!confirm(`Stop ${formatBotName(processName)}?`)) return;
    }
    fetch(`/supervisor/${action}/${processName}`, { method: 'POST' })
        .then(r => r.json())
        .then(data => {
            if (data.status === 'success') setTimeout(requestStatus, 1000);
            else alert(`Error: ${data.message}`);
        })
        .catch(() => alert(`Failed to ${action} the process.`));
}

function restartBot(processName) {
    if (!confirm(`Restart ${formatBotName(processName)}?`)) return;
    fetch(`/supervisor/restart/${processName}`, { method: 'POST' })
        .then(r => r.json())
        .then(data => {
            if (data.status === 'success') setTimeout(requestStatus, 2000);
            else alert(`Error: ${data.message}`);
        })
        .catch(() => alert('Failed to restart the process.'));
}

function pauseBot(processName) {
    fetch(`/supervisor/pause/${processName}`, { method: 'POST' })
        .then(r => r.json())
        .then(data => {
            if (data.status === 'success') setTimeout(requestStatus, 1000);
            else alert(`Error: ${data.message}`);
        });
}

function resumeBot(processName) {
    fetch(`/supervisor/resume/${processName}`, { method: 'POST' })
        .then(r => r.json())
        .then(data => {
            if (data.status === 'success') setTimeout(requestStatus, 1000);
            else alert(`Error: ${data.message}`);
        });
}

function clearFailure(processName) {
    fetch(`/supervisor/clear_failure/${processName}`, { method: 'POST' })
        .then(r => r.json())
        .then(data => {
            if (data.status === 'success') setTimeout(requestStatus, 1500);
            else alert(`Error: ${data.message}`);
        })
        .catch(() => alert('Failed to clear failure state.'));
}

function viewLogs(processName) {
    fetch(`/supervisor/log/${processName}`)
        .then(response => {
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            return response.blob();
        })
        .then(blob => {
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.style.display = 'none';
            a.href = url;
            a.download = `${processName}_log.txt`;
            document.body.appendChild(a);
            a.click();
            window.URL.revokeObjectURL(url);
            document.body.removeChild(a);
        })
        .catch(() => alert('Failed to fetch logs.'));
}

// ── Cron modal ───────────────────────────────────────────

function openCronModal() {
    document.getElementById('cron-modal').style.display = 'block';
}

function closeCronModal() {
    document.getElementById('cron-modal').style.display = 'none';
}

function loadCronSetting() {
    fetch('/config/cron')
        .then(r => r.json())
        .then(data => {
            if (data.hours !== undefined) {
                document.getElementById('cron-hours').value = data.hours;
            }
        })
        .catch(() => { });
}

function saveCron() {
    const hours = parseInt(document.getElementById('cron-hours').value) || 0;
    fetch('/config/cron', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ hours: hours })
    })
        .then(r => r.json())
        .then(data => {
            if (data.status === 'success') {
                closeCronModal();
            } else {
                alert('Failed to save cron setting.');
            }
        })
        .catch(() => alert('Failed to save cron setting.'));
}

// ── Visibility handling ──────────────────────────────────

document.addEventListener('visibilitychange', function () {
    if (document.hidden) {
        if (updateInterval) clearInterval(updateInterval);
    } else {
        requestStatus();
        updateInterval = setInterval(requestStatus, 3000);
    }
});

window.onbeforeunload = function () {
    if (socket) socket.disconnect();
    if (updateInterval) clearInterval(updateInterval);
};
