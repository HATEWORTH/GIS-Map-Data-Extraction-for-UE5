#!/usr/bin/env python3
"""
convert_to_ue5.py - Convert GeoJSON road data to UE5-compatible format.

Transforms geographic coordinates to local UE5 coordinates and outputs
JSON matching the ImportedRoadNetwork format.
"""

import argparse
import json
import math
import os
import sys
from typing import Dict, List, Tuple

# UE5 scale factor: 1 meter = 100 Unreal Units
UE5_SCALE = 100.0


def latlon_to_meters(lat: float, lon: float, center_lat: float, center_lon: float) -> Tuple[float, float]:
    """
    Convert lat/lon to local coordinates in meters from center.

    Uses equirectangular projection (accurate for small areas).

    Args:
        lat: Latitude to convert
        lon: Longitude to convert
        center_lat: Center latitude
        center_lon: Center longitude

    Returns:
        Tuple of (x, y) in meters from center
    """
    # Earth's radius in meters
    R = 6371000.0

    # Convert to radians
    lat_rad = math.radians(lat)
    lon_rad = math.radians(lon)
    center_lat_rad = math.radians(center_lat)
    center_lon_rad = math.radians(center_lon)

    # X is east-west (longitude)
    x = R * (lon_rad - center_lon_rad) * math.cos(center_lat_rad)

    # Y is north-south (latitude)
    y = R * (lat_rad - center_lat_rad)

    return (x, y)


def meters_to_ue5(x: float, y: float) -> Tuple[float, float]:
    """
    Convert meters to UE5 units.

    Args:
        x: X coordinate in meters
        y: Y coordinate in meters

    Returns:
        Tuple of (x, y) in Unreal Units
    """
    return (x * UE5_SCALE, y * UE5_SCALE)


def simplify_polyline(points: List[List[float]], tolerance: float = 1.0) -> List[List[float]]:
    """
    Simplify polyline using Ramer-Douglas-Peucker algorithm.

    Args:
        points: List of [x, y] points
        tolerance: Maximum distance for simplification (in same units as points)

    Returns:
        Simplified list of points
    """
    if len(points) < 3:
        return points

    def perpendicular_distance(point: List[float], line_start: List[float], line_end: List[float]) -> float:
        """Calculate perpendicular distance from point to line segment."""
        dx = line_end[0] - line_start[0]
        dy = line_end[1] - line_start[1]

        if dx == 0 and dy == 0:
            return math.sqrt((point[0] - line_start[0])**2 + (point[1] - line_start[1])**2)

        t = max(0, min(1, ((point[0] - line_start[0]) * dx + (point[1] - line_start[1]) * dy) / (dx*dx + dy*dy)))

        proj_x = line_start[0] + t * dx
        proj_y = line_start[1] + t * dy

        return math.sqrt((point[0] - proj_x)**2 + (point[1] - proj_y)**2)

    # Find point with maximum distance
    max_dist = 0
    max_idx = 0

    for i in range(1, len(points) - 1):
        dist = perpendicular_distance(points[i], points[0], points[-1])
        if dist > max_dist:
            max_dist = dist
            max_idx = i

    # If max distance exceeds tolerance, recursively simplify
    if max_dist > tolerance:
        left = simplify_polyline(points[:max_idx + 1], tolerance)
        right = simplify_polyline(points[max_idx:], tolerance)
        return left[:-1] + right
    else:
        return [points[0], points[-1]]


def build_node_graph(features: List[Dict], center_lat: float, center_lon: float) -> Tuple[List[Dict], Dict]:
    """
    Build node graph from road features.

    Identifies intersection points and creates node entries.

    Args:
        features: GeoJSON features list
        center_lat: Center latitude
        center_lon: Center longitude

    Returns:
        Tuple of (nodes list, endpoint_to_node_id mapping)
    """
    # Collect all endpoints with precision for matching
    endpoint_counts = {}

    for feature in features:
        coords = feature['geometry'].get('coordinates', [])
        if len(coords) < 2:
            continue

        for coord in [coords[0], coords[-1]]:
            # Round to ~1m precision for endpoint matching
            key = (round(coord[0], 5), round(coord[1], 5))
            endpoint_counts[key] = endpoint_counts.get(key, 0) + 1

    # Create nodes for all endpoints
    nodes = []
    endpoint_to_node = {}
    node_id = 0

    for (lon, lat), count in endpoint_counts.items():
        x_m, y_m = latlon_to_meters(lat, lon, center_lat, center_lon)
        x_uu, y_uu = meters_to_ue5(x_m, y_m)

        nodes.append({
            'id': node_id,
            'x': round(x_uu, 1),
            'y': round(y_uu, 1),
            'degree': count  # Number of roads meeting at this node
        })

        endpoint_to_node[(lon, lat)] = node_id
        # Also map the rounded version
        endpoint_to_node[(round(lon, 5), round(lat, 5))] = node_id
        node_id += 1

    return nodes, endpoint_to_node


def find_node_id(coord: List[float], endpoint_to_node: Dict) -> int:
    """Find node ID for a coordinate, using rounded matching."""
    # Try exact match
    key = (coord[0], coord[1])
    if key in endpoint_to_node:
        return endpoint_to_node[key]

    # Try rounded match
    key = (round(coord[0], 5), round(coord[1], 5))
    if key in endpoint_to_node:
        return endpoint_to_node[key]

    return -1


def convert_geojson_to_ue5(geojson: Dict, simplify: bool = True,
                           simplify_tolerance: float = 2.0) -> Dict:
    """
    Convert GeoJSON to UE5-compatible road network format.

    Args:
        geojson: GeoJSON FeatureCollection
        simplify: Whether to simplify polylines
        simplify_tolerance: Simplification tolerance in meters

    Returns:
        UE5-compatible road network dict
    """
    metadata = geojson.get('metadata', {})
    center_lat = metadata.get('center_lat', 0)
    center_lon = metadata.get('center_lon', 0)
    size_km = metadata.get('size_km', 8)

    features = geojson.get('features', [])

    # Build node graph
    nodes, endpoint_to_node = build_node_graph(features, center_lat, center_lon)

    # Convert edges
    edges = []
    edge_id = 0

    for feature in features:
        coords = feature['geometry'].get('coordinates', [])
        if len(coords) < 2:
            continue

        props = feature.get('properties', {})

        # Find start and end nodes
        start_node = find_node_id(coords[0], endpoint_to_node)
        end_node = find_node_id(coords[-1], endpoint_to_node)

        # Convert all points to UE5 coordinates
        points_uu = []
        for coord in coords:
            x_m, y_m = latlon_to_meters(coord[1], coord[0], center_lat, center_lon)
            x_uu, y_uu = meters_to_ue5(x_m, y_m)
            points_uu.append([round(x_uu, 1), round(y_uu, 1)])

        # Simplify if requested
        if simplify and len(points_uu) > 2:
            tolerance_uu = simplify_tolerance * UE5_SCALE
            points_uu = simplify_polyline(points_uu, tolerance_uu)

        # Create edge
        edge = {
            'id': edge_id,
            'start_node': start_node,
            'end_node': end_node,
            'road_type': props.get('road_type', 'unclassified'),
            'color': props.get('color', '#FFFFFF'),
            'width': props.get('width', 600),
            'name': props.get('name', ''),
            'osm_id': props.get('osm_id', 0),
            'oneway': props.get('oneway', 'no') == 'yes',
            'points': points_uu
        }
        edges.append(edge)
        edge_id += 1

    # Calculate bounds in UE5 units
    half_size_uu = (size_km * 1000 * UE5_SCALE) / 2

    # Build output
    output = {
        'metadata': {
            'city': metadata.get('city', 'unknown'),
            'category': metadata.get('category', 'unknown'),
            'center_lat': center_lat,
            'center_lon': center_lon,
            'size_km': size_km,
            'bounds_uu': {
                'min': [-half_size_uu, -half_size_uu],
                'max': [half_size_uu, half_size_uu]
            },
            'road_stats': metadata.get('road_stats', {}),
            'total_roads': len(edges),
            'total_nodes': len(nodes),
            'source': 'OpenStreetMap',
            'converted_at': metadata.get('extracted_at', '')
        },
        'nodes': nodes,
        'edges': edges
    }

    return output


def validate_output(data: Dict) -> List[str]:
    """
    Validate the output data structure.

    Returns list of warnings/errors.
    """
    warnings = []

    if not data.get('nodes'):
        warnings.append("No nodes in output")

    if not data.get('edges'):
        warnings.append("No edges in output")

    # Check for orphan nodes
    referenced_nodes = set()
    for edge in data.get('edges', []):
        referenced_nodes.add(edge.get('start_node', -1))
        referenced_nodes.add(edge.get('end_node', -1))

    all_nodes = {n['id'] for n in data.get('nodes', [])}
    orphans = all_nodes - referenced_nodes
    if orphans:
        warnings.append(f"{len(orphans)} orphan nodes (not connected to any edge)")

    # Check for invalid node references
    invalid_refs = referenced_nodes - all_nodes - {-1}
    if invalid_refs:
        warnings.append(f"{len(invalid_refs)} edges reference non-existent nodes")

    # Check for very short edges
    short_edges = sum(1 for e in data.get('edges', []) if len(e.get('points', [])) < 2)
    if short_edges:
        warnings.append(f"{short_edges} edges have less than 2 points")

    return warnings


def main():
    parser = argparse.ArgumentParser(
        description='Convert GeoJSON road data to UE5 format'
    )
    parser.add_argument('--input', '-i', type=str, required=True,
                        help='Input GeoJSON file')
    parser.add_argument('--output', '-o', type=str, default=None,
                        help='Output JSON file (default: auto-generate)')
    parser.add_argument('--no-simplify', action='store_true',
                        help='Disable polyline simplification')
    parser.add_argument('--tolerance', type=float, default=2.0,
                        help='Simplification tolerance in meters (default: 2.0)')
    parser.add_argument('--validate', '-v', action='store_true',
                        help='Validate output and show warnings')

    args = parser.parse_args()

    if not os.path.exists(args.input):
        print(f"Error: File not found: {args.input}")
        sys.exit(1)

    # Load input
    print(f"Loading: {args.input}")
    with open(args.input, 'r', encoding='utf-8') as f:
        geojson = json.load(f)

    # Convert
    print("Converting to UE5 format...")
    ue5_data = convert_geojson_to_ue5(
        geojson,
        simplify=not args.no_simplify,
        simplify_tolerance=args.tolerance
    )

    # Validate if requested
    if args.validate:
        warnings = validate_output(ue5_data)
        if warnings:
            print("\nValidation Warnings:")
            for w in warnings:
                print(f"  - {w}")
        else:
            print("\nValidation: OK")

    # Determine output path
    if args.output:
        output_path = args.output
    else:
        # Auto-generate based on input
        base = os.path.splitext(os.path.basename(args.input))[0]
        output_path = f"../../output/ue5_ready/{base}_ue5.json"

    # Save output
    os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(ue5_data, f, indent=2)

    print(f"Saved: {output_path}")

    # Print summary
    meta = ue5_data['metadata']
    print(f"\nSummary:")
    print(f"  City: {meta['city']}")
    print(f"  Category: {meta['category']}")
    print(f"  Nodes: {meta['total_nodes']}")
    print(f"  Edges: {meta['total_roads']}")
    print(f"  Bounds: {meta['bounds_uu']['min']} to {meta['bounds_uu']['max']} UU")


if __name__ == '__main__':
    main()
