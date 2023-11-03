
function getDisplayValue(value, defaultValue = 'N/A') {
    return value ? value : defaultValue;
}

// Better error handling with SweetAlert
const showError = (error) => {
    Swal.fire({
        title: 'Error!',
        text: error.toString(),
        icon: 'error',
        confirmButtonText: 'OK'
    });
 };

async function loadConsoleData(containerID, action) {
    try {
        const response = await fetch(`/api/console/${action}/${containerID}`);
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

    var socket = io.connect({transports: ["websocket", "polling"]});
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
        socket.emit("pty_input", { "input": key, "id": window.location.pathname.split("/")[2] });
        }
    });

    // Handle paste event
    term.on('paste', (data) => {
        socket.emit("pty_input", { "input": data, "id": window.location.pathname.split("/")[2] });
    });

    socket.on("pty_output", function (output) {
        //console.log(output["output"])
        term.write(output["output"])
    })

    socket.on("connect", () => {
        status.innerHTML = '<span style="background-color: lightgreen;">connected</span>'
        socket.emit(action, { "Id": containerID })
        term.focus()
    });

    socket.on("disconnect", () => {
        status.innerHTML = '<span style="background-color: #ff8383;">disconnected</span>'

    })

    function resize() {
        term.fit()
        socket.emit("resize", { "cols": term.cols, "rows": term.rows })
    }

    window.onresize = resize
    window.onload = resize

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

