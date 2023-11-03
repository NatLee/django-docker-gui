
function handleImageAction(html_btn, action) {
    html_btn.innerHTML = "Loading...";

    let image_id = html_btn.dataset.id;

    let data = { 'image_id': image_id };

    let url = action === 'run' ? '/api/images/run' : '/api/images/remove';

    console.log(`${action.charAt(0).toUpperCase() + action.slice(1)} -> ${image_id}`);
    const csrftoken = getCookie('csrftoken'); // Get CSRF token from cookies
    fetch(url, {
       method: "POST",
       body: JSON.stringify(data),
       mode: 'same-origin',
       headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': csrftoken
      },
    }).then(response => {
       if (!response.ok) {
           throw new Error(`HTTP error! status: ${response.status}`);
       }
       return response.json();    
    }).then(data => {
       console.log(data["task_id"])
       return getUpdate(data["task_id"])
    }).then(() => {
       fetchAndDisplayImages();
    })
}

function fetchAndDisplayImages() {
 fetch('/api/images')
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

document.addEventListener('DOMContentLoaded', fetchAndDisplayImages);
