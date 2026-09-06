def select_swap(path):
    # REPRODUCTION DESIGN CHOICE: Phase 1 routes by moving the first logical
    # operand one step along the shortest path toward the second operand.
    return path[0], path[1]


def route_until_adjacent(state, logical_left, logical_right, node_id=None):
    while True:
        physical_left = state.logical_to_physical[logical_left]
        physical_right = state.logical_to_physical[logical_right]
        if state.device.is_adjacent(physical_left, physical_right):
            return

        path = state.device.shortest_path(physical_left, physical_right)
        if len(path) <= 2:
            return
        swap_left, swap_right = select_swap(path)
        state.apply_swap(
            swap_left,
            swap_right,
            reason=f"route q{logical_left} toward q{logical_right}",
            node_id=node_id,
        )
