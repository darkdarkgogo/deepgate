import argparse
import os
import random
from typing import List


def parse_args():
    parser = argparse.ArgumentParser(description="Generate mixed-scale AIG-style .bench circuits for DeepGate.")
    parser.add_argument("--output-dir", type=str, required=True, help="Directory to write generated .bench files.")
    parser.add_argument("--seed", type=int, default=208, help="Random seed.")
    parser.add_argument("--num-small", type=int, default=120, help="Number of small/medium-large circuits.")
    parser.add_argument("--num-medium", type=int, default=80, help="Number of medium circuits.")
    parser.add_argument("--num-large", type=int, default=40, help="Number of large circuits.")
    parser.add_argument("--small-min", type=int, default=3000, help="Minimum gate count for small bucket.")
    parser.add_argument("--small-max", type=int, default=8000, help="Maximum gate count for small bucket.")
    parser.add_argument("--medium-min", type=int, default=8000, help="Minimum gate count for medium bucket.")
    parser.add_argument("--medium-max", type=int, default=20000, help="Maximum gate count for medium bucket.")
    parser.add_argument("--large-min", type=int, default=20000, help="Minimum gate count for large bucket.")
    parser.add_argument("--large-max", type=int, default=50000, help="Maximum gate count for large bucket.")
    parser.add_argument("--not-ratio", type=float, default=0.18, help="Probability of generating a NOT gate.")
    return parser.parse_args()


def weighted_pick(existing_count: int, hot_nodes: List[int]) -> int:
    if existing_count <= 1:
        return 0

    recent_window = min(existing_count, 1024)
    mode = random.random()
    if hot_nodes and mode < 0.35:
        return random.choice(hot_nodes)
    if mode < 0.80:
        return random.randrange(existing_count - recent_window, existing_count)
    return random.randrange(existing_count)


def compute_num_inputs(target_gates: int) -> int:
    estimated = max(64, min(4096, target_gates // 8))
    return estimated


def build_circuit(target_gates: int, not_ratio: float):
    num_inputs = compute_num_inputs(target_gates)
    lines = []
    fanout = []

    for idx in range(num_inputs):
        lines.append(f"INPUT(pi{idx})")
        fanout.append(0)

    hot_nodes: List[int] = []
    next_node_id = 0

    for gate_idx in range(target_gates):
        dst = num_inputs + next_node_id
        gate_name = f"g{next_node_id}"
        next_node_id += 1
        src = None
        src_a = None
        src_b = None

        if random.random() < not_ratio:
            src = weighted_pick(dst, hot_nodes)
            fanout[src] += 1
            lines.append(f"{gate_name} = NOT({node_name(src, num_inputs)})")
        else:
            src_a = weighted_pick(dst, hot_nodes)
            src_b = weighted_pick(dst, hot_nodes)
            if dst > 1:
                while src_b == src_a:
                    src_b = weighted_pick(dst, hot_nodes)
            fanout[src_a] += 1
            fanout[src_b] += 1
            lines.append(f"{gate_name} = AND({node_name(src_a, num_inputs)}, {node_name(src_b, num_inputs)})")

        fanout.append(0)
        if src_a is not None and fanout[src_a] > 1:
            hot_nodes.append(src_a)
        if src_b is not None and fanout[src_b] > 1:
            hot_nodes.append(src_b)
        if src is not None and fanout[src] > 1:
            hot_nodes.append(src)

        if len(hot_nodes) > 4096:
            hot_nodes = hot_nodes[-2048:]

    last_gate_name = f"g{next_node_id - 1}"
    lines.append(f"OUTPUT({last_gate_name})")
    return lines, num_inputs, target_gates


def node_name(node_idx: int, num_inputs: int) -> str:
    if node_idx < num_inputs:
        return f"pi{node_idx}"
    return f"g{node_idx - num_inputs}"


def write_bench(path: str, lines: List[str]):
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines))
        f.write("\n")


def bucket_specs(args):
    specs = []
    for idx in range(args.num_small):
        specs.append(("small", idx, random.randint(args.small_min, args.small_max)))
    for idx in range(args.num_medium):
        specs.append(("medium", idx, random.randint(args.medium_min, args.medium_max)))
    for idx in range(args.num_large):
        specs.append(("large", idx, random.randint(args.large_min, args.large_max)))
    random.shuffle(specs)
    return specs


def main():
    args = parse_args()
    random.seed(args.seed)
    os.makedirs(args.output_dir, exist_ok=True)

    specs = bucket_specs(args)
    summary = {"small": 0, "medium": 0, "large": 0}
    total_gates = 0

    for bucket, idx, gate_count in specs:
        lines, num_inputs, gate_total = build_circuit(gate_count, args.not_ratio)
        filename = f"mixed_{bucket}_{idx:03d}_{gate_total}g.bench"
        write_bench(os.path.join(args.output_dir, filename), lines)
        summary[bucket] += 1
        total_gates += gate_total
        print(f"Generated {filename}: inputs={num_inputs}, gates={gate_total}")

    print("Summary:")
    print(f"  small : {summary['small']}")
    print(f"  medium: {summary['medium']}")
    print(f"  large : {summary['large']}")
    print(f"  total circuits: {len(specs)}")
    print(f"  total gates   : {total_gates}")


if __name__ == "__main__":
    main()
