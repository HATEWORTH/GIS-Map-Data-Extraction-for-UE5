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
    'https://overpass.kumi.systems/api/interpreter'
];

// State
let map;
let selectionRectangle = null;
let roadLayers = null;
let currentCenter = { lat: 40.7580, lon: -73.9855 };
let currentChunkSize = 8;
let extractedData = null;

// Initialize map
function initMap() {
    map = L.map('map', {
        center: [currentCenter.lat, currentCenter.lon],
        zoom: 13,
        zoomControl: true
    });

    // Add dark tile layer
    L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/">CARTO</a>',
        subdomains: 'abcd',
        maxZoom: 19
    }).addTo(map);

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
    for (const endpoint of OVERPASS_ENDPOINTS) {
        try {
            setStatus(`Querying ${new URL(endpoint).hostname}...`, 'loading');

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
                setStatus('Rate limited. Waiting...', 'loading');
                await new Promise(resolve => setTimeout(resolve, 30000));
            }
        } catch (error) {
            console.error(`Error with ${endpoint}:`, error);
        }
    }

    throw new Error('All Overpass endpoints failed');
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

    // Download Heightmap (in results panel) - disabled for now
    const heightmapBtn = document.getElementById('download-heightmap');
    if (heightmapBtn) {
        heightmapBtn.addEventListener('click', async () => {
            await downloadHeightmap();
        });
    }

    // Download Heightmap (standalone - always visible) - disabled for now
    const heightmapStandaloneBtn = document.getElementById('download-heightmap-standalone');
    if (heightmapStandaloneBtn) {
        heightmapStandaloneBtn.addEventListener('click', async () => {
            await downloadHeightmap();
        });
    }

    // Update heightmap info when resolution changes - disabled for now
    const heightmapResolution = document.getElementById('heightmap-resolution');
    if (heightmapResolution) {
        heightmapResolution.addEventListener('change', updateHeightmapInfo);
        setTimeout(updateHeightmapInfo, 100);
    }
}

// Update heightmap resolution info
function updateHeightmapInfo() {
    const infoEl = document.getElementById('heightmap-info');
    if (!infoEl) return;

    const resolutionSelect = document.getElementById('heightmap-resolution');
    const resolutionSetting = resolutionSelect ? resolutionSelect.value : '15';

    let zoom, upscaleFactor;
    if (resolutionSetting === 'max') {
        zoom = 15;
        upscaleFactor = 2;
    } else {
        zoom = parseInt(resolutionSetting);
        upscaleFactor = 1;
    }

    // Estimate output size
    const bounds = calculateBounds(currentCenter.lat, currentCenter.lon, currentChunkSize);
    const topLeft = latLonToTile(bounds.north, bounds.west, zoom);
    const bottomRight = latLonToTile(bounds.south, bounds.east, zoom);

    const tilesX = bottomRight.x - topLeft.x + 1;
    const tilesY = bottomRight.y - topLeft.y + 1;
    const totalTiles = tilesX * tilesY;

    const estWidth = tilesX * 256 * upscaleFactor;
    const estHeight = tilesY * 256 * upscaleFactor;
    const metersPerPixel = (currentChunkSize * 1000) / estWidth;

    infoEl.textContent = `Est. ${estWidth}x${estHeight}px (~${metersPerPixel.toFixed(1)}m/pixel) • ${totalTiles} tiles to fetch`;
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

// Generate heightmap for selected area
async function generateHeightmap() {
    const bounds = calculateBounds(currentCenter.lat, currentCenter.lon, currentChunkSize);

    // Get resolution setting
    const resolutionSelect = document.getElementById('heightmap-resolution');
    const resolutionSetting = resolutionSelect ? resolutionSelect.value : '15';

    // Determine zoom level and upscale factor
    let zoom, upscaleFactor;
    if (resolutionSetting === 'max') {
        zoom = 15;  // Max tile zoom
        upscaleFactor = 2;  // 2x upscale for ~2.2m/pixel
    } else {
        zoom = parseInt(resolutionSetting);
        upscaleFactor = 1;
    }

    // Clamp zoom for very large areas
    if (currentChunkSize > 20) zoom = Math.min(zoom, 13);
    else if (currentChunkSize > 10) zoom = Math.min(zoom, 14);

    setStatus('Calculating tile coverage...', 'loading');
    showProgress(5);

    // Get tile range
    const topLeft = latLonToTile(bounds.north, bounds.west, zoom);
    const bottomRight = latLonToTile(bounds.south, bounds.east, zoom);

    const tilesX = bottomRight.x - topLeft.x + 1;
    const tilesY = bottomRight.y - topLeft.y + 1;
    const totalTiles = tilesX * tilesY;

    setStatus(`Fetching ${totalTiles} terrain tiles...`, 'loading');
    showProgress(10);

    // Fetch all tiles
    const tiles = [];
    let loaded = 0;
    let failedTiles = 0;

    for (let y = topLeft.y; y <= bottomRight.y; y++) {
        const row = [];
        for (let x = topLeft.x; x <= bottomRight.x; x++) {
            const result = await fetchTerrainTile(x, y, zoom);
            row.push(result.data);
            if (!result.success) failedTiles++;
            loaded++;
            showProgress(10 + (loaded / totalTiles) * 50);
        }
        tiles.push(row);
    }

    if (failedTiles > 0) {
        console.warn(`${failedTiles} of ${totalTiles} tiles failed to load`);
    }

    setStatus('Processing elevation data...', 'loading');
    showProgress(65);

    // Composite tiles into single canvas
    const compositeWidth = tilesX * 256;
    const compositeHeight = tilesY * 256;

    // Collect elevation data from all tiles
    setStatus('Decoding elevation data...', 'loading');
    showProgress(65);

    let minElev = Infinity;
    let maxElev = -Infinity;
    const elevationData = new Array(compositeHeight);

    for (let ty = 0; ty < tilesY; ty++) {
        for (let tx = 0; tx < tilesX; tx++) {
            const tileData = tiles[ty][tx];
            const data = tileData.data;

            for (let py = 0; py < 256; py++) {
                const globalY = ty * 256 + py;
                if (!elevationData[globalY]) {
                    elevationData[globalY] = new Array(compositeWidth);
                }

                for (let px = 0; px < 256; px++) {
                    const i = (py * 256 + px) * 4;
                    const r = data[i];
                    const g = data[i + 1];
                    const b = data[i + 2];

                    // Terrarium encoding: elevation = (R * 256 + G + B / 256) - 32768
                    const elev = (r * 256 + g + b / 256) - 32768;

                    const globalX = tx * 256 + px;
                    elevationData[globalY][globalX] = elev;

                    // Only count valid elevations (not from failed tiles)
                    if (r !== 0 || g !== 0 || b !== 0) {
                        if (elev < minElev) minElev = elev;
                        if (elev > maxElev) maxElev = elev;
                    }
                }
            }
        }
    }

    // Handle edge case where all tiles failed
    if (minElev === Infinity) {
        minElev = 0;
        maxElev = 100;
    }

    console.log(`Elevation range: ${minElev.toFixed(1)}m to ${maxElev.toFixed(1)}m`);
    setStatus(`Elevation: ${minElev.toFixed(0)}m to ${maxElev.toFixed(0)}m`, 'loading');

    showProgress(80);
    setStatus('Generating heightmap image...', 'loading');

    // Calculate crop region to match exact bounds
    const topLeftCoord = tileToLatLon(topLeft.x, topLeft.y, zoom);
    const bottomRightCoord = tileToLatLon(bottomRight.x + 1, bottomRight.y + 1, zoom);

    // Pixel coordinates for bounds within composite
    const pixelPerDegLon = compositeWidth / (bottomRightCoord.lon - topLeftCoord.lon);
    const pixelPerDegLat = compositeHeight / (topLeftCoord.lat - bottomRightCoord.lat);

    const cropLeft = Math.floor((bounds.west - topLeftCoord.lon) * pixelPerDegLon);
    const cropTop = Math.floor((topLeftCoord.lat - bounds.north) * pixelPerDegLat);
    const cropRight = Math.floor((bounds.east - topLeftCoord.lon) * pixelPerDegLon);
    const cropBottom = Math.floor((topLeftCoord.lat - bounds.south) * pixelPerDegLat);

    const cropWidth = cropRight - cropLeft;
    const cropHeight = cropBottom - cropTop;

    // Create base heightmap canvas at tile resolution
    const baseCanvas = document.createElement('canvas');
    baseCanvas.width = cropWidth;
    baseCanvas.height = cropHeight;
    const baseCtx = baseCanvas.getContext('2d');
    const baseImageData = baseCtx.createImageData(cropWidth, cropHeight);

    // Get enhancement settings
    const contrastSelect = document.getElementById('heightmap-contrast');
    const contrastMode = contrastSelect ? contrastSelect.value : 'enhanced';
    const invertCheckbox = document.getElementById('heightmap-invert');
    const shouldInvert = invertCheckbox ? invertCheckbox.checked : false;

    // Calculate elevation range based on contrast mode
    let elevRange = maxElev - minElev;
    let useHistogramEq = false;

    switch (contrastMode) {
        case 'raw':
            // Use actual elevation values, no enhancement
            break;
        case 'enhanced':
            // Ensure minimum 10m range for visibility
            if (elevRange < 10) {
                const midElev = (maxElev + minElev) / 2;
                minElev = midElev - 5;
                maxElev = midElev + 5;
                elevRange = 10;
            }
            break;
        case 'extreme':
            // Use 2nd and 98th percentile for extreme contrast
            const allElevations = [];
            for (let y = cropTop; y < cropTop + cropHeight; y++) {
                for (let x = cropLeft; x < cropLeft + cropWidth; x++) {
                    if (elevationData[y] && elevationData[y][x] !== undefined) {
                        allElevations.push(elevationData[y][x]);
                    }
                }
            }
            allElevations.sort((a, b) => a - b);
            const p2 = allElevations[Math.floor(allElevations.length * 0.02)] || minElev;
            const p98 = allElevations[Math.floor(allElevations.length * 0.98)] || maxElev;
            minElev = p2;
            maxElev = p98;
            elevRange = maxElev - minElev || 1;
            break;
        case 'histogram':
            // Will apply histogram equalization
            useHistogramEq = true;
            break;
    }

    showProgress(85);
    setStatus('Rendering heightmap...', 'loading');

    // For histogram equalization, first collect all values and build lookup table
    let histogramLUT = null;
    if (useHistogramEq) {
        const allElevations = [];
        for (let y = cropTop; y < cropTop + cropHeight; y++) {
            for (let x = cropLeft; x < cropLeft + cropWidth; x++) {
                if (elevationData[y] && elevationData[y][x] !== undefined) {
                    allElevations.push(elevationData[y][x]);
                }
            }
        }
        allElevations.sort((a, b) => a - b);

        // Build cumulative distribution function lookup
        histogramLUT = new Map();
        for (let i = 0; i < allElevations.length; i++) {
            const elev = allElevations[i];
            if (!histogramLUT.has(elev)) {
                histogramLUT.set(elev, Math.round((i / allElevations.length) * 255));
            }
        }
    }

    for (let y = 0; y < cropHeight; y++) {
        for (let x = 0; x < cropWidth; x++) {
            const srcY = cropTop + y;
            const srcX = cropLeft + x;

            let elev = minElev;
            if (elevationData[srcY] && elevationData[srcY][srcX] !== undefined) {
                elev = elevationData[srcY][srcX];
            }

            let gray;
            if (useHistogramEq && histogramLUT) {
                // Find closest elevation in LUT
                gray = histogramLUT.get(elev);
                if (gray === undefined) {
                    // Linear interpolation fallback
                    gray = Math.round(((elev - minElev) / (elevRange || 1)) * 255);
                }
            } else {
                // Standard linear normalization
                const normalized = ((elev - minElev) / (elevRange || 1)) * 255;
                gray = Math.max(0, Math.min(255, Math.round(normalized)));
            }

            // Apply inversion if requested
            if (shouldInvert) {
                gray = 255 - gray;
            }

            const i = (y * cropWidth + x) * 4;
            baseImageData.data[i] = gray;     // R
            baseImageData.data[i + 1] = gray; // G
            baseImageData.data[i + 2] = gray; // B
            baseImageData.data[i + 3] = 255;  // A
        }
    }

    baseCtx.putImageData(baseImageData, 0, 0);

    // Apply upscaling if requested
    const finalWidth = cropWidth * upscaleFactor;
    const finalHeight = cropHeight * upscaleFactor;

    const heightmapCanvas = document.createElement('canvas');
    heightmapCanvas.width = finalWidth;
    heightmapCanvas.height = finalHeight;
    const heightmapCtx = heightmapCanvas.getContext('2d');

    // Use high-quality image scaling
    heightmapCtx.imageSmoothingEnabled = true;
    heightmapCtx.imageSmoothingQuality = 'high';
    heightmapCtx.drawImage(baseCanvas, 0, 0, finalWidth, finalHeight);

    showProgress(95);

    // Update info display
    const infoEl = document.getElementById('heightmap-info');
    if (infoEl) {
        const metersPerPixel = (currentChunkSize * 1000) / finalWidth;
        const actualRange = maxElev - minElev;
        infoEl.textContent = `Output: ${finalWidth}x${finalHeight}px | Elevation: ${minElev.toFixed(0)}m - ${maxElev.toFixed(0)}m (${actualRange.toFixed(0)}m range)`;
    }

    // Return as blob
    return new Promise((resolve) => {
        heightmapCanvas.toBlob((blob) => {
            resolve({
                blob,
                width: finalWidth,
                height: finalHeight,
                minElevation: minElev,
                maxElevation: maxElev
            });
        }, 'image/png');
    });
}

// Download heightmap with save dialog
async function downloadHeightmap() {
    try {
        const result = await generateHeightmap();

        showProgress(100);
        const range = result.maxElevation - result.minElevation;
        setStatus(`Heightmap ready: ${result.width}x${result.height}px | ${result.minElevation.toFixed(0)}m to ${result.maxElevation.toFixed(0)}m (${range.toFixed(0)}m range)`, 'success');

        const filename = `heightmap_${currentCenter.lat.toFixed(4)}_${currentCenter.lon.toFixed(4)}.png`;

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

                setStatus(`Saved: ${handle.name} (${result.width}x${result.height}px)`, 'success');
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

// Initialize on load
document.addEventListener('DOMContentLoaded', () => {
    initMap();
    setupEventHandlers();
    setStatus('Click on the map to place extraction area');
});
