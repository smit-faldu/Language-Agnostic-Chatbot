fetch('/admin/stats')
    .then(response => response.json())
    .then(data => {
        document.getElementById('total').innerText = data.total_queries;
        document.getElementById('successful').innerText = data.successful;
        document.getElementById('failed').innerText = data.failed;
        document.getElementById('recent').innerHTML = data.recent_queries.map(q => `<li class="p-2 bg-gray-50 rounded"><strong>Q:</strong> ${q.query}<br><strong>A:</strong> ${q.summary}</li>`).join('');
        document.getElementById('failed-list').innerHTML = data.failed_questions.map(q => `<li class="p-2 bg-red-50 rounded text-red-700">${q}</li>`).join('');
        // Chart
        const ctx = document.getElementById('dailyChart').getContext('2d');
        const labels = Object.keys(data.daily_stats);
        const values = Object.values(data.daily_stats);
        new Chart(ctx, {
            type: 'line',
            data: {
                labels: labels,
                datasets: [{
                    label: 'Queries per Day',
                    data: values,
                    borderColor: 'rgba(75, 192, 192, 1)',
                    backgroundColor: 'rgba(75, 192, 192, 0.2)',
                }]
            },
            options: {
                responsive: true,
                scales: {
                    y: {
                        beginAtZero: true
                    }
                }
            }
        });
    })
    .catch(error => console.error('Error fetching stats:', error));
