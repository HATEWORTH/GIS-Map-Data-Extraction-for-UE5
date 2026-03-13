#!/usr/bin/env python3
"""
export_svg_preprocessed.py - Export preprocessed road network to SVG with intersection visualization.

Shows:
- Roads color-coded by type
- Intersections as circles with arm indicators
- Node types (endpoint, through, intersection)
- Edge trimming visualization
"""

import argparse
import json
import math
import os
import sys
from typing import Dict, List, Tuple

# Road draw order (back to front)
ROAD_ORDER = ['service', 'unclassified', 'residential', 'collector',
              'minor_arterial', 'arterial', 'highway', 'interstate']

# Stroke widths by type
STROKE_WIDTHS = {
    'interstate': 6, 'highway': 5, 'arterial': 4, 'minor_arterial': 3.5,
    'collector': 3, 'residential': 2.5, 'service': 1.5, 'unclassified': 2
}

# Colors by type
ROAD_COLORS = {
    'interstate': '#E31C1C',
    'highway': '#F48C06',
    'arterial': '#FFC300',
    'minor_arterial': '#FFE066',
    'collector': '#74C0FC',
    'residential': '#51CF66',
    'service': '#868E96',
    'unclassified': '#FFFFFF'
}

# Node type colors
NODE_COLORS = {
    'intersection': '#FF6B6B',
    'endpoint': '#4ECDC4',
    'through': '#95A5A6'
}


def load_json(filepath: str) -> Dict:
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)


def export_svg(data: Dict, output_path: str, width: int = 1400, height: int = 1400,
               show_intersections: bool = True, show_arms: bool = True,
               show_all_nodes: bool = False, trim_preview: bool = True) -> None:
    """
    Export preprocessed road network to SVG.

    Args:
        data: Preprocessed JSON data
        output_path: Output SVG file path
        width: SVG width in pixels
        height: SVG height in pixels
        show_intersections: Whether to show intersection circles
        show_arms: Whether to show intersection arm directions
        show_all_nodes: Whether to show all nodes (not just intersections)
        trim_preview: Whether to show trim boundaries around intersections
    """
    meta = data.get('metadata', {})
    bounds = meta.get('bounds_uu', {'min': [-400000, -400000], 'max': [400000, 400000]})

    # Calculate scale to fit canvas with padding
    padding = 60
    data_width = bounds['max'][0] - bounds['min'][0]
    data_height = bounds['max'][1] - bounds['min'][1]

    scale_x = (width - 2 * padding) / data_width
    scale_y = (height - 2 * padding) / data_height
    scale = min(scale_x, scale_y)

    # Transform function
    def transform(x: float, y: float) -> Tuple[float, float]:
        sx = padding + (x - bounds['min'][0]) * scale
        sy = height - padding - (y - bounds['min'][1]) * scale  # Flip Y
        return sx, sy

    # Build node lookup for intersection data
    intersections_by_id = {}
    for intersection in data.get('intersections', []):
        intersections_by_id[intersection['node_id']] = intersection

    # Build node lookup
    nodes_by_id = {}
    for node in data.get('nodes', []):
        nodes_by_id[node['id']] = node

    # Group edges by type
    edges = data.get('edges', [])
    edges_by_type = {}
    for edge in edges:
        t = edge.get('road_type', 'unclassified')
        if t not in edges_by_type:
            edges_by_type[t] = []
        edges_by_type[t].append(edge)

    # Start SVG
    svg_lines = [
        f'<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        f'  <defs>',
        f'    <filter id="glow" x="-50%" y="-50%" width="200%" height="200%">',
        f'      <feGaussianBlur stdDeviation="2" result="coloredBlur"/>',
        f'      <feMerge><feMergeNode in="coloredBlur"/><feMergeNode in="SourceGraphic"/></feMerge>',
        f'    </filter>',
        f'  </defs>',
        f'  <rect width="100%" height="100%" fill="#0a0a0f"/>',
        f'  <title>{meta.get("city", "Road Network")} - Preprocessed</title>',
    ]

    # Draw roads in order
    for road_type in ROAD_ORDER:
        edge_list = edges_by_type.get(road_type, [])
        if not edge_list:
            continue

        color = ROAD_COLORS.get(road_type, '#FFFFFF')
        stroke_width = STROKE_WIDTHS.get(road_type, 2)

        svg_lines.append(f'  <g id="roads_{road_type}" stroke="{color}" stroke-linecap="round" stroke-linejoin="round" fill="none" opacity="0.85">')

        for edge in edge_list:
            points = edge.get('points', [])
            if len(points) < 2:
                continue

            # Build path
            path_parts = []
            for i, pt in enumerate(points):
                x, y = pt[0], pt[1]
                sx, sy = transform(x, y)
                if i == 0:
                    path_parts.append(f'M{sx:.1f},{sy:.1f}')
                else:
                    path_parts.append(f'L{sx:.1f},{sy:.1f}')

            path_d = ''.join(path_parts)
            svg_lines.append(f'    <path d="{path_d}" stroke-width="{stroke_width}"/>')

        svg_lines.append(f'  </g>')

    # Draw intersection trim boundaries (optional)
    if trim_preview and show_intersections:
        svg_lines.append(f'  <g id="trim_boundaries" fill="none" stroke="#FF6B6B" stroke-width="1" stroke-dasharray="4,4" opacity="0.3">')
        for intersection in data.get('intersections', []):
            x, y = intersection['x'], intersection['y']
            sx, sy = transform(x, y)
            geom = intersection.get('geometry', {})
            radius = geom.get('radius', 400) * scale
            if radius > 2:
                svg_lines.append(f'    <circle cx="{sx:.1f}" cy="{sy:.1f}" r="{radius:.1f}"/>')
        svg_lines.append(f'  </g>')

    # Draw all nodes (optional)
    if show_all_nodes:
        svg_lines.append(f'  <g id="all_nodes">')
        for node in data.get('nodes', []):
            x, y = node['x'], node['y']
            sx, sy = transform(x, y)
            node_type = node.get('type', 'through')
            color = NODE_COLORS.get(node_type, '#FFFFFF')

            if node_type == 'endpoint':
                size = 3
            elif node_type == 'through':
                size = 2
            else:
                size = 5

            svg_lines.append(f'    <circle cx="{sx:.1f}" cy="{sy:.1f}" r="{size}" fill="{color}" opacity="0.6"/>')
        svg_lines.append(f'  </g>')

    # Draw intersections
    if show_intersections:
        svg_lines.append(f'  <g id="intersections">')

        for intersection in data.get('intersections', []):
            x, y = intersection['x'], intersection['y']
            sx, sy = transform(x, y)
            arms = intersection.get('arms', [])
            geom = intersection.get('geometry', {})
            int_type = geom.get('type', 'crossroads')

            # Intersection center
            if int_type == 't_junction':
                size = 6
                color = '#FF6B6B'
            elif int_type == 'crossroads':
                size = 8
                color = '#FFD93D'
            else:
                size = 5
                color = '#6BCB77'

            svg_lines.append(f'    <circle cx="{sx:.1f}" cy="{sy:.1f}" r="{size}" fill="{color}" filter="url(#glow)"/>')

            # Draw arm directions
            if show_arms and arms:
                arm_length = 25
                for arm in arms:
                    angle_rad = math.radians(arm.get('angle', 0))
                    # Note: SVG Y is flipped, so we negate the sin
                    dx = math.cos(angle_rad) * arm_length
                    dy = -math.sin(angle_rad) * arm_length  # Flip for SVG coords

                    ex = sx + dx
                    ey = sy + dy

                    arm_color = ROAD_COLORS.get(arm.get('road_type', 'residential'), '#FFFFFF')
                    arm_width = max(1, arm.get('width', 600) / 400)

                    svg_lines.append(f'    <line x1="{sx:.1f}" y1="{sy:.1f}" x2="{ex:.1f}" y2="{ey:.1f}" stroke="{arm_color}" stroke-width="{arm_width:.1f}" stroke-linecap="round" opacity="0.8"/>')

        svg_lines.append(f'  </g>')

    # Draw legend
    svg_lines.append(f'  <g id="legend" transform="translate(20, 20)">')
    svg_lines.append(f'    <rect x="0" y="0" width="200" height="320" fill="#16213e" rx="6" opacity="0.95"/>')
    svg_lines.append(f'    <text x="12" y="24" fill="#60a5fa" font-family="Arial" font-size="14" font-weight="bold">{meta.get("city", "Road Network")}</text>')
    svg_lines.append(f'    <text x="12" y="42" fill="#9ca3af" font-family="Arial" font-size="10">Preprocessed | {meta.get("merged_edge_count", 0)} edges</text>')

    # Road type legend
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
        y_pos = 60 + i * 20
        svg_lines.append(f'    <rect x="12" y="{y_pos}" width="20" height="8" fill="{color}" rx="2"/>')
        svg_lines.append(f'    <text x="40" y="{y_pos + 8}" fill="#9ca3af" font-family="Arial" font-size="10">{label}</text>')

    # Node type legend
    svg_lines.append(f'    <text x="12" y="220" fill="#60a5fa" font-family="Arial" font-size="11" font-weight="bold">Node Types</text>')

    node_legend = [
        ('Intersection', '#FF6B6B', 6),
        ('Endpoint', '#4ECDC4', 4),
        ('Through', '#95A5A6', 3),
    ]

    for i, (label, color, size) in enumerate(node_legend):
        y_pos = 238 + i * 22
        svg_lines.append(f'    <circle cx="22" cy="{y_pos}" r="{size}" fill="{color}"/>')
        svg_lines.append(f'    <text x="40" y="{y_pos + 4}" fill="#9ca3af" font-family="Arial" font-size="10">{label}</text>')

    # Stats
    svg_lines.append(f'    <text x="12" y="305" fill="#6b7280" font-family="Arial" font-size="9">Intersections: {meta.get("intersection_count", 0)}</text>')

    svg_lines.append(f'  </g>')

    # Scale bar
    scale_meters = 500
    scale_pixels = scale_meters * 100 * scale
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
    print(f"  Edges: {meta.get('merged_edge_count', len(edges))}")
    print(f"  Intersections: {meta.get('intersection_count', 0)}")


def main():
    parser = argparse.ArgumentParser(description='Export preprocessed road network to SVG')
    parser.add_argument('input', help='Input preprocessed JSON file')
    parser.add_argument('--output', '-o', help='Output SVG file')
    parser.add_argument('--width', type=int, default=1400, help='SVG width')
    parser.add_argument('--height', type=int, default=1400, help='SVG height')
    parser.add_argument('--no-intersections', action='store_true', help='Hide intersection markers')
    parser.add_argument('--no-arms', action='store_true', help='Hide intersection arm directions')
    parser.add_argument('--show-all-nodes', action='store_true', help='Show all nodes, not just intersections')
    parser.add_argument('--no-trim', action='store_true', help='Hide trim boundary circles')

    args = parser.parse_args()

    if not os.path.exists(args.input):
        print(f"Error: File not found: {args.input}")
        sys.exit(1)

    data = load_json(args.input)

    # Check if preprocessed
    meta = data.get('metadata', {})
    if not meta.get('preprocessed'):
        print("Warning: This doesn't appear to be preprocessed data. Results may vary.")

    output = args.output or args.input.replace('.json', '_visual.svg')

    export_svg(
        data, output,
        width=args.width,
        height=args.height,
        show_intersections=not args.no_intersections,
        show_arms=not args.no_arms,
        show_all_nodes=args.show_all_nodes,
        trim_preview=not args.no_trim
    )


if __name__ == '__main__':
    main()
