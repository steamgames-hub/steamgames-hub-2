function show_loading() {
    document.getElementById("change_save_drafts_button").style.display = "none";
    document.getElementById("loading").style.display = "block";
}

function hide_loading() {
    document.getElementById("change_save_drafts_button").style.display = "block";
    document.getElementById("loading").style.display = "none";
}

hide_loading()

function clean_upload_errors() {
    let upload_error = document.getElementById("upload_error");
    upload_error.innerHTML = "";
    upload_error.style.display = 'none';
}

function write_upload_error(error_message) {
    let upload_error = document.getElementById("upload_error");
    let alert = document.createElement('p');
    alert.style.margin = '0';
    alert.style.padding = '0';
    alert.textContent = 'Upload error: ' + error_message;
    upload_error.appendChild(alert);
    upload_error.style.display = 'block';
}

document.getElementById('change_save_drafts_button').addEventListener('click', function () {
    
    show_loading();

    fetch('/profile/save_drafts', {
        method: 'PUT'
    })
    .then(response => {
        if (response.ok) {
            console.log('Save draft preferences changed succesfully');
            hide_loading();
            window.location.reload();
        } else {
            hide_loading();
            response.then(data => {
                console.error('Error: ' + data.message);
                write_upload_error(data.message);

            });
        }
    })
    .catch(error => {
        console.error('Error in PUT request:', error);
    });
});
