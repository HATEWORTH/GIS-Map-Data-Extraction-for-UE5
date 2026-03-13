#!/usr/bin/env python3
"""
extract_osm.py - Extract road network data from OpenStreetMap via Overpass API.

Extracts an 8x8 km chunk of road data centered on given coordinates,
classifies roads by type, and outputs GeoJSON with color coding.
"""

import argparse
import json
import math
import os
import sys
import time
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import requests

# Road type classification with colors and widths (in UE5 units)
ROAD_TYPES = {
    # Interstate/Freeway
    'motorway': {'type': 'interstate', 'color': '#E31C1C', 'width': 2400, 'priority': 1},
    'motorway_link': {'type': 'interstate', 'color': '#E31C1C', 'width': 1800, 'priority': 1},
    # Highway/Expressway
    'trunk': {'type': 'highway', 'color': '#F48C06', 'width': 2000, 'priority': 2},
    'trunk_link': {'type': 'highway', 'color': '#F48C06', 'width': 1500, 'priority': 2},
    # Principal Arterial
    'primary': {'type': 'arterial', 'color': '#FFC300', 'width': 1600, 'priority': 3},
    'primary_link': {'type': 'arterial', 'color': '#FFC300', 'width': 1200, 'priority': 3},
    # Minor Arterial
    'secondary': {'type': 'minor_arterial', 'color': '#FFE066', 'width': 1200, 'priority': 4},
    'secondary_link': {'type': 'minor_arterial', 'color': '#FFE066', 'width': 900, 'priority': 4},
    # Collector
    'tertiary': {'type': 'collector', 'color': '#74C0FC', 'width': 800, 'priority': 5},
    'tertiary_link': {'type': 'collector', 'color': '#74C0FC', 'width': 600, 'priority': 5},
    # Residential/Local
    'residential': {'type': 'residential', 'color': '#51CF66', 'width': 600, 'priority': 6},
    'living_street': {'type': 'residential', 'color': '#51CF66', 'width': 500, 'priority': 6},
    # Service/Alley
    'service': {'type': 'service', 'color': '#868E96', 'width': 400, 'priority': 7},
    'track': {'type': 'service', 'color': '#868E96', 'width': 300, 'priority': 7},
    # Unclassified
    'unclassified': {'type': 'unclassified', 'color': '#FFFFFF', 'width': 600, 'priority': 8},
    'road': {'type': 'unclassified', 'color': '#FFFFFF', 'width': 600, 'priority': 8},
}

# Default for unknown road types
DEFAULT_ROAD = {'type': 'unclassified', 'color': '#FFFFFF', 'width': 600, 'priority': 9}

# Overpass API endpoints (use multiple for fallback)
OVERPASS_ENDPOINTS = [
    'https://overpass-api.de/api/interpreter',
    'https://overpass.kumi.systems/api/interpreter',
    'https://maps.mail.ru/osm/tools/overpass/api/interpreter',
]


def calculate_bounds(lat: float, lon: float, size_km: float = 8.0) -> Tuple[float, float, float, float]:
    """
    Calculate bounding box for a square chunk centered on coordinates.

    Args:
        lat: Center latitude
        lon: Center longitude
        size_km: Size of chunk in kilometers

    Returns:
        Tuple of (south, west, north, east) bounds
    """
    # Earth's radius in km
    R = 6371.0

    # Half size in km
    half_size = size_km / 2.0

    # Latitude offset (degrees)
    lat_offset = math.degrees(half_size / R)

    # Longitude offset (degrees) - accounts for latitude
    lon_offset = math.degrees(half_size / (R * math.cos(math.radians(lat))))

    south = lat - lat_offset
    north = lat + lat_offset
    west = lon - lon_offset
    east = lon + lon_offset

    return (south, west, north, east)


def build_overpass_query(bounds: Tuple[float, float, float, float]) -> str:
    """
    Build Overpass QL query for road network within bounds.

    Args:
        bounds: (south, west, north, east) bounding box

    Returns:
        Overpass QL query string
    """
    south, west, north, east = bounds
    bbox = f"{south},{west},{north},{east}"

    # Query for all highway types we care about
    highway_types = '|'.join(ROAD_TYPES.keys())

    query = f"""
[out:json][timeout:120];
(
  way["highway"~"^({highway_types})$"]({bbox});
);
out body;
>;
out skel qt;
"""
    return query


def query_overpass(query: str, max_retries: int = 3) -> Optional[Dict]:
    """
    Query Overpass API with retry logic and endpoint fallback.

    Args:
        query: Overpass QL query string
        max_retries: Maximum retry attempts per endpoint

    Returns:
        JSON response dict or None on failure
    """
    for endpoint in OVERPASS_ENDPOINTS:
        for attempt in range(max_retries):
            try:
                print(f"Querying {endpoint} (attempt {attempt + 1}/{max_retries})...")
                response = requests.post(
                    endpoint,
                    data={'data': query},
                    timeout=180,
                    headers={'User-Agent': 'UE5-RoadNetworkExtractor/1.0'}
                )

                if response.status_code == 200:
                    return response.json()
                elif response.status_code == 429:
                    # Rate limited - wait and retry
                    wait_time = 30 * (attempt + 1)
                    print(f"Rate limited. Waiting {wait_time}s...")
                    time.sleep(wait_time)
                elif response.status_code == 504:
                    # Timeout - the query might be too large
                    print(f"Query timeout (504). Try a smaller area.")
                    return None
                else:
                    print(f"Error {response.status_code}: {response.text[:200]}")

            except requests.exceptions.Timeout:
                print(f"Request timeout. Retrying...")
                time.sleep(5)
            except requests.exceptions.RequestException as e:
                print(f"Request error: {e}")
                time.sleep(5)

        print(f"Failed on {endpoint}, trying next...")

    print("All Overpass endpoints failed.")
    return None


def parse_osm_response(data: Dict, center_lat: float, center_lon: float) -> Dict:
    """
    Parse Overpass API response into GeoJSON format.

    Args:
        data: Raw Overpass API JSON response
        center_lat: Center latitude for metadata
        center_lon: Center longitude for metadata

    Returns:
        GeoJSON FeatureCollection dict
    """
    # Build node lookup table
    nodes = {}
    for element in data.get('elements', []):
        if element['type'] == 'node':
            nodes[element['id']] = (element['lon'], element['lat'])

    # Process ways into features
    features = []
    road_stats = {
        'interstate': 0, 'highway': 0, 'arterial': 0, 'minor_arterial': 0,
        'collector': 0, 'residential': 0, 'service': 0, 'unclassified': 0
    }

    for element in data.get('elements', []):
        if element['type'] != 'way':
            continue

        tags = element.get('tags', {})
        highway_tag = tags.get('highway', '')

        if highway_tag not in ROAD_TYPES:
            continue

        # Get road classification
        road_info = ROAD_TYPES.get(highway_tag, DEFAULT_ROAD)
        road_type = road_info['type']
        road_stats[road_type] = road_stats.get(road_type, 0) + 1

        # Build coordinate list
        coordinates = []
        for node_id in element.get('nodes', []):
            if node_id in nodes:
                coordinates.append(list(nodes[node_id]))

        if len(coordinates) < 2:
            continue

        # Create GeoJSON feature
        feature = {
            'type': 'Feature',
            'geometry': {
                'type': 'LineString',
                'coordinates': coordinates
            },
            'properties': {
                'osm_id': element['id'],
                'highway': highway_tag,
                'road_type': road_type,
                'color': road_info['color'],
                'width': road_info['width'],
                'priority': road_info['priority'],
                'name': tags.get('name', ''),
                'lanes': tags.get('lanes', ''),
                'maxspeed': tags.get('maxspeed', ''),
                'oneway': tags.get('oneway', 'no'),
                'surface': tags.get('surface', ''),
            }
        }
        features.append(feature)

    # Sort features by priority (major roads first)
    features.sort(key=lambda f: f['properties']['priority'])

    # Create GeoJSON FeatureCollection
    geojson = {
        'type': 'FeatureCollection',
        'metadata': {
            'source': 'OpenStreetMap',
            'center_lat': center_lat,
            'center_lon': center_lon,
            'extracted_at': datetime.utcnow().isoformat() + 'Z',
            'road_stats': road_stats,
            'total_roads': len(features)
        },
        'features': features
    }

    return geojson


def classify_chunk_category(geojson: Dict) -> str:
    """
    Classify chunk category based on road distribution.

    Args:
        geojson: GeoJSON FeatureCollection

    Returns:
        Category string: 'downtown', 'residential', 'rural',
                        'downtown_residential', or 'residential_rural'
    """
    stats = geojson.get('metadata', {}).get('road_stats', {})
    total = geojson.get('metadata', {}).get('total_roads', 0)

    if total == 0:
        return 'rural'

    # Calculate percentages
    major_roads = stats.get('interstate', 0) + stats.get('highway', 0) + \
                  stats.get('arterial', 0) + stats.get('minor_arterial', 0)
    collectors = stats.get('collector', 0)
    residential = stats.get('residential', 0)
    service = stats.get('service', 0)

    major_pct = major_roads / total * 100
    residential_pct = residential / total * 100
    density = total  # Raw count as proxy for density

    # Classification logic
    if density < 50:
        return 'rural'

    if major_pct > 15 and residential_pct < 40:
        return 'downtown'

    if residential_pct > 70:
        return 'residential'

    if major_pct > 8 and residential_pct > 40:
        return 'downtown_residential'

    if density < 200 and residential_pct > 50:
        return 'residential_rural'

    # Default based on dominant type
    if residential_pct > major_pct:
        return 'residential'
    else:
        return 'downtown_residential'


def extract_chunk(lat: float, lon: float, size_km: float = 8.0,
                  city_name: str = "unknown") -> Optional[Dict]:
    """
    Extract road network chunk from OpenStreetMap.

    Args:
        lat: Center latitude
        lon: Center longitude
        size_km: Chunk size in kilometers (default 8)
        city_name: Name for the city/location

    Returns:
        GeoJSON FeatureCollection with metadata, or None on failure
    """
    print(f"Extracting {size_km}x{size_km}km chunk at ({lat}, {lon})...")

    # Calculate bounds
    bounds = calculate_bounds(lat, lon, size_km)
    print(f"Bounds: S={bounds[0]:.4f}, W={bounds[1]:.4f}, N={bounds[2]:.4f}, E={bounds[3]:.4f}")

    # Build and execute query
    query = build_overpass_query(bounds)
    data = query_overpass(query)

    if data is None:
        return None

    print(f"Received {len(data.get('elements', []))} elements from OSM")

    # Parse to GeoJSON
    geojson = parse_osm_response(data, lat, lon)

    # Add additional metadata
    geojson['metadata']['city'] = city_name
    geojson['metadata']['size_km'] = size_km
    geojson['metadata']['bounds'] = {
        'south': bounds[0],
        'west': bounds[1],
        'north': bounds[2],
        'east': bounds[3]
    }

    # Classify chunk category
    category = classify_chunk_category(geojson)
    geojson['metadata']['category'] = category

    print(f"Extracted {geojson['metadata']['total_roads']} roads, category: {category}")

    return geojson


def save_geojson(geojson: Dict, output_path: str) -> None:
    """Save GeoJSON to file."""
    os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(geojson, f, indent=2)
    print(f"Saved to: {output_path}")


def main():
    parser = argparse.ArgumentParser(
        description='Extract road network data from OpenStreetMap'
    )
    parser.add_argument('--lat', type=float, required=True,
                        help='Center latitude')
    parser.add_argument('--lon', type=float, required=True,
                        help='Center longitude')
    parser.add_argument('--size', type=float, default=8.0,
                        help='Chunk size in km (default: 8)')
    parser.add_argument('--city', type=str, default='unknown',
                        help='City name for output file')
    parser.add_argument('--output', type=str, default=None,
                        help='Output file path (default: auto-generate)')

    args = parser.parse_args()

    # Extract chunk
    geojson = extract_chunk(args.lat, args.lon, args.size, args.city)

    if geojson is None:
        print("Extraction failed.")
        sys.exit(1)

    # Determine output path
    if args.output:
        output_path = args.output
    else:
        category = geojson['metadata']['category']
        safe_city = args.city.replace(' ', '_').replace(',', '')
        output_path = f"../../data/chunks/{category}/{safe_city}.geojson"

    # Save result
    save_geojson(geojson, output_path)

    # Print summary
    stats = geojson['metadata']['road_stats']
    print("\nRoad Statistics:")
    for road_type, count in stats.items():
        if count > 0:
            print(f"  {road_type}: {count}")
    print(f"  Total: {geojson['metadata']['total_roads']}")


if __name__ == '__main__':
    main()
