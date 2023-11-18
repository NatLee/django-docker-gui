
function handleContainerAction(html_btn, cmd) {
    containerID = html_btn.dataset.id;
    let url = '/api/containers/start-stop-remove'
    let data = { 'id': containerID, 'cmd': cmd };
    //console.log(cmd + "->" + containerID);

    // Retrieve the JWT from local storage
    const accessToken = localStorage.getItem('accessToken');

    fetch(url, {
       method: "POST",
       body: JSON.stringify(data),
       headers: {
           'Content-Type': 'application/json',
           'Authorization': `Bearer ${accessToken}`
      },
    }).then(response => {
       if (!response.ok) {
           window.location.href = '/login';
       }
       return response.json();    
    }).then(data => {
        console.log(data["task_id"])
    })
 }

 function fetchAndDisplayContainers() {

     // Retrieve the JWT from local storage
     const accessToken = localStorage.getItem('accessToken');

     fetch('/api/containers', {
         method: "GET",
         headers: {
             'Content-Type': 'application/json',
             'Authorization': `Bearer ${accessToken}`
         },
     })
        .then(response => response.json())
        .then(data => {
            const containers = data.containers;
            const table = document.getElementById('containerTableBody');
            table.innerHTML = '';

            containers.forEach(item => {
                let actionButtons = '';

                if (item.status === "running") {
                    actionButtons = `
                        <button class="btn btn-info btn-sm me-3" onclick="window.open('/console/shell/${item.id}')">Console</button>
                        <button class="btn btn-info btn-sm me-3" onclick="window.open('/console/attach/${item.id}')">Attach</button>
                        <button data-id="${item.id}" class="btn btn-warning btn-sm me-3" onclick="handleContainerAction(this, 'restart')">Restart</button>
                        <button data-id="${item.id}" class="btn btn-warning btn-sm me-3" onclick="handleContainerAction(this, 'stop')">Stop</button>
                    `;
                } else {
                    actionButtons = `
                        <button data-id="${item.id}" class="btn btn-success btn-sm me-3" onclick="handleContainerAction(this, 'start')">Start</button>
                        <button data-id="${item.id}" class="btn btn-danger btn-sm" onclick="handleContainerAction(this, 'remove')">Remove</button>
                    `;
                }

                const row = `
                <tr>
                    <td>${item.name}</td>
                    <td>${item.image_tag || '&lt;none&gt;'}</td>
                    <td>${item.short_id}</td>
                    <td>${item.command}</td>
                    <td>
                        <div class='d-flex'>
                            <span class="btn ${item.status === "running" ? 'btn-success' : 'btn-secondary'} btn-sm" id="${item.id}-span">${item.status}</span>
                        </div>
                    </td>
                    <td>
                        <div class='d-flex' id="actions-${item.id}">
                            ${actionButtons}
                        </div>
                    </td>
                </tr>`;
                table.innerHTML += row;
            });
        })
        .catch(error => {
            console.error('Error fetching container data:', error);
        });
}


function notificationWebsocket() {

    var ws_scheme = window.location.protocol == "https:" ? "wss" : "ws";
    var ws_path = ws_scheme + '://' + window.location.host + "/ws/notifications/";
    var socket = new WebSocket(ws_path);

    // Update the status of the WebSocket connection
    function updateWebSocketStatus(isConnected) {
        const statusElement = document.getElementById("websocket-status");
        if (statusElement) {
            statusElement.classList.toggle('connected', isConnected);
            statusElement.classList.toggle('disconnected', !isConnected);
        }
    }

    socket.onopen = function () {
        updateWebSocketStatus(true);
    };

    socket.onmessage = function (event) {
        const data = JSON.parse(event.data);
        console.log('Notification message:', data.message);
        let action = data.message.action;
        if (action === "WAITING") {
            createToastAlert(data.message.details, false);
            let containerID = data.message.data.container_id;
            // get the record from the table by id
            let record = document.getElementById("actions-" + containerID);
            // block actions & show the waiting status
            record.innerHTML = `
                <span class="btn btn-warning btn-sm me-3">Waiting</span>
            `;
        }
        if (action === "CREATED" || action === "STARTED" || action === "STOPPED" || action === "REMOVED") {
            createToastAlert(data.message.details, false);
            fetchAndDisplayContainers();
        }

    };

    socket.onclose = function (e) {
        updateWebSocketStatus(false);
        console.error('Notification WebSocket closed unexpectedly:', e);

        // Reconnect after 3 seconds
        setTimeout(notificationWebsocket, 3000);
    };

    // Handle any errors that occur.
    socket.onerror = function (error) {
        updateWebSocketStatus(false);
        console.error('WebSocket Error:', error);
    };

}


document.addEventListener('DOMContentLoaded', fetchAndDisplayContainers);
document.addEventListener('DOMContentLoaded', notificationWebsocket);