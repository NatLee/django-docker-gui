function handleImageAction(imageID, action) {
    apiFetch(`/api/images/${action}`, {
        method: "POST",
        body: JSON.stringify({ 'image_id': imageID }),
    });
}

function fetchAndDisplayImages() {
    apiFetch('/api/images')
        .then(response => response.json())
        .then(data => {
            const table = document.getElementById('imageTableBody');
            table.innerHTML = '';

            data.images.forEach(item => {
                table.insertAdjacentHTML('beforeend', `
                <tr>
                    <td>${escapeHtml(item.name || '<none>')}</td>
                    <td>${escapeHtml(item.short_id)}</td>
                    <td>${escapeHtml(item.size)} MB</td>
                    <td>
                        <div class='d-flex'>
                            <button data-action="run" data-id="${escapeHtml(item.short_id)}" class="btn btn-success btn-sm me-3">Run</button>
                            <button data-action="remove" data-id="${escapeHtml(item.short_id)}" class="btn btn-danger btn-sm">Remove</button>
                        </div>
                    </td>
                </tr>`);
            });
        })
        .catch(error => {
            console.error('Error fetching image data:', error);
        });
}

function onNotification(message) {
    if (JOB_DONE_EVENTS.includes(message.action)) {
        createToastAlert(message.details, message.action === "FAILED");
        fetchAndDisplayImages();
    }
}

document.addEventListener('DOMContentLoaded', () => {
    document.getElementById('imageTableBody').addEventListener('click', (event) => {
        const button = event.target.closest('button[data-action]');
        if (button) {
            handleImageAction(button.dataset.id, button.dataset.action);
        }
    });
});
document.addEventListener('DOMContentLoaded', fetchAndDisplayImages);
document.addEventListener('DOMContentLoaded', () => listenForNotifications(onNotification));
