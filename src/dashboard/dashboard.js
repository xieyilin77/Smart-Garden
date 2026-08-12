// ============================================
// SMART GARDEN MANAGER - Dashboard JavaScript
// ============================================

// ============================================
// CONFIGURATION
// ============================================

const API_URL = window.SMART_GARDEN_CONFIG.API_URL;
const REQUEST_TIMEOUT = window.SMART_GARDEN_CONFIG.REQUEST_TIMEOUT;
const SENSOR_ID = window.SMART_GARDEN_CONFIG.SENSOR_ID;
const REFRESH_INTERVAL = window.SMART_GARDEN_CONFIG.REFRESH_INTERVAL;

console.log('📡 API URL:', API_URL);
console.log('🎯 USE_MOCK_DATA:', window.USE_MOCK_DATA);
console.log('🔑 SENSOR ID:', SENSOR_ID);

// ============================================
// TOAST NOTIFICATION
// ============================================

function showToast(message, type = 'info', duration = 5000) {
    document.querySelectorAll('.toast-container').forEach(el => el.remove());
    
    const container = document.createElement('div');
    container.className = 'toast-container';
    container.style.cssText = `
        position: fixed; bottom: 20px; right: 20px; z-index: 9999;
        max-width: 450px; background: rgba(11, 26, 46, 0.95);
        backdrop-filter: blur(12px); border-radius: 12px;
        padding: 16px 20px; border: 1px solid rgba(255,255,255,0.1);
        box-shadow: 0 8px 32px rgba(0,0,0,0.4);
        animation: slideIn 0.3s ease; color: #f0f8ff;
        font-size: 0.9rem; display: flex; align-items: center; gap: 12px;
    `;
    
    container.innerHTML = `
        <span style="flex:1; word-break: break-word;">${message}</span>
        <button onclick="this.parentElement.remove()" style="background:none;border:none;color:rgba(255,255,255,0.5);cursor:pointer;font-size:1.2rem;padding:0 4px;">✕</button>
    `;
    
    document.body.appendChild(container);
    
    if (duration > 0) {
        setTimeout(() => { 
            if (container.parentElement) container.remove(); 
        }, duration);
    }
}

// Toast animation
if (!document.getElementById('toastStyles')) {
    const style = document.createElement('style');
    style.id = 'toastStyles';
    style.textContent = `
        @keyframes slideIn {
            from { transform: translateX(100%); opacity: 0; }
            to { transform: translateX(0); opacity: 1; }
        }
    `;
    document.head.appendChild(style);
}

// ============================================
// HELPER FUNCTIONS
// ============================================

function round(value, decimals) {
    if (value === null || value === undefined || isNaN(value)) return null;
    return Number(Math.round(value + 'e' + decimals) + 'e-' + decimals);
}

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

function parseTimestamp(timestamp) {
    if (!timestamp) return null;
    try {
        if (timestamp.includes('T')) {
            return new Date(timestamp);
        }
        const parts = timestamp.split(' ');
        if (parts.length === 2) {
            const dateParts = parts[0].split('-');
            const timeParts = parts[1].split(':');
            return new Date(
                parseInt(dateParts[0]),
                parseInt(dateParts[1]) - 1,
                parseInt(dateParts[2]),
                parseInt(timeParts[0]),
                parseInt(timeParts[1]),
                parseInt(timeParts[2])
            );
        }
        return new Date(timestamp);
    } catch (e) {
        return null;
    }
}

function getDataAgeMinutes(timestamp) {
    if (!timestamp) return 999;
    const dataTime = parseTimestamp(timestamp);
    if (!dataTime) return 999;
    return Math.floor((new Date() - dataTime) / 60000);
}

function getDataAgeText(timestamp) {
    if (!timestamp) return '⏳ No data';
    const minutes = getDataAgeMinutes(timestamp);
    if (minutes < 1) return '🟢 Just now';
    if (minutes < 5) return `🟢 ${minutes}m ago`;
    if (minutes < 30) return `🟡 ${minutes}m ago`;
    if (minutes < 60) return `🟠 ${minutes}m ago`;
    return `🔴 ${Math.floor(minutes / 60)}h ${minutes % 60}m ago`;
}

function getStatusIndicator(value, min, max) {
    if (value === null || value === undefined || isNaN(value)) return '⏳';
    if (value < min) return '🔽';
    if (value > max) return '🔼';
    return '✅';
}

// ============================================
// MOCK DATA (fallback)
// ============================================

function generateMockData() {
    console.log('📊 Generating mock data...');
    const now = new Date();
    const history = [];
    const count = 50;
    for (let i = 0; i < count; i++) {
        const timestamp = new Date(now - i * 60000);
        const timeOfDay = timestamp.getHours() / 24;
        const dayFactor = Math.sin(timeOfDay * Math.PI * 2) * 3;
        history.push({
            timestamp: formatLocalTime(timestamp),
            temperature: round(20 + dayFactor + Math.random() * 4 + Math.sin(i / 10) * 2, 1),
            humidity: round(55 + Math.random() * 20 - dayFactor * 2 + Math.cos(i / 15) * 5, 1),
            soil_moisture: round(35 + Math.random() * 30 + Math.sin(i / 20) * 8 - dayFactor * 3, 1)
        });
    }
    const latest = history[0] || { 
        sensor_id: SENSOR_ID, 
        temperature: 22.5, 
        humidity: 62.0, 
        soil_moisture: 45.0, 
        timestamp: formatLocalTime(now) 
    };
    latest.sensor_id = SENSOR_ID;
    latest.last_updated = formatLocalTime(now);
    
    const temps = history.map(h => h.temperature).filter(v => v !== null && v !== undefined);
    const hums = history.map(h => h.humidity).filter(v => v !== null && v !== undefined);
    const soils = history.map(h => h.soil_moisture).filter(v => v !== null && v !== undefined);
    
    const stats = {};
    if (temps.length > 0) {
        stats.temperature = { 
            avg: round(temps.reduce((a, b) => a + b, 0) / temps.length, 1), 
            min: round(Math.min(...temps), 1), 
            max: round(Math.max(...temps), 1) 
        };
    }
    if (hums.length > 0) {
        stats.humidity = { 
            avg: round(hums.reduce((a, b) => a + b, 0) / hums.length, 1), 
            min: round(Math.min(...hums), 1), 
            max: round(Math.max(...hums), 1) 
        };
    }
    if (soils.length > 0) {
        stats.soil_moisture = { 
            avg: round(soils.reduce((a, b) => a + b, 0) / soils.length, 1), 
            min: round(Math.min(...soils), 1), 
            max: round(Math.max(...soils), 1) 
        };
    }
    
    return { 
        latest, 
        history, 
        stats, 
        count: history.length, 
        sensor_id: SENSOR_ID, 
        time_range: 'Last 24 hours (MOCK)', 
        query_timestamp: formatLocalTime(now) 
    };
}

// ============================================
// GLOBAL VARIABLES
// ============================================

let charts = {};
let refreshTimer = null;
let currentHistory = [];
let isRefreshing = false;
let abortController = null;
let isManualRefresh = false;

// ============================================
// INIT CHARTS
// ============================================

function initCharts() {
    console.log('📊 Initializing charts...');
    
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
                    backgroundColor: 'rgba(11,26,46,0.9)', 
                    titleColor: '#f0f8ff', 
                    bodyColor: '#f0f8ff', 
                    borderColor: 'rgba(255,255,255,0.1)', 
                    borderWidth: 1 
                } 
            },
            interaction: { mode: 'nearest', intersect: false },
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
        console.log('✅ Temperature chart initialized');
    }
    
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
        console.log('✅ Humidity chart initialized');
    }
    
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
        console.log('✅ Soil moisture chart initialized');
    }
}

// ============================================
// LOAD DATA
// ============================================

async function loadData() {
    if (isRefreshing) { 
        console.log('⏳ Already refreshing...'); 
        return; 
    }
    if (abortController) { 
        abortController.abort(); 
        abortController = null; 
    }
    isRefreshing = true;
    abortController = new AbortController();
    
    try {
        console.log('🔄 Loading data...');
        let data;
        
        if (window.USE_MOCK_DATA) {
            console.log('📊 Using MOCK data');
            data = generateMockData();
        } else {
            const timeRange = document.getElementById('timeRange');
            const hours = timeRange ? timeRange.value : 24;
            const url = `${API_URL}?sensor_id=${SENSOR_ID}&hours=${hours}`;
            console.log(`📡 API Call: ${url}`);
            
            document.getElementById('dataTableBody').innerHTML = 
                '<tr><td colspan="4" class="loading-text">⏳ Loading data...</td></tr>';
            
            const timeoutId = setTimeout(() => { 
                if (abortController) { 
                    abortController.abort(); 
                    abortController = null; 
                } 
            }, REQUEST_TIMEOUT);
            
            try {
                const response = await fetch(url, { signal: abortController.signal });
                clearTimeout(timeoutId);
                
                console.log(`📡 Response status: ${response.status}`);
                
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
                
                const responseText = await response.text();
                
                try {
                    data = JSON.parse(responseText);
                } catch (parseError) {
                    console.error('❌ Failed to parse JSON:', parseError);
                    console.log('📄 Raw response:', responseText.substring(0, 500));
                    throw new Error('Invalid JSON response from API');
                }
                
                console.log('✅ Data received:', {
                    count: data.count || 0,
                    hasStats: !!data.stats,
                    hasTemperatureStats: !!data.stats?.temperature,
                    hasHumidityStats: !!data.stats?.humidity,
                    hasMoistureStats: !!data.stats?.soil_moisture
                });
                
            } catch (error) {
                clearTimeout(timeoutId);
                if (error.name === 'AbortError') { 
                    throw new Error('Request timeout - please try again'); 
                }
                throw error;
            }
        }
        
        if (data && data.history) {
            currentHistory = data.history;
            updateUI(data);
            const count = data.count || data.history.length || 0;
           //showToast(`✅ Data updated (${count} records)`, 'success', 2000);
        } else {
            console.warn('⚠️ No data received - using fallback');
            data = generateMockData();
            currentHistory = data.history;
            updateUI(data);
            showToast('⚠️ Using fallback data (no real data available)', 'warning', 5000);
        }
        
    } catch (error) {
        console.error('❌ Error loading data:', error);
        let errorMessage = error.message || 'Unknown error';
        
        if (errorMessage.includes('Failed to fetch') || errorMessage.includes('NetworkError')) {
            errorMessage = 'Network error - please check your connection';
            showToast(`🌐 ${errorMessage}`, 'warning', 5000);
            
            const mockData = generateMockData();
            currentHistory = mockData.history;
            updateUI(mockData);
            showToast('📊 Using mock data (offline mode)', 'info', 5000);
        } else {
            showToast(`❌ ${errorMessage}`, 'error', 5000);
            document.getElementById('dataTableBody').innerHTML = 
                `<tr><td colspan="4" class="loading-text">❌ Error: ${errorMessage}</td></tr>`;
        }
    } finally {
        isRefreshing = false;
        abortController = null;
    }
}

// ============================================
// UPDATE UI
// ============================================

function updateUI(data) {
    if (!data) { 
        console.warn('⚠️ No data to update UI'); 
        return; 
    }
    
    console.log('🔄 Updating UI...');
    
    if (data.latest) {
        updateCurrentValues(data.latest);
    }
    
    if (data.history && data.history.length > 0) {
        updateCharts(data.history);
    }
    
    if (data.stats) {
        updateStats(data.stats, data.count);
    }
    
    if (data.history) {
        updateTable(data.history);
    }
    
    const now = new Date();
    document.getElementById('lastUpdate').textContent = 
        `🔄 Last Update: ${now.toLocaleTimeString('de-DE')}`;
    document.getElementById('dataPoints').textContent = 
        `${data.count || data.history?.length || 0} data points`;
}

// ============================================
// UPDATE CURRENT VALUES
// ============================================

function updateCurrentValues(latest) {
    console.log('📊 Updating current values:', latest);
    
    if (!latest || Object.keys(latest).length === 0) {
        document.getElementById('currentTemp').textContent = '--°C';
        document.getElementById('currentHumidity').textContent = '--%';
        document.getElementById('currentMoisture').textContent = '--%';
        document.getElementById('sensorStatus').textContent = '🔴 Offline';
        return;
    }
    
    const dataAge = getDataAgeMinutes(latest.timestamp);
    if (dataAge > 30) { 
        showToast(`⚠️ Data is ${dataAge} minutes old!`, 'warning', 10000); 
    }
    
    const temp = latest.temperature !== undefined && latest.temperature !== null 
        ? round(latest.temperature, 1) : null;
    const hum = latest.humidity !== undefined && latest.humidity !== null 
        ? round(latest.humidity, 1) : null;
    const moist = latest.soil_moisture !== undefined && latest.soil_moisture !== null 
        ? round(latest.soil_moisture, 1) : null;
    
    document.getElementById('currentTemp').textContent = temp !== null ? `${temp}°C` : '--°C';
    document.getElementById('currentHumidity').textContent = hum !== null ? `${hum}%` : '--%';
    document.getElementById('currentMoisture').textContent = moist !== null ? `${moist}%` : '--%';
    
    const ageText = getDataAgeText(latest.timestamp);
    document.getElementById('sensorStatus').textContent = ageText || '---';
    document.getElementById('sensorStatus').style.color = 
        dataAge < 5 ? '#27ae60' : dataAge < 30 ? '#f39c12' : '#e74c3c';
    
    updateStatusBadge('tempStatus', temp, 15, 35, '°C');
    updateStatusBadge('humidityStatus', hum, 30, 80, '%');
    updateStatusBadge('moistureStatus', moist, 30, 70, '%');
}

function updateStatusBadge(elementId, value, min, max, unit) {
    const el = document.getElementById(elementId);
    if (!el) return;
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

function updateCharts(history) {
    if (!history || history.length === 0) { 
        console.log('⚠️ No history data for charts'); 
        return; 
    }
    
    console.log(`📊 Updating charts with ${history.length} records`);
    
    const reversed = [...history].reverse();
    const labels = reversed.map(h => {
        if (!h.timestamp) return '';
        const ts = parseTimestamp(h.timestamp);
        if (ts) {
            return ts.toLocaleTimeString('de-DE', { hour: '2-digit', minute: '2-digit' });
        }
        return h.timestamp.substring(11, 16);
    });
    
    const tempData = reversed.map(h => {
        const val = h.temperature;
        return val !== undefined && val !== null ? parseFloat(val) || 0 : 0;
    });
    const humData = reversed.map(h => {
        const val = h.humidity;
        return val !== undefined && val !== null ? parseFloat(val) || 0 : 0;
    });
    const moistData = reversed.map(h => {
        const val = h.soil_moisture;
        return val !== undefined && val !== null ? parseFloat(val) || 0 : 0;
    });
    
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
// UPDATE STATS
// ============================================

function updateStats(stats, count) {
    console.log('📊 Updating stats:', stats);
    
    if (!stats || Object.keys(stats).length === 0) {
        ['avgTemp', 'avgHumidity', 'avgMoisture', 'minTemp', 'maxTemp'].forEach(id => { 
            const el = document.getElementById(id);
            if (el) el.textContent = '--';
        });
        const countEl = document.getElementById('dataPointCount');
        if (countEl) countEl.textContent = count || 0;
        return;
    }
    
    if (stats.temperature) {
        const el = document.getElementById('avgTemp');
        if (el) el.textContent = `${stats.temperature.avg}°C`;
        const minEl = document.getElementById('minTemp');
        if (minEl) minEl.textContent = `${stats.temperature.min}°C`;
        const maxEl = document.getElementById('maxTemp');
        if (maxEl) maxEl.textContent = `${stats.temperature.max}°C`;
    }
    if (stats.humidity) { 
        const el = document.getElementById('avgHumidity');
        if (el) el.textContent = `${stats.humidity.avg}%`; 
    }
    if (stats.soil_moisture) { 
        const el = document.getElementById('avgMoisture');
        if (el) el.textContent = `${stats.soil_moisture.avg}%`; 
    }
    const countEl = document.getElementById('dataPointCount');
    if (countEl) countEl.textContent = count || 0;
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
        const rawTimestamp = row.timestamp || '--';
        let displayTimestamp = rawTimestamp;
        let ageText = '';
        
        if (rawTimestamp.includes(' ')) {
            displayTimestamp = rawTimestamp;
            const minutes = getDataAgeMinutes(rawTimestamp);
            if (minutes < 1) {
                ageText = 'Just now';
            } else if (minutes < 5) {
                ageText = `${minutes}m ago`;
            } else if (minutes < 30) {
                ageText = `${minutes}m ago`;
            } else if (minutes < 60) {
                ageText = `${minutes}m ago`;
            } else {
                const hours = Math.floor(minutes / 60);
                const mins = minutes % 60;
                ageText = `${hours}h ${mins}m ago`;
            }
        }
        else if (rawTimestamp.includes('T')) {
            try {
                const date = new Date(rawTimestamp);
                if (!isNaN(date.getTime())) {
                    const year = date.getFullYear();
                    const month = String(date.getMonth() + 1).padStart(2, '0');
                    const day = String(date.getDate()).padStart(2, '0');
                    const hours = String(date.getHours()).padStart(2, '0');
                    const minutes = String(date.getMinutes()).padStart(2, '0');
                    const seconds = String(date.getSeconds()).padStart(2, '0');
                    displayTimestamp = `${year}-${month}-${day} ${hours}:${minutes}:${seconds}`;
                    
                    const mins = getDataAgeMinutes(rawTimestamp);
                    if (mins < 1) {
                        ageText = 'Just now';
                    } else if (mins < 5) {
                        ageText = `${mins}m ago`;
                    } else if (mins < 30) {
                        ageText = `${mins}m ago`;
                    } else if (mins < 60) {
                        ageText = `${mins}m ago`;
                    } else {
                        const hours = Math.floor(mins / 60);
                        const minsLeft = mins % 60;
                        ageText = `${hours}h ${minsLeft}m ago`;
                    }
                }
            } catch (e) {
                displayTimestamp = rawTimestamp;
            }
        }
        // Fallback
        else {
            displayTimestamp = rawTimestamp;
        }
        
        const tempVal = row.temperature !== undefined && row.temperature !== null 
            ? round(row.temperature, 1) : '--';
        const humVal = row.humidity !== undefined && row.humidity !== null 
            ? round(row.humidity, 1) : '--';
        const moistVal = row.soil_moisture !== undefined && row.soil_moisture !== null 
            ? round(row.soil_moisture, 1) : '--';
        
        const tempIcon = getStatusIndicator(tempVal, 15, 35);
        const humIcon = getStatusIndicator(humVal, 30, 80);
        const moistIcon = getStatusIndicator(moistVal, 30, 70);
        
        const displayText = ageText ? `${displayTimestamp} ${ageText}` : displayTimestamp;
        
        return `<tr>
            <td>${displayText}</td>
            <td>${tempIcon} ${tempVal}</td>
            <td>${humIcon} ${humVal}</td>
            <td>${moistIcon} ${moistVal}</td>
        </tr>`;
    }).join('');
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
        timestamp: formatLocalTime(now), 
        temperature: temp, 
        humidity: humidity, 
        soil_moisture: moisture, 
        sensor_id: sensorId, 
        battery: 100 
    };
    
    currentHistory.unshift(newPoint);
    if (currentHistory.length > 200) { 
        currentHistory = currentHistory.slice(0, 200); 
    }
    
    const stats = calculateStatsFromHistory(currentHistory);
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

function calculateStatsFromHistory(history) {
    if (!history || history.length === 0) { return {}; }
    
    const temps = history.map(h => h.temperature).filter(v => v !== null && v !== undefined);
    const hums = history.map(h => h.humidity).filter(v => v !== null && v !== undefined);
    const soils = history.map(h => h.soil_moisture).filter(v => v !== null && v !== undefined);
    
    const stats = {};
    if (temps.length > 0) {
        stats.temperature = { 
            avg: round(temps.reduce((a, b) => a + b, 0) / temps.length, 1), 
            min: round(Math.min(...temps), 1), 
            max: round(Math.max(...temps), 1) 
        };
    }
    if (hums.length > 0) {
        stats.humidity = { 
            avg: round(hums.reduce((a, b) => a + b, 0) / hums.length, 1), 
            min: round(Math.min(...hums), 1), 
            max: round(Math.max(...hums), 1) 
        };
    }
    if (soils.length > 0) {
        stats.soil_moisture = { 
            avg: round(soils.reduce((a, b) => a + b, 0) / soils.length, 1), 
            min: round(Math.min(...soils), 1), 
            max: round(Math.max(...soils), 1) 
        };
    }
    return stats;
}

// ============================================
// REFRESH
// ============================================

function refreshData() {
    console.log('🔄 Manual refresh...');
    isManualRefresh = true;
    loadData();
    setTimeout(() => { isManualRefresh = false; }, 1000);
}

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

document.addEventListener('DOMContentLoaded', function() {
    console.log('🚀 Initializing dashboard...');
    console.log(`📡 API URL: ${API_URL}`);
    console.log(`🔑 Sensor ID: ${SENSOR_ID}`);
    console.log(`🎯 Mock Mode: ${window.USE_MOCK_DATA ? 'ON (Offline)' : 'OFF (AWS)'}`);
    
    const modeIndicator = document.createElement('span');
    modeIndicator.className = 'mode-indicator';
    modeIndicator.textContent = window.USE_MOCK_DATA ? '📡 OFFLINE' : '☁️ ONLINE';
    modeIndicator.style.cssText = 'font-size:0.8rem;font-weight:700;padding:4px 12px;border-radius:20px;background:' + (window.USE_MOCK_DATA ? '#f39c12' : '#27ae60') + ';color:white;margin-left:10px;';
    
    const headerRight = document.querySelector('.header-right');
    if (headerRight) { 
        headerRight.appendChild(modeIndicator); 
    }
    
    const exportBtn = document.createElement('button');
    exportBtn.className = 'refresh-btn';
    exportBtn.textContent = '📥 Export';
    exportBtn.style.marginLeft = '8px';
    exportBtn.style.background = 'linear-gradient(135deg, #4dabf7, #339af0)';
    exportBtn.onclick = exportData;
    if (headerRight) { 
        headerRight.appendChild(exportBtn); 
    }
    
    const debugBtn = document.createElement('button');
    debugBtn.className = 'toggle-btn';
    debugBtn.textContent = '🐛 Debug';
    debugBtn.style.marginLeft = '8px';
    debugBtn.onclick = async function() {
        try {
            const response = await fetch(`${API_URL}?sensor_id=${SENSOR_ID}&hours=24`);
            const data = await response.json();
            console.log('🔍 Debug data:', data);
            
            let msg = '=== API Debug Info ===\n\n';
            msg += `Status: ${response.status}\n`;
            msg += `Records: ${data.count || data.history?.length || 0}\n\n`;
            msg += 'Stats:\n';
            msg += `  Temperature: ${data.stats?.temperature ? JSON.stringify(data.stats.temperature) : '❌ MISSING'}\n`;
            msg += `  Humidity: ${data.stats?.humidity ? JSON.stringify(data.stats.humidity) : '❌ MISSING'}\n`;
            msg += `  Soil Moisture: ${data.stats?.soil_moisture ? JSON.stringify(data.stats.soil_moisture) : '❌ MISSING'}\n\n`;
            msg += 'Latest:\n';
            msg += `  Temp: ${data.latest?.temperature}°C\n`;
            msg += `  Humidity: ${data.latest?.humidity}%\n`;
            msg += `  Moisture: ${data.latest?.soil_moisture}%\n`;
            
            alert(msg);
        } catch (e) {
            alert(`Debug error: ${e.message}`);
        }
    };
    if (headerRight) { 
        headerRight.appendChild(debugBtn); 
    }
    
    initCharts();
    
    setTimeout(() => {
        loadData();
    }, 500);
    
    startAutoRefresh();
    
    document.addEventListener('keydown', function(e) { 
        if (e.ctrlKey && e.key === 'r') { 
            e.preventDefault(); 
            refreshData(); 
        } 
    });
});

// Global error handling
window.addEventListener('unhandledrejection', function(event) {
    console.error('❌ Unhandled Promise Rejection:', event.reason);
    showToast(`⚠️ Unhandled error: ${event.reason?.message || 'Unknown error'}`, 'error');
});

window.addEventListener('error', function(event) {
    console.error('❌ Uncaught error:', event.error);
    showToast(`⚠️ Error: ${event.message || 'Unknown error'}`, 'error');
});

// Expose functions
window.loadData = loadData;
window.refreshData = refreshData;
window.addManualDataPoint = addManualDataPoint;
window.exportData = exportData;
window.showToast = showToast;

console.log('✅ Dashboard loaded successfully!');