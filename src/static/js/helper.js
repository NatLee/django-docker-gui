
// ============================
// Utility Functions
// ============================

async function verifyAccessToken() {
   const accessToken = localStorage.getItem('accessToken');
   if (!accessToken) {
      window.location.href = '/login';
   }
   const response = await fetch('/api/auth/token/verify', {
      method: 'POST',
      headers: {
         'Content-Type': 'application/json',
      },
      body: JSON.stringify({ token: accessToken })
   });

   if (!response.ok) {
      window.location.href = '/login';
   }
}

// Every WebSocket of this app logs in with the access token offered as a subprotocol,
// "token.<base64 of the token>", next to a second subprotocol that names the connection (the
// server answers with that one). Subprotocols can't contain "=", so the base64 padding is dropped.
function openSocket(path, name) {
   const scheme = window.location.protocol === "https:" ? "wss" : "ws";
   const token = btoa(localStorage.getItem('accessToken') || '').replace(/=+$/, '');
   return new WebSocket(`${scheme}://${window.location.host}${path}`, [name, `token.${token}`]);
}

// fetch() for the JSON API: sends the access token, and goes to the login page when it's refused.
async function apiFetch(url, options = {}) {
   const response = await fetch(url, {
      ...options,
      headers: {
         'Content-Type': 'application/json',
         'Authorization': `Bearer ${localStorage.getItem('accessToken')}`,
         ...(options.headers || {}),
      },
   });
   if (response.status === 401) {
      window.location.href = '/login';
   }
   return response;
}

// Listens to /ws/notifications/ (job queued, done or failed) and reconnects when it drops.
// The dot next to the page title (#websocket-status), if there is one, shows the state.
function listenForNotifications(onMessage) {
   const socket = openSocket("/ws/notifications/", "notifications");
   const showStatus = (isConnected) => {
      const status = document.getElementById("websocket-status");
      if (status) {
         status.classList.toggle('connected', isConnected);
         status.classList.toggle('disconnected', !isConnected);
      }
   };
   socket.onopen = () => showStatus(true);
   socket.onmessage = (event) => onMessage(JSON.parse(event.data).message);
   socket.onclose = () => {
      showStatus(false);
      setTimeout(() => listenForNotifications(onMessage), 3000);
   };
}

// Events that end a job (xterm/notifications.py); after any of them the lists are reloaded.
const JOB_DONE_EVENTS = ["CREATED", "STARTED", "STOPPED", "RESTARTED", "REMOVED", "FAILED"];

// Container names and commands, image descriptions from Docker Hub and daemon messages are not
// ours: everything that goes into HTML goes through here first.
function escapeHtml(value) {
   const entities = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' };
   return String(value ?? '').replace(/[&<>"']/g, (c) => entities[c]);
}

function uniqueID() {
   return Math.random().toString(36).slice(2, 18);
}


function createToastAlert(msg, isFailure) {
   const toastId = `toast-${uniqueID()}`;
   const toastColorClass = isFailure ? 'bg-danger' : 'bg-primary';
   const toastHtml = `
       <div id="${toastId}" class="toast align-items-center text-white ${toastColorClass} border-0" role="alert" aria-live="assertive" aria-atomic="true">
           <div class="d-flex">
               <div class="toast-body"></div>
               <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast" aria-label="Close"></button>
           </div>
       </div>
   `;

   const toastContainer = document.getElementById('toastContainer');
   toastContainer.insertAdjacentHTML('beforeend', toastHtml);
   document.getElementById(toastId).querySelector(".toast-body").textContent = msg;

   const toastElement = $(`#${toastId}`);
   toastElement.toast('show');

   toastElement.on('hidden.bs.toast', function () {
      toastElement.remove();
   });

   setTimeout(() => {
      toastElement.toast('hide');
   }, 2000);
}


function debounce(func, wait) {
   let timeout;
   return function executedFunction(...args) {
       const later = () => {
           clearTimeout(timeout);
           func(...args);
       };
       clearTimeout(timeout);
       timeout = setTimeout(later, wait);
   };
}


// ---------------------------------------
// check token on page load
verifyAccessToken();
// ---------------------------------------

