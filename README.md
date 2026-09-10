# CaQR-main

[![Python Version](https://img.shields.io/badge/python-3.8%2B-blue.svg)](https://www.python.org/)
[![Qiskit](https://img.shields.io/badge/Qiskit-Supported-purple.svg)](https://qiskit.org/)
[![Tests](https://img.shields.io/badge/Tests-29%20Passed-brightgreen.svg)]()

A research-oriented implementation and extension of **CaQR: A Compiler-Assisted Approach for Qubit Reuse through Dynamic Circuit**.

This repository is based on the original implementation available at [ruadapt/CaQR](https://github.com/ruadapt/CaQR). It extends that codebase with an independent **SR-CaQR** mode, a physical-qubit-count parameter, regression tests for the original QS-CaQR behavior, and correctness tests for the new SR-CaQR implementation.

---

## Overview

CaQR is a compiler-assisted approach for qubit reuse through dynamic circuits. It uses mid-circuit measurement and reset to reuse physical qubits during circuit execution. The original paper introduces two main modes:

- **QS-CaQR (Qubit Saving):** reduces the number of qubits required by reusing qubits and resizing logical resources.
- **SR-CaQR (SWAP Reduction):** reduces the number of SWAP gates by reusing physical qubits.

The original public repository mainly implements the QS-CaQR portion of the paper. This repository keeps that implementation and adds an independent SR-CaQR mode based on the paper.

---

## Paper

The implementation is based on the following paper:

**CaQR: A Compiler-Assisted Approach for Qubit Reuse through Dynamic Circuit**  
Fei Hua, Yuwei Jin, Yanhao Chen, Suhas Vittal, Kevin Krsulich, Lev S. Bishop, John Lapeyre, Ali Javaidi-Abhari, Eddy Z. Zhang  
ASPLOS 2023

DOI: [10.1145/3582016.3582030](https://doi.org/10.1145/3582016.3582030)

---

## Original Repository and Attribution

The initial source code used in this project comes from:

[https://github.com/ruadapt/CaQR](https://github.com/ruadapt/CaQR)

That repository provides the original QS-CaQR implementation. This repository is a derivative work that extends the original code with additional functionality and tests.

Original repository:  
[https://github.com/ruadapt/CaQR](https://github.com/ruadapt/CaQR)

This repository:  
[https://github.com/atenaraeisi/CaQR-main](https://github.com/atenaraeisi/CaQR-main)

---

## Features

- QS-CaQR mode preserved from the original repository.
- Independent SR-CaQR mode implemented according to the paper.
- Physical-qubit-count parameter added through `-k`.
- Modular structure separating QS-CaQR and SR-CaQR modes.
- Regression tests for the original QS-CaQR behavior.
- Correctness tests for SR-CaQR, including reuse, SWAP insertion, measurement/reset, mapping, and semantic equivalence.
- Experiment notebooks for reproducing and analyzing CaQR behavior.

---

## Differences from the Upstream Repository

The upstream repository [ruadapt/CaQR](https://github.com/ruadapt/CaQR) mainly implements QS-CaQR, which covers qubit saving and logical resizing. It does not provide a ready-to-use SR-CaQR implementation. It also does not accept the number of available physical qubits as a direct input parameter in the QS workflow.

This repository makes the following changes:

1. **Added SR-CaQR support.**  
   The SR-CaQR mode is implemented based on the paper. It includes:
   - Dynamic mapping
   - Coupling map support
   - Critical path analysis
   - Delaying selected gates
   - Reclaiming and reusing physical qubits
   - SWAP insertion

2. **Added the `-k` parameter.**  
   The `-k` option allows the user to specify the number of physical qubits available on the target hardware. This parameter is used by the QS-CaQR workflow where physical qubit availability matters.

3. **Refactored the project into independent modes.**  
   The codebase now separates QS-CaQR and SR-CaQR so that both modes can be used and tested independently.

4. **Kept QS-CaQR unchanged where possible.**  
   The original QS-CaQR behavior is preserved, and regression tests are included to detect unintended changes.

5. **Added correctness tests.**  
   The test suite currently includes 29 passing tests covering reuse, SWAP, measurement/reset, mapping, and semantic equivalence for small circuits.

---

## Project Structure

```text
CaQR-main/
├── caqr/
│   ├── modes/                  # QS-CaQR and SR-CaQR modes
│   ├── sr/                     # SR-CaQR implementation
│   ├── device.py               # Device and coupling map handling
│   ├── reuse_mapping.py        # Reuse mapping logic
│   └── __init__.py
├── benchmarks/                 # Example QASM benchmark files
├── devices/                    # Device information
├── tests/                      # Correctness and regression tests
├── main.py                     # Main entry point
├── circuit_analysis.py         # Circuit analysis utilities
├── experiments.ipynb           # General CaQR experiments
├── QS-experiment.ipynb         # QS-CaQR experiments
├── SR_REPRODUCTION_NOTES.md    # Notes on reproducing SR-CaQR
└── README.md
```

---

## Requirements

- Python 3.8 or newer
- Qiskit
- networkx

The notebooks in this repository record the environment used for the experiments. Depending on your Qiskit version, minor API adjustments may be required.

---

## Installation

Install the main dependencies:

```bash
pip install qiskit networkx
```

If you are using a specific Qiskit version for reproducibility, install that version explicitly.

---

## Usage

### QS-CaQR

Run QS-CaQR on a benchmark circuit:

```bash
python main.py -b benchmarks/bv_n10.qasm -v 0 -k 10
```

Arguments:

- `-b`: path to the QASM benchmark file
- `-v`: verbosity level
  - `0`: only the result
  - `1`: display the circuit
- `-k`: number of physical qubits available on the target device

The output is typically written to the `output/` directory with a `_reuse` suffix.

### SR-CaQR

Run SR-CaQR on a benchmark circuit:

```bash
python main.py -b benchmarks/bv_n10.qasm -v 0 --mode sr
```

To see all available options:

```bash
python main.py --help
```

---

## Parameter `-k`

The `-k` parameter was added because the original QS-CaQR workflow did not directly accept the number of physical qubits available on the target hardware.

Example:

```bash
python main.py -b benchmarks/bv_n10.qasm -v 0 -k 10
```

Here, `-k 10` means that the target hardware or simulated device has 10 physical qubits. This value is used by the mapping and reuse logic when deciding how qubits can be allocated and reused.

---

## Tests

Run the test suite with:

```bash
python -m pytest tests/
```

At the time of writing, 29 tests pass successfully. These tests cover:

- Qubit reuse
- SWAP insertion
- Measurement and reset behavior
- Mapping correctness
- Semantic equivalence between the original circuit and the transformed circuit
- Regression behavior for QS-CaQR

The SR-CaQR implementation has been validated on small circuits. Larger-scale validation is part of ongoing work.

---

## Experiments

The file `experiments.ipynb` contains the main experiments for this repository.

Key observations so far:

- CaQR was run on Qiskit and verified to execute correctly.
- On BV10, CaQR reduces the requirement from 10 qubits to 2 resources.
- The reuse chain behavior was identified and analyzed.
- The upstream public repository mainly implements QS-CaQR, not SR-CaQR.
- After refactoring, QS-CaQR and SR-CaQR are independent modes.
- QS-CaQR was preserved and protected with regression tests.
- SR-CaQR Phase 1 was implemented based on the paper.
- Correctness tests for SR-CaQR pass on small circuits and produce logically equivalent outputs.

Additional notebooks:

- `QS-experiment.ipynb`: QS-CaQR experiments.
- `SR_REPRODUCTION_NOTES.md`: notes for reproducing SR-CaQR results.

---

## Validation

To validate QS-CaQR output, first generate the output with `main.py`, then run:

```bash
python validate.py bv_n10
```

Make sure the corresponding benchmark output has already been generated.

---

## Implementation Notes

### QS-CaQR

The QS-CaQR implementation is kept close to the original upstream code. Regression tests are included to ensure that changes made for SR-CaQR do not accidentally alter the QS-CaQR behavior.

### SR-CaQR

The SR-CaQR implementation follows the paper and includes the following steps:

1. Dynamic mapping
2. Coupling map handling
3. Critical path analysis
4. Delaying selected gates
5. Reclaiming and reusing physical qubits
6. SWAP insertion

The current implementation is experimental but has passed correctness tests on small circuits. It produces logically equivalent outputs compared with the original circuits in the tested cases.

---

## Reproducibility

For details about reproducing the SR-CaQR results, see:

```text
SR_REPRODUCTION_NOTES.md
```

The notebooks also contain the exact commands and workflows used during development.

---

## Citation

If you use this project in academic work, please cite the original CaQR paper.

```bibtex
@inproceedings{hua2023caqr,
  title={CaQR: A Compiler-Assisted Approach for Qubit Reuse through Dynamic Circuit},
  author={Hua, Fei and Jin, Yuwei and Chen, Yanhao and Vittal, Suhas and Krsulich, Kevin and Bishop, Lev S. and Lapeyre, John and Javaidi-Abhari, Ali and Zhang, Eddy Z.},
  booktitle={Proceedings of the 28th ACM International Conference on Architectural Support for Programming Languages and Operating Systems, Volume 3},
  pages={59--71},
  year={2023},
  doi={10.1145/3582016.3582030}
}
```

Original repository:  
[https://github.com/ruadapt/CaQR](https://github.com/ruadapt/CaQR)

This repository:  
[https://github.com/atenaraeisi/CaQR-main](https://github.com/atenaraeisi/CaQR-main)

---

## License

This repository is based on the original implementation from [ruadapt/CaQR](https://github.com/ruadapt/CaQR). Please consult the original repository for its license terms. This derivative work should be used and distributed in compliance with the original license and the terms of the original project.

If you plan to redistribute this repository, add an explicit license file and ensure that the original attribution requirements are satisfied.

---

## Acknowledgements

This project builds on the original CaQR implementation by the authors of the paper and the contributors to [ruadapt/CaQR](https://github.com/ruadapt/CaQR). Their work provided the foundation for the QS-CaQR implementation and the overall structure of the codebase.

The SR-CaQR mode, the `-k` parameter, the refactored mode structure, and the additional correctness tests were developed in this repository.