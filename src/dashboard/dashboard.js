// ============================================
// SMART GARDEN MANAGER - Dashboard JavaScript
// ============================================

// ============================================
// CONFIGURATION
// ============================================


window.USE_MOCK_DATA = false;

// 🔥 OFFLINE DASHBOARD TEST with MOCK API
//const API_URL = 'http://localhost:5000/prod/query';

// 🔥 
const API_URL = document.querySelector('meta[name="api-url"]')?.content 
    || window.API_CONFIG?.API_URL
    || 'http://localhost:5000/prod/query'; 

console.log('📡 API URL:', API_URL);
console.log('🎯 USE_MOCK_DATA:', window.USE_MOCK_DATA);

/** Request timeout in milliseconds */
const REQUEST_TIMEOUT = 1000;

/** Default sensor ID for queries */
const SENSOR_ID = 'sensor-001';

/** Auto-refresh interval in milliseconds (30 seconds) */
const REFRESH_INTERVAL = 3000;

// ============================================
// TOAST NOTIFICATION SYSTEM
// ============================================

/**
 * Display a toast notification
 * @param {string} message - Message to display
 * @param {string} type - 'info', 'success', 'warning', 'error'
 * @param {number} duration - Duration in milliseconds
 */
function showToast(message, type = 'info', duration = 5000) {
    // Remove existing toast
    const existing = document.querySelector('.toast-container');
    if (existing) existing.remove();
    
    // Create toast container
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
    
    // Icons for different message types
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

// Toast slide-in animation
const style = document.createElement('style');
style.textContent = `
    @keyframes slideIn {
        from { transform: translateX(100%); opacity: 0; }
        to { transform: translateX(0); opacity: 1; }
    }
`;
document.head.appendChild(style);

// ============================================
// HELPER FUNCTIONS
// ============================================

/**
 * Round a number to specified decimal places
 * @param {number} value - Value to round
 * @param {number} decimals - Number of decimal places
 * @returns {number} Rounded value
 */
function round(value, decimals) {
    return Number(Math.round(value + 'e' + decimals) + 'e-' + decimals);
}

/**
 * Format a date to local time string (YYYY-MM-DD HH:MM:SS)
 * @param {Date} date - Date object to format
 * @returns {string} Formatted local time string
 */
function formatLocalTime(date) {
    if (!date) date = new Date();
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const day = String(date.getDate()).padStart(2, '0');
    const hours = String(date.getHours()).padStart(2, '0');
    const minutes = String(date.getMinutes()).padStart(2, '0');
    const seconds = String(date.getSeconds()).padStart(2, '0');
    return `${year}-${month}-${day} ${hours}:${minutes}:${seconds}`;
}

/**
 * Calculate age of a data point in minutes
 * @param {string} timestamp - Timestamp string (ISO or local format)
 * @returns {number} Age in minutes
 */
function getDataAgeMinutes(timestamp) {
    if (!timestamp) return 999;
    const now = new Date();
    let dataTime;
    
    // Handle both ISO (UTC) and local format
    if (timestamp.includes('T')) {
        // ISO format: "2026-08-05T11:35:26.123Z"
        dataTime = new Date(timestamp);
    } else {
        // Local format: "2026-08-05 11:35:26"
        const parts = timestamp.split(' ');
        const dateParts = parts[0].split('-');
        const timeParts = parts[1].split(':');
        dataTime = new Date(
            parseInt(dateParts[0]),
            parseInt(dateParts[1]) - 1,
            parseInt(dateParts[2]),
            parseInt(timeParts[0]),
            parseInt(timeParts[1]),
            parseInt(timeParts[2])
        );
    }
    return Math.floor((now - dataTime) / 60000);
}

/**
 * Get color-coded age text for a data point
 * @param {string} timestamp - Timestamp string
 * @returns {string} Age text with emoji indicator
 */
function getDataAgeText(timestamp) {
    if (!timestamp) return '';
    const minutes = getDataAgeMinutes(timestamp);
    
    if (minutes < 1) return '🟢 just now';
    if (minutes < 5) return '🟢 ' + minutes + 'm ago';
    if (minutes < 30) return '🟡 ' + minutes + 'm ago';
    if (minutes < 60) return '🟠 ' + minutes + 'm ago';
    return '🔴 ' + Math.floor(minutes / 60) + 'h ' + (minutes % 60) + 'm ago';
}

// ============================================
// MOCK DATA GENERATOR
// ============================================

/**
 * Generate realistic mock sensor data with current local timestamps
 * @returns {Object} Complete data object with latest, history, and stats
 */
function generateMockData() {
    const now = new Date();
    const history = [];
    const count = 50; // Number of data points
    
    // Generate 50 data points with current local timestamps
    // i=0 is the newest measurement (now)
    for (let i = 0; i < count; i++) {
        const timestamp = new Date(now - i * 60000); // i minutes ago
        const timeOfDay = timestamp.getHours() / 24;
        const dayFactor = Math.sin(timeOfDay * Math.PI * 2) * 3;
        
        history.push({
            timestamp: formatLocalTime(timestamp), // Local time!
            temperature: round(20 + dayFactor + Math.random() * 4 + Math.sin(i / 10) * 2, 1),
            humidity: round(55 + Math.random() * 20 - dayFactor * 2 + Math.cos(i / 15) * 5, 1),
            soil_moisture: round(35 + Math.random() * 30 + Math.sin(i / 20) * 8 - dayFactor * 3, 1)
        });
    }
    
    // Newest measurement = first entry (index 0)
    const latest = history[0] || {
        sensor_id: SENSOR_ID,
        temperature: 22.5,
        humidity: 62.0,
        soil_moisture: 45.0,
        timestamp: formatLocalTime(now)
    };
    latest.sensor_id = SENSOR_ID;
    latest.last_updated = formatLocalTime(now);

    // Calculate statistics from historical data
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
        query_timestamp: formatLocalTime(now)
    };
}

// ============================================
// GLOBAL VARIABLES
// ============================================

/** Chart instances */
let charts = {};

/** Auto-refresh timer reference */
let refreshTimer = null;

/** Current history data (for manual additions and export) */
let currentHistory = [];

/** Flag to prevent concurrent refreshes */
let isRefreshing = false;

/** AbortController for request cancellation */
let abortController = null;

/** Flag for manual refresh (prevents auto-refresh interference) */
let isManualRefresh = false;

// ============================================
// INITIALIZE CHARTS
// ============================================

/**
 * Initialize Chart.js charts for temperature, humidity, and soil moisture
 */
function initCharts() {
    console.log('📊 Initializing charts...');
    
    // Base chart configuration
    const chartConfig = {
        type: 'line',
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                tooltip: {
                    mode: 'index',
                    intersect: false,
                    backgroundColor: 'rgba(11, 26, 46, 0.9)',
                    titleColor: '#f0f8ff',
                    bodyColor: '#f0f8ff',
                    borderColor: 'rgba(255,255,255,0.1)',
                    borderWidth: 1,
                    callbacks: {
                        label: function(context) {
                            return context.dataset.label + ': ' + context.parsed.y;
                        }
                    }
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
                point: { radius: 2, hoverRadius: 4 },
                line: { borderWidth: 2, tension: 0.4 }
            },
            animation: { duration: 750 }
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

/**
 * Load sensor data from API or generate mock data
 * Handles timeout, abort, and error states
 */
async function loadData() {
    // Prevent concurrent refreshes
    if (isRefreshing) {
        console.log('⏳ Already refreshing...');
        return;
    }
    
    // Cancel any pending request
    if (abortController) {
        abortController.abort();
        abortController = null;
    }
    
    isRefreshing = true;
    abortController = new AbortController();
    
    try {
        console.log('🔄 Loading data...');
        let data;

        // Use mock data if in offline mode
        if (window.USE_MOCK_DATA) {
            console.log('📊 Using MOCK data (offline mode)');
            data = generateMockData(); // Always generates fresh data
        } else {
            // Build API URL with query parameters
            const timeRange = document.getElementById('timeRange');
            const hours = timeRange ? timeRange.value : 24;
            const url = `${API_URL}?sensor_id=${SENSOR_ID}&hours=${hours}`;
            console.log(`📡 API Call: ${url}`);

            // Show loading state
            document.getElementById('dataTableBody').innerHTML = 
                '<tr><td colspan="4" class="loading-text">⏳ Loading data...</td></tr>';

            // Set timeout for request
            const timeoutId = setTimeout(() => {
                if (abortController) {
                    abortController.abort();
                    abortController = null;
                }
            }, REQUEST_TIMEOUT);

            try {
                const response = await fetch(url, { signal: abortController.signal });
                clearTimeout(timeoutId);
                
                if (!response.ok) {
                    let errorMessage = `HTTP ${response.status}: ${response.statusText}`;
                    try {
                        const errorData = await response.json();
                        if (errorData.message) {
                            errorMessage = errorData.message;
                        }
                    } catch (e) {}
                    throw new Error(errorMessage);
                }
                
                data = await response.json();
                console.log('✅ Data received:', data);
            } catch (error) {
                clearTimeout(timeoutId);
                if (error.name === 'AbortError') {
                    throw new Error('Request timeout - please try again');
                }
                throw error;
            }
        }

        // Store history for manual additions and export
        if (data.history) {
            currentHistory = data.history;
        }

        updateUI(data);
        showToast('✅ Data updated successfully', 'success', 2000);

    } catch (error) {
        console.error('❌ Error loading data:', error);
        let errorMessage = error.message || 'Unknown error';
        
        // Handle network errors specifically
        if (errorMessage.includes('Failed to fetch') || errorMessage.includes('NetworkError')) {
            errorMessage = 'Network error - please check your connection';
            showToast(`🌐 ${errorMessage}`, 'warning', 5000);
        } else {
            showToast(`❌ ${errorMessage}`, 'error', 5000);
        }
        
        document.getElementById('dataTableBody').innerHTML =
            `<tr><td colspan="4" class="loading-text">❌ Error: ${errorMessage}</td></tr>`;
    } finally {
        isRefreshing = false;
        abortController = null;
    }
}

// ============================================
// UPDATE UI
// ============================================

/**
 * Update all UI components with new data
 * @param {Object} data - Data object containing latest, history, and stats
 */
function updateUI(data) {
    updateCurrentValues(data.latest);
    updateCharts(data.history);
    updateStats(data.stats, data.count);
    updateTable(data.history);

    const now = new Date();
    document.getElementById('lastUpdate').textContent =
        `🔄 Last Update: ${now.toLocaleTimeString('de-DE')}`;

    document.getElementById('dataPoints').textContent =
        `${data.count || 0} data points`;
}

// ============================================
// UPDATE CURRENT VALUES
// ============================================

/**
 * Update the current sensor value cards
 * @param {Object} latest - Latest sensor data
 */
function updateCurrentValues(latest) {
    // Check if data exists
    if (!latest || Object.keys(latest).length === 0) {
        document.getElementById('currentTemp').textContent = '--°C';
        document.getElementById('currentHumidity').textContent = '--%';
        document.getElementById('currentMoisture').textContent = '--%';
        document.getElementById('sensorStatus').textContent = '🔴 Offline';
        return;
    }

    // Check data age and warn if too old
    const dataAge = getDataAgeMinutes(latest.timestamp);
    if (dataAge > 30) {
        showToast(`⚠️ Data is ${dataAge} minutes old! Sensor may be offline.`, 'warning', 10000);
    }

    // Extract and format values
    const temp = latest.temperature !== undefined && latest.temperature !== null 
        ? Math.round(latest.temperature * 10) / 10 : null;
    const hum = latest.humidity !== undefined && latest.humidity !== null 
        ? Math.round(latest.humidity * 10) / 10 : null;
    const moist = latest.soil_moisture !== undefined && latest.soil_moisture !== null 
        ? Math.round(latest.soil_moisture * 10) / 10 : null;

    // Update display
    document.getElementById('currentTemp').textContent = temp !== null ? `${temp}°C` : '--°C';
    document.getElementById('currentHumidity').textContent = hum !== null ? `${hum}%` : '--%';
    document.getElementById('currentMoisture').textContent = moist !== null ? `${moist}%` : '--%';

    // Show data age in sensor status
    const ageText = getDataAgeText(latest.timestamp);
    document.getElementById('sensorStatus').textContent = ageText || '---';
    document.getElementById('sensorStatus').style.color = 
        dataAge < 5 ? '#27ae60' : dataAge < 30 ? '#f39c12' : '#e74c3c';

    // Update status badges for each value
    updateStatusBadge('tempStatus', temp, 15, 35, '°C');
    updateStatusBadge('humidityStatus', hum, 30, 80, '%');
    updateStatusBadge('moistureStatus', moist, 30, 70, '%');
}

/**
 * Update a single status badge with color coding
 * @param {string} elementId - HTML element ID
 * @param {number} value - Current value
 * @param {number} min - Minimum threshold
 * @param {number} max - Maximum threshold
 * @param {string} unit - Unit of measurement
 */
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

// ============================================
// UPDATE CHARTS
// ============================================

/**
 * Update all charts with historical data
 * @param {Array} history - Array of historical data points
 */
function updateCharts(history) {
    if (!history || history.length === 0) {
        console.log('⚠️ No history data for charts');
        return;
    }

    // Reverse for chronological order (oldest to newest)
    const reversed = [...history].reverse();
    
    // Extract labels (only time, not full date)
    const labels = reversed.map(h => {
        if (!h.timestamp) return '';
        const parts = h.timestamp.split(' ');
        if (parts.length > 1) {
            return parts[1].substring(0, 5); // HH:MM
        }
        return h.timestamp.substring(11, 16); // Fallback for ISO format
    });

    // Extract data for each metric
    const tempData = reversed.map(h => h.temperature || 0);
    const humData = reversed.map(h => h.humidity || 0);
    const moistData = reversed.map(h => h.soil_moisture || 0);

    updateChart('tempChart', labels, tempData);
    updateChart('humidityChart', labels, humData);
    updateChart('moistureChart', labels, moistData);
}

/**
 * Update a single chart with new data
 * @param {string} chartId - Chart instance ID
 * @param {Array} labels - X-axis labels
 * @param {Array} data - Y-axis data
 */
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

/**
 * Update statistics display
 * @param {Object} stats - Statistics object
 * @param {number} count - Total number of data points
 */
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
// UPDATE TABLE - NEWEST FIRST
// ============================================

/**
 * Update the recent measurements table
 * Displays newest data points first
 * @param {Array} history - Array of historical data points
 */
function updateTable(history) {
    const tbody = document.getElementById('dataTableBody');
    if (!history || history.length === 0) {
        tbody.innerHTML = '<tr><td colspan="4" class="loading-text">📭 No data available</td></tr>';
        return;
    }

    // ✅ NEWEST FIRST: Display the 20 most recent measurements
    const displayData = history.slice(0, 20);
    
    tbody.innerHTML = displayData.map(row => {
        const ts = row.timestamp || '--';
        const ageText = getDataAgeText(row.timestamp);

        const tempIcon = getStatusIndicator(row.temperature, 15, 35);
        const humIcon = getStatusIndicator(row.humidity, 30, 80);
        const moistIcon = getStatusIndicator(row.soil_moisture, 30, 70);
        
        const tempVal = row.temperature !== undefined && row.temperature !== null 
            ? Math.round(row.temperature * 10) / 10 : '--';
        const humVal = row.humidity !== undefined && row.humidity !== null 
            ? Math.round(row.humidity * 10) / 10 : '--';
        const moistVal = row.soil_moisture !== undefined && row.soil_moisture !== null 
            ? Math.round(row.soil_moisture * 10) / 10 : '--';
        
        return `
            <tr>
                <td>${ts} <span style="font-size:0.7rem; opacity:0.6;">${ageText}</span></td>
                <td>${tempIcon} ${tempVal}</td>
                <td>${humIcon} ${humVal}</td>
                <td>${moistIcon} ${moistVal}</td>
            </tr>
        `;
    }).join('');
}

// ============================================
// GET STATUS ICON
// ============================================

/**
 * Get status indicator icon for table values
 * @param {number} value - Value to check
 * @param {number} min - Minimum threshold
 * @param {number} max - Maximum threshold
 * @returns {string} Emoji indicator
 */
function getStatusIndicator(value, min, max) {
    if (value === null || value === undefined || isNaN(value)) {
        return '⏳';
    }
    if (value < min) {
        return '🔽'; // Too low
    } else if (value > max) {
        return '🔼'; // Too high
    } else {
        return '✅'; // Normal
    }
}

// ============================================
// MANUAL DATA INPUT - WITH LOCAL TIME
// ============================================

/**
 * Add a manually entered data point to the dashboard
 * Uses current local time as timestamp
 */
function addManualDataPoint() {
    const sensorId = document.getElementById('manualSensorId').value || SENSOR_ID;
    const temp = parseFloat(document.getElementById('manualTemp').value);
    const humidity = parseFloat(document.getElementById('manualHumidity').value);
    const moisture = parseFloat(document.getElementById('manualMoisture').value);

    // Validate inputs
    if (isNaN(temp) || isNaN(humidity) || isNaN(moisture)) {
        showToast('❌ Please enter valid numbers for all fields', 'error');
        document.getElementById('manualFeedback').textContent = '❌ Please enter valid numbers.';
        document.getElementById('manualFeedback').style.color = '#ff6b6b';
        return;
    }

    // Validate ranges
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
        timestamp: formatLocalTime(now), // Use local time!
        temperature: temp,
        humidity: humidity,
        soil_moisture: moisture,
        sensor_id: sensorId,
        battery: 100
    };

    // ✅ NEWEST FIRST: Add to beginning of array
    currentHistory.unshift(newPoint);

    // Keep maximum 200 data points
    if (currentHistory.length > 200) {
        currentHistory = currentHistory.slice(0, 200);
    }

    // Recalculate statistics
    const stats = calculateStats(currentHistory);

    const data = {
        latest: newPoint,
        history: currentHistory,
        stats: stats,
        count: currentHistory.length,
        sensor_id: sensorId,
        time_range: 'Manually added',
        query_timestamp: formatLocalTime(now)
    };

    updateUI(data);

    // Show feedback with alerts if thresholds are exceeded
    let feedbackMsg = `✅ Data point added: ${temp}°C, ${humidity}%, ${moisture}%`;
    let feedbackColor = '#69db7c';

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

/**
 * Calculate statistics from historical data
 * @param {Array} history - Array of historical data points
 * @returns {Object} Statistics object with avg, min, max for each metric
 */
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

/**
 * Manually refresh data
 */
function refreshData() {
    console.log('🔄 Manual refresh...');
    isManualRefresh = true;
    loadData();
    setTimeout(() => { isManualRefresh = false; }, 1000);
}

/**
 * Start auto-refresh timer
 * Refreshes data every REFRESH_INTERVAL milliseconds
 */
function startAutoRefresh() {
    if (refreshTimer) clearInterval(refreshTimer);
    refreshTimer = setInterval(() => {
        if (!isManualRefresh) {
            loadData();
        }
    }, REFRESH_INTERVAL);
    console.log(`⏰ Auto-refresh started (${REFRESH_INTERVAL / 1000}s)`);
}

// ============================================
// EXPORT DATA
// ============================================

/**
 * Export current data as JSON file
 */
function exportData() {
    if (!currentHistory || currentHistory.length === 0) {
        showToast('❌ No data to export', 'error');
        return;
    }

    try {
        const data = {
            sensor_id: SENSOR_ID,
            export_date: formatLocalTime(new Date()),
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

/**
 * Initialize dashboard on page load
 */
document.addEventListener('DOMContentLoaded', function() {
    console.log('🚀 Initializing dashboard...');
    console.log(`📡 API URL: ${API_URL}`);
    console.log(`🔑 Sensor ID: ${SENSOR_ID}`);
    console.log(`🎯 Mock Mode: ${window.USE_MOCK_DATA ? 'ON (Offline)' : 'OFF (AWS)'}`);

    // Add mode indicator to header
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

    // Initialize charts and load initial data
    initCharts();
    loadData();
    startAutoRefresh();

    // Keyboard shortcut: Ctrl+R for refresh
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

// Handle unhandled promise rejections
window.addEventListener('unhandledrejection', function(event) {
    console.error('❌ Unhandled Promise Rejection:', event.reason);
    showToast(`⚠️ Unhandled error: ${event.reason?.message || 'Unknown error'}`, 'error');
});

// Handle uncaught errors
window.addEventListener('error', function(event) {
    console.error('❌ Uncaught error:', event.error);
    showToast(`⚠️ Error: ${event.message || 'Unknown error'}`, 'error');
});

// ============================================
// EXPOSE FUNCTIONS TO GLOBAL SCOPE
// ============================================

// Make functions globally accessible for inline HTML event handlers
window.loadData = loadData;
window.refreshData = refreshData;
window.addManualDataPoint = addManualDataPoint;
window.exportData = exportData;
window.showToast = showToast;