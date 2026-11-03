// Console and Attach open the terminal page; the others queue a job.
const TERMINAL_ACTIONS = ['shell', 'attach'];

function handleContainerAction(containerID, cmd) {
    if (TERMINAL_ACTIONS.includes(cmd)) {
        window.open(`/console/${cmd}/${encodeURIComponent(containerID)}`);
        return;
    }
    apiFetch('/api/containers/start-stop-remove', {
        method: "POST",
        body: JSON.stringify({ 'id': containerID, 'cmd': cmd }),
    });
}

function actionButton(label, style, cmd, id) {
    return `<button class="btn ${style} btn-sm me-3" data-cmd="${cmd}" data-id="${escapeHtml(id)}">${label}</button>`;
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
                    actionButtons = actionButton('Console', 'btn-info', 'shell', item.id)
                        + actionButton('Attach', 'btn-info', 'attach', item.id)
                        + actionButton('Restart', 'btn-warning', 'restart', item.id)
                        + actionButton('Stop', 'btn-warning', 'stop', item.id);
                } else {
                    actionButtons = actionButton('Start', 'btn-success', 'start', item.id)
                        + actionButton('Remove', 'btn-danger', 'remove', item.id);
                }

                table.insertAdjacentHTML('beforeend', `
                <tr>
                    <td>${escapeHtml(item.name)}</td>
                    <td>${escapeHtml(item.image_tag || '<none>')}</td>
                    <td>${escapeHtml(item.short_id)}</td>
                    <td>${escapeHtml(item.command)}</td>
                    <td>
                        <div class='d-flex'>
                            <span class="btn ${item.status === "running" ? 'btn-success' : 'btn-secondary'} btn-sm">${escapeHtml(item.status)}</span>
                        </div>
                    </td>
                    <td>
                        <div class='d-flex' id="actions-${escapeHtml(item.id)}">
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

document.addEventListener('DOMContentLoaded', () => {
    document.getElementById('containerTableBody').addEventListener('click', (event) => {
        const button = event.target.closest('button[data-cmd]');
        if (button) {
            handleContainerAction(button.dataset.id, button.dataset.cmd);
        }
    });
});
document.addEventListener('DOMContentLoaded', fetchAndDisplayContainers);
document.addEventListener('DOMContentLoaded', () => listenForNotifications(onNotification));
