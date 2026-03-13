#!/usr/bin/env python3
"""
update_gallery.py - Scan output folders and rebuild gallery.html + manifest.json

Automatically categorizes cities and generates the gallery page.
Run this after any new data is exported.
"""

import json
import os
import re
from pathlib import Path
from typing import Dict, List

# Category keywords for auto-detection
CATEGORY_KEYWORDS = {
    'downtown': ['downtown', 'loop', 'midtown', 'central', 'cbd', 'financial'],
    'residential': ['residential', 'suburb', 'heights', 'park', 'slope', 'village', 'hills', 'estates'],
    'rural': ['farm', 'rural', 'plains', 'country', 'ranch', 'prairie'],
    'highway': ['highway', 'interstate', 'freeway', 'hub', 'interchange', 'junction'],
    'neighborhood': ['neighborhood', 'st', 'street', 'ave', 'avenue', 'rd', 'road', 'ct', 'court']
}

# Category display order and colors
CATEGORY_CONFIG = {
    'downtown': {'title': 'Downtown / Urban Core', 'color': '#ef4444'},
    'residential': {'title': 'Residential / Suburban', 'color': '#22c55e'},
    'rural': {'title': 'Rural / Farmland', 'color': '#f59e0b'},
    'highway': {'title': 'Highway Interchanges', 'color': '#8b5cf6'},
    'neighborhood': {'title': 'Neighborhood', 'color': '#06b6d4'},
    'mixed': {'title': 'Mixed / Other', 'color': '#6b7280'}
}


def detect_category(name: str, metadata: dict) -> str:
    """Auto-detect category from name and metadata."""
    name_lower = name.lower()

    # Name-based detection takes priority (metadata categories are often wrong)

    # Check for rural keywords first (farmland, plains, etc.)
    rural_keywords = ['farm', 'rural', 'plains', 'country', 'ranch', 'prairie', 'panhandle']
    for keyword in rural_keywords:
        if keyword in name_lower:
            return 'rural'

    # Check for highway keywords
    highway_keywords = ['highway', 'interstate', 'freeway', 'hub', 'interchange', 'junction']
    for keyword in highway_keywords:
        if keyword in name_lower:
            return 'highway'

    # Check for neighborhood keywords (street names indicate neighborhood-level)
    neighborhood_patterns = ['st ', 'st_', 'street', 'ave ', 'ave_', 'avenue', 'rd ', 'rd_',
                             'road', 'ct ', 'ct_', 'court', 'blvd', 'lane', 'way ', 'way_',
                             'dr ', 'dr_', 'drive', '20th', '19th', '18th', 'nth']
    for pattern in neighborhood_patterns:
        if pattern in name_lower:
            return 'neighborhood'

    # Check for downtown keywords
    downtown_keywords = ['downtown', 'loop', 'midtown', 'central', 'cbd', 'financial']
    for keyword in downtown_keywords:
        if keyword in name_lower:
            return 'downtown'

    # Check for residential keywords
    residential_keywords = ['suburb', 'heights', 'park', 'slope', 'village', 'hills',
                           'estates', 'katy', 'residential']
    for keyword in residential_keywords:
        if keyword in name_lower:
            return 'residential'

    # Fallback: analyze road distribution from stats
    stats = metadata.get('road_stats', {}).get('by_type', {})
    total = sum(stats.values()) if stats else 0

    if total > 0:
        residential_pct = stats.get('residential', 0) / total
        arterial_pct = (stats.get('arterial', 0) + stats.get('minor_arterial', 0)) / total
        highway_pct = (stats.get('interstate', 0) + stats.get('highway', 0)) / total
        service_pct = stats.get('service', 0) / total

        # Rural areas have very few roads and mostly unclassified/service
        if total < 500 and service_pct > 0.3:
            return 'rural'
        if highway_pct > 0.15:
            return 'highway'
        elif arterial_pct > 0.25:
            return 'downtown'
        elif residential_pct > 0.5:
            return 'residential'

    return 'mixed'


def scan_output_folder(output_dir: Path) -> List[Dict]:
    """Scan output folder for all city data."""
    cities = []
    ue5_ready = output_dir / 'ue5_ready'

    if not ue5_ready.exists():
        return cities

    # Find all JSON files (prefer preprocessed)
    json_files = {}
    for f in ue5_ready.glob('*.json'):
        name = f.stem
        # Skip preprocessed suffix for grouping
        base_name = name.replace('_ue5_preprocessed', '_ue5').replace('_ue5', '')

        if base_name not in json_files:
            json_files[base_name] = {'json': None, 'preprocessed': None, 'svg': None}

        if '_preprocessed' in name:
            json_files[base_name]['preprocessed'] = f
        else:
            json_files[base_name]['json'] = f

    # Find matching SVGs
    for f in ue5_ready.glob('*.svg'):
        name = f.stem
        # Match to base name
        for base_name in json_files:
            if base_name in name and 'preprocessed' not in name:
                json_files[base_name]['svg'] = f
                break

    # Also check category folders for SVGs
    for category_dir in output_dir.glob('*/'):
        if category_dir.is_dir() and category_dir.name != 'ue5_ready':
            for svg in category_dir.glob('*.svg'):
                base_name = svg.stem.replace('_ue5', '')
                if base_name in json_files and not json_files[base_name]['svg']:
                    json_files[base_name]['svg'] = svg

    # Build city entries
    for base_name, files in json_files.items():
        json_file = files['preprocessed'] or files['json']
        if not json_file:
            continue

        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            metadata = data.get('metadata', {})

            # Clean up display name
            display_name = base_name.replace('_', ' ').replace('  ', ' ')
            display_name = re.sub(r'\b(ue5|preprocessed)\b', '', display_name, flags=re.IGNORECASE).strip()

            # Get or detect category
            category = detect_category(display_name, metadata)

            # Find SVG path (relative to output dir)
            svg_path = None
            if files['svg']:
                svg_path = str(files['svg'].relative_to(output_dir))
            else:
                # Check for clean svg
                clean_svg = ue5_ready / f"{base_name}_clean.svg"
                if clean_svg.exists():
                    svg_path = str(clean_svg.relative_to(output_dir))

            city_entry = {
                'id': base_name,
                'name': display_name,
                'category': category,
                'json_file': str(json_file.relative_to(output_dir)),
                'svg_file': svg_path,
                'preprocessed': files['preprocessed'] is not None,
                'metadata': {
                    'city': metadata.get('city', display_name),
                    'size_km': metadata.get('size_km', 8),
                    'road_count': metadata.get('road_stats', {}).get('total_roads', 0),
                    'edge_count': metadata.get('merged_edge_count', len(data.get('edges', []))),
                    'intersection_count': metadata.get('intersection_count', 0)
                }
            }

            cities.append(city_entry)

        except Exception as e:
            print(f"Warning: Could not process {json_file}: {e}")

    return cities


def generate_manifest(cities: List[Dict], output_dir: Path) -> None:
    """Generate manifest.json."""
    manifest = {
        'generated': True,
        'cities': cities,
        'categories': CATEGORY_CONFIG
    }

    manifest_path = output_dir / 'manifest.json'
    with open(manifest_path, 'w', encoding='utf-8') as f:
        json.dump(manifest, f, indent=2)

    print(f"Generated: {manifest_path}")


def generate_gallery_html(cities: List[Dict], output_dir: Path) -> None:
    """Generate gallery.html from city data."""

    # Group by category
    by_category = {}
    for city in cities:
        cat = city['category']
        if cat not in by_category:
            by_category[cat] = []
        by_category[cat].append(city)

    # Sort cities within each category
    for cat in by_category:
        by_category[cat].sort(key=lambda x: x['name'])

    # Build HTML
    html = '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Road Network Gallery - GIS Map Data</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            background: #0a0a0f;
            color: #e8e8e8;
            padding: 20px;
            min-height: 100vh;
        }
        header {
            text-align: center;
            margin-bottom: 30px;
            padding-bottom: 20px;
            border-bottom: 1px solid #374151;
        }
        h1 { color: #60a5fa; margin-bottom: 8px; }
        .subtitle { color: #9ca3af; }
        .stats { margin-top: 10px; color: #6b7280; font-size: 0.9rem; }

        .category {
            margin-bottom: 40px;
        }
        .category h2 {
            font-size: 1.3rem;
            margin-bottom: 15px;
            padding-left: 12px;
            border-left: 4px solid;
        }

        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
            gap: 20px;
        }

        .card {
            background: #16213e;
            border-radius: 8px;
            overflow: hidden;
            transition: transform 0.2s, box-shadow 0.2s;
        }
        .card:hover {
            transform: translateY(-4px);
            box-shadow: 0 8px 25px rgba(0,0,0,0.4);
        }

        .card-image {
            width: 100%;
            height: 200px;
            background: #0f172a;
            display: flex;
            align-items: center;
            justify-content: center;
            overflow: hidden;
        }
        .card-image img {
            width: 100%;
            height: 100%;
            object-fit: cover;
        }
        .card-image.no-image {
            color: #4b5563;
            font-size: 0.9rem;
        }

        .card-content {
            padding: 15px;
        }
        .card-title {
            font-size: 1.1rem;
            color: #f3f4f6;
            margin-bottom: 8px;
        }
        .card-meta {
            font-size: 0.85rem;
            color: #9ca3af;
            display: flex;
            flex-wrap: wrap;
            gap: 10px;
        }
        .card-meta span {
            background: #1e293b;
            padding: 2px 8px;
            border-radius: 4px;
        }
        .preprocessed {
            background: #065f46 !important;
            color: #6ee7b7;
        }

        .card-links {
            margin-top: 12px;
            display: flex;
            gap: 8px;
        }
        .card-links a {
            font-size: 0.8rem;
            color: #60a5fa;
            text-decoration: none;
            padding: 4px 10px;
            border: 1px solid #3b82f6;
            border-radius: 4px;
            transition: background 0.2s;
        }
        .card-links a:hover {
            background: #3b82f6;
            color: white;
        }
    </style>
</head>
<body>
    <header>
        <h1>Road Network Gallery</h1>
        <p class="subtitle">Extracted OpenStreetMap data ready for UE5 import</p>
        <p class="stats">STATS_PLACEHOLDER</p>
    </header>
'''

    total_cities = len(cities)
    preprocessed_count = sum(1 for c in cities if c['preprocessed'])

    stats_text = f"{total_cities} cities | {preprocessed_count} preprocessed with intersection data"
    html = html.replace('STATS_PLACEHOLDER', stats_text)

    # Add categories in order
    category_order = ['downtown', 'residential', 'neighborhood', 'highway', 'rural', 'mixed']

    for cat_id in category_order:
        if cat_id not in by_category:
            continue

        cat_config = CATEGORY_CONFIG.get(cat_id, {'title': cat_id.title(), 'color': '#6b7280'})
        cities_in_cat = by_category[cat_id]

        html += f'''
    <div class="category">
        <h2 style="border-color: {cat_config['color']}">{cat_config['title']} ({len(cities_in_cat)})</h2>
        <div class="grid">
'''

        for city in cities_in_cat:
            meta = city['metadata']

            # Image section
            if city['svg_file']:
                img_html = f'<img src="{city["svg_file"]}" alt="{city["name"]}">'
            else:
                img_html = '<span>No preview</span>'

            card_image_class = 'card-image' if city['svg_file'] else 'card-image no-image'

            # Preprocessed badge
            preprocessed_badge = '<span class="preprocessed">preprocessed</span>' if city['preprocessed'] else ''

            # Stats
            stats_html = f'<span>{meta["edge_count"]} edges</span>'
            if meta['intersection_count'] > 0:
                stats_html += f'<span>{meta["intersection_count"]} intersections</span>'
            stats_html += f'<span>{meta["size_km"]}km</span>'

            html += f'''
            <div class="card">
                <div class="{card_image_class}">
                    {img_html}
                </div>
                <div class="card-content">
                    <div class="card-title">{city['name']}</div>
                    <div class="card-meta">
                        {stats_html}
                        {preprocessed_badge}
                    </div>
                    <div class="card-links">
                        <a href="{city['json_file']}" download>Download JSON</a>
                        {f'<a href="{city["svg_file"]}" target="_blank">View SVG</a>' if city['svg_file'] else ''}
                    </div>
                </div>
            </div>
'''

        html += '''
        </div>
    </div>
'''

    html += '''
</body>
</html>
'''

    gallery_path = output_dir / 'gallery.html'
    with open(gallery_path, 'w', encoding='utf-8') as f:
        f.write(html)

    print(f"Generated: {gallery_path}")


def main():
    import argparse

    parser = argparse.ArgumentParser(description='Update gallery from output folder')
    parser.add_argument('--output-dir', '-o', default=None,
                        help='Output directory (default: auto-detect)')

    args = parser.parse_args()

    # Find output directory
    if args.output_dir:
        output_dir = Path(args.output_dir)
    else:
        # Auto-detect relative to script location
        script_dir = Path(__file__).parent
        output_dir = script_dir.parent.parent / 'output'

    if not output_dir.exists():
        print(f"Error: Output directory not found: {output_dir}")
        return

    print(f"Scanning: {output_dir}")

    # Scan for cities
    cities = scan_output_folder(output_dir)
    print(f"Found {len(cities)} cities")

    if not cities:
        print("No cities found. Make sure JSON files are in output/ue5_ready/")
        return

    # Generate outputs
    generate_manifest(cities, output_dir)
    generate_gallery_html(cities, output_dir)

    # Summary
    by_cat = {}
    for c in cities:
        cat = c['category']
        by_cat[cat] = by_cat.get(cat, 0) + 1

    print("\nCategories:")
    for cat, count in sorted(by_cat.items()):
        print(f"  {cat}: {count}")


if __name__ == '__main__':
    main()
