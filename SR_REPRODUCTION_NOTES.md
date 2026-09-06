# SR-CaQR Phase 1 Reproduction Notes

This implementation covers SR-CaQR for regular applications only.
It does not implement the QAOA / commuting-gate branch and does not
use calibration, error-rate, or gate-duration scoring yet.

## PAPER-SPECIFIED BEHAVIOR

- Build a logical circuit DAG for regular applications.
- Process gates from the current frontier.
- Delay frontier gates with unmapped logical qubits when they are not on the critical path.
- Map a critical two-qubit gate's first unmapped operand by choosing the logical qubit with more remaining gates.
- Map an unmapped partner near its already mapped logical partner.
- Use hardware coupling constraints.
- Insert SWAP gates when mapped operands are not adjacent.
- Reclaim a physical qubit after its logical qubit has completed all operations.
- Reuse reclaimed physical qubits for logical qubits that have not started yet.
- Preserve measurement/reset boundaries for reuse.

## REPRODUCTION DESIGN CHOICES

- REPRODUCTION DESIGN CHOICE: Phase 1 supports regular circuits with 1-qubit unitary gates, 2-qubit unitary gates, and at most one final measurement per logical qubit. Mid-circuit measurement, reset, classical conditions, control flow, and wider gates are rejected.
- REPRODUCTION DESIGN CHOICE: Critical-path detection uses unit operation weights on the current remaining DAG. A frontier node is critical iff its longest downstream path length equals the maximum among the current frontier.
- REPRODUCTION DESIGN CHOICE: Eager reclamation is used. When a logical qubit finishes while unscheduled DAG nodes remain, any required original measurement is emitted, the physical qubit is reset, and only then the physical qubit returns to physicalList.
- REPRODUCTION DESIGN CHOICE: If the entire DAG has completed, required final measurements are emitted without an unnecessary reset.
- REPRODUCTION DESIGN CHOICE: A critical single-qubit frontier gate maps by looking ahead to future two-qubit interactions, preferring locations close to already mapped future partners; otherwise it prefers higher physical degree and then lower physical index.
- REPRODUCTION DESIGN CHOICE: If two unmapped logical operands have equal remaining use count, the lower logical-qubit index is mapped first.
- REPRODUCTION DESIGN CHOICE: Physical-qubit selection uses topology only: shortest-path distance, then higher degree, then lower physical index. Readout and CNOT error tie-breaks are intentionally left for later phases.
- REPRODUCTION DESIGN CHOICE: Phase 1 uses an undirected view of the coupling graph for routing and hardware-compliance checks, while preserving directed edges in DeviceInfo for future direction/error modeling.
- REPRODUCTION DESIGN CHOICE: Routing uses shortest-path SWAPs and moves the first logical operand toward the second until the two operands are adjacent. It does not perform a final SWAP between adjacent operands.
- REPRODUCTION DESIGN CHOICE: A free physical qubit is always clean because it enters physicalList only after reset or from the initial fresh pool. A SWAP between an occupied endpoint and a free endpoint moves the free slot to the previous occupied location.
- REPRODUCTION DESIGN CHOICE: The local Qiskit comparison is named qiskit_sabre_baseline. It uses optimization_level=3, routing_method="sabre", and a fixed seed, but is not claimed as an exact paper-baseline reproduction.
- REPRODUCTION DESIGN CHOICE: The Fig. 12-style test fixture uses the visible dependency pattern from the paper text: g1=(q1,q2), g2=(q0,q4), g3=(q3,q4), g4=(q1,q4) on a line topology. The paper figure extraction does not fully specify all hidden drawing details, so this is treated as a documented behavioral fixture rather than a numerical reproduction.

## METRIC DEFINITIONS

- Pre-basis metrics are measured on routed circuits that may still contain logical SWAP instructions. They report SWAP count, circuit depth, and routed two-qubit operation count without treating one SWAP as one basis hardware two-qubit gate.
- Post-basis metrics are measured after translating routed circuits to `u1`, `u2`, `u3`, `cx`, `measure`, and `reset` with optimization disabled. They report basis two-qubit gate count and translated depth.
- The Qiskit comparison is `qiskit_sabre_baseline`, using the same device coupling map, Qiskit 0.45.3, `routing_method="sabre"`, `optimization_level=3`, and seed 0.
- SR and Qiskit both report available physical qubits, distinct used physical qubits, original logical width, pre-basis metrics, and post-basis metrics.
