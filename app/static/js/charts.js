/**
 * OpsLens Chart.js Visualizations
 * Fetches data asynchronously from /analytics/api/chart-data
 * Forwards current dashboard date filter query parameters to maintain visualization synchronization.
 */

document.addEventListener('DOMContentLoaded', () => {
    const statusCtx = document.getElementById('statusChart');
    const priorityCtx = document.getElementById('priorityChart');
    const categoryCtx = document.getElementById('categoryChart');
    const volumeCtx = document.getElementById('volumeChart');

    if (!statusCtx || !priorityCtx || !categoryCtx) {
        return; // Not on the dashboard page
    }

    // Chart instance registry to prevent duplicate charts on re-initialization
    const chartRegistry = {};

    function renderOrCreateChart(key, canvas, config) {
        if (chartRegistry[key]) {
            chartRegistry[key].destroy();
        }
        chartRegistry[key] = new Chart(canvas, config);
        return chartRegistry[key];
    }

    function showEmptyState(canvas, message) {
        const parent = canvas.parentElement;
        if (parent) {
            canvas.style.display = 'none';
            let emptyBox = parent.querySelector('.chart-empty-state');
            if (!emptyBox) {
                emptyBox = document.createElement('div');
                emptyBox.className = 'chart-empty-state';
                emptyBox.setAttribute(
                    'style',
                    'display: flex; flex-direction: column; align-items: center; justify-content: center; height: 100%; color: var(--text-muted); font-size: 0.85rem; text-align: center; gap: 0.4rem; padding: 1rem;'
                );
                parent.appendChild(emptyBox);
            }
            emptyBox.innerHTML = '<span style="font-size: 1.6rem;" aria-hidden="true">📊</span><p style="margin: 0; color: var(--text-secondary); font-size: 0.8125rem;">' + message + '</p>';
        }
    }

    // Defensive check: verify Chart.js library is loaded before initialization
    if (typeof Chart === 'undefined') {
        console.warn('OpsLens: Chart.js library unavailable; skipping chart initialization.');
        [volumeCtx, statusCtx, priorityCtx, categoryCtx].forEach(ctx => {
            if (ctx) {
                showEmptyState(ctx, 'Chart visualization library unavailable.');
            }
        });
        return;
    }

    // Modern dark theme defaults for Chart.js matching OpsLens design tokens
    Chart.defaults.color = '#94a3b8';
    Chart.defaults.font.family = "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif";
    Chart.defaults.borderColor = '#2b3a51';

    // Standardized high-contrast tooltip configuration
    const tooltipConfig = {
        backgroundColor: '#152033',
        titleColor: '#f8fafc',
        bodyColor: '#94a3b8',
        borderColor: '#2b3a51',
        borderWidth: 1,
        padding: 10,
        cornerRadius: 6,
        boxPadding: 4,
        usePointStyle: true
    };

    // Synchronize chart data request with the page's current date filter query params
    const urlParams = new URLSearchParams(window.location.search);
    const queryString = urlParams.toString();
    const apiUrl = '/analytics/api/chart-data' + (queryString ? '?' + queryString : '');

    fetch(apiUrl)
        .then(response => {
            if (!response.ok) {
                throw new Error('Network response was not ok');
            }
            return response.json();
        })
        .then(data => {
            // 1. Incident Volume Trends Over Time (Line Chart)
            if (volumeCtx) {
                if (data.volume_trend && data.volume_trend.labels && data.volume_trend.labels.length > 0) {
                    volumeCtx.style.display = 'block';
                    renderOrCreateChart('volume', volumeCtx, {
                        type: 'line',
                        data: {
                            labels: data.volume_trend.labels,
                            datasets: [{
                                label: 'Tickets Raised',
                                data: data.volume_trend.counts,
                                borderColor: '#38bdf8',
                                backgroundColor: 'rgba(56, 189, 248, 0.12)',
                                fill: true,
                                tension: 0.3,
                                pointRadius: 4,
                                pointHoverRadius: 6,
                                pointBackgroundColor: '#38bdf8',
                                borderWidth: 2
                            }]
                        },
                        options: {
                            responsive: true,
                            maintainAspectRatio: false,
                            plugins: {
                                legend: { display: false },
                                tooltip: Object.assign({}, tooltipConfig, {
                                    callbacks: {
                                        label: context => ' ' + context.parsed.y + ' incidents'
                                    }
                                })
                            },
                            scales: {
                                y: {
                                    beginAtZero: true,
                                    ticks: { precision: 0, color: '#94a3b8' },
                                    grid: { color: 'rgba(43, 58, 81, 0.5)' }
                                },
                                x: {
                                    ticks: { color: '#94a3b8' },
                                    grid: { display: false }
                                }
                            }
                        }
                    });
                } else {
                    showEmptyState(volumeCtx, 'No incident volume recorded for the selected time window.');
                }
            }

            // 2. Status Breakdown (Doughnut Chart)
            if (statusCtx) {
                const totalStatus = (data.status && data.status.counts)
                    ? data.status.counts.reduce((a, b) => a + b, 0)
                    : 0;

                if (totalStatus > 0) {
                    statusCtx.style.display = 'block';
                    renderOrCreateChart('status', statusCtx, {
                        type: 'doughnut',
                        data: {
                            labels: data.status.labels,
                            datasets: [{
                                data: data.status.counts,
                                backgroundColor: [
                                    'rgba(56, 189, 248, 0.9)',   // Open - Cyan/Sky
                                    'rgba(251, 191, 36, 0.9)',   // In Progress - Amber
                                    'rgba(52, 211, 153, 0.9)',   // Resolved - Emerald
                                    'rgba(148, 163, 184, 0.9)'   // Closed - Slate
                                ],
                                borderColor: '#152033',
                                borderWidth: 2
                            }]
                        },
                        options: {
                            responsive: true,
                            maintainAspectRatio: false,
                            cutout: '68%',
                            plugins: {
                                legend: {
                                    position: 'bottom',
                                    labels: { boxWidth: 10, boxHeight: 10, padding: 14, color: '#94a3b8', font: { size: 11 } }
                                },
                                tooltip: tooltipConfig
                            }
                        }
                    });
                } else {
                    showEmptyState(statusCtx, 'No status telemetry available for this time window.');
                }
            }

            // 3. Priority Distribution (Bar Chart)
            if (priorityCtx) {
                const totalPriority = (data.priority && data.priority.counts)
                    ? data.priority.counts.reduce((a, b) => a + b, 0)
                    : 0;

                if (totalPriority > 0) {
                    priorityCtx.style.display = 'block';
                    renderOrCreateChart('priority', priorityCtx, {
                        type: 'bar',
                        data: {
                            labels: data.priority.labels,
                            datasets: [{
                                label: 'Incidents',
                                data: data.priority.counts,
                                backgroundColor: [
                                    'rgba(148, 163, 184, 0.85)', // Low
                                    'rgba(56, 189, 248, 0.85)',  // Medium
                                    'rgba(251, 146, 60, 0.85)',  // High
                                    'rgba(248, 113, 113, 0.9)'   // Critical
                                ],
                                borderRadius: 6
                            }]
                        },
                        options: {
                            responsive: true,
                            maintainAspectRatio: false,
                            plugins: {
                                legend: { display: false },
                                tooltip: tooltipConfig
                            },
                            scales: {
                                y: {
                                    beginAtZero: true,
                                    ticks: { precision: 0, color: '#94a3b8' },
                                    grid: { color: 'rgba(43, 58, 81, 0.5)' }
                                },
                                x: {
                                    ticks: { color: '#94a3b8' },
                                    grid: { display: false }
                                }
                            }
                        }
                    });
                } else {
                    showEmptyState(priorityCtx, 'No priority distribution data for this time window.');
                }
            }

            // 4. Category Classification (Horizontal Bar Chart)
            if (categoryCtx) {
                const totalCategory = (data.category && data.category.counts)
                    ? data.category.counts.reduce((a, b) => a + b, 0)
                    : 0;

                if (totalCategory > 0) {
                    categoryCtx.style.display = 'block';
                    renderOrCreateChart('category', categoryCtx, {
                        type: 'bar',
                        data: {
                            labels: data.category.labels,
                            datasets: [{
                                label: 'Tickets',
                                data: data.category.counts,
                                backgroundColor: 'rgba(99, 102, 241, 0.85)', // Indigo
                                borderRadius: 6
                            }]
                        },
                        options: {
                            indexAxis: 'y',
                            responsive: true,
                            maintainAspectRatio: false,
                            plugins: {
                                legend: { display: false },
                                tooltip: tooltipConfig
                            },
                            scales: {
                                x: {
                                    beginAtZero: true,
                                    ticks: { precision: 0, color: '#94a3b8' },
                                    grid: { color: 'rgba(43, 58, 81, 0.5)' }
                                },
                                y: {
                                    ticks: { color: '#94a3b8' },
                                    grid: { display: false }
                                }
                            }
                        }
                    });
                } else {
                    showEmptyState(categoryCtx, 'No category classification data for this time window.');
                }
            }
        })
        .catch(error => {
            console.error('Failed to load chart analytics data:', error);
            [volumeCtx, statusCtx, priorityCtx, categoryCtx].forEach(ctx => {
                if (ctx) {
                    showEmptyState(ctx, 'Unable to load analytics chart data.');
                }
            });
        });
});
