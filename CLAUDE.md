# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

GIS Map Data Extraction Pipeline for UE5 - extracts real US city road network data from OpenStreetMap and converts it into Unreal Engine 5-compatible JSON format for spline-based road generation. Processes 8×8 km geographic chunks with road classification and color coding.

## Commands

### Setup
```bash
pip install -r tools/python/requirements.txt
```

### Single City Extraction
```bash
cd tools/python
python extract_osm.py --lat 40.758 --lon -73.9855 --city "Manhattan_NYC"
```

### Batch Processing
```bash
python batch_process.py --config ../../data/cities.json --delay 5
```

### Format Conversion (GeoJSON to UE5 JSON)
```bash
python convert_to_ue5.py --input [geojson_file] --output [json_file]
```

### Network Preprocessing
```bash
python preprocess_network.py [ue5_json_file]
```

### SVG Export
```bash
python export_svg.py [ue5_json_file]
```

### Web Interface
Open `tools/web/index.html` in browser for interactive extraction.

## Architecture

### Pipeline Flow
1. **extract_osm.py** - Queries Overpass API, outputs GeoJSON with road classification
2. **convert_to_ue5.py** - Transforms lat/lon to UE5 coordinates (1m = 100 Unreal Units), builds node-edge graph
3. **preprocess_network.py** - Merges edges, classifies nodes, calculates intersection angles
4. **batch_process.py** - Orchestrates multi-city extraction with rate limiting

### Road Type Classification (8 types)
| Type | OSM Tags | UE5 Width |
|------|----------|-----------|
| Interstate | motorway, motorway_link | 2400 UU |
| Highway | trunk, trunk_link | 2000 UU |
| Principal Arterial | primary, primary_link | 1600 UU |
| Minor Arterial | secondary, secondary_link | 1200 UU |
| Collector | tertiary, tertiary_link | 800 UU |
| Residential | residential, living_street | 600 UU |
| Service | service, track | 400 UU |
| Unclassified | unclassified, road | 600 UU |

### Output Format (UE5 JSON)
```json
{
  "metadata": { "city", "category", "center_lat", "center_lon", "size_km", "bounds_uu", "road_stats" },
  "nodes": [{ "id", "x", "y", "degree" }],
  "edges": [{ "id", "start_node", "end_node", "road_type", "color", "width", "name", "points" }]
}
```

### Key Files
- `data/cities.json` - 32 pre-configured city locations with categories (downtown/residential/rural)
- `output/ue5_ready/` - Final UE5-compatible JSON files
- `tools/web/` - Interactive browser-based extraction UI using Leaflet

### External Dependencies
- **Overpass API** - Uses 3 fallback endpoints with automatic failover
- **Rate Limiting** - 5-second delays between API calls to respect public servers
- **Coordinate Projection** - Equirectangular projection (accurate within ~8km chunks)
