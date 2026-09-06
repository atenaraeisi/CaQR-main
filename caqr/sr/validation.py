def assert_compiled_hardware_compliant(circuit, device):
    for index, (instruction, qargs, _) in enumerate(circuit.data):
        if len(qargs) != 2:
            continue
        left = circuit.find_bit(qargs[0]).index
        right = circuit.find_bit(qargs[1]).index
        if not device.is_adjacent(left, right):
            raise RuntimeError(
                f"Instruction {index} ({instruction.name}) uses non-adjacent "
                f"physical qubits {left}, {right}"
            )


def count_two_qubit_operations(circuit):
    return sum(1 for _, qargs, _ in circuit.data if len(qargs) == 2)
