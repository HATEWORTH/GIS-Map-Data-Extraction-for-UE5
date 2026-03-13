#!/usr/bin/env python3
"""
classify_chunk.py - Analyze and categorize road network chunks.

Provides utilities for analyzing road distribution and automatically
categorizing chunks based on their characteristics.
"""

import argparse
import json
import os
import sys
from typing import Dict, List, Tuple


def load_geojson(filepath: str) -> Dict:
    """Load GeoJSON file."""
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)


def calculate_road_lengths(geojson: Dict) -> Dict[str, float]:
    """
    Calculate total length of roads by type (in approximate meters).

    Args:
        geojson: GeoJSON FeatureCollection

    Returns:
        Dict mapping road type to total length in meters
    """
    from math import radians, sin, cos, sqrt, atan2

    def haversine(coord1: List[float], coord2: List[float]) -> float:
        """Calculate distance between two points in meters."""
        R = 6371000  # Earth radius in meters

        lon1, lat1 = radians(coord1[0]), radians(coord1[1])
        lon2, lat2 = radians(coord2[0]), radians(coord2[1])

        dlat = lat2 - lat1
        dlon = lon2 - lon1

        a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
        c = 2 * atan2(sqrt(a), sqrt(1-a))

        return R * c

    lengths = {}

    for feature in geojson.get('features', []):
        road_type = feature['properties'].get('road_type', 'unclassified')
        coords = feature['geometry'].get('coordinates', [])

        # Calculate polyline length
        length = 0
        for i in range(len(coords) - 1):
            length += haversine(coords[i], coords[i+1])

        lengths[road_type] = lengths.get(road_type, 0) + length

    return lengths


def calculate_intersection_density(geojson: Dict) -> float:
    """
    Estimate intersection density based on road endpoints.

    Args:
        geojson: GeoJSON FeatureCollection

    Returns:
        Approximate number of intersections per square km
    """
    # Collect all endpoints
    endpoints = {}

    for feature in geojson.get('features', []):
        coords = feature['geometry'].get('coordinates', [])
        if len(coords) < 2:
            continue

        # Round coordinates to ~10m precision for matching
        for point in [coords[0], coords[-1]]:
            key = (round(point[0], 4), round(point[1], 4))
            endpoints[key] = endpoints.get(key, 0) + 1

    # Count intersections (endpoints shared by 3+ roads)
    intersections = sum(1 for count in endpoints.values() if count >= 3)

    # Get area from metadata
    metadata = geojson.get('metadata', {})
    size_km = metadata.get('size_km', 8)
    area_km2 = size_km * size_km

    return intersections / area_km2


def calculate_grid_regularity(geojson: Dict) -> float:
    """
    Estimate how grid-like the road network is.

    Returns a score from 0 (organic) to 1 (perfect grid).
    """
    from math import atan2, degrees

    # Collect road segment angles
    angles = []

    for feature in geojson.get('features', []):
        coords = feature['geometry'].get('coordinates', [])
        if len(coords) < 2:
            continue

        # Sample angles from this road
        for i in range(len(coords) - 1):
            dx = coords[i+1][0] - coords[i][0]
            dy = coords[i+1][1] - coords[i][1]
            angle = degrees(atan2(dy, dx)) % 90  # Normalize to 0-90
            angles.append(angle)

    if not angles:
        return 0.0

    # Count angles near 0, 45, or 90 degrees (grid-aligned)
    grid_aligned = sum(1 for a in angles if a < 10 or a > 80 or (40 < a < 50))
    regularity = grid_aligned / len(angles)

    return regularity


def classify_chunk(geojson: Dict) -> Dict:
    """
    Perform detailed classification of a road network chunk.

    Args:
        geojson: GeoJSON FeatureCollection

    Returns:
        Classification result with category and detailed metrics
    """
    stats = geojson.get('metadata', {}).get('road_stats', {})
    total = geojson.get('metadata', {}).get('total_roads', 0)

    if total == 0:
        return {
            'category': 'rural',
            'confidence': 1.0,
            'metrics': {
                'total_roads': 0,
                'density': 'none'
            }
        }

    # Calculate metrics
    lengths = calculate_road_lengths(geojson)
    intersection_density = calculate_intersection_density(geojson)
    grid_score = calculate_grid_regularity(geojson)

    # Calculate percentages
    total_length = sum(lengths.values())
    major_roads = stats.get('interstate', 0) + stats.get('highway', 0) + \
                  stats.get('arterial', 0) + stats.get('minor_arterial', 0)
    residential = stats.get('residential', 0)

    major_pct = major_roads / total * 100 if total > 0 else 0
    residential_pct = residential / total * 100 if total > 0 else 0

    # Length-based percentages
    major_length = lengths.get('interstate', 0) + lengths.get('highway', 0) + \
                   lengths.get('arterial', 0) + lengths.get('minor_arterial', 0)
    major_length_pct = major_length / total_length * 100 if total_length > 0 else 0

    # Classification logic with confidence scores
    scores = {
        'downtown': 0.0,
        'residential': 0.0,
        'rural': 0.0,
        'downtown_residential': 0.0,
        'residential_rural': 0.0
    }

    # Rural indicators
    if total < 30:
        scores['rural'] += 0.5
    if intersection_density < 2:
        scores['rural'] += 0.3
    if total_length < 20000:  # Less than 20km total
        scores['rural'] += 0.2

    # Downtown indicators
    if major_pct > 15:
        scores['downtown'] += 0.3
    if grid_score > 0.6:
        scores['downtown'] += 0.2
    if intersection_density > 20:
        scores['downtown'] += 0.3
    if major_length_pct > 20:
        scores['downtown'] += 0.2

    # Residential indicators
    if residential_pct > 60:
        scores['residential'] += 0.4
    if grid_score < 0.4:
        scores['residential'] += 0.2
    if 5 < intersection_density < 15:
        scores['residential'] += 0.2
    if stats.get('service', 0) / total > 0.1 if total > 0 else False:
        scores['residential'] += 0.2

    # Blend indicators
    if 8 < major_pct < 20 and 30 < residential_pct < 60:
        scores['downtown_residential'] += 0.5
    if total < 150 and residential_pct > 50 and intersection_density < 8:
        scores['residential_rural'] += 0.5

    # Find highest scoring category
    category = max(scores, key=scores.get)
    confidence = scores[category]

    # Normalize confidence
    total_score = sum(scores.values())
    if total_score > 0:
        confidence = scores[category] / total_score

    return {
        'category': category,
        'confidence': round(confidence, 2),
        'metrics': {
            'total_roads': total,
            'total_length_m': round(total_length, 0),
            'major_roads_pct': round(major_pct, 1),
            'residential_pct': round(residential_pct, 1),
            'intersection_density': round(intersection_density, 1),
            'grid_regularity': round(grid_score, 2),
            'scores': {k: round(v, 2) for k, v in scores.items()}
        },
        'lengths_by_type': {k: round(v, 0) for k, v in lengths.items()}
    }


def print_classification(result: Dict, verbose: bool = False) -> None:
    """Print classification results in a readable format."""
    print(f"\nCategory: {result['category'].upper()}")
    print(f"Confidence: {result['confidence'] * 100:.0f}%")

    metrics = result['metrics']
    print(f"\nMetrics:")
    print(f"  Total Roads: {metrics['total_roads']}")
    print(f"  Total Length: {metrics['total_length_m'] / 1000:.1f} km")
    print(f"  Major Roads: {metrics['major_roads_pct']:.1f}%")
    print(f"  Residential: {metrics['residential_pct']:.1f}%")
    print(f"  Intersections/km²: {metrics['intersection_density']:.1f}")
    print(f"  Grid Regularity: {metrics['grid_regularity']:.0%}")

    if verbose:
        print(f"\nCategory Scores:")
        for cat, score in metrics['scores'].items():
            print(f"  {cat}: {score:.2f}")

        print(f"\nLengths by Type (m):")
        for road_type, length in result['lengths_by_type'].items():
            if length > 0:
                print(f"  {road_type}: {length:.0f}")


def main():
    parser = argparse.ArgumentParser(
        description='Classify road network chunk category'
    )
    parser.add_argument('input', type=str,
                        help='Input GeoJSON file')
    parser.add_argument('--verbose', '-v', action='store_true',
                        help='Show detailed analysis')
    parser.add_argument('--json', action='store_true',
                        help='Output as JSON')
    parser.add_argument('--update', action='store_true',
                        help='Update the GeoJSON file with classification')

    args = parser.parse_args()

    if not os.path.exists(args.input):
        print(f"Error: File not found: {args.input}")
        sys.exit(1)

    # Load and classify
    geojson = load_geojson(args.input)
    result = classify_chunk(geojson)

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print_classification(result, args.verbose)

    # Update file if requested
    if args.update:
        geojson['metadata']['category'] = result['category']
        geojson['metadata']['classification'] = result
        with open(args.input, 'w', encoding='utf-8') as f:
            json.dump(geojson, f, indent=2)
        print(f"\nUpdated: {args.input}")


if __name__ == '__main__':
    main()
