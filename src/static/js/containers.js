
function handleContainerAction(html_btn, cmd) {
    html_btn.innerHTML = "Loading...";
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
       return getUpdate(data["task_id"])
    }).then(() => {
       fetchAndDisplayContainers();
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
                        <div class='d-flex'>
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

document.addEventListener('DOMContentLoaded', fetchAndDisplayContainers);
