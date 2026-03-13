#!/usr/bin/env python3
"""
preprocess_network.py - Preprocess road network for UE5 spline import.

Performs:
1. Node classification (endpoint, through, intersection)
2. Edge merging through degree-2 nodes of same road type
3. Intersection arm angle calculation
4. Duplicate edge removal
"""

import argparse
import json
import math
import os
import sys
from typing import Dict, List, Set, Tuple, Optional
from collections import defaultdict


# Node type classification
NODE_TYPE_ENDPOINT = "endpoint"       # degree == 1
NODE_TYPE_THROUGH = "through"         # degree == 2, same road type continues
NODE_TYPE_INTERSECTION = "intersection"  # degree >= 3, or type change


def load_json(filepath: str) -> Dict:
    """Load JSON file."""
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_json(data: Dict, filepath: str) -> None:
    """Save JSON file."""
    os.makedirs(os.path.dirname(filepath) or '.', exist_ok=True)
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)


def calculate_angle(p1: List[float], p2: List[float]) -> float:
    """Calculate angle from p1 to p2 in degrees (0-360)."""
    dx = p2[0] - p1[0]
    dy = p2[1] - p1[1]
    angle = math.degrees(math.atan2(dy, dx))
    if angle < 0:
        angle += 360
    return angle


def normalize_angle(angle: float) -> float:
    """Normalize angle to 0-360 range."""
    while angle < 0:
        angle += 360
    while angle >= 360:
        angle -= 360
    return angle


def build_node_edge_map(edges: List[Dict]) -> Dict[int, List[Dict]]:
    """Build mapping of node_id -> list of connected edges with direction info."""
    node_edges = defaultdict(list)

    for edge in edges:
        start_node = edge.get('start_node', -1)
        end_node = edge.get('end_node', -1)

        if start_node >= 0:
            node_edges[start_node].append({
                'edge_id': edge['id'],
                'direction': 'outgoing',
                'other_node': end_node,
                'road_type': edge.get('road_type', 'unclassified'),
                'edge': edge
            })

        if end_node >= 0:
            node_edges[end_node].append({
                'edge_id': edge['id'],
                'direction': 'incoming',
                'other_node': start_node,
                'road_type': edge.get('road_type', 'unclassified'),
                'edge': edge
            })

    return dict(node_edges)


def classify_nodes(nodes: List[Dict], node_edge_map: Dict[int, List[Dict]]) -> Dict[int, Dict]:
    """
    Classify each node by type.

    Returns dict of node_id -> {type, degree, connected_types, arms}
    """
    classified = {}

    for node in nodes:
        node_id = node['id']
        connected = node_edge_map.get(node_id, [])
        degree = len(connected)

        # Get unique road types connected to this node
        connected_types = set(c['road_type'] for c in connected)

        # Classify
        if degree == 0:
            node_type = NODE_TYPE_ENDPOINT  # Orphan node
        elif degree == 1:
            node_type = NODE_TYPE_ENDPOINT
        elif degree == 2:
            # Through node only if same road type continues
            if len(connected_types) == 1:
                node_type = NODE_TYPE_THROUGH
            else:
                node_type = NODE_TYPE_INTERSECTION
        else:
            node_type = NODE_TYPE_INTERSECTION

        # Calculate arm angles for intersections
        arms = []
        if node_type == NODE_TYPE_INTERSECTION:
            node_pos = [node['x'], node['y']]
            for conn in connected:
                edge = conn['edge']
                points = edge.get('points', [])

                if len(points) >= 2:
                    # Find the point adjacent to this node
                    if conn['direction'] == 'outgoing':
                        # Edge starts at this node, get direction to second point
                        arm_point = points[1] if len(points) > 1 else points[0]
                    else:
                        # Edge ends at this node, get direction from second-to-last
                        arm_point = points[-2] if len(points) > 1 else points[-1]

                    angle = calculate_angle(node_pos, arm_point)
                    arms.append({
                        'edge_id': edge['id'],
                        'road_type': edge.get('road_type', 'unclassified'),
                        'width': edge.get('width', 600),
                        'angle': round(angle, 1),
                        'direction': conn['direction']
                    })

        # Sort arms by angle for consistent ordering
        arms.sort(key=lambda a: a['angle'])

        classified[node_id] = {
            'id': node_id,
            'x': node['x'],
            'y': node['y'],
            'type': node_type,
            'degree': degree,
            'connected_types': list(connected_types),
            'arms': arms
        }

    return classified


def find_mergeable_chains(
    nodes: Dict[int, Dict],
    edges: List[Dict],
    node_edge_map: Dict[int, List[Dict]]
) -> List[List[int]]:
    """
    Find chains of edges that can be merged (connected through through-nodes).

    Returns list of edge ID chains, e.g. [[1, 5, 8], [2, 3], [4]]
    """
    # Track which edges have been assigned to chains
    assigned_edges: Set[int] = set()
    chains: List[List[int]] = []

    # Build edge adjacency through through-nodes
    edge_connections: Dict[int, List[int]] = defaultdict(list)

    for node_id, node_info in nodes.items():
        if node_info['type'] != NODE_TYPE_THROUGH:
            continue

        # This is a through-node - connect the two edges
        connected = node_edge_map.get(node_id, [])
        if len(connected) == 2:
            edge1_id = connected[0]['edge_id']
            edge2_id = connected[1]['edge_id']

            # Only connect if same road type
            if connected[0]['road_type'] == connected[1]['road_type']:
                edge_connections[edge1_id].append(edge2_id)
                edge_connections[edge2_id].append(edge1_id)

    # Build chains using DFS
    def build_chain(start_edge: int) -> List[int]:
        chain = []
        stack = [start_edge]
        visited = set()

        while stack:
            edge_id = stack.pop()
            if edge_id in visited:
                continue
            visited.add(edge_id)
            chain.append(edge_id)

            for connected_edge in edge_connections.get(edge_id, []):
                if connected_edge not in visited:
                    stack.append(connected_edge)

        return chain

    # Find all chains
    for edge in edges:
        edge_id = edge['id']
        if edge_id not in assigned_edges:
            chain = build_chain(edge_id)
            chains.append(chain)
            assigned_edges.update(chain)

    return chains


def merge_edge_chain(
    chain: List[int],
    edges_by_id: Dict[int, Dict],
    nodes: Dict[int, Dict]
) -> Dict:
    """
    Merge a chain of edges into a single edge.

    Combines points, preserves start/end nodes of the full chain.
    """
    if len(chain) == 1:
        # Single edge, no merging needed
        return edges_by_id[chain[0]].copy()

    # Order the chain by following connections
    ordered_chain = order_edge_chain(chain, edges_by_id, nodes)

    # Get first and last edges to determine endpoints
    first_edge = edges_by_id[ordered_chain[0]]
    last_edge = edges_by_id[ordered_chain[-1]]

    # Combine all points
    combined_points = []
    prev_end_node = None

    for i, edge_id in enumerate(ordered_chain):
        edge = edges_by_id[edge_id]
        points = edge.get('points', [])

        if i == 0:
            # First edge - include all points
            combined_points.extend(points)
            # Determine which end connects to next edge
            if len(ordered_chain) > 1:
                next_edge = edges_by_id[ordered_chain[1]]
                if edge['end_node'] in [next_edge['start_node'], next_edge['end_node']]:
                    prev_end_node = edge['end_node']
                else:
                    # Need to reverse this edge
                    combined_points = list(reversed(points))
                    prev_end_node = edge['start_node']
        else:
            # Subsequent edges - skip first point (it's the connection point)
            # Check if we need to reverse
            if edge['start_node'] == prev_end_node:
                combined_points.extend(points[1:])
                prev_end_node = edge['end_node']
            else:
                combined_points.extend(reversed(points[:-1]))
                prev_end_node = edge['start_node']

    # Determine actual start and end nodes
    # Find the intersection/endpoint nodes at the chain ends
    first_edge = edges_by_id[ordered_chain[0]]
    last_edge = edges_by_id[ordered_chain[-1]]

    # Find which nodes are intersections/endpoints (not through-nodes)
    start_candidates = [first_edge['start_node'], first_edge['end_node']]
    end_candidates = [last_edge['start_node'], last_edge['end_node']]

    start_node = -1
    end_node = -1

    for n in start_candidates:
        if n >= 0 and nodes.get(n, {}).get('type') != NODE_TYPE_THROUGH:
            start_node = n
            break

    for n in end_candidates:
        if n >= 0 and nodes.get(n, {}).get('type') != NODE_TYPE_THROUGH:
            end_node = n
            break

    # Create merged edge
    merged = {
        'id': ordered_chain[0],  # Use first edge's ID
        'start_node': start_node,
        'end_node': end_node,
        'road_type': first_edge.get('road_type', 'unclassified'),
        'color': first_edge.get('color', '#FFFFFF'),
        'width': first_edge.get('width', 600),
        'name': first_edge.get('name', ''),
        'osm_id': first_edge.get('osm_id', 0),
        'oneway': first_edge.get('oneway', False),
        'points': combined_points,
        'merged_from': ordered_chain  # Track original edges
    }

    return merged


def order_edge_chain(
    chain: List[int],
    edges_by_id: Dict[int, Dict],
    nodes: Dict[int, Dict]
) -> List[int]:
    """Order a chain of edges by following node connections."""
    if len(chain) <= 1:
        return chain

    # Build node-to-edge mapping for this chain
    node_to_edges: Dict[int, List[int]] = defaultdict(list)
    for edge_id in chain:
        edge = edges_by_id[edge_id]
        node_to_edges[edge['start_node']].append(edge_id)
        node_to_edges[edge['end_node']].append(edge_id)

    # Find chain endpoints (nodes connected to only one edge in chain)
    endpoint_nodes = [n for n, edges in node_to_edges.items() if len(edges) == 1]

    if not endpoint_nodes:
        # Circular chain - just return as-is
        return chain

    # Start from first endpoint
    ordered = []
    current_node = endpoint_nodes[0]
    visited_edges: Set[int] = set()

    while len(ordered) < len(chain):
        # Find unvisited edge connected to current node
        found = False
        for edge_id in node_to_edges.get(current_node, []):
            if edge_id not in visited_edges:
                ordered.append(edge_id)
                visited_edges.add(edge_id)

                # Move to other end of edge
                edge = edges_by_id[edge_id]
                if edge['start_node'] == current_node:
                    current_node = edge['end_node']
                else:
                    current_node = edge['start_node']
                found = True
                break

        if not found:
            break

    return ordered


def remove_duplicate_edges(edges: List[Dict]) -> List[Dict]:
    """Remove duplicate edges (same start/end nodes, same road type)."""
    seen = set()
    unique = []

    for edge in edges:
        # Create a key that's the same regardless of direction
        start = edge.get('start_node', -1)
        end = edge.get('end_node', -1)
        road_type = edge.get('road_type', '')

        key = (min(start, end), max(start, end), road_type)

        if key not in seen:
            seen.add(key)
            unique.append(edge)

    return unique


def calculate_intersection_geometry(node_info: Dict) -> Dict:
    """
    Calculate intersection geometry parameters.

    Returns info needed to generate intersection mesh.
    """
    arms = node_info.get('arms', [])

    if len(arms) < 2:
        return {'type': 'endpoint', 'radius': 0}

    # Determine intersection type
    if len(arms) == 2:
        # Check angle between arms
        angle_diff = abs(arms[1]['angle'] - arms[0]['angle'])
        if angle_diff > 180:
            angle_diff = 360 - angle_diff

        if angle_diff > 150:  # Nearly straight
            return {'type': 'straight', 'radius': 0}
        else:
            return {'type': 'curve', 'angle': angle_diff}

    elif len(arms) == 3:
        int_type = 't_junction'
    elif len(arms) == 4:
        int_type = 'crossroads'
    else:
        int_type = 'complex'

    # Calculate radius based on widest road
    max_width = max(arm.get('width', 600) for arm in arms)
    radius = max_width * 0.75  # Intersection radius

    return {
        'type': int_type,
        'radius': radius,
        'arm_count': len(arms)
    }


def preprocess_network(data: Dict) -> Dict:
    """
    Main preprocessing function.

    Takes raw UE5 JSON and returns preprocessed version with:
    - Classified nodes
    - Merged edges
    - Intersection geometry info
    """
    nodes = data.get('nodes', [])
    edges = data.get('edges', [])
    metadata = data.get('metadata', {})

    print(f"Preprocessing network: {len(nodes)} nodes, {len(edges)} edges")

    # Remove duplicate edges
    edges = remove_duplicate_edges(edges)
    print(f"After deduplication: {len(edges)} edges")

    # Build lookup structures
    edges_by_id = {e['id']: e for e in edges}
    node_edge_map = build_node_edge_map(edges)

    # Classify nodes
    classified_nodes = classify_nodes(nodes, node_edge_map)

    # Count node types
    type_counts = defaultdict(int)
    for node_info in classified_nodes.values():
        type_counts[node_info['type']] += 1

    print(f"Node classification: {dict(type_counts)}")

    # Find mergeable chains
    chains = find_mergeable_chains(classified_nodes, edges, node_edge_map)

    # Count chains that will be merged
    merge_count = sum(1 for c in chains if len(c) > 1)
    print(f"Found {merge_count} edge chains to merge")

    # Merge edges
    merged_edges = []
    for chain in chains:
        merged = merge_edge_chain(chain, edges_by_id, classified_nodes)
        merged_edges.append(merged)

    print(f"After merging: {len(merged_edges)} edges")

    # Calculate intersection geometry
    intersections = []
    for node_id, node_info in classified_nodes.items():
        if node_info['type'] == NODE_TYPE_INTERSECTION:
            geom = calculate_intersection_geometry(node_info)
            intersections.append({
                'node_id': node_id,
                'x': node_info['x'],
                'y': node_info['y'],
                'arms': node_info['arms'],
                'geometry': geom
            })

    print(f"Intersections: {len(intersections)}")

    # Build output
    output = {
        'metadata': {
            **metadata,
            'preprocessed': True,
            'original_edge_count': len(edges),
            'merged_edge_count': len(merged_edges),
            'intersection_count': len(intersections),
            'node_types': dict(type_counts)
        },
        'nodes': [
            {
                'id': n['id'],
                'x': n['x'],
                'y': n['y'],
                'type': n['type'],
                'degree': n['degree']
            }
            for n in classified_nodes.values()
        ],
        'edges': merged_edges,
        'intersections': intersections
    }

    return output


def main():
    parser = argparse.ArgumentParser(
        description='Preprocess road network for UE5 spline import'
    )
    parser.add_argument('input', help='Input UE5 JSON file')
    parser.add_argument('--output', '-o', help='Output file (default: input_preprocessed.json)')

    args = parser.parse_args()

    if not os.path.exists(args.input):
        print(f"Error: File not found: {args.input}")
        sys.exit(1)

    # Load input
    data = load_json(args.input)

    # Preprocess
    processed = preprocess_network(data)

    # Determine output path
    if args.output:
        output_path = args.output
    else:
        base = os.path.splitext(args.input)[0]
        output_path = f"{base}_preprocessed.json"

    # Save output
    save_json(processed, output_path)
    print(f"\nSaved: {output_path}")


if __name__ == '__main__':
    main()
