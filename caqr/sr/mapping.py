def choose_first_logical(logical_qubits, remaining_counts):
    # REPRODUCTION DESIGN CHOICE: If two unmapped logical operands are tied by
    # remaining use count, pick the lower logical-qubit index deterministically.
    return max(
        logical_qubits,
        key=lambda logical: (remaining_counts.get(logical, 0), -logical),
    )


def select_physical_for_first_logical(state, dag, logical):
    # REPRODUCTION DESIGN CHOICE: topology-only lookahead. Prefer locations
    # close to already-mapped future interaction partners; otherwise prefer
    # higher connectivity, then lower physical index.
    candidates = list(state.physicalList)
    if not candidates:
        raise RuntimeError(f"No fresh physical qubit available for logical q{logical}")

    scored = []
    for physical in candidates:
        distances = []
        for _, partner in dag.future_two_qubit_interactions(logical):
            if partner in state.logical_to_physical:
                distances.append(
                    state.device.distance(physical, state.logical_to_physical[partner])
                )
        if distances:
            score = (0, min(distances), sum(distances), -state.device.degree(physical), physical)
        else:
            score = (1, 0, 0, -state.device.degree(physical), physical)
        scored.append((score, physical))
    return min(scored)[1]


def select_physical_near_partner(state, partner_physical):
    # REPRODUCTION DESIGN CHOICE: Phase 1 tie-breaking uses topology only:
    # minimum shortest-path distance, then higher degree, then lower index.
    candidates = list(state.physicalList)
    if not candidates:
        raise RuntimeError(
            "No fresh physical qubit available to map near physical "
            f"{partner_physical}"
        )
    return min(
        candidates,
        key=lambda physical: (
            state.device.distance(physical, partner_physical),
            -state.device.degree(physical),
            physical,
        ),
    )


def select_physical_for_single_qubit_gate(state, dag, logical):
    # REPRODUCTION DESIGN CHOICE: for a critical single-qubit frontier gate with
    # an unmapped logical qubit, use the same topology-only future-interaction
    # selector as first-operand mapping.
    return select_physical_for_first_logical(state, dag, logical)
