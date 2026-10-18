/**
 * OpsLens Chart.js Visualizations
 * Fetches data asynchronously from /analytics/api/chart-data
 */

document.addEventListener('DOMContentLoaded', () => {
    const statusCtx = document.getElementById('statusChart');
    const priorityCtx = document.getElementById('priorityChart');
    const categoryCtx = document.getElementById('categoryChart');

    if (!statusCtx || !priorityCtx || !categoryCtx) {
        return; // Not on the dashboard page
    }

    // Modern dark theme defaults for Chart.js
    Chart.defaults.color = '#94a3b8';
    Chart.defaults.font.family = "'Inter', sans-serif";
    Chart.defaults.borderColor = '#334155';

    fetch('/analytics/api/chart-data')
        .then(response => {
            if (!response.ok) {
                throw new Error('Network response was not ok');
            }
            return response.json();
        })
        .then(data => {
            // 1. Status Breakdown (Doughnut Chart)
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

            // 2. Priority Distribution (Bar Chart)
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

            // 3. Category Distribution (Horizontal Bar Chart)
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

