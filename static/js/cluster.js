let socket;
let updateInterval;
let reconnectAttempts = 0;
const MAX_RECONNECT_ATTEMPTS = 5;

document.addEventListener('DOMContentLoaded', function() {
    // Initialize Socket.IO with reconnection options
    socket = io({
        reconnection: true,
        reconnectionDelay: 1000,
        reconnectionDelayMax: 5000,
        reconnectionAttempts: MAX_RECONNECT_ATTEMPTS
    });
    
    socket.on('connect', function() {
        console.log('Connected to server');
        reconnectAttempts = 0;
        requestStatus();
        
        // Set up periodic status updates
        if (updateInterval) clearInterval(updateInterval);
        updateInterval = setInterval(requestStatus, 5000); // Update every 5 seconds
    });

    socket.on('disconnect', function() {
        console.log('Disconnected from server');
        if (updateInterval) clearInterval(updateInterval);
    });

    socket.on('connect_error', function(error) {
        console.error('Connection error:', error);
        reconnectAttempts++;
        if (reconnectAttempts >= MAX_RECONNECT_ATTEMPTS) {
            console.error('Max reconnection attempts reached');
            alert('Connection to server lost. Please refresh the page.');
        }
    });

    socket.on('status_update', function(data) {
        console.log('Received status update:', data);
        if (data.processes && Array.isArray(data.processes)) {
            updateBotCards(data.processes);
        } else {
            console.error('Invalid status update data:', data);
        }
    });

    // Modal handling
    const modal = document.getElementById('log-modal');
    const span = document.getElementsByClassName('close')[0];
    
    if (span) {
        span.onclick = function() {
            modal.style.display = "none";
        }
    }

    window.onclick = function(event) {
        if (event.target == modal) {
            modal.style.display = "none";
        }
    }

    // Theme toggle handling
    const toggleButton = document.getElementById('theme-toggle');
    const body = document.body;
    const header = document.querySelector('.header');

    // Check for saved mode in localStorage
    const savedMode = localStorage.getItem('theme-mode');
    if (savedMode) {
        body.classList.add(savedMode);
        header.classList.add(savedMode);
    }

    toggleButton.addEventListener('click', function() {
        if (body.classList.contains('light-mode')) {
            body.classList.replace('light-mode', 'dark-mode');
            header.classList.replace('light-mode', 'dark-mode');
            localStorage.setItem('theme-mode', 'dark-mode');
        } else {
            body.classList.replace('dark-mode', 'light-mode');
            header.classList.replace('dark-mode', 'light-mode');
            localStorage.setItem('theme-mode', 'light-mode');
        }
    });
});

function requestStatus() {
    if (socket && socket.connected) {
        socket.emit('request_status');
    } else {
        console.log('Socket not connected, attempting to reconnect...');
        socket.connect();
    }
}

function getBotNumber(processName) {
    // Extract bot number from process name
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
    return botNumber ? `Bot#${botNumber}` : processName;
}

function updateBotCards(processes) {
    const botGrid = document.getElementById('bot-grid');
    if (!botGrid) return;

    botGrid.innerHTML = '';

    // Sort processes by bot number
    const sortedProcesses = sortProcesses(processes);

    sortedProcesses.forEach((process) => {
        const botCard = document.createElement('div');
        botCard.className = 'bot-card';
        const isRunning = process.status === 'RUNNING';

        // Format the bot name using the actual bot number from the process name
        const displayName = formatBotName(process.name);

        // Get current UTC time
        const now = new Date();
        const utcTime = now.toISOString().replace('T', ' ').slice(0, 19);

        botCard.innerHTML = `
            <div class="bot-header">
                <h2>${displayName}</h2>
                <span class="bot-status ${isRunning ? 'status-online' : 'status-offline'}">
                    ${isRunning ? 'Online' : 'Offline'}
                </span>
            </div>
            <div class="bot-info">
                <p><strong>Process Name:</strong> ${process.name}</p>
                <p><strong>Status:</strong> ${process.status}</p>
                <p><strong>PID:</strong> ${process.pid || 'N/A'}</p>
                <p><strong>Uptime:</strong> ${process.uptime || '0:00:00'}</p>
                <p><strong>Last Updated:</strong> ${utcTime}</p>
            </div>
            <div class="bot-controls">
                <button onclick="toggleBot('${process.name}', '${process.status}')" 
                        class="control-btn ${isRunning ? 'stop-btn' : 'start-btn'}">
                    ${isRunning ? 'Stop' : 'Killing..'}
                </button>
                <button onclick="restartBot('${process.name}')" 
                        class="control-btn restart-btn"
                        ${!isRunning ? 'disabled' : ''}>
                    Restart
                </button>
                <button onclick="viewLogs('${process.name}')" class="control-btn log-btn">
                    View Logs
                </button>
            </div>
        `;

        botGrid.appendChild(botCard);
    });
}

function toggleBot(processName, currentStatus) {
    const action = currentStatus === 'RUNNING' ? 'stop' : 'start';
    fetch(`/supervisor/${action}/${processName}`, {
        method: 'POST'
    })
    .then(response => response.json())
    .then(data => {
        if (data.status === 'success') {
            // Add a small delay before requesting status
            setTimeout(requestStatus, 1000);
        } else {
            console.error('Error:', data.message);
            alert(`Error: ${data.message}`);
        }
    })
    .catch(error => {
        console.error('Error:', error);
        alert(`An error occurred while trying to ${action} the process.`);
    });
}

function restartBot(processName) {
    const confirmed = confirm(`Are you sure you want to restart ${formatBotName(processName)}?`);
    if (!confirmed) return;

    fetch(`/supervisor/restart/${processName}`, {
        method: 'POST'
    })
    .then(response => response.json())
    .then(data => {
        if (data.status === 'success') {
            // Add a small delay before requesting status
            setTimeout(requestStatus, 2000);
        } else {
            console.error('Error:', data.message);
            alert(`Error: ${data.message}`);
        }
    })
    .catch(error => {
        console.error('Error:', error);
        alert('An error occurred while trying to restart the process.');
    });
}

function viewLogs(processName) {
    fetch(`/supervisor/log/${processName}`)
    .then(response => {
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
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
    .catch(error => {
        console.error('Error:', error);
        alert('An error occurred while trying to fetch the logs.');
    });
}

// Handle page visibility changes
document.addEventListener('visibilitychange', function() {
    if (document.hidden) {
        if (updateInterval) clearInterval(updateInterval);
    } else {
        requestStatus();
        updateInterval = setInterval(requestStatus, 5000);
    }
});

// Clean up when the page is closed
window.onbeforeunload = function() {
    if (socket) socket.disconnect();
    if (updateInterval) clearInterval(updateInterval);
};
