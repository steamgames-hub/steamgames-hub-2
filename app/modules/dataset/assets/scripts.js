// Cleaned & simplified after cherry-pick: removed duplicate blocks and Zenodo test to avoid runtime errors.
// Core helpers --------------------------------------------------------------
let currentId = 0;
let amount_authors = 0;

function show_upload_dataset() {
    const el = document.getElementById("upload_dataset");
    if (el) el.style.display = "block";
}

function generateIncrementalId() { return currentId++; }

function addField(newAuthor, name, text, className = 'col-lg-6 col-12 mb-3') {
    let fieldWrapper = document.createElement('div');
    fieldWrapper.className = className;
    let label = document.createElement('label');
    label.className = 'form-label';
    label.for = name;
    label.textContent = text;

    let field = document.createElement('input');
    field.name = name;
    field.className = 'form-control';

    fieldWrapper.appendChild(label);
    fieldWrapper.appendChild(field);
    newAuthor.appendChild(fieldWrapper);
}

function addRemoveButton(newAuthor) {
    let buttonWrapper = document.createElement('div');
    buttonWrapper.className = 'col-12 mb-2';
    let button = document.createElement('button');
    button.textContent = 'Remove author';
    button.className = 'btn btn-danger btn-sm';
    button.type = 'button';
    button.addEventListener('click', function (event) {
        event.preventDefault();
        newAuthor.remove();
    });
    buttonWrapper.appendChild(button);
    newAuthor.appendChild(buttonWrapper);
}

function createAuthorBlock(idx, suffix) {
    let newAuthor = document.createElement('div');
    newAuthor.className = 'author row';
    newAuthor.style.cssText = "border:2px dotted #ccc;border-radius:10px;padding:10px;margin:10px 0; background-color: white";
    addField(newAuthor, `${suffix}authors-${idx}-name`, 'Name *');
    addField(newAuthor, `${suffix}authors-${idx}-affiliation`, 'Affiliation');
    addField(newAuthor, `${suffix}authors-${idx}-orcid`, 'ORCID');
    addRemoveButton(newAuthor);

    return newAuthor;
}

function isValidOrcid(orcid) { return /^\d{4}-\d{4}-\d{4}-\d{4}$/.test(orcid); }

function check_title_and_description() {
    let titleInput = document.querySelector('input[name="title"]');
    let descriptionTextarea = document.querySelector('textarea[name="desc"]');
    titleInput.classList.remove("error");
    descriptionTextarea.classList.remove("error");
    clean_upload_errors();
    let titleLength = titleInput.value.trim().length;
    let descriptionLength = descriptionTextarea.value.trim().length;
    if (titleLength < 3) { write_upload_error("title must be of minimum length 3"); titleInput.classList.add("error"); }
    if (descriptionLength < 3) { write_upload_error("description must be of minimum length 3"); descriptionTextarea.classList.add("error"); }
    return (titleLength >= 3 && descriptionLength >= 3);
}

function check_name_and_surname() {
    let nameInput = document.querySelector('input[name="name"]');
    let surnameInput = document.querySelector('input[name="surname"]');

    nameInput.classList.remove("error");
    surnameInput.classList.remove("error");
    clean_edit_profile_errors();

    let nameLength = nameInput.value.trim().length;
    let surnameLength = surnameInput.value.trim().length;

    if (nameLength < 1) {
        write_profile_error("the profile needs a name");
        nameInput.classList.add("error");
    }

    if (surnameLength < 1) {
        write_profile_error("the profile needs a surname");
        surnameInput.classList.add("error");
    }

    return (nameLength >= 1 && surnameLength >= 1);
}

function clean_edit_profile_errors() {
    let profile_error = document.getElementById("edit_profile_error");
    profile_error.innerHTML = "";
    profile_error.style.display = 'none';
}

// Event wiring --------------------------------------------------------------
document.addEventListener('click', function (event) {
    if (event.target && event.target.classList.contains('add_author_to_file')) {
        let authorsButtonId = event.target.id;
        let authorsId = authorsButtonId.replace("_button", "");
        let authors = document.getElementById(authorsId);
        let id = authorsId.replace("_form_authors", "");
        let newAuthor = createAuthorBlock(amount_authors, `feature_models-${id}-`);
        authors.appendChild(newAuthor);
    }
});

document.getElementById('add_author').addEventListener('click', function () {
    let authors = document.getElementById('authors');
    let newAuthor = createAuthorBlock(amount_authors++, "");
    authors.appendChild(newAuthor);
});

function show_loading() {
    document.getElementById("upload_button").style.display = "none";
    document.getElementById("loading").style.display = "block";
}
function hide_loading() {
    document.getElementById("upload_button").style.display = "block";
    document.getElementById("loading").style.display = "none";
}
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
function write_profile_error(error_message) {
    let profile_error = document.getElementById("edit_profile_error");
    let alert = document.createElement('p');
    alert.style.margin = '0';
    alert.style.padding = '0';
    alert.textContent = 'Profile error: ' + error_message;
    profile_error.appendChild(alert);
    profile_error.style.display = 'block';
}


window.onload = function () {
    const uploadBtn = document.getElementById('upload_button');
    if (uploadBtn) {
        uploadBtn.addEventListener('click', function () {
            clean_upload_errors();
            show_loading();
            if (!check_title_and_description()) { hide_loading(); return; }

            // Gather form data
            const formData = {};
            ["basic_info_form", "uploaded_models_form"].forEach((formId) => {
                const form = document.getElementById(formId);
                if (!form) return;
                const inputs = form.querySelectorAll('input, select, textarea');
                inputs.forEach(input => {
                    if (input.name) {
                        formData[input.name] = formData[input.name] || [];
                        formData[input.name].push(input.value);
                    }
                });
            });

            const csrfTokenEl = document.getElementById('csrf_token');
            const csrfToken = csrfTokenEl ? csrfTokenEl.value : '';
            const formUploadData = new FormData();
            formUploadData.append('csrf_token', csrfToken);
            for (let key in formData) { if (formData.hasOwnProperty(key)) formUploadData.set(key, formData[key]); }

            // Validate ORCID + names
            let checked_orcid = true;
            if (Array.isArray(formData.author_orcid)) {
                for (let orcid of formData.author_orcid) {
                    orcid = orcid.trim();
                    if (orcid !== '' && !isValidOrcid(orcid)) { hide_loading(); write_upload_error("ORCID value does not conform to valid format: " + orcid); checked_orcid = false; break; }
                }
            }
            let checked_name = true;
            if (Array.isArray(formData.author_name)) {
                for (let name of formData.author_name) {
                    name = name.trim();
                    if (name === '') { hide_loading(); write_upload_error("The author's name cannot be empty"); checked_name = false; break; }
                }
            }
            if (!(checked_orcid && checked_name)) return;

            fetch('/dataset/upload', { method: 'POST', body: formUploadData })
                .then(response => {
                    if (response.ok) {
                        response.json().then(data => { window.location.href = "/dataset/list"; });
                    } else {
                        response.json().then(data => { hide_loading(); write_upload_error(data.message); });
                    }
                })
                .catch(error => { console.error('Error in POST request:', error); hide_loading(); write_upload_error('Unexpected network error'); });
        });
    }
};

// NOTE: show_upload_dataset() is called by Dropzone success handler in template.


let hasAnswered = false;
let urlToLeave = "";


function handleChangePreference() {
    fetch('/profile/save_drafts', {
        method: 'PUT'
    })
    .then(response => {
        if (response.ok) {
            console.log('Save draft preferences changed succesfully');
        } else {
            response.then(data => {
                console.error('Error: ' + data.message);

            });
        }
    })
    .catch(error => {
        console.error('Error in PUT request:', error);
    });
}

function showModal(event) {
    event.preventDefault()
    document.getElementById("myModal").style.display = "flex";
}

function saveDraft() {
    window.location.href = urlToLeave;
    document.getElementById("myModal").style.display = "none";
    if(document.getElementById("save_drafts_preference").checked === true){
        handleChangePreference();
    }
}

function discardDraft() {
    window.location.href = urlToLeave;
    document.getElementById("myModal").style.display = "none";
    if(document.getElementById("save_drafts_preference").checked === true){
        handleChangePreference();
    }
}
