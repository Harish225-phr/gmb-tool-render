/**
 * LeadPulse - Frontend Application Logic
 * Production-ready lead scraper dashboard
 */

document.addEventListener('DOMContentLoaded', () => {
  // State management
  let currentJobId = null;
  let pollInterval = null;
  let allLeads = [];
  let filteredLeads = [];
  let selectedIndices = new Set(); // indices in allLeads
  let currentPage = 1;
  const pageSize = 15;

  // DOM Elements
  const searchForm = document.getElementById('search-form');
  const nicheInput = document.getElementById('niche-input');
  const locationsInput = document.getElementById('locations-input');
  const limitInput = document.getElementById('limit-input');
  const submitBtn = document.getElementById('submit-btn');
  const cancelBtn = document.getElementById('cancel-btn');
  const presetBtn = document.getElementById('preset-btn');
  const loadSampleBtn = document.getElementById('load-sample-btn');
  const tableSampleBtn = document.getElementById('table-sample-btn');
  const locationCountBadge = document.getElementById('location-count-badge');

  // Stat Elements
  const statTotalLeads = document.getElementById('stat-total-leads');
  const statLeadsSub = document.getElementById('stat-leads-sub');
  const statUniqueDomains = document.getElementById('stat-unique-domains');
  const statDomainsSub = document.getElementById('stat-domains-sub');
  const statNoWebsite = document.getElementById('stat-no-website');
  const statAvgRating = document.getElementById('stat-avg-rating');
  const statRatingSub = document.getElementById('stat-rating-sub');

  // Progress Elements
  const progressCard = document.getElementById('progress-card');
  const progressBar = document.getElementById('progress-bar');
  const progressStatusText = document.getElementById('progress-status-text');
  const progressBadge = document.getElementById('progress-badge');
  const currentLocText = document.getElementById('current-loc-text');
  const progressCountsText = document.getElementById('progress-counts-text');
  const progressSpinner = document.getElementById('progress-spinner');
  const progressWarnings = document.getElementById('progress-warnings');
  const progressWarningsText = document.getElementById('progress-warnings-text');

  // Filter Elements
  const websiteFilter = document.getElementById('website-filter');
  const ratingFilter = document.getElementById('rating-filter');
  const keywordFilter = document.getElementById('keyword-filter');

  // Table Elements
  const tableBody = document.getElementById('leads-tbody');
  const tableCountBadge = document.getElementById('table-count-badge');
  const selectAllCheckbox = document.getElementById('select-all-checkbox');
  const selectedCounter = document.getElementById('selected-counter');
  const clearSelectionBtn = document.getElementById('clear-selection-btn');
  const paginationInfo = document.getElementById('pagination-info');
  const paginationNav = document.getElementById('pagination-nav');

  // Modal & Toast
  const leadModal = new bootstrap.Modal(document.getElementById('leadDetailsModal'));
  const modalBodyContent = document.getElementById('modal-body-content');
  const actionToast = new bootstrap.Toast(document.getElementById('actionToast'), { delay: 3000 });
  const toastMessage = document.getElementById('toast-message');
  const toastIcon = document.getElementById('toast-icon');

  // Helper: Display Toast Notification
  function showToast(message, isError = false) {
    toastMessage.textContent = message;
    if (isError) {
      toastIcon.className = 'bi bi-exclamation-triangle-fill text-warning fs-5';
    } else {
      toastIcon.className = 'bi bi-check-circle-fill text-success fs-5';
    }
    actionToast.show();
  }

  // Helper: Fallback Clipboard Copy
  async function copyToClipboard(text, successMsg) {
    if (!text || text.trim() === '') {
      showToast('No matching data to copy.', true);
      return;
    }
    try {
      if (navigator.clipboard && window.isSecureContext) {
        await navigator.clipboard.writeText(text);
        showToast(successMsg);
      } else {
        // Fallback for non-https or older browser context
        const textarea = document.createElement('textarea');
        textarea.value = text;
        textarea.style.position = 'fixed';
        textarea.style.left = '-9999px';
        document.body.appendChild(textarea);
        textarea.select();
        document.execCommand('copy');
        document.body.removeChild(textarea);
        showToast(successMsg);
      }
    } catch (err) {
      console.error('Clipboard error:', err);
      showToast('Failed to copy to clipboard.', true);
    }
  }

  // Update Location Count Badge
  function updateLocationCount() {
    const lines = locationsInput.value.split('\n').map(l => l.trim()).filter(l => l.length > 0);
    const unique = new Set(lines.map(l => l.toLowerCase()));
    locationCountBadge.textContent = `${unique.size} locations`;
  }
  locationsInput.addEventListener('input', updateLocationCount);
  updateLocationCount();

  // Load Preset Locations
  presetBtn.addEventListener('click', () => {
    locationsInput.value = `Indianapolis, IN\nCarmel, IN\nFishers, IN\nNoblesville, IN\nGreenwood, IN\nAvon, IN\nZionsville, IN\nPlainfield, IN`;
    updateLocationCount();
    showToast('Loaded 8 sample locations.');
  });

  // Calculate & Render Stats
  function updateSummaryStats(stats, leads) {
    if (!stats) {
      const uniqueDomains = new Set(leads.map(l => l.website_domain).filter(Boolean));
      const noWebsites = leads.filter(l => !l.website_url).length;
      const validRatings = leads.map(l => l.rating).filter(r => r !== null && r !== undefined);
      const avg = validRatings.length > 0 ? (validRatings.reduce((a, b) => a + b, 0) / validRatings.length).toFixed(2) : null;
      stats = {
        total_records: leads.length,
        unique_domains: uniqueDomains.size,
        businesses_without_websites: noWebsites,
        valid_ratings_count: validRatings.length,
        average_rating: avg
      };
    }

    statTotalLeads.textContent = stats.total_records.toLocaleString();
    statUniqueDomains.textContent = stats.unique_domains.toLocaleString();
    statNoWebsite.textContent = stats.businesses_without_websites.toLocaleString();

    if (stats.total_records > 0) {
      const siteRate = Math.round(((stats.total_records - stats.businesses_without_websites) / stats.total_records) * 100);
      statDomainsSub.textContent = `${siteRate}% have websites`;
    } else {
      statDomainsSub.textContent = '0% website discovery rate';
    }

    if (stats.average_rating !== null && stats.average_rating !== undefined) {
      statAvgRating.textContent = `${stats.average_rating} ★`;
      statRatingSub.textContent = `Across ${stats.valid_ratings_count} rated records`;
    } else {
      statAvgRating.textContent = '—';
      statRatingSub.textContent = 'No rating data available';
    }
  }

  // Filter Leads
  function applyFilters() {
    const webFilterVal = websiteFilter.value;
    const ratingFilterVal = ratingFilter.value;
    const keyword = keywordFilter.value.trim().toLowerCase();

    filteredLeads = allLeads.filter(lead => {
      // Website filter
      if (webFilterVal === 'with_site' && !lead.website_url) return false;
      if (webFilterVal === 'without_site' && lead.website_url) return false;

      // Rating filter
      if (ratingFilterVal === 'unrated') {
        if (lead.rating !== null && lead.rating !== undefined) return false;
      } else if (ratingFilterVal !== '0') {
        const minRating = parseFloat(ratingFilterVal);
        if (lead.rating === null || lead.rating === undefined || lead.rating < minRating) return false;
      }

      // Keyword filter
      if (keyword) {
        const name = (lead.business_name || '').toLowerCase();
        const domain = (lead.website_domain || '').toLowerCase();
        const location = (lead.location || '').toLowerCase();
        if (!name.includes(keyword) && !domain.includes(keyword) && !location.includes(keyword)) {
          return false;
        }
      }

      return true;
    });

    currentPage = 1;
    renderTable();
  }

  websiteFilter.addEventListener('change', applyFilters);
  ratingFilter.addEventListener('change', applyFilters);
  keywordFilter.addEventListener('input', applyFilters);

  // Render Table Rows
  function renderTable() {
    tableCountBadge.textContent = `${filteredLeads.length} leads`;
    tableBody.innerHTML = '';

    if (filteredLeads.length === 0) {
      tableBody.innerHTML = `
        <tr>
          <td colspan="9" class="text-center py-5">
            <div class="text-muted">
              <i class="bi bi-inbox display-6 d-block mb-3 text-secondary opacity-50"></i>
              <h6 class="fw-semibold">No Matching Leads Found</h6>
              <p class="small mb-0">Try adjusting your filters or running a new search.</p>
            </div>
          </td>
        </tr>
      `;
      paginationInfo.textContent = 'Showing 0 of 0 leads';
      paginationNav.innerHTML = '';
      return;
    }

    const startIndex = (currentPage - 1) * pageSize;
    const endIndex = Math.min(startIndex + pageSize, filteredLeads.length);
    const pageLeads = filteredLeads.slice(startIndex, endIndex);

    pageLeads.forEach((lead) => {
      // Find actual index in allLeads for stable selection
      const globalIndex = allLeads.indexOf(lead);
      const isChecked = selectedIndices.has(globalIndex);

      const tr = document.createElement('tr');

      // Rating formatting
      let ratingHtml = `<span class="unrated-pill">Unrated</span>`;
      if (lead.rating !== null && lead.rating !== undefined) {
        const reviewsText = lead.review_count !== null && lead.review_count !== undefined 
          ? `<span class="text-muted small ms-1">(${lead.review_count.toLocaleString()})</span>` 
          : '';
        ratingHtml = `<span class="rating-pill"><i class="bi bi-star-fill text-warning"></i>${lead.rating.toFixed(1)}</span>${reviewsText}`;
      }

      // Website formatting
      let websiteHtml = `<span class="badge badge-warning-soft"><i class="bi bi-x-circle me-1"></i>No Website</span>`;
      let domainHtml = `<span class="text-muted small">—</span>`;
      if (lead.website_url) {
        websiteHtml = `<a href="${lead.website_url}" target="_blank" rel="noopener noreferrer" class="text-decoration-none text-primary d-inline-flex align-items-center gap-1 small text-truncate" style="max-width: 170px;" title="${lead.website_url}">
          <span>Visit</span><i class="bi bi-box-arrow-up-right fs-7"></i>
        </a>`;
        if (lead.website_domain) {
          domainHtml = `<span class="domain-tag" title="${lead.website_domain}">${lead.website_domain}</span>`;
        }
      }

      // Status badge
      let statusBadge = `<span class="badge badge-live">Live</span>`;
      if (lead.collection_status === 'sample') {
        statusBadge = `<span class="badge badge-sample">Sample</span>`;
      } else if (lead.collection_status === 'partial') {
        statusBadge = `<span class="badge bg-warning-subtle text-warning border">Partial</span>`;
      }

      tr.innerHTML = `
        <td class="text-center">
          <input type="checkbox" class="form-check-input row-checkbox" data-index="${globalIndex}" ${isChecked ? 'checked' : ''}>
        </td>
        <td>
          <a href="#" class="business-name-link view-details-link" data-index="${globalIndex}">
            ${escapeHtml(lead.business_name)}
          </a>
          <div class="text-muted small">${escapeHtml(lead.category_or_niche || '')}</div>
        </td>
        <td>
          <span class="small fw-medium">${escapeHtml(lead.location)}</span>
        </td>
        <td>${ratingHtml}</td>
        <td>${websiteHtml}</td>
        <td>${domainHtml}</td>
        <td><span class="badge bg-light text-secondary border small">${escapeHtml(lead.source_name || 'Web')}</span></td>
        <td>${statusBadge}</td>
        <td class="text-end pe-3">
          <button class="btn btn-xs btn-outline-secondary view-details-btn" data-index="${globalIndex}" title="View metadata and source link">
            <i class="bi bi-info-circle"></i>
          </button>
        </td>
      `;

      tableBody.appendChild(tr);
    });

    updateSelectionUI();
    renderPagination(filteredLeads.length, startIndex, endIndex);
  }

  function renderPagination(totalItems, startIndex, endIndex) {
    paginationInfo.textContent = `Showing ${startIndex + 1}–${endIndex} of ${totalItems} leads`;
    const totalPages = Math.ceil(totalItems / pageSize);
    paginationNav.innerHTML = '';

    if (totalPages <= 1) return;

    // Previous Button
    const prevLi = document.createElement('li');
    prevLi.className = `page-item ${currentPage === 1 ? 'disabled' : ''}`;
    prevLi.innerHTML = `<a class="page-link" href="#" aria-label="Previous">&laquo;</a>`;
    prevLi.addEventListener('click', (e) => {
      e.preventDefault();
      if (currentPage > 1) {
        currentPage--;
        renderTable();
      }
    });
    paginationNav.appendChild(prevLi);

    // Numbered pages
    for (let p = 1; p <= totalPages; p++) {
      if (p === 1 || p === totalPages || (p >= currentPage - 2 && p <= currentPage + 2)) {
        const li = document.createElement('li');
        li.className = `page-item ${p === currentPage ? 'active' : ''}`;
        li.innerHTML = `<a class="page-link" href="#">${p}</a>`;
        li.addEventListener('click', (e) => {
          e.preventDefault();
          currentPage = p;
          renderTable();
        });
        paginationNav.appendChild(li);
      } else if (p === currentPage - 3 || p === currentPage + 3) {
        const li = document.createElement('li');
        li.className = 'page-item disabled';
        li.innerHTML = `<span class="page-link">…</span>`;
        paginationNav.appendChild(li);
      }
    }

    // Next Button
    const nextLi = document.createElement('li');
    nextLi.className = `page-item ${currentPage === totalPages ? 'disabled' : ''}`;
    nextLi.innerHTML = `<a class="page-link" href="#" aria-label="Next">&raquo;</a>`;
    nextLi.addEventListener('click', (e) => {
      e.preventDefault();
      if (currentPage < totalPages) {
        currentPage++;
        renderTable();
      }
    });
    paginationNav.appendChild(nextLi);
  }

  // Row Checkbox & Selection Handlers
  tableBody.addEventListener('change', (e) => {
    if (e.target.classList.contains('row-checkbox')) {
      const index = parseInt(e.target.dataset.index, 10);
      if (e.target.checked) {
        selectedIndices.add(index);
      } else {
        selectedIndices.delete(index);
      }
      updateSelectionUI();
    }
  });

  selectAllCheckbox.addEventListener('change', () => {
    const isChecked = selectAllCheckbox.checked;
    filteredLeads.forEach(lead => {
      const idx = allLeads.indexOf(lead);
      if (isChecked) {
        selectedIndices.add(idx);
      } else {
        selectedIndices.delete(idx);
      }
    });
    document.querySelectorAll('.row-checkbox').forEach(cb => cb.checked = isChecked);
    updateSelectionUI();
  });

  clearSelectionBtn.addEventListener('click', () => {
    selectedIndices.clear();
    selectAllCheckbox.checked = false;
    document.querySelectorAll('.row-checkbox').forEach(cb => cb.checked = false);
    updateSelectionUI();
    showToast('Selection cleared.');
  });

  function updateSelectionUI() {
    selectedCounter.textContent = `${selectedIndices.size} selected`;
  }

  // Open Lead Details Modal
  tableBody.addEventListener('click', (e) => {
    const target = e.target.closest('.view-details-btn, .view-details-link');
    if (target) {
      e.preventDefault();
      const index = parseInt(target.dataset.index, 10);
      const lead = allLeads[index];
      if (lead) {
        openLeadModal(lead);
      }
    }
  });

  function openLeadModal(lead) {
    modalBodyContent.innerHTML = `
      <div class="mb-3">
        <h5 class="fw-bold mb-1">${escapeHtml(lead.business_name)}</h5>
        <span class="badge bg-primary-subtle text-primary border">${escapeHtml(lead.category_or_niche || 'Business')}</span>
        <span class="badge bg-light text-dark border ms-1">${escapeHtml(lead.collection_status || 'Live')}</span>
      </div>

      <div class="row g-2">
        <div class="col-6">
          <div class="detail-label">Location</div>
          <div class="detail-value"><i class="bi bi-geo-alt me-1 text-danger"></i>${escapeHtml(lead.location)}</div>
        </div>
        <div class="col-6">
          <div class="detail-label">Rating & Reviews</div>
          <div class="detail-value">
            ${lead.rating !== null && lead.rating !== undefined ? `<strong>${lead.rating.toFixed(1)} ★</strong> (${(lead.review_count || 0)} reviews)` : '<span class="text-muted">No rating available</span>'}
          </div>
        </div>
        <div class="col-12">
          <div class="detail-label">Physical Address</div>
          <div class="detail-value text-muted">${escapeHtml(lead.address || 'Not specified by public source')}</div>
        </div>
        <div class="col-6">
          <div class="detail-label">Phone Number</div>
          <div class="detail-value">${lead.phone ? `<a href="tel:${lead.phone}">${escapeHtml(lead.phone)}</a>` : '<span class="text-muted">None available</span>'}</div>
        </div>
        <div class="col-6">
          <div class="detail-label">Registrable Domain</div>
          <div class="detail-value">${lead.website_domain ? `<code>${escapeHtml(lead.website_domain)}</code>` : '<span class="text-muted">None</span>'}</div>
        </div>
        <div class="col-12">
          <div class="detail-label">Website URL</div>
          <div class="detail-value">
            ${lead.website_url ? `<a href="${lead.website_url}" target="_blank" rel="noopener noreferrer">${escapeHtml(lead.website_url)} <i class="bi bi-box-arrow-up-right fs-7"></i></a>` : '<span class="badge badge-warning-soft">No website listed</span>'}
          </div>
        </div>
        <div class="col-12 border-top pt-2">
          <div class="detail-label">Data Provenance / Source</div>
          <div class="detail-value small">
            <div><strong>Source:</strong> ${escapeHtml(lead.source_name || 'Web Provider')}</div>
            <div class="text-truncate"><strong>URL:</strong> <a href="${lead.source_url}" target="_blank" rel="noopener noreferrer">${escapeHtml(lead.source_url || '')}</a></div>
            <div class="text-muted mt-1"><strong>Collected At:</strong> ${lead.collected_at ? new Date(lead.collected_at).toLocaleString() : 'N/A'}</div>
          </div>
        </div>
      </div>
    `;
    leadModal.show();
  }

  // Handle Search Submission
  searchForm.addEventListener('submit', async (e) => {
    e.preventDefault();

    const niche = nicheInput.value.trim();
    const locations = locationsInput.value.split('\n').map(l => l.trim()).filter(Boolean);
    const limit = parseInt(limitInput.value, 10) || 20;

    if (!niche) {
      showToast('Please enter a business niche.', true);
      return;
    }
    if (locations.length === 0) {
      showToast('Please enter at least one location.', true);
      return;
    }

    // UI state for running search
    submitBtn.disabled = true;
    submitBtn.classList.add('d-none');
    cancelBtn.classList.remove('d-none');
    cancelBtn.disabled = false;

    progressCard.classList.remove('d-none');
    progressBar.style.width = '5%';
    progressBar.classList.add('progress-bar-animated', 'progress-bar-striped');
    progressStatusText.textContent = `Queuing search across ${locations.length} locations...`;
    progressBadge.textContent = `0 / ${locations.length}`;
    currentLocText.textContent = 'Preparing worker pool...';
    progressCountsText.textContent = '0 leads collected';
    progressWarnings.classList.add('d-none');

    // Reset leads
    allLeads = [];
    selectedIndices.clear();
    applyFilters();

    try {
      const resp = await fetch('/api/search', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          niche: niche,
          locations: locations,
          limit_per_location: limit
        })
      });

      const data = await resp.json();
      if (!resp.ok || !data.success) {
        throw new Error(data.error || 'Failed to start search');
      }

      currentJobId = data.job_id;
      startPolling(currentJobId);
      showToast(`Search started across ${data.total_locations} locations.`);

    } catch (err) {
      console.error('Search start error:', err);
      showToast(err.message, true);
      resetSearchControls();
    }
  });

  // Polling Job Status
  function startPolling(jobId) {
    if (pollInterval) clearInterval(pollInterval);

    pollInterval = setInterval(async () => {
      try {
        const resp = await fetch(`/api/jobs/${jobId}`);
        if (!resp.ok) return;

        const res = await resp.json();
        if (!res.success) return;

        const job = res.data;
        updateJobProgressUI(job);

        // Update leads continuously
        if (job.leads && job.leads.length > 0) {
          allLeads = job.leads;
          applyFilters();
          updateSummaryStats(job.summary_stats, allLeads);
        }

        // Check if finished
        if (job.status === 'completed' || job.status === 'failed' || job.status === 'cancelled') {
          clearInterval(pollInterval);
          pollInterval = null;
          finalizeJobUI(job);
        }

      } catch (err) {
        console.warn('Poll error:', err);
      }
    }, 1500);
  }

  function updateJobProgressUI(job) {
    const total = job.total_locations || 1;
    const completed = job.completed_locations || 0;
    const percent = Math.min(100, Math.round((completed / total) * 100));

    progressBar.style.width = `${Math.max(5, percent)}%`;
    progressBadge.textContent = `${completed} / ${total}`;
    progressStatusText.textContent = job.status === 'running' 
      ? `Processing: ${job.current_location || 'Searching...'}` 
      : `Status: ${job.status}`;
    currentLocText.textContent = job.current_location ? `Current: ${job.current_location}` : '—';
    progressCountsText.textContent = `${(job.lead_count || 0).toLocaleString()} leads discovered`;

    if (job.errors && job.errors.length > 0) {
      progressWarnings.classList.remove('d-none');
      progressWarningsText.textContent = `${job.errors.length} provider notice(s). Handled gracefully with fallbacks.`;
    }
  }

  function finalizeJobUI(job) {
    resetSearchControls();
    progressBar.classList.remove('progress-bar-animated', 'progress-bar-striped');
    progressSpinner.classList.add('d-none');

    if (job.status === 'completed') {
      progressBar.style.width = '100%';
      progressStatusText.textContent = `Search completed! ${job.lead_count} leads discovered.`;
      showToast(`Search completed with ${job.lead_count} leads.`);
    } else if (job.status === 'cancelled') {
      progressStatusText.textContent = 'Search was cancelled.';
      showToast('Search was cancelled.');
    } else {
      progressStatusText.textContent = 'Search finished with warnings.';
      showToast('Search finished.', true);
    }
  }

  function resetSearchControls() {
    submitBtn.disabled = false;
    submitBtn.classList.remove('d-none');
    cancelBtn.classList.add('d-none');
  }

  // Cancel Job
  cancelBtn.addEventListener('click', async () => {
    if (!currentJobId) return;
    cancelBtn.disabled = true;
    cancelBtn.innerHTML = `<span class="spinner-border spinner-border-sm me-1"></span>Cancelling...`;
    try {
      await fetch(`/api/jobs/${currentJobId}/cancel`, { method: 'POST' });
      showToast('Cancelling search...');
    } catch (err) {
      console.error('Cancel error:', err);
    }
  });

  // Load Sample Data (For Preview / Testing)
  async function loadSamplePreview() {
    try {
      const resp = await fetch('/api/sample-data');
      const res = await resp.json();
      if (res.success) {
        allLeads = res.data.leads;
        selectedIndices.clear();
        applyFilters();
        updateSummaryStats(res.data.summary_stats, allLeads);
        statLeadsSub.textContent = 'Loaded sample preview data';
        showToast('Sample dataset loaded for testing.');
      }
    } catch (err) {
      showToast('Could not load sample data.', true);
    }
  }
  loadSampleBtn.addEventListener('click', loadSamplePreview);
  tableSampleBtn.addEventListener('click', loadSamplePreview);

  // Bulk Clipboard Copy Actions
  // 1. Copy Selected Websites
  document.getElementById('copy-selected-sites-btn').addEventListener('click', () => {
    const urls = [];
    selectedIndices.forEach(idx => {
      const lead = allLeads[idx];
      if (lead && lead.website_url) {
        urls.push(lead.website_url);
      }
    });
    const unique = [...new Set(urls)];
    copyToClipboard(unique.join('\n'), `Copied ${unique.length} selected website URLs to clipboard!`);
  });

  // 2. Copy All Websites
  document.getElementById('copy-all-sites-btn').addEventListener('click', () => {
    const urls = allLeads.map(l => l.website_url).filter(Boolean);
    const unique = [...new Set(urls)];
    copyToClipboard(unique.join('\n'), `Copied ${unique.length} unique website URLs to clipboard!`);
  });

  // 3. Copy Unique Domains
  document.getElementById('copy-domains-btn').addEventListener('click', () => {
    const domains = allLeads.map(l => l.website_domain).filter(Boolean);
    const unique = [...new Set(domains)];
    copyToClipboard(unique.join('\n'), `Copied ${unique.length} unique domains to clipboard!`);
  });

  // 4. Copy Selected Leads (TSV for Excel / Sheets)
  document.getElementById('copy-tsv-btn').addEventListener('click', () => {
    const selectedLeads = [];
    selectedIndices.forEach(idx => {
      const lead = allLeads[idx];
      if (lead) selectedLeads.push(lead);
    });

    if (selectedLeads.length === 0) {
      showToast('Please select at least one lead from the table.', true);
      return;
    }

    const headers = ['Business Name', 'Location', 'Rating', 'Reviews', 'Website URL', 'Domain', 'Phone'];
    const lines = [headers.join('\t')];
    selectedLeads.forEach(l => {
      lines.push([
        l.business_name || '',
        l.location || '',
        l.rating !== null && l.rating !== undefined ? l.rating : '',
        l.review_count !== null && l.review_count !== undefined ? l.review_count : '',
        l.website_url || '',
        l.website_domain || '',
        l.phone || ''
      ].join('\t'));
    });

    copyToClipboard(lines.join('\n'), `Copied ${selectedLeads.length} leads as TSV for spreadsheet paste!`);
  });

  // 5. Copy Leads Without Websites
  document.getElementById('copy-no-site-btn').addEventListener('click', () => {
    const noSiteLeads = allLeads.filter(l => !l.website_url);
    if (noSiteLeads.length === 0) {
      showToast('No leads without websites found in current results.', true);
      return;
    }
    const lines = noSiteLeads.map(l => `${l.business_name} - ${l.location}`);
    copyToClipboard(lines.join('\n'), `Copied ${noSiteLeads.length} leads without websites to clipboard!`);
  });

  // CSV Export Actions
  async function triggerCsvExport(exportType) {
    let payload = {
      export_type: exportType
    };

    if (exportType === 'selected') {
      const selected = [];
      selectedIndices.forEach(idx => {
        if (allLeads[idx]) selected.push(allLeads[idx]);
      });
      if (selected.length === 0) {
        showToast('Please select at least one lead to export.', true);
        return;
      }
      payload.leads_data = selected;
    } else if (exportType === 'filtered') {
      payload.leads_data = filteredLeads;
    } else {
      payload.leads_data = allLeads;
    }

    try {
      showToast('Generating CSV file...');
      const resp = await fetch('/api/export/csv', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });

      if (!resp.ok) throw new Error('CSV generation failed');

      const blob = await resp.blob();
      const contentDisposition = resp.headers.get('Content-Disposition') || '';
      let filename = `leads_export_${Date.now()}.csv`;
      const match = contentDisposition.match(/filename="?([^"]+)"?/);
      if (match && match[1]) {
        filename = match[1];
      }

      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);

      showToast('CSV downloaded successfully!');
    } catch (err) {
      console.error('Export error:', err);
      showToast('Failed to export CSV.', true);
    }
  }

  document.getElementById('export-all-btn').addEventListener('click', () => triggerCsvExport('all'));
  document.getElementById('export-selected-btn').addEventListener('click', () => triggerCsvExport('selected'));
  document.getElementById('export-filtered-btn').addEventListener('click', () => triggerCsvExport('filtered'));
  document.getElementById('export-unique-domains-btn').addEventListener('click', () => triggerCsvExport('domains'));
  document.getElementById('export-no-site-btn').addEventListener('click', () => triggerCsvExport('no_websites'));

  // Utility to escape HTML
  function escapeHtml(text) {
    if (!text) return '';
    return String(text)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

});
