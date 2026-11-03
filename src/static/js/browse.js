// Docker Hub page: search (GET /api/browse, the daemon's `docker search`) and pull with live
// progress (/ws/pull-image/).

async function searchDockerHub(query) {
    const results = document.getElementById('results');
    const response = await apiFetch(`/api/browse?q=${encodeURIComponent(query)}`);
    const data = await response.json();
    if (!response.ok) {
        results.textContent = data.detail || `Search failed (${response.status})`;
        return;
    }
    if (data.summary.length === 0) {
        results.innerHTML = query
            ? `<p class="text-center text-muted">Nothing found for “${escapeHtml(query)}”.</p>`
            : '<p class="text-center text-muted">Type a name and press Search to find images on Docker Hub.</p>';
        return;
    }
    results.innerHTML = data.summary.map((item) => `
        <div class="d-flex justify-content-center">
          <div class="d-flex border-start border-primary border-5 p-4 shadow-lg mb-4 bg-body rounded col-sm-8 col-12">
            <div class="col d-flex flex-column">
              <h5>${escapeHtml(item.name)}${item.is_official ? '<span class="badge bg-primary ms-2 align-middle">Official</span>' : ''}</h5>
              <p>${escapeHtml(item.description || 'No description available.')}</p>
              <small class="text-muted">★ ${escapeHtml(item.star_count)}</small>
            </div>
            <div class="flex-shrink-0 d-flex justify-content-center ms-2">
              <div class="align-self-end">
                <button type="button" class="btn btn-md btn-primary text-nowrap" data-bs-toggle="modal"
                        data-bs-target="#imageModal" data-bs-name="${escapeHtml(item.name)}">Pull</button>
              </div>
            </div>
          </div>
        </div>`).join('');
}

// The pull output goes to a small terminal inside the dialog.
const pullTerm = new Terminal({ cursorBlink: true, convertEol: true });
const pullFit = new FitAddon.FitAddon();
pullTerm.loadAddon(pullFit);
let pullTermOpened = false;

function pullImage() {
    const image = document.getElementById('modal_input').value;
    const version = document.getElementById('modal_input_version').value || 'latest';
    const terminal = document.getElementById('terminal');

    document.getElementById('pullImageBtn').classList.add('d-none');
    terminal.classList.remove('d-none');
    if (!pullTermOpened) {
        pullTerm.open(terminal);
        pullTermOpened = true;
    }
    pullFit.fit();

    const socket = openSocket('/ws/pull-image/', 'pull-image');
    socket.onopen = () => {
        pullTerm.write('Pulling image, please wait...\n');
        document.getElementById('btn-close').classList.add('disabled');
        socket.send(JSON.stringify({ action: 'pull_image', payload: { image, version } }));
    };
    socket.onmessage = (event) => {
        const data = JSON.parse(event.data);
        pullTerm.write(`${data.status}${data.progress}\n`);
    };
    socket.onclose = (event) => {
        pullTerm.write(event.wasClean ? `\nDone\nConnection closed cleanly, code=${event.code}` : '\nConnection died');
        document.getElementById('modal_footer').classList.replace('d-none', 'd-flex');
        document.getElementById('btn-close').classList.remove('disabled');
    };
}

document.addEventListener('DOMContentLoaded', () => {
    const modal = document.getElementById('imageModal');
    modal.addEventListener('show.bs.modal', (event) => {
        document.getElementById('modal_input').value = event.relatedTarget.getAttribute('data-bs-name');
    });
    modal.addEventListener('hidden.bs.modal', () => {
        pullTerm.reset();
        document.getElementById('modal_footer').classList.replace('d-flex', 'd-none');
        document.getElementById('pullImageBtn').classList.remove('d-none');
        document.getElementById('terminal').classList.add('d-none');
    });
    document.getElementById('pullImageBtn').addEventListener('click', pullImage);
    document.getElementById('searchForm').addEventListener('submit', (event) => {
        event.preventDefault();
        searchDockerHub(document.querySelector('[name="q"]').value);
    });
    window.addEventListener('resize', debounce(() => pullTermOpened && pullFit.fit(), 50));
    searchDockerHub('');
});
