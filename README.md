# GIS Map Data Extraction Pipeline

Extract real US city road data from OpenStreetMap for UE5 spline import.

## Overview

This pipeline extracts 8×8 km chunks of road network data from OpenStreetMap, classifies roads by type with color coding, and outputs UE5-compatible JSON for spline generation.

## Specifications

- **Chunk Size**: 8×8 km (800,000 × 800,000 UU in UE5)
- **Scale**: 1 meter = 100 Unreal Units
- **Data Source**: OpenStreetMap via Overpass API
- **Output**: GeoJSON (intermediate) → UE5-ready JSON

## Road Type Classification

| Road Type | OSM Tags | Color | UE5 Width (UU) |
|-----------|----------|-------|----------------|
| Interstate/Freeway | motorway, motorway_link | #E31C1C (Red) | 2400 |
| Highway/Expressway | trunk, trunk_link | #F48C06 (Orange) | 2000 |
| Principal Arterial | primary, primary_link | #FFC300 (Yellow) | 1600 |
| Minor Arterial | secondary, secondary_link | #FFE066 (Lt Yellow) | 1200 |
| Collector | tertiary, tertiary_link | #74C0FC (Lt Blue) | 800 |
| Residential/Local | residential, living_street | #51CF66 (Green) | 600 |
| Service/Alley | service, track | #868E96 (Gray) | 400 |
| Unclassified | unclassified | #FFFFFF (White) | 600 |

## Chunk Categories

1. **Downtown** - High arterial density, grid patterns
2. **Residential** - Local streets, cul-de-sacs
3. **Rural** - Sparse roads, long segments
4. **Downtown-Residential** - Mix of arterials and residential
5. **Residential-Rural** - Suburban edge transitions

## Quick Start

### Prerequisites

```bash
pip install -r tools/python/requirements.txt
```

### Extract a Single Chunk

```bash
cd tools/python
python extract_osm.py --lat 40.758 --lon -73.9855 --city "Manhattan_NYC"
```

### Use the Web Interface

Open `tools/web/index.html` in a browser:
1. Select a city from the dropdown or navigate manually
2. Click to place the 8×8 km selection box
3. Click "Extract Roads" to download GeoJSON

### Convert to UE5 Format

```bash
python convert_to_ue5.py --input ../data/chunks/downtown/Manhattan_NYC.geojson
```

### Batch Process Multiple Cities

```bash
python batch_process.py --config ../data/cities.json
```

## Output Format

The UE5-ready JSON matches the `ImportedRoadNetwork` format:

```json
{
  "metadata": {
    "city": "Manhattan_NYC",
    "category": "downtown",
    "center_lat": 40.758,
    "center_lon": -73.9855,
    "size_km": 8,
    "bounds_uu": {"min": [-400000, -400000], "max": [400000, 400000]}
  },
  "nodes": [
    {"id": 0, "x": 12500.5, "y": -8700.2}
  ],
  "edges": [
    {
      "id": 0,
      "start_node": 0,
      "end_node": 1,
      "road_type": "residential",
      "color": "#51CF66",
      "width": 600,
      "points": [[12500.5, -8700.2], [12600.0, -8650.0]]
    }
  ]
}
```

## Directory Structure

```
GIS_Map_Data_V1/
├── README.md
├── tools/
│   ├── python/
│   │   ├── requirements.txt
│   │   ├── extract_osm.py      # OSM extraction
│   │   ├── classify_chunk.py   # Category detection
│   │   ├── convert_to_ue5.py   # GeoJSON → UE5 JSON
│   │   └── batch_process.py    # Batch extraction
│   └── web/
│       ├── index.html          # Visual selector
│       ├── style.css
│       └── app.js
├── data/
│   ├── cities.json             # Pre-configured locations
│   └── chunks/                 # Extracted GeoJSON by category
└── output/
    └── ue5_ready/              # Final UE5-compatible JSON
```

## UE5 Import

Use the `RoadNetworkImportLibrary` to import the JSON:

```cpp
URoadNetworkImportLibrary::ImportFromJSON(FilePath, OutRoadNetwork);
```

Or via Blueprint, call `Import Road Network From JSON`.

## License

Road data from OpenStreetMap © OpenStreetMap contributors, licensed under ODbL.
