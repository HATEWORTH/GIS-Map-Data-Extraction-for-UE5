/**
 * GIS Road Data Extractor - Web Interface
 *
 * Interactive map-based tool for extracting OpenStreetMap road data
 * and converting to UE5-compatible format.
 */

// Road type configuration
const ROAD_TYPES = {
    motorway: { type: 'interstate', color: '#E31C1C', width: 2400 },
    motorway_link: { type: 'interstate', color: '#E31C1C', width: 1800 },
    trunk: { type: 'highway', color: '#F48C06', width: 2000 },
    trunk_link: { type: 'highway', color: '#F48C06', width: 1500 },
    primary: { type: 'arterial', color: '#FFC300', width: 1600 },
    primary_link: { type: 'arterial', color: '#FFC300', width: 1200 },
    secondary: { type: 'minor_arterial', color: '#FFE066', width: 1200 },
    secondary_link: { type: 'minor_arterial', color: '#FFE066', width: 900 },
    tertiary: { type: 'collector', color: '#74C0FC', width: 800 },
    tertiary_link: { type: 'collector', color: '#74C0FC', width: 600 },
    residential: { type: 'residential', color: '#51CF66', width: 600 },
    living_street: { type: 'residential', color: '#51CF66', width: 500 },
    service: { type: 'service', color: '#868E96', width: 400 },
    track: { type: 'service', color: '#868E96', width: 300 },
    unclassified: { type: 'unclassified', color: '#FFFFFF', width: 600 },
    road: { type: 'unclassified', color: '#FFFFFF', width: 600 }
};

// Overpass API endpoints (fallback chain)
const OVERPASS_ENDPOINTS = [
    'https://overpass-api.de/api/interpreter',
    'https://overpass.kumi.systems/api/interpreter',
    'https://maps.mail.ru/osm/tools/overpass/api/interpreter',
    'https://overpass.openstreetmap.ru/api/interpreter'
];

// Map tile layer definitions (all free, no API key required)
const MAP_LAYERS = {
    'carto-dark': {
        url: 'https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png',
        options: {
            attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OSM</a> &copy; <a href="https://carto.com/">CARTO</a>',
            subdomains: 'abcd', maxZoom: 20
        }
    },
    'carto-dark-nolabels': {
        url: 'https://{s}.basemaps.cartocdn.com/dark_nolabels/{z}/{x}/{y}.png',
        options: {
            attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OSM</a> &copy; <a href="https://carto.com/">CARTO</a>',
            subdomains: 'abcd', maxZoom: 20
        }
    },
    'carto-light': {
        url: 'https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}.png',
        options: {
            attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OSM</a> &copy; <a href="https://carto.com/">CARTO</a>',
            subdomains: 'abcd', maxZoom: 20
        }
    },
    'osm': {
        url: 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
        options: {
            attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
            maxZoom: 19
        }
    },
    'osm-hot': {
        url: 'https://{s}.tile.openstreetmap.fr/hot/{z}/{x}/{y}.png',
        options: {
            attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OSM</a> &copy; <a href="https://hot.openstreetmap.org/">HOT</a>',
            maxZoom: 19
        }
    },
    'esri-topo': {
        url: 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Topo_Map/MapServer/tile/{z}/{y}/{x}',
        options: {
            attribution: '&copy; Esri, DeLorme, NAVTEQ, TomTom',
            maxZoom: 19
        }
    },
    'opentopomap': {
        url: 'https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png',
        options: {
            attribution: '&copy; <a href="https://opentopomap.org">OpenTopoMap</a> &copy; <a href="https://www.openstreetmap.org/copyright">OSM</a>',
            maxZoom: 17
        }
    },
    'esri-shaded': {
        url: 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Shaded_Relief/MapServer/tile/{z}/{y}/{x}',
        options: {
            attribution: '&copy; Esri, USGS',
            maxZoom: 13
        }
    },
    'esri-natgeo': {
        url: 'https://server.arcgisonline.com/ArcGIS/rest/services/NatGeo_World_Map/MapServer/tile/{z}/{y}/{x}',
        options: {
            attribution: '&copy; Esri, National Geographic',
            maxZoom: 16
        }
    },
    'esri-imagery': {
        url: 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
        options: {
            attribution: '&copy; Esri, Maxar, Earthstar Geographics',
            maxZoom: 19
        }
    },
    'usgs-imagery': {
        url: 'https://basemap.nationalmap.gov/arcgis/rest/services/USGSImageryOnly/MapServer/tile/{z}/{y}/{x}',
        options: {
            attribution: '&copy; USGS',
            maxZoom: 16
        }
    },
    'esri-streets': {
        url: 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}',
        options: {
            attribution: '&copy; Esri',
            maxZoom: 19
        }
    }
};

// State
let map;
let currentTileLayer = null;
let selectionRectangle = null;
let roadLayers = null;
let currentCenter = { lat: 40.7580, lon: -73.9855 };
let currentChunkSize = 8;
let extractedData = null;

// Switch map tile layer
function setMapLayer(layerId) {
    const layerDef = MAP_LAYERS[layerId];
    if (!layerDef) return;

    if (currentTileLayer) {
        map.removeLayer(currentTileLayer);
    }
    currentTileLayer = L.tileLayer(layerDef.url, layerDef.options).addTo(map);
    // Ensure tile layer is behind overlays
    currentTileLayer.bringToBack();
}

// Initialize map
function initMap() {
    map = L.map('map', {
        center: [currentCenter.lat, currentCenter.lon],
        zoom: 13,
        zoomControl: true
    });

    // Set default tile layer
    setMapLayer('carto-dark');

    // Create layer groups
    roadLayers = L.layerGroup().addTo(map);

    // Map click handler
    map.on('click', onMapClick);

    // Initial selection rectangle
    updateSelectionRectangle();
}

// Calculate bounds for chunk
function calculateBounds(lat, lon, sizeKm) {
    const R = 6371; // Earth radius in km
    const halfSize = sizeKm / 2;

    const latOffset = (halfSize / R) * (180 / Math.PI);
    const lonOffset = (halfSize / (R * Math.cos(lat * Math.PI / 180))) * (180 / Math.PI);

    return {
        south: lat - latOffset,
        north: lat + latOffset,
        west: lon - lonOffset,
        east: lon + lonOffset
    };
}

// Update selection rectangle on map
function updateSelectionRectangle() {
    if (selectionRectangle) {
        map.removeLayer(selectionRectangle);
    }

    const bounds = calculateBounds(currentCenter.lat, currentCenter.lon, currentChunkSize);

    selectionRectangle = L.rectangle(
        [[bounds.south, bounds.west], [bounds.north, bounds.east]],
        {
            color: '#60a5fa',
            weight: 2,
            fillOpacity: 0.1,
            dashArray: '5, 5'
        }
    ).addTo(map);

    // Update info display
    updateSelectionInfo();
}

// Update selection info panel
function updateSelectionInfo() {
    document.getElementById('selection-info').classList.remove('hidden');
    document.getElementById('sel-center').textContent =
        `${currentCenter.lat.toFixed(4)}, ${currentCenter.lon.toFixed(4)}`;
    document.getElementById('sel-size').textContent = `${currentChunkSize} km × ${currentChunkSize} km`;
    document.getElementById('sel-area').textContent = `${currentChunkSize * currentChunkSize} km²`;

    // Update coordinate inputs
    document.getElementById('lat-input').value = currentCenter.lat.toFixed(4);
    document.getElementById('lon-input').value = currentCenter.lon.toFixed(4);
}

// Map click handler
function onMapClick(e) {
    currentCenter = { lat: e.latlng.lat, lon: e.latlng.lng };
    updateSelectionRectangle();

    // Clear previous roads
    roadLayers.clearLayers();
    hideResults();

    // Update heightmap info
    if (typeof updateHeightmapInfo === 'function') {
        updateHeightmapInfo();
    }
}

// Set status message
function setStatus(message, type = '') {
    const statusEl = document.getElementById('status-message');
    statusEl.textContent = message;
    statusEl.className = type;
}

// Show/hide progress bar
function showProgress(percent) {
    const progressBar = document.getElementById('progress-bar');
    const progressFill = document.getElementById('progress-fill');

    if (percent === null) {
        progressBar.classList.add('hidden');
    } else {
        progressBar.classList.remove('hidden');
        progressFill.style.width = `${percent}%`;
    }
}

// Build Overpass query
function buildOverpassQuery(bounds) {
    const bbox = `${bounds.south},${bounds.west},${bounds.north},${bounds.east}`;
    const highwayTypes = Object.keys(ROAD_TYPES).join('|');

    return `
[out:json][timeout:120];
(
  way["highway"~"^(${highwayTypes})$"](${bbox});
);
out body;
>;
out skel qt;
`;
}

// Query Overpass API
async function queryOverpass(query) {
    const errors = [];
    for (let i = 0; i < OVERPASS_ENDPOINTS.length; i++) {
        const endpoint = OVERPASS_ENDPOINTS[i];
        try {
            setStatus(`Trying ${new URL(endpoint).hostname} (${i + 1}/${OVERPASS_ENDPOINTS.length})...`, 'loading');

            const response = await fetch(endpoint, {
                method: 'POST',
                body: `data=${encodeURIComponent(query)}`,
                headers: {
                    'Content-Type': 'application/x-www-form-urlencoded'
                }
            });

            if (response.ok) {
                return await response.json();
            } else if (response.status === 429) {
                setStatus(`Rate limited by ${new URL(endpoint).hostname}. Trying next...`, 'loading');
                errors.push(`${new URL(endpoint).hostname}: rate limited`);
                await new Promise(resolve => setTimeout(resolve, 2000));
            } else if (response.status === 504 || response.status === 503) {
                setStatus(`Server ${new URL(endpoint).hostname} overloaded. Trying next...`, 'loading');
                errors.push(`${new URL(endpoint).hostname}: server overloaded (${response.status})`);
                await new Promise(resolve => setTimeout(resolve, 1000));
            } else {
                errors.push(`${new URL(endpoint).hostname}: HTTP ${response.status}`);
            }
        } catch (error) {
            console.error(`Error with ${endpoint}:`, error);
            errors.push(`${new URL(endpoint).hostname}: ${error.message}`);
        }
    }

    throw new Error(`All Overpass endpoints failed. Errors: ${errors.join('; ')}`);
}

// Parse OSM response to GeoJSON
function parseOSMResponse(data) {
    const nodes = {};
    const features = [];
    const roadStats = {
        interstate: 0, highway: 0, arterial: 0, minor_arterial: 0,
        collector: 0, residential: 0, service: 0, unclassified: 0
    };

    // Build node lookup
    for (const element of data.elements || []) {
        if (element.type === 'node') {
            nodes[element.id] = [element.lon, element.lat];
        }
    }

    // Process ways
    for (const element of data.elements || []) {
        if (element.type !== 'way') continue;

        const tags = element.tags || {};
        const highwayTag = tags.highway || '';

        if (!ROAD_TYPES[highwayTag]) continue;

        const roadInfo = ROAD_TYPES[highwayTag];
        roadStats[roadInfo.type] = (roadStats[roadInfo.type] || 0) + 1;

        // Build coordinates
        const coordinates = [];
        for (const nodeId of element.nodes || []) {
            if (nodes[nodeId]) {
                coordinates.push(nodes[nodeId]);
            }
        }

        if (coordinates.length < 2) continue;

        features.push({
            type: 'Feature',
            geometry: {
                type: 'LineString',
                coordinates
            },
            properties: {
                osm_id: element.id,
                highway: highwayTag,
                road_type: roadInfo.type,
                color: roadInfo.color,
                width: roadInfo.width,
                name: tags.name || '',
                oneway: tags.oneway || 'no'
            }
        });
    }

    return {
        type: 'FeatureCollection',
        metadata: {
            source: 'OpenStreetMap',
            center_lat: currentCenter.lat,
            center_lon: currentCenter.lon,
            size_km: currentChunkSize,
            extracted_at: new Date().toISOString(),
            road_stats: roadStats,
            total_roads: features.length
        },
        features
    };
}

// Classify chunk category
function classifyChunk(geojson) {
    const stats = geojson.metadata.road_stats;
    const total = geojson.metadata.total_roads;

    if (total === 0) return 'rural';

    const majorRoads = (stats.interstate || 0) + (stats.highway || 0) +
                       (stats.arterial || 0) + (stats.minor_arterial || 0);
    const residential = stats.residential || 0;

    const majorPct = (majorRoads / total) * 100;
    const residentialPct = (residential / total) * 100;

    if (total < 50) return 'rural';
    if (majorPct > 15 && residentialPct < 40) return 'downtown';
    if (residentialPct > 70) return 'residential';
    if (majorPct > 8 && residentialPct > 40) return 'downtown_residential';
    if (total < 200 && residentialPct > 50) return 'residential_rural';

    return residentialPct > majorPct ? 'residential' : 'downtown_residential';
}

// Display roads on map
function displayRoads(geojson) {
    roadLayers.clearLayers();

    for (const feature of geojson.features) {
        const coords = feature.geometry.coordinates.map(c => [c[1], c[0]]);
        const color = feature.properties.color;
        const weight = Math.max(2, Math.min(6, feature.properties.width / 400));

        L.polyline(coords, {
            color,
            weight,
            opacity: 0.8,
            className: 'road-preview'
        }).addTo(roadLayers);
    }
}

// Show results panel
function showResults(geojson) {
    const resultsPanel = document.getElementById('results-panel');
    resultsPanel.classList.remove('hidden');

    const stats = geojson.metadata.road_stats;
    const statsHtml = Object.entries(stats)
        .filter(([_, count]) => count > 0)
        .map(([type, count]) => {
            const colorMap = {
                interstate: '#E31C1C', highway: '#F48C06', arterial: '#FFC300',
                minor_arterial: '#FFE066', collector: '#74C0FC', residential: '#51CF66',
                service: '#868E96', unclassified: '#FFFFFF'
            };
            return `
                <div class="stat-item">
                    <span class="stat-color" style="background:${colorMap[type] || '#fff'}"></span>
                    <span class="stat-label">${type}</span>
                    <span class="stat-value">${count}</span>
                </div>
            `;
        }).join('');

    document.getElementById('road-stats').innerHTML = statsHtml;

    const category = geojson.metadata.category;
    document.getElementById('category-display').innerHTML = `
        <span class="category-label">Detected Category:</span>
        <span class="category-value">${category.replace('_', ' ')}</span>
    `;
}

// Hide results panel
function hideResults() {
    document.getElementById('results-panel').classList.add('hidden');
}

// Convert GeoJSON to UE5 format
function convertToUE5(geojson) {
    const metadata = geojson.metadata;
    const centerLat = metadata.center_lat;
    const centerLon = metadata.center_lon;
    const sizeKm = metadata.size_km;

    const R = 6371000; // Earth radius in meters
    const UE5_SCALE = 100;

    function latLonToMeters(lat, lon) {
        const latRad = lat * Math.PI / 180;
        const lonRad = lon * Math.PI / 180;
        const centerLatRad = centerLat * Math.PI / 180;
        const centerLonRad = centerLon * Math.PI / 180;

        const x = R * (lonRad - centerLonRad) * Math.cos(centerLatRad);
        const y = R * (latRad - centerLatRad);

        return [x * UE5_SCALE, y * UE5_SCALE];
    }

    // Build nodes
    const endpointMap = new Map();
    const nodes = [];

    for (const feature of geojson.features) {
        const coords = feature.geometry.coordinates;
        if (coords.length < 2) continue;

        for (const coord of [coords[0], coords[coords.length - 1]]) {
            const key = `${coord[0].toFixed(5)},${coord[1].toFixed(5)}`;
            if (!endpointMap.has(key)) {
                const [x, y] = latLonToMeters(coord[1], coord[0]);
                endpointMap.set(key, nodes.length);
                nodes.push({ id: nodes.length, x: Math.round(x * 10) / 10, y: Math.round(y * 10) / 10 });
            }
        }
    }

    // Build edges
    const edges = [];
    for (const feature of geojson.features) {
        const coords = feature.geometry.coordinates;
        if (coords.length < 2) continue;

        const startKey = `${coords[0][0].toFixed(5)},${coords[0][1].toFixed(5)}`;
        const endKey = `${coords[coords.length - 1][0].toFixed(5)},${coords[coords.length - 1][1].toFixed(5)}`;

        const points = coords.map(c => {
            const [x, y] = latLonToMeters(c[1], c[0]);
            return [Math.round(x * 10) / 10, Math.round(y * 10) / 10];
        });

        edges.push({
            id: edges.length,
            start_node: endpointMap.get(startKey) ?? -1,
            end_node: endpointMap.get(endKey) ?? -1,
            road_type: feature.properties.road_type,
            color: feature.properties.color,
            width: feature.properties.width,
            name: feature.properties.name,
            osm_id: feature.properties.osm_id,
            oneway: feature.properties.oneway === 'yes',
            points
        });
    }

    const halfSizeUU = (sizeKm * 1000 * UE5_SCALE) / 2;

    return {
        metadata: {
            city: `${centerLat.toFixed(4)}_${centerLon.toFixed(4)}`,
            category: metadata.category,
            center_lat: centerLat,
            center_lon: centerLon,
            size_km: sizeKm,
            bounds_uu: {
                min: [-halfSizeUU, -halfSizeUU],
                max: [halfSizeUU, halfSizeUU]
            },
            road_stats: metadata.road_stats,
            total_roads: edges.length,
            total_nodes: nodes.length,
            source: 'OpenStreetMap'
        },
        nodes,
        edges
    };
}

// Download file with save dialog
async function downloadFile(data, suggestedName, fileType = 'json') {
    const jsonString = JSON.stringify(data, null, 2);
    const blob = new Blob([jsonString], { type: 'application/json' });

    // Try to use File System Access API (modern browsers)
    if ('showSaveFilePicker' in window) {
        try {
            const fileTypes = fileType === 'geojson'
                ? [{ description: 'GeoJSON File', accept: { 'application/geo+json': ['.geojson'] } }]
                : [{ description: 'JSON File', accept: { 'application/json': ['.json'] } }];

            const handle = await window.showSaveFilePicker({
                suggestedName: suggestedName,
                types: fileTypes
            });

            const writable = await handle.createWritable();
            await writable.write(blob);
            await writable.close();

            setStatus(`Saved: ${handle.name}`, 'success');
            return;
        } catch (err) {
            // User cancelled or API not supported - fall back to traditional download
            if (err.name === 'AbortError') {
                return; // User cancelled, don't fall back
            }
        }
    }

    // Fallback: traditional download
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = suggestedName;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
}

// Extract roads
async function extractRoads(previewOnly = false) {
    try {
        const bounds = calculateBounds(currentCenter.lat, currentCenter.lon, currentChunkSize);

        setStatus('Building query...', 'loading');
        showProgress(10);

        const query = buildOverpassQuery(bounds);

        showProgress(20);
        const data = await queryOverpass(query);

        setStatus('Parsing response...', 'loading');
        showProgress(60);

        const geojson = parseOSMResponse(data);
        geojson.metadata.category = classifyChunk(geojson);
        geojson.metadata.bounds = bounds;

        showProgress(80);
        displayRoads(geojson);

        showProgress(100);

        extractedData = geojson;
        showResults(geojson);

        const totalRoads = geojson.metadata.total_roads;
        const category = geojson.metadata.category;
        setStatus(`Extracted ${totalRoads} roads. Category: ${category}`, 'success');

        setTimeout(() => showProgress(null), 500);

    } catch (error) {
        console.error('Extraction error:', error);
        setStatus(`Error: ${error.message}`, 'error');
        showProgress(null);
    }
}

// Event handlers
function setupEventHandlers() {
    // City select
    document.getElementById('city-select').addEventListener('change', (e) => {
        if (e.target.value) {
            const [lat, lon] = e.target.value.split(',').map(Number);
            currentCenter = { lat, lon };
            map.setView([lat, lon], 13);
            updateSelectionRectangle();
            roadLayers.clearLayers();
            hideResults();
        }
    });

    // Go button
    document.getElementById('goto-btn').addEventListener('click', () => {
        const lat = parseFloat(document.getElementById('lat-input').value);
        const lon = parseFloat(document.getElementById('lon-input').value);
        if (!isNaN(lat) && !isNaN(lon)) {
            currentCenter = { lat, lon };
            map.setView([lat, lon], 13);
            updateSelectionRectangle();
            roadLayers.clearLayers();
            hideResults();
        }
    });

    // Chunk size
    document.getElementById('chunk-size').addEventListener('change', (e) => {
        currentChunkSize = parseInt(e.target.value);
        updateSelectionRectangle();
        roadLayers.clearLayers();
        hideResults();
        updateHeightmapInfo();
    });

    // Extract button
    document.getElementById('extract-btn').addEventListener('click', () => {
        extractRoads(false);
    });

    // Preview button
    document.getElementById('preview-btn').addEventListener('click', () => {
        extractRoads(true);
    });

    // Download GeoJSON
    document.getElementById('download-geojson').addEventListener('click', async () => {
        if (extractedData) {
            const filename = `roads_${currentCenter.lat.toFixed(4)}_${currentCenter.lon.toFixed(4)}.geojson`;
            await downloadFile(extractedData, filename, 'geojson');
        }
    });

    // Download UE5 JSON
    document.getElementById('download-ue5').addEventListener('click', async () => {
        if (extractedData) {
            const ue5Data = convertToUE5(extractedData);
            const filename = `roads_${currentCenter.lat.toFixed(4)}_${currentCenter.lon.toFixed(4)}_ue5.json`;
            await downloadFile(ue5Data, filename, 'json');
        }
    });

    // Heightmap panel toggle
    const heightmapToggle = document.getElementById('heightmap-toggle');
    const heightmapHeader = document.querySelector('.heightmap-header');
    const heightmapBody = document.getElementById('heightmap-body');
    if (heightmapHeader && heightmapBody) {
        heightmapHeader.addEventListener('click', () => {
            heightmapBody.classList.toggle('collapsed');
            heightmapToggle?.classList.toggle('collapsed');
        });
    }

    // Map mode selector
    document.getElementById('map-mode').addEventListener('change', (e) => {
        setMapLayer(e.target.value);
    });

    // Download Heightmap
    const heightmapStandaloneBtn = document.getElementById('download-heightmap-standalone');
    if (heightmapStandaloneBtn) {
        heightmapStandaloneBtn.addEventListener('click', async () => {
            await downloadHeightmap();
        });
    }

    // Size mode changes dimension options
    const sizeModeSelect = document.getElementById('heightmap-size-mode');
    if (sizeModeSelect) {
        sizeModeSelect.addEventListener('change', updateHeightmapSizeOptions);
    }

    // All heightmap controls trigger info update
    const hmControls = [
        'heightmap-size-mode', 'heightmap-size', 'heightmap-bitdepth',
        'heightmap-contrast', 'heightmap-invert'
    ];
    hmControls.forEach(id => {
        const el = document.getElementById(id);
        if (el) {
            el.addEventListener('change', updateHeightmapInfo);
            el.addEventListener('input', updateHeightmapInfo);
        }
    });

    // Initialize heightmap info
    setTimeout(() => {
        updateHeightmapSizeOptions();
        updateHeightmapInfo();
    }, 100);
}

// UE5 Landscape valid sizes (must be (component * sections) + 1)
const UE5_LANDSCAPE_SIZES = [253, 505, 1009, 2017, 4033, 8129];

// Gaea 2 standard sizes (powers of 2)
const GAEA_SIZES = [512, 1024, 2048, 4096, 8192];

// Update heightmap dimension options based on size mode
function updateHeightmapSizeOptions() {
    const modeSelect = document.getElementById('heightmap-size-mode');
    const sizeSelect = document.getElementById('heightmap-size');
    if (!modeSelect || !sizeSelect) return;

    const mode = modeSelect.value;
    const currentValue = sizeSelect.value;
    sizeSelect.innerHTML = '';

    if (mode === 'ue5') {
        UE5_LANDSCAPE_SIZES.forEach(s => {
            const opt = document.createElement('option');
            opt.value = s;
            opt.textContent = `${s} x ${s}`;
            if (s === 4033) opt.selected = true;
            sizeSelect.appendChild(opt);
        });
    } else if (mode === 'gaea') {
        GAEA_SIZES.forEach(s => {
            const opt = document.createElement('option');
            opt.value = s;
            opt.textContent = `${s} x ${s}`;
            if (s === 4096) opt.selected = true;
            sizeSelect.appendChild(opt);
        });
    } else {
        const opt = document.createElement('option');
        opt.value = 'auto';
        opt.textContent = 'Auto (from tile resolution)';
        sizeSelect.appendChild(opt);
    }

    updateHeightmapInfo();
}

// Update heightmap resolution info
function updateHeightmapInfo() {
    const infoEl = document.getElementById('heightmap-info');
    if (!infoEl) return;

    const sizeMode = document.getElementById('heightmap-size-mode')?.value || 'ue5';
    const sizeSelect = document.getElementById('heightmap-size');
    const targetSize = sizeSelect?.value === 'auto' ? null : parseInt(sizeSelect?.value || '4033');
    const bitDepth = document.getElementById('heightmap-bitdepth')?.value || '16';

    // Calculate tile coverage at zoom 15 (best quality source)
    const zoom = 15;
    const bounds = calculateBounds(currentCenter.lat, currentCenter.lon, currentChunkSize);
    const topLeft = latLonToTile(bounds.north, bounds.west, zoom);
    const bottomRight = latLonToTile(bounds.south, bounds.east, zoom);

    const tilesX = bottomRight.x - topLeft.x + 1;
    const tilesY = bottomRight.y - topLeft.y + 1;
    const totalTiles = tilesX * tilesY;

    const sourceWidth = tilesX * 256;
    const sourceHeight = tilesY * 256;

    const outputSize = targetSize || sourceWidth;
    const metersPerPixel = (currentChunkSize * 1000) / outputSize;

    const bitLabel = bitDepth === '16' ? '16-bit' : '8-bit';
    const fileSizeEstMB = bitDepth === '16'
        ? ((outputSize * outputSize * 2) / (1024 * 1024)).toFixed(1)
        : ((outputSize * outputSize) / (1024 * 1024)).toFixed(1);

    infoEl.innerHTML = `<strong>${outputSize} x ${outputSize}px</strong> | ${bitLabel} | ~${metersPerPixel.toFixed(1)}m/pixel | ~${fileSizeEstMB} MB (uncompressed)<br>` +
        `Source: ${totalTiles} tiles (zoom ${zoom}, ${sourceWidth}x${sourceHeight}px) | Terrain: ${currentChunkSize} km`;
}

// Heightmap generation using terrain tiles
const TERRAIN_TILE_URL = 'https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png';

// Convert lat/lon to tile coordinates
function latLonToTile(lat, lon, zoom) {
    const n = Math.pow(2, zoom);
    const x = Math.floor((lon + 180) / 360 * n);
    const latRad = lat * Math.PI / 180;
    const y = Math.floor((1 - Math.log(Math.tan(latRad) + 1 / Math.cos(latRad)) / Math.PI) / 2 * n);
    return { x, y };
}

// Convert tile coordinates back to lat/lon (top-left corner)
function tileToLatLon(x, y, zoom) {
    const n = Math.pow(2, zoom);
    const lon = x / n * 360 - 180;
    const latRad = Math.atan(Math.sinh(Math.PI * (1 - 2 * y / n)));
    const lat = latRad * 180 / Math.PI;
    return { lat, lon };
}

// Fetch and decode terrain tile
async function fetchTerrainTile(x, y, zoom) {
    const url = TERRAIN_TILE_URL.replace('{z}', zoom).replace('{x}', x).replace('{y}', y);

    return new Promise((resolve, reject) => {
        const img = new Image();
        img.crossOrigin = 'anonymous';
        img.onload = () => {
            const canvas = document.createElement('canvas');
            canvas.width = 256;
            canvas.height = 256;
            const ctx = canvas.getContext('2d');
            ctx.drawImage(img, 0, 0);
            const imageData = ctx.getImageData(0, 0, 256, 256);
            resolve({ data: imageData, success: true });
        };
        img.onerror = () => {
            // Return empty tile on failure
            const canvas = document.createElement('canvas');
            canvas.width = 256;
            canvas.height = 256;
            const ctx = canvas.getContext('2d');
            resolve({ data: ctx.getImageData(0, 0, 256, 256), success: false });
        };
        img.src = url;
    });
}

// Decode Terrarium elevation from RGB
function decodeTerrarium(r, g, b) {
    return (r * 256 + g + b / 256) - 32768;
}

// ============================================================
// 16-bit PNG Encoder (for UE5/Gaea heightmap export)
// ============================================================

// CRC32 lookup table for PNG chunk checksums
const CRC32_TABLE = (() => {
    const table = new Uint32Array(256);
    for (let n = 0; n < 256; n++) {
        let c = n;
        for (let k = 0; k < 8; k++) {
            c = (c & 1) ? (0xEDB88320 ^ (c >>> 1)) : (c >>> 1);
        }
        table[n] = c;
    }
    return table;
})();

function crc32(data) {
    let crc = 0xFFFFFFFF;
    for (let i = 0; i < data.length; i++) {
        crc = CRC32_TABLE[(crc ^ data[i]) & 0xFF] ^ (crc >>> 8);
    }
    return (crc ^ 0xFFFFFFFF) >>> 0;
}

function makePNGChunk(type, data) {
    const typeBytes = new Uint8Array([type.charCodeAt(0), type.charCodeAt(1), type.charCodeAt(2), type.charCodeAt(3)]);
    const chunk = new Uint8Array(4 + 4 + data.length + 4);
    const view = new DataView(chunk.buffer);

    view.setUint32(0, data.length); // Length
    chunk.set(typeBytes, 4);         // Type
    chunk.set(data, 8);              // Data

    // CRC over type + data
    const crcInput = new Uint8Array(4 + data.length);
    crcInput.set(typeBytes, 0);
    crcInput.set(data, 4);
    view.setUint32(8 + data.length, crc32(crcInput));

    return chunk;
}

/**
 * Encode a 16-bit grayscale PNG from a Uint16Array.
 * Returns a Uint8Array containing the full PNG file.
 */
function encode16BitPNG(width, height, data16) {
    // PNG signature
    const signature = new Uint8Array([137, 80, 78, 71, 13, 10, 26, 10]);

    // IHDR: width(4) + height(4) + bitDepth(1) + colorType(1) + compression(1) + filter(1) + interlace(1) = 13 bytes
    const ihdrData = new Uint8Array(13);
    const ihdrView = new DataView(ihdrData.buffer);
    ihdrView.setUint32(0, width);
    ihdrView.setUint32(4, height);
    ihdrData[8] = 16;  // bit depth
    ihdrData[9] = 0;   // color type: grayscale
    ihdrData[10] = 0;  // compression: deflate
    ihdrData[11] = 0;  // filter method
    ihdrData[12] = 0;  // interlace: none
    const ihdrChunk = makePNGChunk('IHDR', ihdrData);

    // Build raw scanlines: each row = 1 filter byte + width * 2 bytes (16-bit big-endian)
    const rowBytes = 1 + width * 2;
    const rawData = new Uint8Array(height * rowBytes);

    for (let y = 0; y < height; y++) {
        const offset = y * rowBytes;
        rawData[offset] = 0; // Filter: None
        for (let x = 0; x < width; x++) {
            const value = data16[y * width + x];
            const pixelOffset = offset + 1 + x * 2;
            rawData[pixelOffset] = (value >> 8) & 0xFF;     // High byte
            rawData[pixelOffset + 1] = value & 0xFF;         // Low byte
        }
    }

    // Compress with pako (zlib deflate)
    const compressed = pako.deflate(rawData);
    const idatChunk = makePNGChunk('IDAT', compressed);

    // IEND
    const iendChunk = makePNGChunk('IEND', new Uint8Array(0));

    // Combine all parts
    const png = new Uint8Array(signature.length + ihdrChunk.length + idatChunk.length + iendChunk.length);
    let offset = 0;
    png.set(signature, offset); offset += signature.length;
    png.set(ihdrChunk, offset); offset += ihdrChunk.length;
    png.set(idatChunk, offset); offset += idatChunk.length;
    png.set(iendChunk, offset);

    return png;
}

// ============================================================
// Heightmap Generation (16-bit / 8-bit with UE5/Gaea sizing)
// ============================================================

// Bilinear interpolation for resampling elevation grid to target size
function resampleElevation(srcData, srcWidth, srcHeight, dstWidth, dstHeight) {
    const dst = new Float32Array(dstWidth * dstHeight);
    const xRatio = (srcWidth - 1) / (dstWidth - 1);
    const yRatio = (srcHeight - 1) / (dstHeight - 1);

    for (let dy = 0; dy < dstHeight; dy++) {
        const srcY = dy * yRatio;
        const y0 = Math.floor(srcY);
        const y1 = Math.min(y0 + 1, srcHeight - 1);
        const fy = srcY - y0;

        for (let dx = 0; dx < dstWidth; dx++) {
            const srcX = dx * xRatio;
            const x0 = Math.floor(srcX);
            const x1 = Math.min(x0 + 1, srcWidth - 1);
            const fx = srcX - x0;

            const v00 = srcData[y0 * srcWidth + x0];
            const v10 = srcData[y0 * srcWidth + x1];
            const v01 = srcData[y1 * srcWidth + x0];
            const v11 = srcData[y1 * srcWidth + x1];

            dst[dy * dstWidth + dx] =
                v00 * (1 - fx) * (1 - fy) +
                v10 * fx * (1 - fy) +
                v01 * (1 - fx) * fy +
                v11 * fx * fy;
        }
    }
    return dst;
}

// Generate heightmap for selected area
async function generateHeightmap() {
    const bounds = calculateBounds(currentCenter.lat, currentCenter.lon, currentChunkSize);

    // Get settings
    const sizeMode = document.getElementById('heightmap-size-mode')?.value || 'ue5';
    const sizeSelect = document.getElementById('heightmap-size');
    const targetSize = sizeSelect?.value === 'auto' ? null : parseInt(sizeSelect?.value || '4033');
    const bitDepth = parseInt(document.getElementById('heightmap-bitdepth')?.value || '16');
    const contrastMode = document.getElementById('heightmap-contrast')?.value || 'smart';
    const shouldInvert = document.getElementById('heightmap-invert')?.checked || false;

    // Always fetch at max zoom for best source quality
    const zoom = 15;

    setStatus('Calculating tile coverage...', 'loading');
    showProgress(5);

    // Get tile range
    const topLeft = latLonToTile(bounds.north, bounds.west, zoom);
    const bottomRight = latLonToTile(bounds.south, bounds.east, zoom);

    const tilesX = bottomRight.x - topLeft.x + 1;
    const tilesY = bottomRight.y - topLeft.y + 1;
    const totalTiles = tilesX * tilesY;

    setStatus(`Fetching ${totalTiles} terrain tiles (zoom ${zoom})...`, 'loading');
    showProgress(10);

    // Fetch all tiles (batch parallel per row for speed)
    const tiles = [];
    let loaded = 0;
    let failedTiles = 0;

    for (let y = topLeft.y; y <= bottomRight.y; y++) {
        const rowPromises = [];
        for (let x = topLeft.x; x <= bottomRight.x; x++) {
            rowPromises.push(fetchTerrainTile(x, y, zoom));
        }
        const rowResults = await Promise.all(rowPromises);
        const row = rowResults.map(r => {
            if (!r.success) failedTiles++;
            loaded++;
            return r.data;
        });
        tiles.push(row);
        showProgress(10 + (loaded / totalTiles) * 40);
    }

    if (failedTiles > 0) {
        console.warn(`${failedTiles} of ${totalTiles} tiles failed to load`);
    }

    setStatus('Decoding elevation data...', 'loading');
    showProgress(55);

    // Composite tiles and decode elevation
    const compositeWidth = tilesX * 256;
    const compositeHeight = tilesY * 256;
    const fullElevation = new Float32Array(compositeWidth * compositeHeight);

    let minElev = Infinity;
    let maxElev = -Infinity;

    for (let ty = 0; ty < tilesY; ty++) {
        for (let tx = 0; tx < tilesX; tx++) {
            const tileData = tiles[ty][tx];
            const data = tileData.data;

            for (let py = 0; py < 256; py++) {
                const globalY = ty * 256 + py;
                for (let px = 0; px < 256; px++) {
                    const i = (py * 256 + px) * 4;
                    const r = data[i];
                    const g = data[i + 1];
                    const b = data[i + 2];

                    const elev = (r * 256 + g + b / 256) - 32768;
                    const globalX = tx * 256 + px;
                    fullElevation[globalY * compositeWidth + globalX] = elev;

                    if (r !== 0 || g !== 0 || b !== 0) {
                        if (elev < minElev) minElev = elev;
                        if (elev > maxElev) maxElev = elev;
                    }
                }
            }
        }
    }

    if (minElev === Infinity) { minElev = 0; maxElev = 100; }

    console.log(`Elevation range: ${minElev.toFixed(1)}m to ${maxElev.toFixed(1)}m`);
    setStatus(`Elevation: ${minElev.toFixed(0)}m to ${maxElev.toFixed(0)}m. Reprojecting...`, 'loading');
    showProgress(65);

    // Resample from Mercator tile grid to equirectangular projection
    // This ensures the heightmap aligns with road data which uses equirectangular
    const n = Math.pow(2, zoom);

    // Helper: convert lat/lon to fractional pixel position in the Mercator tile composite
    function latLonToMercatorPixel(lat, lon) {
        const px = ((lon + 180) / 360 * n - topLeft.x) * 256;
        const latRad = lat * Math.PI / 180;
        const py = ((1 - Math.log(Math.tan(latRad) + 1 / Math.cos(latRad)) / Math.PI) / 2 * n - topLeft.y) * 256;
        return { px, py };
    }

    // Bilinear sample from the Mercator elevation grid
    function sampleElevation(px, py) {
        const x0 = Math.floor(px);
        const y0 = Math.floor(py);
        const x1 = Math.min(x0 + 1, compositeWidth - 1);
        const y1 = Math.min(y0 + 1, compositeHeight - 1);
        const fx = px - x0;
        const fy = py - y0;

        const cx0 = Math.max(0, Math.min(x0, compositeWidth - 1));
        const cy0 = Math.max(0, Math.min(y0, compositeHeight - 1));

        const v00 = fullElevation[cy0 * compositeWidth + cx0];
        const v10 = fullElevation[cy0 * compositeWidth + x1];
        const v01 = fullElevation[y1 * compositeWidth + cx0];
        const v11 = fullElevation[y1 * compositeWidth + x1];

        return v00 * (1 - fx) * (1 - fy) + v10 * fx * (1 - fy) +
               v01 * (1 - fx) * fy + v11 * fx * fy;
    }

    // Build equirectangular grid - each pixel maps linearly to lat/lon
    // This matches how convertToUE5() maps coordinates (linear lat/lon to meters)
    const outputSize = targetSize || 1009;
    const resampled = new Float32Array(outputSize * outputSize);

    setStatus(`Reprojecting to ${outputSize}x${outputSize} equirectangular...`, 'loading');
    showProgress(70);

    minElev = Infinity;
    maxElev = -Infinity;

    for (let row = 0; row < outputSize; row++) {
        // Linear latitude mapping (equirectangular) - north to south
        const lat = bounds.north - (row / (outputSize - 1)) * (bounds.north - bounds.south);

        for (let col = 0; col < outputSize; col++) {
            // Linear longitude mapping - west to east
            const lon = bounds.west + (col / (outputSize - 1)) * (bounds.east - bounds.west);

            // Convert to Mercator pixel position and sample
            const { px, py } = latLonToMercatorPixel(lat, lon);
            const elev = sampleElevation(px, py);
            resampled[row * outputSize + col] = elev;

            if (elev < minElev) minElev = elev;
            if (elev > maxElev) maxElev = elev;
        }
    }

    const rawMinElev = minElev;
    const rawMaxElev = maxElev;

    setStatus('Applying contrast and encoding...', 'loading');
    showProgress(80);

    // Apply contrast enhancement to get final min/max
    let elevRange = maxElev - minElev;

    switch (contrastMode) {
        case 'raw':
            break;
        case 'smart': {
            // Smart normalization: 0.1% / 99.9% window (like unrealheightmap)
            // Filters extreme outliers while preserving nearly all terrain detail
            const sorted = Float32Array.from(resampled).sort();
            const lo = sorted[Math.floor(sorted.length * 0.001)] ?? minElev;
            const hi = sorted[Math.floor(sorted.length * 0.999)] ?? maxElev;
            minElev = lo;
            maxElev = hi;
            elevRange = maxElev - minElev || 1;
            break;
        }
        case 'enhanced':
            if (elevRange < 10) {
                const mid = (maxElev + minElev) / 2;
                minElev = mid - 5;
                maxElev = mid + 5;
                elevRange = 10;
            }
            break;
        case 'extreme': {
            const sorted = Float32Array.from(resampled).sort();
            minElev = sorted[Math.floor(sorted.length * 0.02)] ?? minElev;
            maxElev = sorted[Math.floor(sorted.length * 0.98)] ?? maxElev;
            elevRange = maxElev - minElev || 1;
            break;
        }
        case 'histogram':
            // Handled below
            break;
    }

    // Build histogram LUT for histogram equalization
    let histogramLUT = null;
    if (contrastMode === 'histogram') {
        const sorted = Float32Array.from(resampled).sort();
        histogramLUT = new Map();
        for (let i = 0; i < sorted.length; i++) {
            const elev = sorted[i];
            if (!histogramLUT.has(elev)) {
                histogramLUT.set(elev, i / sorted.length);
            }
        }
    }

    showProgress(85);

    const maxVal = bitDepth === 16 ? 65535 : 255;
    let resultBlob;
    let resultWidth = outputSize;
    let resultHeight = outputSize;

    if (bitDepth === 16) {
        // 16-bit grayscale PNG
        setStatus(`Encoding 16-bit PNG (${outputSize}x${outputSize})...`, 'loading');
        const data16 = new Uint16Array(outputSize * outputSize);

        for (let i = 0; i < resampled.length; i++) {
            let elev = resampled[i];
            let normalized;

            if (contrastMode === 'histogram' && histogramLUT) {
                normalized = histogramLUT.get(elev);
                if (normalized === undefined) {
                    normalized = Math.max(0, Math.min(1, (elev - minElev) / (elevRange || 1)));
                }
            } else {
                normalized = Math.max(0, Math.min(1, (elev - minElev) / (elevRange || 1)));
            }

            if (shouldInvert) normalized = 1 - normalized;
            data16[i] = Math.round(normalized * 65535);
        }

        showProgress(90);
        const pngBytes = encode16BitPNG(outputSize, outputSize, data16);
        resultBlob = new Blob([pngBytes], { type: 'image/png' });

    } else {
        // 8-bit grayscale via canvas
        setStatus(`Encoding 8-bit PNG (${outputSize}x${outputSize})...`, 'loading');
        const canvas = document.createElement('canvas');
        canvas.width = outputSize;
        canvas.height = outputSize;
        const ctx = canvas.getContext('2d');
        const imageData = ctx.createImageData(outputSize, outputSize);

        for (let i = 0; i < resampled.length; i++) {
            let elev = resampled[i];
            let normalized;

            if (contrastMode === 'histogram' && histogramLUT) {
                normalized = histogramLUT.get(elev);
                if (normalized === undefined) {
                    normalized = Math.max(0, Math.min(1, (elev - minElev) / (elevRange || 1)));
                }
            } else {
                normalized = Math.max(0, Math.min(1, (elev - minElev) / (elevRange || 1)));
            }

            if (shouldInvert) normalized = 1 - normalized;
            const gray = Math.round(normalized * 255);

            const idx = i * 4;
            imageData.data[idx] = gray;
            imageData.data[idx + 1] = gray;
            imageData.data[idx + 2] = gray;
            imageData.data[idx + 3] = 255;
        }

        ctx.putImageData(imageData, 0, 0);

        resultBlob = await new Promise(resolve => {
            canvas.toBlob(resolve, 'image/png');
        });
    }

    showProgress(95);

    // Update info display
    const infoEl = document.getElementById('heightmap-info');
    if (infoEl) {
        const metersPerPixel = (currentChunkSize * 1000) / outputSize;
        const range = rawMaxElev - rawMinElev;
        infoEl.innerHTML = `<strong>Output: ${outputSize}x${outputSize}px</strong> | ${bitDepth}-bit | ~${metersPerPixel.toFixed(1)}m/pixel<br>` +
            `Elevation: ${rawMinElev.toFixed(1)}m to ${rawMaxElev.toFixed(1)}m (${range.toFixed(1)}m range)`;
    }

    return {
        blob: resultBlob,
        width: resultWidth,
        height: resultHeight,
        minElevation: rawMinElev,
        maxElevation: rawMaxElev,
        outputSize,
        bitDepth,
        bounds
    };
}

// Download heightmap with save dialog
async function downloadHeightmap() {
    try {
        const result = await generateHeightmap();

        showProgress(100);
        const range = result.maxElevation - result.minElevation;
        setStatus(`Heightmap ready: ${result.outputSize}x${result.outputSize}px ${result.bitDepth}-bit | ${result.minElevation.toFixed(0)}m to ${result.maxElevation.toFixed(0)}m (${range.toFixed(0)}m range)`, 'success');

        lastHeightmapResult = result;

        const bitLabel = result.bitDepth === 16 ? '16bit' : '8bit';
        const filename = `heightmap_${currentCenter.lat.toFixed(4)}_${currentCenter.lon.toFixed(4)}_${result.outputSize}px_${bitLabel}.png`;

        // Try File System Access API
        if ('showSaveFilePicker' in window) {
            try {
                const handle = await window.showSaveFilePicker({
                    suggestedName: filename,
                    types: [{ description: 'PNG Image', accept: { 'image/png': ['.png'] } }]
                });

                const writable = await handle.createWritable();
                await writable.write(result.blob);
                await writable.close();

                setStatus(`Saved: ${handle.name} (${result.outputSize}x${result.outputSize}px, ${result.bitDepth}-bit)`, 'success');
                setTimeout(() => showProgress(null), 500);
                return;
            } catch (err) {
                if (err.name === 'AbortError') {
                    setTimeout(() => showProgress(null), 500);
                    return;
                }
            }
        }

        // Fallback download
        const url = URL.createObjectURL(result.blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);

        setTimeout(() => showProgress(null), 500);

    } catch (error) {
        console.error('Heightmap error:', error);
        setStatus(`Error generating heightmap: ${error.message}`, 'error');
        showProgress(null);
    }
}

// Last heightmap result for Gaea export
let lastHeightmapResult = null;

// Initialize on load
document.addEventListener('DOMContentLoaded', () => {
    initMap();
    setupEventHandlers();
    setStatus('Click on the map to place extraction area');
});
