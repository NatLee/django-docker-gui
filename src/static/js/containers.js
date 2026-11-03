function handleContainerAction(html_btn, cmd) {
    apiFetch('/api/containers/start-stop-remove', {
        method: "POST",
        body: JSON.stringify({ 'id': html_btn.dataset.id, 'cmd': cmd }),
    });
}

function fetchAndDisplayContainers() {
    apiFetch('/api/containers')
        .then(response => response.json())
        .then(data => {
            const table = document.getElementById('containerTableBody');
            table.innerHTML = '';

            data.containers.forEach(item => {
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

                table.insertAdjacentHTML('beforeend', `
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
                </tr>`);
            });
        })
        .catch(error => {
            console.error('Error fetching container data:', error);
        });
}

function onNotification(message) {
    if (message.action === "WAITING") {
        createToastAlert(message.details, false);
        // block the row's actions until the job reports back
        const record = document.getElementById("actions-" + message.data.container_id);
        if (record) {
            record.innerHTML = '<span class="btn btn-warning btn-sm me-3">Waiting</span>';
        }
    } else if (JOB_DONE_EVENTS.includes(message.action)) {
        createToastAlert(message.details, message.action === "FAILED");
        fetchAndDisplayContainers();
    }
}

document.addEventListener('DOMContentLoaded', fetchAndDisplayContainers);
document.addEventListener('DOMContentLoaded', () => listenForNotifications(onNotification));
