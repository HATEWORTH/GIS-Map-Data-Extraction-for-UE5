#!/usr/bin/env python3
"""
export_svg.py - Export road network data to SVG for visualization.
"""

import argparse
import json
import os
import sys

# Road draw order (back to front)
ROAD_ORDER = ['service', 'unclassified', 'residential', 'collector',
              'minor_arterial', 'arterial', 'highway', 'interstate']

# Stroke widths by type
STROKE_WIDTHS = {
    'interstate': 5, 'highway': 4, 'arterial': 3.5, 'minor_arterial': 3,
    'collector': 2.5, 'residential': 2, 'service': 1.5, 'unclassified': 2
}


def load_json(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)


def export_svg(data, output_path, width=1200, height=1200):
    """Export road network to SVG."""
    meta = data['metadata']
    bounds = meta['bounds_uu']

    # Calculate scale to fit canvas with padding
    padding = 50
    data_width = bounds['max'][0] - bounds['min'][0]
    data_height = bounds['max'][1] - bounds['min'][1]

    scale_x = (width - 2 * padding) / data_width
    scale_y = (height - 2 * padding) / data_height
    scale = min(scale_x, scale_y)

    # Transform function
    def transform(x, y):
        sx = padding + (x - bounds['min'][0]) * scale
        sy = height - padding - (y - bounds['min'][1]) * scale  # Flip Y
        return sx, sy

    # Group edges by type
    edges_by_type = {}
    for edge in data['edges']:
        t = edge['road_type']
        if t not in edges_by_type:
            edges_by_type[t] = []
        edges_by_type[t].append(edge)

    # Build SVG
    svg_lines = [
        f'<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        f'  <rect width="100%" height="100%" fill="#0a0a0f"/>',
        f'  <title>{meta["city"]} Road Network</title>',
        f'  <desc>Category: {meta["category"]}, Roads: {meta["total_roads"]}</desc>',
    ]

    # Draw roads in order
    for road_type in ROAD_ORDER:
        edges = edges_by_type.get(road_type, [])
        if not edges:
            continue

        svg_lines.append(f'  <g id="{road_type}" stroke-linecap="round" stroke-linejoin="round">')

        for edge in edges:
            points = edge.get('points', [])
            if len(points) < 2:
                continue

            # Build path
            path_parts = []
            for i, (x, y) in enumerate(points):
                sx, sy = transform(x, y)
                if i == 0:
                    path_parts.append(f'M{sx:.1f},{sy:.1f}')
                else:
                    path_parts.append(f'L{sx:.1f},{sy:.1f}')

            path_d = ''.join(path_parts)
            color = edge['color']
            stroke_width = STROKE_WIDTHS.get(road_type, 2)

            svg_lines.append(f'    <path d="{path_d}" stroke="{color}" stroke-width="{stroke_width}" fill="none" opacity="0.9"/>')

        svg_lines.append(f'  </g>')

    # Add legend
    svg_lines.append(f'  <g id="legend" transform="translate(20, 20)">')
    svg_lines.append(f'    <rect x="0" y="0" width="160" height="230" fill="#16213e" rx="6" opacity="0.95"/>')
    svg_lines.append(f'    <text x="12" y="24" fill="#60a5fa" font-family="Arial" font-size="14" font-weight="bold">{meta["city"]}</text>')
    svg_lines.append(f'    <text x="12" y="42" fill="#9ca3af" font-family="Arial" font-size="11">{meta["total_roads"]} roads | {meta["category"]}</text>')

    legend_items = [
        ('Interstate', '#E31C1C'),
        ('Highway', '#F48C06'),
        ('Arterial', '#FFC300'),
        ('Minor Arterial', '#FFE066'),
        ('Collector', '#74C0FC'),
        ('Residential', '#51CF66'),
        ('Service', '#868E96'),
    ]

    for i, (label, color) in enumerate(legend_items):
        y_pos = 65 + i * 22
        svg_lines.append(f'    <rect x="12" y="{y_pos}" width="20" height="8" fill="{color}" rx="2"/>')
        svg_lines.append(f'    <text x="40" y="{y_pos + 8}" fill="#9ca3af" font-family="Arial" font-size="11">{label}</text>')

    svg_lines.append(f'  </g>')

    # Add scale bar
    scale_meters = 500  # 500m bar
    scale_pixels = scale_meters * 100 * scale  # Convert UU to pixels
    svg_lines.append(f'  <g id="scale" transform="translate(20, {height - 40})">')
    svg_lines.append(f'    <rect x="0" y="0" width="{scale_pixels:.0f}" height="4" fill="#374151"/>')
    svg_lines.append(f'    <text x="0" y="-8" fill="#9ca3af" font-family="Arial" font-size="11">{scale_meters}m</text>')
    svg_lines.append(f'  </g>')

    svg_lines.append('</svg>')

    # Write file
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(svg_lines))

    print(f"Exported: {output_path}")
    print(f"  Size: {width}x{height}px")
    print(f"  Roads: {meta['total_roads']}")


def main():
    parser = argparse.ArgumentParser(description='Export road network to SVG')
    parser.add_argument('input', help='Input UE5 JSON file')
    parser.add_argument('--output', '-o', help='Output SVG file')
    parser.add_argument('--width', type=int, default=1200, help='SVG width')
    parser.add_argument('--height', type=int, default=1200, help='SVG height')

    args = parser.parse_args()

    if not os.path.exists(args.input):
        print(f"Error: File not found: {args.input}")
        sys.exit(1)

    data = load_json(args.input)

    output = args.output or args.input.replace('.json', '.svg')
    export_svg(data, output, args.width, args.height)


if __name__ == '__main__':
    main()
