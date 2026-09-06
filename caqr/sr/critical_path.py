def unit_operation_weight(node):
    # REPRODUCTION DESIGN CHOICE: Phase 1 uses unit operation weights. This
    # function isolates weights so hardware durations can replace them later.
    return 1


def downstream_lengths(dag, weight_fn=unit_operation_weight):
    lengths = {}
    for node_id in sorted(dag.remaining_ids, reverse=True):
        successors = [
            successor
            for successor in dag.successors[node_id]
            if successor in dag.remaining_ids
        ]
        if successors:
            lengths[node_id] = weight_fn(dag.nodes_by_id[node_id]) + max(
                lengths[successor] for successor in successors
            )
        else:
            lengths[node_id] = weight_fn(dag.nodes_by_id[node_id])
    return lengths


def critical_frontier_ids(dag, weight_fn=unit_operation_weight):
    # REPRODUCTION DESIGN CHOICE: On the current remaining DAG, a frontier node
    # is critical iff its unit-weight longest downstream path length equals the
    # maximum downstream path length among current frontier nodes.
    frontier = dag.frontier()
    if not frontier:
        return set()
    lengths = downstream_lengths(dag, weight_fn)
    max_length = max(lengths[node.node_id] for node in frontier)
    return {
        node.node_id
        for node in frontier
        if lengths[node.node_id] == max_length
    }
