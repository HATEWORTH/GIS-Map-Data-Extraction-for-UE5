#!/usr/bin/env python3
"""
batch_process.py - Batch extract and process multiple city chunks.

Reads cities.json configuration and extracts road data for all defined locations,
organizing output by category.
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime
from typing import Dict, List, Optional

try:
    from tqdm import tqdm
    HAS_TQDM = True
except ImportError:
    HAS_TQDM = False

from extract_osm import extract_chunk, save_geojson
from convert_to_ue5 import convert_geojson_to_ue5
from update_gallery import scan_output_folder, generate_manifest, generate_gallery_html


def load_cities_config(config_path: str) -> Dict:
    """Load cities configuration file."""
    with open(config_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def process_location(location: Dict, output_base: str, convert: bool = True,
                     delay: float = 5.0) -> Optional[Dict]:
    """
    Process a single location from the config.

    Args:
        location: Location dict with name, lat, lon, etc.
        output_base: Base output directory
        convert: Whether to also convert to UE5 format
        delay: Delay in seconds between API calls

    Returns:
        Result dict with status and paths, or None on failure
    """
    name = location.get('name', 'unknown')
    lat = location.get('lat')
    lon = location.get('lon')
    size_km = location.get('size_km', 8)
    expected_category = location.get('category', 'unknown')

    if lat is None or lon is None:
        print(f"  Skipping {name}: missing coordinates")
        return None

    print(f"\nProcessing: {name}")
    print(f"  Coordinates: ({lat}, {lon})")
    print(f"  Expected category: {expected_category}")

    # Extract from OSM
    geojson = extract_chunk(lat, lon, size_km, name)

    if geojson is None:
        return {
            'name': name,
            'status': 'failed',
            'error': 'OSM extraction failed'
        }

    # Get actual category
    actual_category = geojson['metadata'].get('category', 'unknown')
    print(f"  Detected category: {actual_category}")

    # Save GeoJSON
    safe_name = name.replace(' ', '_').replace(',', '').replace('/', '_')
    geojson_dir = os.path.join(output_base, 'chunks', actual_category)
    geojson_path = os.path.join(geojson_dir, f"{safe_name}.geojson")

    os.makedirs(geojson_dir, exist_ok=True)
    save_geojson(geojson, geojson_path)

    result = {
        'name': name,
        'status': 'success',
        'lat': lat,
        'lon': lon,
        'expected_category': expected_category,
        'actual_category': actual_category,
        'geojson_path': geojson_path,
        'total_roads': geojson['metadata'].get('total_roads', 0),
        'road_stats': geojson['metadata'].get('road_stats', {})
    }

    # Convert to UE5 format if requested
    if convert:
        ue5_data = convert_geojson_to_ue5(geojson)
        ue5_dir = os.path.join(output_base, 'ue5_ready')
        ue5_path = os.path.join(ue5_dir, f"{safe_name}_ue5.json")

        os.makedirs(ue5_dir, exist_ok=True)
        with open(ue5_path, 'w', encoding='utf-8') as f:
            json.dump(ue5_data, f, indent=2)

        result['ue5_path'] = ue5_path
        print(f"  Converted to UE5: {ue5_path}")

    # Rate limiting delay
    time.sleep(delay)

    return result


def generate_report(results: List[Dict], output_path: str) -> None:
    """Generate a summary report of batch processing."""
    report = {
        'generated_at': datetime.utcnow().isoformat() + 'Z',
        'total_locations': len(results),
        'successful': sum(1 for r in results if r and r.get('status') == 'success'),
        'failed': sum(1 for r in results if r is None or r.get('status') == 'failed'),
        'by_category': {},
        'locations': results
    }

    # Count by category
    for result in results:
        if result and result.get('status') == 'success':
            cat = result.get('actual_category', 'unknown')
            report['by_category'][cat] = report['by_category'].get(cat, 0) + 1

    # Save report
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2)

    print(f"\nReport saved to: {output_path}")


def print_summary(results: List[Dict]) -> None:
    """Print a summary of processing results."""
    successful = [r for r in results if r and r.get('status') == 'success']
    failed = [r for r in results if r is None or r.get('status') == 'failed']

    print("\n" + "="*60)
    print("BATCH PROCESSING SUMMARY")
    print("="*60)
    print(f"Total locations: {len(results)}")
    print(f"Successful: {len(successful)}")
    print(f"Failed: {len(failed)}")

    if successful:
        print("\nBy Category:")
        categories = {}
        for r in successful:
            cat = r.get('actual_category', 'unknown')
            categories[cat] = categories.get(cat, 0) + 1
        for cat, count in sorted(categories.items()):
            print(f"  {cat}: {count}")

        print("\nTotal Roads Extracted:")
        total_roads = sum(r.get('total_roads', 0) for r in successful)
        print(f"  {total_roads} roads")

    if failed:
        print("\nFailed Locations:")
        for r in failed:
            if r:
                print(f"  - {r.get('name', 'unknown')}: {r.get('error', 'unknown error')}")


def main():
    parser = argparse.ArgumentParser(
        description='Batch extract road data for multiple cities'
    )
    parser.add_argument('--config', '-c', type=str,
                        default='../../data/cities.json',
                        help='Path to cities.json config file')
    parser.add_argument('--output', '-o', type=str,
                        default='../../data',
                        help='Base output directory')
    parser.add_argument('--no-convert', action='store_true',
                        help='Skip UE5 conversion')
    parser.add_argument('--delay', type=float, default=5.0,
                        help='Delay between API calls in seconds (default: 5)')
    parser.add_argument('--limit', type=int, default=None,
                        help='Limit number of locations to process')
    parser.add_argument('--category', type=str, default=None,
                        help='Only process locations of this category')
    parser.add_argument('--dry-run', action='store_true',
                        help='Show what would be processed without executing')

    args = parser.parse_args()

    # Load config
    if not os.path.exists(args.config):
        print(f"Error: Config file not found: {args.config}")
        sys.exit(1)

    config = load_cities_config(args.config)
    locations = config.get('locations', [])

    print(f"Loaded {len(locations)} locations from config")

    # Filter by category if specified
    if args.category:
        locations = [loc for loc in locations if loc.get('category') == args.category]
        print(f"Filtered to {len(locations)} locations with category '{args.category}'")

    # Apply limit
    if args.limit:
        locations = locations[:args.limit]
        print(f"Limited to first {len(locations)} locations")

    if not locations:
        print("No locations to process.")
        sys.exit(0)

    # Dry run mode
    if args.dry_run:
        print("\nDRY RUN - Would process:")
        for loc in locations:
            print(f"  - {loc.get('name')}: ({loc.get('lat')}, {loc.get('lon')}) [{loc.get('category')}]")
        sys.exit(0)

    # Process locations
    results = []

    if HAS_TQDM:
        iterator = tqdm(locations, desc="Processing")
    else:
        iterator = locations

    for location in iterator:
        result = process_location(
            location,
            args.output,
            convert=not args.no_convert,
            delay=args.delay
        )
        results.append(result)

    # Generate report
    report_path = os.path.join(args.output, 'batch_report.json')
    generate_report(results, report_path)

    # Print summary
    print_summary(results)

    # Update gallery
    print("\nUpdating gallery...")
    from pathlib import Path
    output_dir = Path(args.output).parent / 'output'
    if output_dir.exists():
        cities = scan_output_folder(output_dir)
        if cities:
            generate_manifest(cities, output_dir)
            generate_gallery_html(cities, output_dir)


if __name__ == '__main__':
    main()
