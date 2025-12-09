function escapeHtml(str) {
    if (str === null || str === undefined) return '';
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

function renderTrendingList(items, byLabel) {
    if (!items || items.length === 0) {
        return '<p class="text-muted">No trending datasets yet.</p>';
    }

    var html = '<ul class="list-unstyled mb-0">';
    items.forEach(function(it) {
        var title = it.title || 'Untitled';
        var author = it.first_author || '';
        var community_name = it.community_name || '';
        var community_url = it.community_url || '';
        var metric = it.metric || 0;
        var url = it.url || '#';

        html += '<li class="mb-2">';
        html += '<div class="d-flex justify-content-between align-items-start">';
        html += '<div>';
        html += '<a href="' + url + '"><strong>' + escapeHtml(title) + '</strong></a>';
        if (author || community_name) {
            html += '<div class="small text-secondary">';
            if (author) {
                html += escapeHtml(author);
            }
            if (community_name) {
                if (community_url) {
                    html += ' &nbsp;•&nbsp; <a href="' + community_url + '">' + escapeHtml(community_name) + '</a>';
                } else {
                    html += ' &nbsp;•&nbsp; ' + escapeHtml(community_name);
                }
            }
            html += '</div>';
        }
        html += '</div>';
        html += '<div class="text-end"><div class="small text-muted">' + metric + ' ' + escapeHtml(byLabel) + '</div></div>';
        html += '</div></li>';
    });
    html += '</ul>';
    return html;
}


function fetchTrendingAndRender(byValue, periodValue) {
    var bySelector = document.getElementById('trending-by');
    var periodSelector = document.getElementById('trending-period');
    var by = byValue || (bySelector ? bySelector.value : 'views');
    var period = periodValue || (periodSelector ? periodSelector.value : 'week');
    var url = '/trending_datasets?by=' + encodeURIComponent(by) + '&period=' + encodeURIComponent(period) + '&limit=5';

    fetch(url, { method: 'GET', credentials: 'same-origin' })
        .then(function(response) {
            if (!response.ok) throw new Error('Network response was not ok');
            return response.json();
        })
        .then(function(data) {
            var byLabel = (data.by === 'downloads') ? 'downloads' : 'views';
            var html = renderTrendingList(data.items, byLabel);
            var container = document.getElementById('trending-list');
            if (container) {
                container.innerHTML = html;
                container.setAttribute('data-by', data.by || by);
                container.setAttribute('data-testid', 'trending-list-primary');
            }
        })
        .catch(function(err) {
            console.error('Error fetching trending datasets:', err);
        });
}

function initializeTrendingWidget() {
    if (window.__trendingWidgetInitialized) {
        return;
    }

    var bySelector = document.getElementById('trending-by');
    var periodSelector = document.getElementById('trending-period');

    if (!bySelector && !periodSelector) {
        return;
    }

    window.__trendingWidgetInitialized = true;
    var lastBy;
    var lastPeriod;

    function maybeFetch(force) {
        var currentBy = (bySelector && bySelector.value) || 'views';
        var currentPeriod = (periodSelector && periodSelector.value) || 'week';

        if (force || currentBy !== lastBy || currentPeriod !== lastPeriod) {
            lastBy = currentBy;
            lastPeriod = currentPeriod;
            fetchTrendingAndRender(currentBy, currentPeriod);
        }
    }

    if (bySelector) {
        bySelector.addEventListener('change', function() {
            maybeFetch(true);
        });
    }

    if (periodSelector) {
        periodSelector.addEventListener('change', function() {
            maybeFetch(true);
        });
    }

    maybeFetch(true);

    if (!window.__trendingWidgetIntervalId) {
        window.__trendingWidgetIntervalId = setInterval(function() {
            maybeFetch(false);
        }, 1200);
    }
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initializeTrendingWidget);
} else {
    initializeTrendingWidget();
}
