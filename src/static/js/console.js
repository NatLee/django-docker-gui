// Console (docker exec a shell) and Attach pages: /console/<shell|attach>/<container id>
const [, action, containerID] = window.location.pathname.split('/').filter(Boolean);

async function startConsole() {
    try {
        const response = await apiFetch(`/api/console/${action}/${encodeURIComponent(containerID)}`);
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        const data = await response.json();
        const show = (value) => value || 'N/A';
        document.getElementById('console-info').textContent =
            `Container Info: ${show(data.container_name)} || ${show(data.image)} || ${show(data.short_id)} || ${show(data.command)}`;
        openTerminalSession({
            socketPath: '/ws/console/',
            protocol: `container.${data.id}`,
            onOpen: (send) => send(data.action, { Id: data.id }),
        });
    } catch (error) {
        Swal.fire({ title: 'Error!', text: error.toString(), icon: 'error', confirmButtonText: 'OK' })
            .then(() => { window.location.href = '/login'; });
    }
}

document.addEventListener('DOMContentLoaded', startConsole);
