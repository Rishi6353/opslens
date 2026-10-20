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

    // Modern dark theme defaults for Chart.js
    Chart.defaults.color = '#94a3b8';
    Chart.defaults.font.family = "'Inter', sans-serif";
    Chart.defaults.borderColor = '#334155';

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
                    new Chart(volumeCtx, {
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
                                tooltip: {
                                    callbacks: {
                                        label: context => ` ${context.parsed.y} incidents`
                                    }
                                }
                            },
                            scales: {
                                y: {
                                    beginAtZero: true,
                                    ticks: { precision: 0 }
                                },
                                x: {
                                    grid: { display: false }
                                }
                            }
                        }
                    });
                } else {
                    const parent = volumeCtx.parentElement;
                    if (parent) {
                        parent.innerHTML = '<div style="display: flex; height: 100%; align-items: center; justify-content: center; color: var(--text-muted); font-size: 0.85rem;">No incident volume recorded for the selected time window.</div>';
                    }
                }
            }

            // 2. Status Breakdown (Doughnut Chart)
            new Chart(statusCtx, {
                type: 'doughnut',
                data: {
                    labels: data.status.labels,
                    datasets: [{
                        data: data.status.counts,
                        backgroundColor: [
                            'rgba(59, 130, 246, 0.85)',   // Open - Blue
                            'rgba(245, 158, 11, 0.85)',  // In Progress - Amber
                            'rgba(16, 185, 129, 0.85)',  // Resolved - Emerald
                            'rgba(148, 163, 184, 0.85)'  // Closed - Slate
                        ],
                        borderColor: '#1e293b',
                        borderWidth: 2
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: {
                            position: 'bottom',
                            labels: { boxWidth: 12, padding: 12 }
                        }
                    }
                }
            });

            // 3. Priority Distribution (Bar Chart)
            new Chart(priorityCtx, {
                type: 'bar',
                data: {
                    labels: data.priority.labels,
                    datasets: [{
                        label: 'Incidents',
                        data: data.priority.counts,
                        backgroundColor: [
                            'rgba(148, 163, 184, 0.8)', // Low
                            'rgba(56, 189, 248, 0.8)',  // Medium
                            'rgba(249, 115, 22, 0.8)',  // High
                            'rgba(239, 68, 68, 0.85)'   // Critical
                        ],
                        borderRadius: 6
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: { display: false }
                    },
                    scales: {
                        y: {
                            beginAtZero: true,
                            ticks: { precision: 0 }
                        }
                    }
                }
            });

            // 4. Category Distribution (Horizontal Bar Chart)
            new Chart(categoryCtx, {
                type: 'bar',
                data: {
                    labels: data.category.labels,
                    datasets: [{
                        label: 'Tickets',
                        data: data.category.counts,
                        backgroundColor: 'rgba(99, 102, 241, 0.8)', // Indigo
                        borderRadius: 6
                    }]
                },
                options: {
                    indexAxis: 'y',
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: { display: false }
                    },
                    scales: {
                        x: {
                            beginAtZero: true,
                            ticks: { precision: 0 }
                        }
                    }
                }
            });
        })
        .catch(error => {
            console.error('Failed to load chart analytics data:', error);
        });
});
