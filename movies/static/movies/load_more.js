document.addEventListener('DOMContentLoaded', () => {
  const loadMoreBtn = document.getElementById('load-more');
  const grid = document.getElementById('movie-grid');
  if (!loadMoreBtn || !grid) return;

  const perPage = parseInt(loadMoreBtn.dataset.perPage || '0', 10);

  loadMoreBtn.addEventListener('click', () => {
    const nextUrl = loadMoreBtn.dataset.nextUrl;
    if (!nextUrl) return;

    const placeholders = [];
    for (let i = 0; i < perPage; i++) {
      const col = document.createElement('div');
      col.className = 'col';
      col.innerHTML = `
        <div class="card h-100" aria-hidden="true">
          <div class="ratio" style="--bs-aspect-ratio: 150%;">
            <div class="card-img-top placeholder-glow w-100 h-100"></div>
          </div>
          <div class="card-body">
            <h5 class="card-title placeholder-glow"><span class="placeholder col-6"></span></h5>
            <p class="card-text placeholder-glow"><span class="placeholder col-7"></span></p>
          </div>
        </div>`;
      grid.appendChild(col);
      placeholders.push(col);
    }

    fetch(nextUrl, { headers: { 'X-Requested-With': 'XMLHttpRequest' } })
      .then(response => response.json())
      .then(data => {
        placeholders.forEach(ph => ph.remove());
        grid.insertAdjacentHTML('beforeend', data.html);
        if (data.next_url) {
          loadMoreBtn.dataset.nextUrl = data.next_url;
        } else {
          loadMoreBtn.remove();
        }
      });
  });
});
