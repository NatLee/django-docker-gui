
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


function setupWebSocketConnection(containerID, action){
    Terminal.applyAddon(fit);

    const accessToken = localStorage.getItem('accessToken');
    var ws_scheme = window.location.protocol == "https:" ? "wss" : "ws";
    var ws_path = ws_scheme + '://' + window.location.host + `/ws/console/`;

    // Token need to be encoded with base64
    const tokenInfo = `token.${btoa(accessToken)}`;
    // Create a ticket for subprotocols
    const ticket = `container.${`${containerID}`}`;
    const socket = new WebSocket(ws_path, [tokenInfo, ticket]);

    // Convert and send a message to the server
    function sendWebSocketMessage(action, message) {
        socket.send(JSON.stringify({ action: action, payload: message }));
    }

    const status = document.getElementById("status")

    var term = new Terminal({
        cursorBlink: true,
    });

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
    };

    socket.onclose = function (event) {
        if (event.wasClean) {
            console.log(`Connection closed cleanly, code=${event.code}, reason=${event.reason}`);
        } else {
            // e.g., WebSocket is closed before the connection is established
            console.log('Connection died');
        }
        status.innerHTML = '<span style="background-color: #ff8383;">disconnected</span>';
    };

    socket.onerror = function (event) {
        console.error(`WebSocket error observed: ${event.reason}`);
    };

    /*
    function resize() {
        term.fit()
        socket.emit("resize", { "cols": term.cols, "rows": term.rows })
    }

    window.onresize = resize
    window.onload = resize
    */
}

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

const { action, containerID } = getPathSegments();

console.log(`Container ID:` + containerID);
console.log(`Action:` + action);

loadConsoleData(containerID, action);

