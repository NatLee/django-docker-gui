
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

function uniqueID() {
   return Math.floor(Math.random() * Date.now())
}

function createToastAlert(msg, isFailure) {

   let div_id = uniqueID();

   const toastHtml =
      `<div id="` + div_id + `" class="toast align-items-center text-white bg-primary border-0" role="alert" aria-live="assertive" aria-atomic="true">
       <div class="d-flex">
          <div class="toast-body">`
      + msg +
      `</div>
          <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"
             aria-label="Close"></button>
       </div>
    </div>
    `;

   var toastContainer = document.getElementById('toastContainer');
   toastContainer.innerHTML += toastHtml;

   // if failure msg, make background color red
   if (isFailure) {
      $('#' + div_id).removeClass('bg-primary').addClass('bg-danger');
   }

   $('#' + div_id).toast('show')
   setTimeout(function () {
      $('#' + div_id).toast('hide')

   }, 5000);
}

function sleep(ms) {
   return new Promise(resolve => setTimeout(resolve, ms));
}

async function getUpdate(task_id) {
   var flag = true;
   let progressUrl = '/progress';
   const accessToken = localStorage.getItem('accessToken');

   while (flag) {

      await sleep(2000);
      await fetch(progressUrl + `/` + task_id, {
         "method": "GET",
         "headers": {
            "Content-Type": "application/json",
            "Authorization": `Bearer ${accessToken}`
         }
      })
         .then(response => response.json())
         .then(data => {
            console.log(data)
            if (data['state'] === 'FINISHED') {
               flag = false;
               let msg = data['details']
               createToastAlert(msg, false)
            }

            else if (data['state'] === 'FAILED') {
               flag = false;
               let msg = data['details']
               createToastAlert(msg, true)

            }

            else if (data['state'] === 'NOT FOUND') {
               flag = false;
               let msg = data['details']
               createToastAlert(msg, true)

            }
         })
   }
   return
}


// ---------------------------------------
// check token on page load
verifyAccessToken();
// ---------------------------------------

