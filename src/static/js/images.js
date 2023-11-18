
function handleImageAction(html_btn, action) {
    let image_id = html_btn.dataset.id;

    let data = { 'image_id': image_id };
    let url = action === 'run' ? '/api/images/run' : '/api/images/remove';

    console.log(`${action.charAt(0).toUpperCase() + action.slice(1)} -> ${image_id}`);

    // Retrieve the JWT from local storage
    const accessToken = localStorage.getItem('accessToken');

    fetch(url, {
       method: "POST",
       body: JSON.stringify(data),
       mode: 'same-origin',
       headers: {
           'Content-Type': 'application/json',
           'Authorization': `Bearer ${accessToken}`
      },
    }).then(response => {
       if (!response.ok) {
           throw new Error(`HTTP error! status: ${response.status}`);
       }
       return response.json();    
    }).then(data => {
        console.log(data["task_id"])
    })
}

function fetchAndDisplayImages() {

    // Retrieve the JWT from local storage
    const accessToken = localStorage.getItem('accessToken');

    fetch('/api/images', {
        method: "GET",
        headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${accessToken}`
        },
    })
        .then(response => response.json())
        .then(data => {
            const images = data.images;
            const table = document.getElementById('imageTableBody');
            table.innerHTML = '';

            images.forEach(item => {
                let actionButtons = '';

                actionButtons = `
                    <button data-id="${item.short_id}" class="btn btn-success btn-sm me-3" onclick="handleImageAction(this, 'run')">Run</button>
                    <button data-id="${item.short_id}" class="btn btn-danger btn-sm" onclick="handleImageAction(this, 'remove')">Remove</button>
                `;

                const row = `
                <tr>
                    <td>${item.name}</td>
                    <td>${item.short_id}</td>
                    <td>${item.size} MB</td>
                    <td>
                        <div class='d-flex'>
                            ${actionButtons}
                        </div>
                    </td>
                </tr>`;
                table.innerHTML += row;
            });
        })
        .catch(error => {
            console.error('Error fetching image data:', error);
        });
}


function notificationWebsocket() {

    var ws_scheme = window.location.protocol == "https:" ? "wss" : "ws";
    var ws_path = ws_scheme + '://' + window.location.host + "/ws/notifications/";
    var socket = new WebSocket(ws_path);

    socket.onmessage = function (event) {
        const data = JSON.parse(event.data);
        console.log('Notification message:', data.message);
        let action = data.message.action;
        if (action === "CREATED" || action === "STARTED" || action === "STOPPED" || action === "REMOVED") {
            createToastAlert(data.message.details, false);
            fetchAndDisplayImages();
        }

    };

}


document.addEventListener('DOMContentLoaded', fetchAndDisplayImages);
document.addEventListener('DOMContentLoaded', notificationWebsocket);
