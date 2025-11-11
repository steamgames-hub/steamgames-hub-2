document.addEventListener('DOMContentLoaded', () => {
    hydrateFromURL();
    send_query(); // engancha listeners y lanza primera búsqueda
});

// Helpers para fechas y URL
function get(id) { return document.getElementById(id); }

function buildDateFromParts(prefix) {
    const d = get(`${prefix}_day`)?.value?.trim();
    const m = get(`${prefix}_month`)?.value?.trim();
    const y = get(`${prefix}_year`)?.value?.trim();
    if (!d || !m || !y) return ""; // si falta alguna parte, no se añade
    
    const dd = String(d).padStart(2, "0");
    const mm = String(m).padStart(2, "0");
    const yy = String(y).padStart(4, "0");
    return `${yy}-${mm}-${dd}`;
}

function updateURL(params) {
    const url = new URL(window.location.href);
    const p = url.searchParams;

    // limpia primero los que gestionamos
    const managed = [
        "query","sorting", "data_category",
        "author","tags","community",
        "date_from","date_to","min_downloads","min_views"
    ];
    managed.forEach(k => p.delete(k));

    // añade solo los que tienen valor
    Object.entries(params).forEach(([k, v]) => {
        if (v !== undefined && v !== null && v !== "") p.set(k, String(v));
    });

    history.replaceState(null, "", `${url.pathname}?${p.toString()}`);
}

function hydrateFromURL() {
    const p = new URLSearchParams(window.location.search);

    const query = p.get("query");
    if (query && get('query')) get('query').value = query;
    
    
    const pt = p.get("data_category");
    if (pt && get('data_category')) get('data_category').value = pt;


    const sorting = p.get("sorting");
    if (sorting) {
        const radio = document.querySelector(`[name="sorting"][value="${sorting}"]`);
        if (radio) radio.checked = true;
    }

    // avanzados
    if (p.get("author") && get('author')) get('author').value = p.get("author");
    if (p.get("tags") && get('tags')) get('tags').value = p.get("tags");
    if (p.get("filenames") && get('filenames')) get('filenames').value = p.get("filenames");
    if (p.get("community") && get('community')) get('community').value = p.get("community");

    // fechas
    const df = p.get("date_from"); // YYYY-MM-DD
    if (df) {
        const [y, m, d] = df.split("-");
        if (get('date_from_year')) get('date_from_year').value = y || "";
        if (get('date_from_month')) get('date_from_month').value = m || "";
        if (get('date_from_day')) get('date_from_day').value = d || "";
    }
    const dt = p.get("date_to");
    if (dt) {
        const [y, m, d] = dt.split("-");
        if (get('date_to_year')) get('date_to_year').value = y || "";
        if (get('date_to_month')) get('date_to_month').value = m || "";
        if (get('date_to_day')) get('date_to_day').value = d || "";
    }

    // descargas y vistas mínimas
    if (p.get("min_downloads") && get('min_downloads')) get('min_downloads').value = p.get("min_downloads");
    if (p.get("min_views") && get('min_views')) get('min_views').value = p.get("min_views");
}

function collectSearchCriteria() {
    const csrfEl = get('csrf_token');
    const csrfToken = csrfEl ? csrfEl.value : "";

    // existentes
    const query = get('query')?.value || "";
    const data_category = get('data_category')?.value || "any";
    const sorting = document.querySelector('[name="sorting"]:checked')?.value || "newest";

    // avanzados
    const author = get('author')?.value?.trim() || "";
    const tags = get('tags')?.value?.trim() || "";             // CSV: "tag1, tag2"
    const community = get('community')?.value?.trim() || "";  // TODO: nuevo campo
    const filenames = get('filenames')?.value?.trim() || "";
    const date_from = buildDateFromParts("date_from");
    const date_to = buildDateFromParts("date_to");
    const min_downloads = get('min_downloads')?.value?.trim();
    const min_views = get('min_views')?.value?.trim();

    const searchCriteria = {
        csrf_token: csrfToken,
        query: query,
        data_category: data_category,
        sorting: sorting
    };

    // añade solo si tienen valor por si el backend aún no soporta estos campos
    if (author) searchCriteria.author = author;
    if (tags) searchCriteria.tags = tags;
    if (filenames) searchCriteria.filenames = filenames;
    if (community) searchCriteria.community = community;
    if (date_from) searchCriteria.date_from = date_from;
    if (date_to) searchCriteria.date_to = date_to;
    if (min_downloads !== "" && !Number.isNaN(Number(min_downloads))) {
        searchCriteria.min_downloads = Number(min_downloads);
    }
    if (min_views !== "" && !Number.isNaN(Number(min_views))) {
        searchCriteria.min_views = Number(min_views);
    }

    // sincroniza URL 
    updateURL({
        query, data_category, sorting,
        author, tags, filenames, community, date_from, date_to,
        min_downloads: searchCriteria.min_downloads,
        min_views: searchCriteria.min_views
    });

    return searchCriteria;
}

// listeners + fetch
function send_query() {

    console.log("send query...");

    // listeners en filtros "clásicos" + avanzados
    const filters = document.querySelectorAll(
        '#filters input, #filters select, #filters [type="radio"], ' +
        '#advanced-filters input, #advanced-filters select, #advanced-filters [type="radio"]'
    );

    // botón Clear Filters
    document.getElementById('clear-filters')?.addEventListener('click', clearFilters);

    // para cualquier cambio en cualquier filtro, buscar
    filters.forEach(filter => {
        filter.addEventListener('input', () => {
            triggerSearch();
        });
    });

    // primera búsqueda (si no la dispara hydrateFromURL)
    triggerSearch();

    function triggerSearch() {
        document.getElementById('results').innerHTML = '';
        document.getElementById("results_not_found").style.display = "none";

        const searchCriteria = collectSearchCriteria();

        fetch('/explore', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(searchCriteria),
        })
        .then(response => response.json())
        .then(data => {
            console.log(data);
            document.getElementById('results').innerHTML = '';

            // results counter
            const resultCount = Array.isArray(data) ? data.length : (data?.length ?? 0);
            const resultText = resultCount === 1 ? 'dataset' : 'datasets';
            document.getElementById('results_number').textContent = `${resultCount} ${resultText} found`;

            if (resultCount === 0) {
                document.getElementById("results_not_found").style.display = "block";
                return;
            } else {
                document.getElementById("results_not_found").style.display = "none";
            }

            (Array.isArray(data) ? data : []).forEach(dataset => {
                let card = document.createElement('div');
                card.className = 'col-12';
                card.innerHTML = `
                    <div class="card">
                        <div class="card-body">
                            <div class="d-flex align-items-center justify-content-between">
                                <h3><a href="${dataset.url}">${escapeHtml(dataset.title)}</a></h3>
                                <div>
                                    <span class="badge bg-primary" style="cursor: pointer;"
                                          onclick="set_data_category_as_query('${dataset.data_category}')">
                                          ${dataset.data_category}
                                    </span>
                                </div>
                            </div>
                            <p class="text-secondary">${formatDate(dataset.created_at)}</p>
                            <div class="row mb-2">
                                <div class="col-md-4 col-12">
                                    <span class=" text-secondary">Description</span>
                                </div>
                                <div class="col-md-8 col-12">
                                    <p class="card-text">${dataset.description}</p>
                                </div>
                            </div>

                            <div class="row mb-2">
                                <div class="col-md-4 col-12">
                                    <span class=" text-secondary">Authors</span>
                                </div>
                                <div class="col-md-8 col-12">
                                    ${ (dataset.authors || []).map(a => `<p> ${escapeHtml(a.name)} </p>`).join('') }
                                </div>
                            </div>

                            <div class="row mb-2">
                                <div class="col-md-4 col-12">
                                    <span class=" text-secondary">Tags</span>
                                </div>
                                <div class="col-md-8 col-12">
                                    ${dataset.tags.map(tag => `
                                        <span class="badge bg-primary me-1" style="cursor: pointer;"
                                              onclick="set_tag_as_query('${tag}')">${tag}</span>
                                    `).join('')}
                                </div>
                            </div>

                            <div class="row">
                                <div class="col-md-4 col-12"></div>
                                <div class="col-md-8 col-12">
                                    <a href="${dataset.url}" class="btn btn-outline-primary btn-sm" style="border-radius: 5px;">
                                        View dataset
                                    </a>
                                    <a href="/dataset/download/${dataset.id}" class="btn btn-outline-primary btn-sm" style="border-radius: 5px;">
                                        Download (${dataset.total_size_in_human_format})
                                    </a>
                                </div>
                            </div>
                        </div>
                    </div>
                `;
                document.getElementById('results').appendChild(card);
            });
        })
        .catch(err => {
            console.error("Explore fetch failed:", err);
        });
    }
}

function formatDate(dateString) {
    const options = {day: 'numeric', month: 'long', year: 'numeric', hour: 'numeric', minute: 'numeric'};
    const date = new Date(dateString);
    return date.toLocaleString('en-US', options);
}
function set_data_category_as_query(DataCategory) {
    const DataCategorySelect = document.getElementById('data_category');
    for (let i = 0; i < DataCategorySelect.options.length; i++) {
        if (DataCategorySelect.options[i].text === DataCategory.trim()) {
            DataCategorySelect.value = DataCategorySelect.options[i].value;
            break;
        }
    }
    DataCategorySelect.dispatchEvent(new Event('input', {bubbles: true}));
}

function set_tag_as_query(tagName) {
    const queryInput = document.getElementById('query');
    queryInput.value = tagName.trim();
    queryInput.dispatchEvent(new Event('input', {bubbles: true}));
}

document.getElementById('clear-filters')?.addEventListener('click', clearFilters);

function clearFilters() {
    // Reset filtros "clásicos"
    let queryInput = document.querySelector('#query');
    queryInput.value = "";
    let DataCategorySelect = document.querySelector('#data_category');
    DataCategorySelect.value = "any";
    let sortingOptions = document.querySelectorAll('[name="sorting"]');
    sortingOptions.forEach(option => {
        option.checked = option.value == "newest";
    });

    // Reset avanzados
    ['author','tags', 'filenames','community','min_downloads','min_views',
     'date_from_day','date_from_month','date_from_year',
     'date_to_day','date_to_month','date_to_year'
    ].forEach(id => { if (get(id)) get(id).value = ""; });

    // dispara nueva búsqueda
    queryInput.dispatchEvent(new Event('input', {bubbles: true}));
}

function escapeHtml(str) {
  if (str === null || str === undefined) return '';
  return String(str)
    .replace(/&/g,'&amp;')
    .replace(/</g,'&lt;')
    .replace(/>/g,'&gt;')
    .replace(/"/g,'&quot;')
    .replace(/'/g,'&#39;');
}
