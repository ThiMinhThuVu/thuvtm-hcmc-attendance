const search = document.querySelector('#student-search');
const filter = document.querySelector('#attendance-filter');
const rows = [...document.querySelectorAll('#student-table tr[data-search]')];
const noResults = document.querySelector('#no-results');

function applyFilters() {
  const query = search.value.trim().toLowerCase();
  const selected = filter.value;
  let visible = 0;
  rows.forEach(row => {
    const matchesText = row.dataset.search.includes(query);
    const matchesFilter = selected === 'all' ||
      (selected === 'hcmc-no' && row.dataset.hcmc === '1' && row.dataset.attendance === 'no') ||
      row.dataset.attendance === selected;
    row.hidden = !(matchesText && matchesFilter);
    if (!row.hidden) visible++;
  });
  noResults.hidden = visible > 0 || rows.length === 0;
}
search.addEventListener('input', applyFilters);
filter.addEventListener('change', applyFilters);

