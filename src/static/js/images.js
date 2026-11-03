function handleImageAction(html_btn, action) {
    const url = action === 'run' ? '/api/images/run' : '/api/images/remove';
    apiFetch(url, {
        method: "POST",
        body: JSON.stringify({ 'image_id': html_btn.dataset.id }),
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
                    <td>${item.name}</td>
                    <td>${item.short_id}</td>
                    <td>${item.size} MB</td>
                    <td>
                        <div class='d-flex'>
                            <button data-id="${item.short_id}" class="btn btn-success btn-sm me-3" onclick="handleImageAction(this, 'run')">Run</button>
                            <button data-id="${item.short_id}" class="btn btn-danger btn-sm" onclick="handleImageAction(this, 'remove')">Remove</button>
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

document.addEventListener('DOMContentLoaded', fetchAndDisplayImages);
document.addEventListener('DOMContentLoaded', () => listenForNotifications(onNotification));
