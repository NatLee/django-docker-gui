// ============================
// Utility Functions
// ============================


function getDisplayValue(value, defaultValue = 'N/A') {
    return value ? value : defaultValue;
}

const showError = (error) => {
    Swal.fire({
        title: 'Error!',
        text: error.toString(),
        icon: 'error',
        confirmButtonText: 'OK'
    }).then((result) => {
        // Redirect to login page after user clicks 'OK'
        if (result.isConfirmed || result.isDismissed) {
            window.location.href = '/login';
        }
    });
};

 function getPathSegments() {
    // This function assumes the pathname follows a specific pattern, e.g., "/api/action/containerID"
    const segments = window.location.pathname.split('/').filter(Boolean);

    // Additional checks can be added here to ensure that segments[1] and segments[2] exist
    if (segments.length < 3) {
        console.error('Unexpected pathname format:', window.location.pathname);
        return { action: null, containerID: null };
    }

    return {
        action: segments[1],
        containerID: segments[2],
    };
}

// ============================
// Fetch and Display Data
// ============================

async function loadConsoleData(containerID, action) {
    try {
        // Retrieve the JWT from local storage
        const accessToken = localStorage.getItem('accessToken');

        // Include the JWT in the authorization header
        const response = await fetch(`/api/console/${action}/${containerID}`, {
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${accessToken}`
            }
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();
        // Use the utility function to ensure no "null" values are displayed.
        const containerInfo = `Container Info: ${getDisplayValue(data.container_name)} || ${getDisplayValue(data.image)} || ${getDisplayValue(data.short_id)} || ${getDisplayValue(data.command)}`;
        document.getElementById('console-info').textContent = containerInfo;
        setupWebSocketConnection(data.id, data.action);
    } catch (error) {
        showError(error);
    }
}

// ============================
// WebSocket Connection
// ============================

function sendWebSocketMessage(action, payload) {
    if (window.socket.readyState !== WebSocket.OPEN) {
        console.error('WebSocket is not open');
        return;
    }
    window.socket.send(JSON.stringify({ action: action, payload: payload }));
}

function setupWebSocketConnection(containerID, action){
    Terminal.applyAddon(fit);
    Terminal.applyAddon(fullscreen);

    const accessToken = localStorage.getItem('accessToken');
    var ws_scheme = window.location.protocol == "https:" ? "wss" : "ws";
    var ws_path = ws_scheme + '://' + window.location.host + `/ws/console/`;

    // Token need to be encoded with base64
    const tokenInfo = `token.${btoa(accessToken)}`;
    // Create a ticket for subprotocols
    const ticket = `container.${`${containerID}`}`;
    const socket = new WebSocket(ws_path, [tokenInfo, ticket]);

    // Expose the socket object to the window
    window.socket = socket;

    const status = document.getElementById("status")

    var term = new Terminal({
        cursorBlink: true,
        fontSize: 14,
        fontFamily: 'Menlo, Monaco, "Courier New", monospace',
    });

    // Expose the terminal object to the window
    window.term = term;

    term.open(document.getElementById('terminal'));

    term.on('key', (key, ev) => {
        const isMac = navigator.platform.toUpperCase().indexOf('MAC') >= 0;
        const ctrlKey = isMac ? ev.metaKey : ev.ctrlKey;

        if (ctrlKey && key === 'c' && term.hasSelection()) {
            // Copy to clipboard
            navigator.clipboard.writeText(term.getSelection());
        } else {
            // Send other key inputs to the server
            sendWebSocketMessage("pty_input", { "input": key, "id": containerID });
        }
    });

    // Handle paste event
    term.on('paste', (data) => {
        // Using the WebSocket connection to send data
        sendWebSocketMessage("pty_input", { "input": data, "id": containerID });
    });


    // Handle incoming WebSocket messages
    socket.onmessage = function (event) {
        term.write(event.data);
    };

    socket.onopen = function () {
        console.log("WebSocket connection established");
        // Handle the connect event
        status.innerHTML = '<span style="background-color: lightgreen;">connected</span>';
        // Here we assume `action` and `containerID` are defined elsewhere in your script
        sendWebSocketMessage(action, { "Id": containerID });
        term.focus();
        // Fit terminal again after connection is established
        handleTerminalResize();
    };

    socket.onclose = function (event) {
        if (event.wasClean) {
            console.log(`Connection closed cleanly, code=${event.code}, reason=${event.reason}`);
        } else {
            // e.g., WebSocket is closed before the connection is established
            console.log('Connection died');
        }
        status.innerHTML = '<span style="background-color: #ff8383;">disconnected</span>';
        // Add visual indication that terminal is disconnected
        term.write('\r\n\n[Connection closed]\r\n');
        term.setOption('cursorBlink', false); // Stop cursor from blinking
        term.setOption('disableStdin', true); // Disable input
        term.setOption('theme', {
            background: '#1e1e1e',
            foreground: '#707070',
        });
    };

    socket.onerror = function (event) {
        console.error(`WebSocket error observed: ${event.reason}`);
    };

}

// ============================
// Terminal Actions
// ============================

const resizeTerminal = debounce((cols, rows) => {
    const termElement = document.querySelector('.terminal');
    if (!termElement) return;

    const height = termElement.offsetHeight;
    const width = termElement.offsetWidth;

    sendWebSocketMessage("pty_resize", { 
        size: {
            rows: rows,
            cols: cols,
            height: height,
            width: width
        }
    });

    console.log(`Resized terminal to ${cols} cols and ${rows} rows`);

}, 250); // 250ms 的延遲


function adjustTerminalHeight(viewportHeight) {
    const terminalWrapper = document.querySelector('.terminal-wrapper');
    const navbarHeight = document.querySelector('nav').offsetHeight;
    
    // 計算 terminal 可用的高度
    let availableHeight = viewportHeight - navbarHeight - 40; // 40px for margin
    
    // 設定 terminal wrapper 的高度
    terminalWrapper.style.height = `${availableHeight}px`;
    
    // 調整 terminal 大小
    if (window.term) {
        window.term.fit();
        const dimensions = window.term.proposeGeometry();
        if (dimensions) {
            resizeTerminal(dimensions.cols, dimensions.rows);
        }
    }
}

function handleTerminalResize() {
    const currentWindowHeight = window.innerHeight;
    adjustTerminalHeight(currentWindowHeight);
}

// ============================
// Main
// ============================

$(document).ready(function () {
    // Initial adjustment
    handleTerminalResize();
    // Listen for window resize events
    window.addEventListener('resize', handleTerminalResize);
});


const { action, containerID } = getPathSegments();

console.log(`Container ID:` + containerID);
console.log(`Action:` + action);

loadConsoleData(containerID, action);
