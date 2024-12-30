// ============================
// Utility Functions
// ============================

function generateConnectionId() {
    return Math.random().toString(36).substring(2, 15) + Math.random().toString(36).substring(2, 15);
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

function setupWebSocketConnection(){
    Terminal.applyAddon(fit);
    Terminal.applyAddon(fullscreen);

    var term = new Terminal({
        cursorBlink: true,
        fontSize: 14,
        fontFamily: 'Menlo, Monaco, "Courier New", monospace',
    });

    // Expose the terminal object to the window
    window.term = term;

    // Get the access token from local storage
    const accessToken = localStorage.getItem('accessToken');
    var ws_scheme = window.location.protocol == "https:" ? "wss" : "ws";
    var ws_path = ws_scheme + '://' + window.location.host + `/ws/terminal/`;

    // Token need to be encoded with base64
    const tokenInfo = `token.${btoa(accessToken)}`;
    // Generate a unique identifier for the connection
    const connectionId = `terminal.${generateConnectionId()}`;
    const socket = new WebSocket(ws_path, [tokenInfo, connectionId]);

    // Expose the socket object to the window
    window.socket = socket;

    term.open(document.getElementById('terminal'));
    term.fit();

    const status = document.getElementById("status")


    term.on('key', (key, ev) => {
        const isMac = navigator.platform.toUpperCase().indexOf('MAC') >= 0;
        const ctrlKey = isMac ? ev.metaKey : ev.ctrlKey;

        if (ctrlKey && key === 'c' && term.hasSelection()) {
            // Copy to clipboard
            navigator.clipboard.writeText(term.getSelection());
        } else {
            // Send other key inputs to the server
            sendWebSocketMessage("pty_input", { input: key });
        }
    });

    // Handle paste event
    term.on('paste', (data) => {
        // Using the WebSocket connection to send data
        sendWebSocketMessage("pty_input", { input: data });
    });


    // Handle incoming WebSocket messages
    socket.onmessage = function(event) {
        term.write(event.data);
        // Scroll to the bottom of the terminal
        term.scrollToBottom();
    };

    socket.onopen = function () {
        console.log("WebSocket connection established");
        // Handle the connect event
        status.innerHTML = '<span style="background-color: lightgreen;">connected</span>';
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
    // Setup WebSocket connection
    setupWebSocketConnection();
});