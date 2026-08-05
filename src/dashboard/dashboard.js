// ============================================
// SMART GARDEN MANAGER - Dashboard JavaScript
// ============================================

// ============================================
// CONFIGURATION (from environment or inline)
// ============================================

// API Gateway URL will be injected during deployment. If not set, mock data will be used.
// const API_URL = '{{API_GATEWAY_URL}}';
const API_URL = 'https://zl7f7b7yh3.execute-api.us-west-2.amazonaws.com/prod/data';

// Mock Mode - Set to true for offline development, false for AWS deployment
// Using window object for global access
window.USE_MOCK_DATA = false;  // Change to false for AWS deployment

// Fallback for offline development
if (API_URL === '{{API_GATEWAY_URL}}') {
    console.warn('⚠️ API_URL not configured! Using mock data.');
    window.USE_MOCK_DATA = true;
}

const SENSOR_ID = 'sensor-001';
const REFRESH_INTERVAL = 30000; // 30 seconds

// ============================================
// TOAST NOTIFICATION SYSTEM
// ============================================

/**
 * Show a toast notification
 * @param {string} message - Message to display
 * @param {string} type - 'info', 'success', 'warning', 'error'
 * @param {number} duration - Duration in milliseconds
 */
function showToast(message, type = 'info', duration = 5000) {
    // Remove existing toasts
    const existing = document.querySelector('.toast-container');
    if (existing) existing.remove();
    
    // Create container
    const container = document.createElement('div');
    container.className = 'toast-container';
    container.style.cssText = `
        position: fixed;
        bottom: 20px;
        right: 20px;
        z-index: 9999;
        max-width: 400px;
        background: rgba(11, 26, 46, 0.95);
        backdrop-filter: blur(12px);
        border-radius: 12px;
        padding: 16px 20px;
        border: 1px solid rgba(255,255,255,0.1);
        box-shadow: 0 8px 32px rgba(0,0,0,0.4);
        animation: slideIn 0.3s ease;
        color: #f0f8ff;
        font-size: 0.9rem;
        display: flex;
        align-items: center;
        gap: 12px;
    `;
    
    // Add icon based on type
    const icons = {
        info: 'ℹ️',
        success: '✅',
        warning: '⚠️',
        error: '❌'
    };
    
    container.innerHTML = `
        <span style="font-size: 1.2rem;">${icons[type] || 'ℹ️'}</span>
        <span style="flex:1;">${message}</span>
        <button onclick="this.parentElement.remove()" style="
            background: none;
            border: none;
            color: rgba(255,255,255,0.5);
            cursor: pointer;
            font-size: 1.2rem;
        ">✕</button>
    `;
    
    document.body.appendChild(container);
    
    // Auto-remove after duration
    setTimeout(() => {
        if (container.parentElement) {
            container.remove();
        }
    }, duration);
}

// Add animation
const style = document.createElement('style');
style.textContent = `
    @keyframes slideIn {
        from { transform: translateX(100%); opacity: 0; }
        to { transform: translateX(0); opacity: 1; }
    }
`;
document.head.appendChild(style);

// ============================================
// MOCK DATA GENERATOR
// ============================================

/**
 * Generate realistic mock data for offline testing
 * @returns {Object} Mock data with latest, history, and stats
 */
function generateMockData() {
    const now = new Date();
    const history = [];
    const count = 50;
    
    // Generate realistic mock data with more variation
    for (let i = count - 1; i >= 0; i--) {
        const timestamp = new Date(now - i * 60000); // Every minute
        
        // Add some realistic patterns
        const timeOfDay = timestamp.getHours() / 24;
        const dayFactor = Math.sin(timeOfDay * Math.PI * 2) * 3;
        
        history.push({
            timestamp: timestamp.toISOString(),
            temperature: 20 + dayFactor + Math.random() * 4 + Math.sin(i / 10) * 2,
            humidity: 55 + Math.random() * 20 - dayFactor * 2 + Math.cos(i / 15) * 5,
            soil_moisture: 35 + Math.random() * 30 + Math.sin(i / 20) * 8 - dayFactor * 3
        });
    }
    
    const latest = history[history.length - 1] || {
        sensor_id: SENSOR_ID,
        temperature: 22.5,
        humidity: 62.0,
        soil_moisture: 45.0,
        timestamp: new Date().toISOString()
    };
    latest.sensor_id = SENSOR_ID;
    latest.last_updated = new Date().toISOString();

    const temps = history.map(h => h.temperature);
    const hums = history.map(h => h.humidity);
    const soils = history.map(h => h.soil_moisture);
    
    const stats = {
        temperature: {
            avg: round(temps.reduce((a, b) => a + b, 0) / temps.length, 1),
            min: round(Math.min(...temps), 1),
            max: round(Math.max(...temps), 1)
        },
        humidity: {
            avg: round(hums.reduce((a, b) => a + b, 0) / hums.length, 1),
            min: round(Math.min(...hums), 1),
            max: round(Math.max(...hums), 1)
        },
        soil_moisture: {
            avg: round(soils.reduce((a, b) => a + b, 0) / soils.length, 1),
            min: round(Math.min(...soils), 1),
            max: round(Math.max(...soils), 1)
        }
    };
    
    return {
        latest: latest,
        history: history,
        stats: stats,
        count: history.length,
        sensor_id: SENSOR_ID,
        time_range: 'Last 24 hours (MOCK)',
        query_timestamp: new Date().toISOString()
    };
}

function round(value, decimals) {
    return Number(Math.round(value + 'e' + decimals) + 'e-' + decimals);
}

// ============================================
// GLOBAL VARIABLES
// ============================================

let charts = {};
let refreshTimer = null;
let currentHistory = [];
let isRefreshing = false;

// ============================================
// INITIALIZE CHARTS
// ============================================

function initCharts() {
    console.log('📊 Initializing charts...');
    
    const chartConfig = {
        type: 'line',
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { 
                    display: false 
                },
                tooltip: {
                    mode: 'index',
                    intersect: false,
                    backgroundColor: 'rgba(11, 26, 46, 0.9)',
                    titleColor: '#f0f8ff',
                    bodyColor: '#f0f8ff',
                    borderColor: 'rgba(255,255,255,0.1)',
                    borderWidth: 1
                }
            },
            interaction: {
                mode: 'nearest',
                intersect: false
            },
            scales: {
                y: {
                    beginAtZero: true,
                    grid: { color: 'rgba(255,255,255,0.05)' },
                    ticks: { color: 'rgba(255,255,255,0.5)' }
                },
                x: {
                    grid: { display: false },
                    ticks: {
                        maxTicksLimit: 12,
                        maxRotation: 45,
                        minRotation: 45,
                        color: 'rgba(255,255,255,0.4)'
                    }
                }
            },
            elements: {
                point: { 
                    radius: 2,
                    hoverRadius: 4
                },
                line: { 
                    borderWidth: 2,
                    tension: 0.4
                }
            },
            animation: {
                duration: 750
            }
        }
    };

    // Temperature Chart
    const tempCtx = document.getElementById('tempChart');
    if (tempCtx) {
        charts.tempChart = new Chart(tempCtx, {
            ...chartConfig,
            data: {
                labels: [],
                datasets: [{
                    label: 'Temperature (°C)',
                    data: [],
                    borderColor: '#ff6b6b',
                    backgroundColor: 'rgba(255,107,107,0.12)',
                    fill: true,
                    tension: 0.4,
                    pointBackgroundColor: '#ff6b6b'
                }]
            }
        });
    }

    // Humidity Chart
    const humidityCtx = document.getElementById('humidityChart');
    if (humidityCtx) {
        charts.humidityChart = new Chart(humidityCtx, {
            ...chartConfig,
            data: {
                labels: [],
                datasets: [{
                    label: 'Humidity (%)',
                    data: [],
                    borderColor: '#4dabf7',
                    backgroundColor: 'rgba(77,171,247,0.12)',
                    fill: true,
                    tension: 0.4,
                    pointBackgroundColor: '#4dabf7'
                }]
            }
        });
    }

    // Soil Moisture Chart
    const moistureCtx = document.getElementById('moistureChart');
    if (moistureCtx) {
        charts.moistureChart = new Chart(moistureCtx, {
            ...chartConfig,
            data: {
                labels: [],
                datasets: [{
                    label: 'Soil Moisture (%)',
                    data: [],
                    borderColor: '#69db7c',
                    backgroundColor: 'rgba(105,219,124,0.12)',
                    fill: true,
                    tension: 0.4,
                    pointBackgroundColor: '#69db7c'
                }]
            }
        });
    }
    console.log('✅ Charts initialized');
}

// ============================================
// LOAD DATA
// ============================================

async function loadData() {
    if (isRefreshing) {
        console.log('⏳ Already refreshing...');
        return;
    }
    
    isRefreshing = true;
    
    try {
        console.log('🔄 Loading data...');
        let data;

        // Use window.USE_MOCK_DATA consistently
        if (window.USE_MOCK_DATA) {
            console.log('📊 Using MOCK data (offline mode)');
            data = generateMockData();
        } else {
            const timeRange = document.getElementById('timeRange');
            const hours = timeRange ? timeRange.value : 24;
            const url = `${API_URL}?sensor_id=${SENSOR_ID}&hours=${hours}`;
            console.log(`📡 API Call: ${url}`);

            // Show loading state
            document.getElementById('dataTableBody').innerHTML = 
                '<tr><td colspan="4" class="loading-text">⏳ Loading data...</td></tr>';

            const response = await fetch(url);
            
            if (!response.ok) {
                let errorMessage = `HTTP ${response.status}: ${response.statusText}`;
                try {
                    const errorData = await response.json();
                    if (errorData.message) {
                        errorMessage = errorData.message;
                    }
                } catch (e) {
                    // Ignore JSON parsing error
                }
                throw new Error(errorMessage);
            }
            
            data = await response.json();
            console.log('✅ Data received:', data);
        }

        // Store history for manual additions
        if (data.history) {
            currentHistory = data.history;
        }

        updateUI(data);
        showToast('✅ Data updated successfully', 'success', 2000);

    } catch (error) {
        console.error('❌ Error loading data:', error);
        showToast(`❌ ${error.message}`, 'error', 5000);
        document.getElementById('dataTableBody').innerHTML =
            `<tr><td colspan="4" class="loading-text">❌ Error: ${error.message}</td></tr>`;
    } finally {
        isRefreshing = false;
    }
}

// ============================================
// UPDATE UI
// ============================================

function updateUI(data) {
    updateCurrentValues(data.latest);
    updateCharts(data.history);
    updateStats(data.stats, data.count);
    updateTable(data.history);

    const now = new Date();
    document.getElementById('lastUpdate').textContent =
        `🔄 Last Update: ${now.toLocaleTimeString('en-US')}`;

    document.getElementById('dataPoints').textContent =
        `${data.count || 0} data points`;
    
    // Update sensor status badge
    updateSensorStatus(data.latest);
}

// ============================================
// UPDATE CURRENT VALUES
// ============================================

function updateCurrentValues(latest) {
    if (!latest || Object.keys(latest).length === 0) {
        document.getElementById('currentTemp').textContent = '--°C';
        document.getElementById('currentHumidity').textContent = '--%';
        document.getElementById('currentMoisture').textContent = '--%';
        document.getElementById('sensorStatus').textContent = '🔴 Offline';
        return;
    }

    const temp = latest.temperature ? Math.round(latest.temperature * 10) / 10 : null;
    const hum = latest.humidity ? Math.round(latest.humidity * 10) / 10 : null;
    const moist = latest.soil_moisture ? Math.round(latest.soil_moisture * 10) / 10 : null;

    document.getElementById('currentTemp').textContent = temp !== null ? `${temp}°C` : '--°C';
    document.getElementById('currentHumidity').textContent = hum !== null ? `${hum}%` : '--%';
    document.getElementById('currentMoisture').textContent = moist !== null ? `${moist}%` : '--%';

    // Single value badges
    updateStatusBadge('tempStatus', temp, 15, 35, '°C');
    updateStatusBadge('humidityStatus', hum, 30, 80, '%');
    updateStatusBadge('moistureStatus', moist, 30, 70, '%');
}

function updateStatusBadge(elementId, value, min, max, unit) {
    const el = document.getElementById(elementId);
    if (value === null || value === undefined) {
        el.textContent = '⏳ No Value';
        el.style.color = 'rgba(255,255,255,0.4)';
        return;
    }
    if (value < min) {
        el.textContent = `⚠️ Too low (${min}${unit})`;
        el.style.color = '#ff6b6b';
    } else if (value > max) {
        el.textContent = `⚠️ Too high (${max}${unit})`;
        el.style.color = '#ffd43b';
    } else {
        el.textContent = '✅ Normal';
        el.style.color = '#69db7c';
    }
}

function updateSensorStatus(latest) {
    const statusEl = document.getElementById('sensorStatus');
    if (!latest || !latest.timestamp) {
        statusEl.textContent = '🔴 Offline';
        statusEl.style.color = '#e74c3c';
        return;
    }
    
    const lastUpdate = new Date(latest.timestamp);
    const now = new Date();
    const diffMinutes = (now - lastUpdate) / 60000;
    
    if (diffMinutes < 5) {
        statusEl.textContent = '🟢 Online';
        statusEl.style.color = '#27ae60';
    } else if (diffMinutes < 15) {
        statusEl.textContent = '🟡 Warning';
        statusEl.style.color = '#f39c12';
    } else {
        statusEl.textContent = '🔴 Offline';
        statusEl.style.color = '#e74c3c';
    }
}

// ============================================
// UPDATE CHARTS
// ============================================

function updateCharts(history) {
    if (!history || history.length === 0) {
        console.log('⚠️ No history data for charts');
        return;
    }

    const labels = history.map(h =>
        h.timestamp ? h.timestamp.substring(11, 16) : ''
    );

    const tempData = history.map(h => h.temperature || 0);
    const humData = history.map(h => h.humidity || 0);
    const moistData = history.map(h => h.soil_moisture || 0);

    updateChart('tempChart', labels, tempData);
    updateChart('humidityChart', labels, humData);
    updateChart('moistureChart', labels, moistData);
}

function updateChart(chartId, labels, data) {
    const chart = charts[chartId];
    if (chart) {
        chart.data.labels = labels;
        chart.data.datasets[0].data = data;
        chart.update('none');
    }
}

// ============================================
// UPDATE STATISTICS
// ============================================

function updateStats(stats, count) {
    if (!stats || Object.keys(stats).length === 0) {
        ['avgTemp', 'avgHumidity', 'avgMoisture', 'minTemp', 'maxTemp'].forEach(id => {
            document.getElementById(id).textContent = '--';
        });
        document.getElementById('dataPointCount').textContent = '0';
        return;
    }

    if (stats.temperature) {
        document.getElementById('avgTemp').textContent = `${stats.temperature.avg}°C`;
        document.getElementById('minTemp').textContent = `${stats.temperature.min}°C`;
        document.getElementById('maxTemp').textContent = `${stats.temperature.max}°C`;
    }
    if (stats.humidity) {
        document.getElementById('avgHumidity').textContent = `${stats.humidity.avg}%`;
    }
    if (stats.soil_moisture) {
        document.getElementById('avgMoisture').textContent = `${stats.soil_moisture.avg}%`;
    }
    document.getElementById('dataPointCount').textContent = count || 0;
}

// ============================================
// UPDATE TABLE
// ============================================

function updateTable(history) {
    const tbody = document.getElementById('dataTableBody');
    if (!history || history.length === 0) {
        tbody.innerHTML = '<tr><td colspan="4" class="loading-text">📭 No data available</td></tr>';
        return;
    }

    const displayData = history.slice(0, 20);
    tbody.innerHTML = displayData.map(row => {
        const ts = row.timestamp ? row.timestamp.replace('T', ' ').substring(0, 19) : '--';

        // Get status icons for each value
        const tempIcon = getStatusIndicator(row.temperature, 15, 35);
        const humIcon = getStatusIndicator(row.humidity, 30, 80);
        const moistIcon = getStatusIndicator(row.soil_moisture, 30, 70);
        
        // Format values
        const tempVal = row.temperature ? Math.round(row.temperature * 10) / 10 : '--';
        const humVal = row.humidity ? Math.round(row.humidity * 10) / 10 : '--';
        const moistVal = row.soil_moisture ? Math.round(row.soil_moisture * 10) / 10 : '--';
        
        return `
            <tr>
                <td>${ts}</td>
                <td>${tempIcon} ${tempVal}</td>
                <td>${humIcon} ${humVal}</td>
                <td>${moistIcon} ${moistVal}</td>
            </tr>
        `;
    }).join('');
}

// ============================================
// GET STATUS ICON FOR TABLE VALUES
// ============================================

function getStatusIndicator(value, min, max) {
    if (value === null || value === undefined || isNaN(value)) {
        return '⏳';
    }
    if (value < min) {
        return '🔽';
    } else if (value > max) {
        return '🔼';
    } else {
        return '✅';
    }
}

// ============================================
// MANUAL DATA INPUT
// ============================================

function addManualDataPoint() {
    const sensorId = document.getElementById('manualSensorId').value || SENSOR_ID;
    const temp = parseFloat(document.getElementById('manualTemp').value);
    const humidity = parseFloat(document.getElementById('manualHumidity').value);
    const moisture = parseFloat(document.getElementById('manualMoisture').value);

    if (isNaN(temp) || isNaN(humidity) || isNaN(moisture)) {
        showToast('❌ Please enter valid numbers for all fields', 'error');
        document.getElementById('manualFeedback').textContent = '❌ Please enter valid numbers.';
        document.getElementById('manualFeedback').style.color = '#ff6b6b';
        return;
    }

    if (temp < -50 || temp > 100) {
        showToast('❌ Temperature must be between -50 and 100°C', 'error');
        return;
    }
    if (humidity < 0 || humidity > 100) {
        showToast('❌ Humidity must be between 0 and 100%', 'error');
        return;
    }
    if (moisture < 0 || moisture > 100) {
        showToast('❌ Soil moisture must be between 0 and 100%', 'error');
        return;
    }

    const now = new Date();
    const newPoint = {
        timestamp: now.toISOString(),
        temperature: temp,
        humidity: humidity,
        soil_moisture: moisture,
        sensor_id: sensorId,
        battery: 100
    };

    // Insert into history (newest first)
    currentHistory.unshift(newPoint);

    // Keep max 200 points
    if (currentHistory.length > 200) {
        currentHistory = currentHistory.slice(0, 200);
    }

    // Recalculate stats
    const stats = calculateStats(currentHistory);

    const data = {
        latest: newPoint,
        history: currentHistory,
        stats: stats,
        count: currentHistory.length,
        sensor_id: sensorId,
        time_range: 'Manually added',
        query_timestamp: now.toISOString()
    };

    updateUI(data);

    let feedbackMsg = `✅ Data point added: ${temp}°C, ${humidity}%, ${moisture}%`;
    let feedbackColor = '#69db7c';

    // Check for alert conditions
    if (moisture < 30) {
        feedbackMsg += ' ⚠️ WARNING: Soil Moisture below 30%!';
        feedbackColor = '#ff6b6b';
        showToast('⚠️ Low soil moisture detected!', 'warning');
    } else if (temp > 35) {
        feedbackMsg += ' ⚠️ WARNING: Temperature above 35°C!';
        feedbackColor = '#ffd43b';
        showToast('⚠️ High temperature detected!', 'warning');
    } else {
        showToast('✅ Data point added successfully', 'success');
    }

    document.getElementById('manualFeedback').textContent = feedbackMsg;
    document.getElementById('manualFeedback').style.color = feedbackColor;
}

function calculateStats(history) {
    if (!history || history.length === 0) { return {}; }
    const temps = history.map(h => h.temperature);
    const hums = history.map(h => h.humidity);
    const soils = history.map(h => h.soil_moisture);

    return {
        temperature: {
            avg: round(temps.reduce((a, b) => a + b, 0) / temps.length, 1),
            min: round(Math.min(...temps), 1),
            max: round(Math.max(...temps), 1)
        },
        humidity: {
            avg: round(hums.reduce((a, b) => a + b, 0) / hums.length, 1),
            min: round(Math.min(...hums), 1),
            max: round(Math.max(...hums), 1)
        },
        soil_moisture: {
            avg: round(soils.reduce((a, b) => a + b, 0) / soils.length, 1),
            min: round(Math.min(...soils), 1),
            max: round(Math.max(...soils), 1)
        }
    };
}

// ============================================
// REFRESH & AUTO-REFRESH
// ============================================

function refreshData() {
    console.log('🔄 Manual refresh...');
    loadData();
}

function startAutoRefresh() {
    if (refreshTimer) clearInterval(refreshTimer);
    refreshTimer = setInterval(loadData, REFRESH_INTERVAL);
    console.log(`⏰ Auto-refresh started (${REFRESH_INTERVAL / 1000}s)`);
}

// ============================================
// EXPORT DATA (NEW FEATURE)
// ============================================

function exportData() {
    if (!currentHistory || currentHistory.length === 0) {
        showToast('❌ No data to export', 'error');
        return;
    }

    try {
        const data = {
            sensor_id: SENSOR_ID,
            export_date: new Date().toISOString(),
            data_points: currentHistory.length,
            data: currentHistory
        };

        const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `smart-garden-data-${new Date().toISOString().substring(0,10)}.json`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);

        showToast(`✅ Exported ${currentHistory.length} data points`, 'success');
    } catch (error) {
        console.error('Export error:', error);
        showToast('❌ Failed to export data', 'error');
    }
}

// ============================================
// INITIALIZATION
// ============================================

document.addEventListener('DOMContentLoaded', function() {
    console.log('🚀 Initializing dashboard...');
    console.log(`📡 API URL: ${API_URL}`);
    console.log(`🔑 Sensor ID: ${SENSOR_ID}`);
    console.log(`🎯 Mock Mode: ${window.USE_MOCK_DATA ? 'ON (Offline)' : 'OFF (AWS)'}`);

    // Display Mode in header
    const modeIndicator = document.createElement('span');
    modeIndicator.className = 'mode-indicator';
    modeIndicator.textContent = window.USE_MOCK_DATA ? '📡 OFFLINE' : '☁️ ONLINE';
    modeIndicator.style.cssText = `
        font-size: 0.8rem;
        font-weight: 700;
        padding: 4px 12px;
        border-radius: 20px;
        background: ${window.USE_MOCK_DATA ? '#f39c12' : '#27ae60'};
        color: white;
        margin-left: 10px;
    `;
    const headerRight = document.querySelector('.header-right');
    if (headerRight) {
        headerRight.appendChild(modeIndicator);
    }

    // Add export button
    const exportBtn = document.createElement('button');
    exportBtn.className = 'refresh-btn';
    exportBtn.textContent = '📥 Export';
    exportBtn.style.marginLeft = '8px';
    exportBtn.style.background = 'linear-gradient(135deg, #4dabf7, #339af0)';
    exportBtn.onclick = exportData;
    if (headerRight) {
        headerRight.appendChild(exportBtn);
    }

    initCharts();
    loadData();
    startAutoRefresh();

    // Add keyboard shortcut (Ctrl+R for refresh)
    document.addEventListener('keydown', function(e) {
        if (e.ctrlKey && e.key === 'r') {
            e.preventDefault();
            refreshData();
        }
    });
});

// ============================================
// GLOBAL ERROR HANDLING
// ============================================

window.addEventListener('unhandledrejection', function(event) {
    console.error('❌ Unhandled Promise Rejection:', event.reason);
    showToast(`⚠️ Unhandled error: ${event.reason?.message || 'Unknown error'}`, 'error');
});

window.addEventListener('error', function(event) {
    console.error('❌ Uncaught error:', event.error);
    showToast(`⚠️ Error: ${event.message || 'Unknown error'}`, 'error');
});

// ============================================
// EXPOSE FUNCTIONS TO GLOBAL SCOPE
// ============================================
window.loadData = loadData;
window.refreshData = refreshData;
window.addManualDataPoint = addManualDataPoint;
window.exportData = exportData;
window.showToast = showToast;