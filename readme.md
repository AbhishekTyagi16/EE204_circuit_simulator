# Circuit Simulator – EE204 Project

This repository contains an advanced Circuit Simulator capable of performing DC Operating Point Analysis, Laplace Domain Analysis, and Time Domain Transient Analysis. Unlike standard Modified Nodal Analysis (MNA) solvers, this project utilizes a Graph-Theoretic Tie-Set Matrix (Loop Analysis) approach to robustly solve linear RLC circuits containing both independent and dependent sources.

**DC + Transient Circuit Simulator**, **Dependent Sources (VCVS, CCVS)**, **Laplace-domain analysis**, **GUI-based circuit builder**.

## Overview

This project implements a **fully functional linear circuit simulation framework**, including a backend solver and a frontend schematic editor.

We can:

- Draw circuits in a GUI
- Export a JSON netlist
- Run DC analysis
- Run Laplace-domain analysis
- Compute exact transient time-domain currents
- Handle dependent sources
- Analyze arbitrary circuit topologies

Everything is implemented in **pure Python**, without using any external circuit-simulation libraries.

The engine solves **any arbitrary linear circuit** composed of:

| Component | Meaning                                  | Supported |
| --------- | ---------------------------------------- | --------- |
| R         | Resistor                                 | ✔         |
| L         | Inductor                                 | ✔         |
| C         | Capacitor                                | ✔         |
| V         | Independent Voltage Source               | ✔         |
| I         | Independent Current Source               | ✔         |
| E         | VCVS (Voltage-Controlled Voltage Source) | ✔         |
| H         | CCVS (Current-Controlled Voltage Source) | ✔         |
| W         | Wire (short circuit)                     | ✔         |

### Fully Supported Circuit Types

- General DC circuits
- RL / RC / LC / RLC circuits
- Multi-loop and multi-node circuits
- Circuits containing multiple independent sources
- Circuits with **dependent sources (E, H)**
- Circuits requiring transient response analysis
- Circuits requiring symbolic Laplace-domain current expressions

### Future Scope

- Non-linear devices (diodes, transistors)
- AC phasor mode (can be implemented very easily but no need)
- Voltage controlled current source and current controlled current source

### Assumptions & Constraints

Initial Conditions: For transient analysis, Zero State Response is assumed (Initial currents in Inductors and voltages across Capacitors are assumed to be zero).

Connectivity: The circuit graph must be fully connected (no floating nodes).

## Backend

The is a custom-built engine using:

### 1. Node Consolidation (Union-Find)

All wires are merged into equivalent nodes automatically.

### 2. Graph-Based Topology (NetworkX)

- Automatically builds circuit graph
- Selects a **spanning tree**
- Forces **current sources to be links** (avoids singular matrices)
- Generates the **tie-set matrix B**

### 3. Loop Equation Formulation

Currents are solved using:
```
Z_loop · I_link = V_loop
```

Where Z is the branch impedance matrix.

### 4. Dependent Source Handling

VCVS and CCVS are processed by modifying the impedance matrix based on:

- Control voltage (E)
- Control current (H)

### 5. DC Analysis

- Inductors → Short
- Capacitors → Open

### 6. Laplace-Domain Analysis

- Inductor impedance: `Z_L = sL`
- Capacitor impedance: `Z_C = 1/(sC)`
- Voltage source: `V/s`
- Current source: `I/s`
- Inductor initial currents included automatically

### 7. Exact Time-Domain Response

Using SymPy:
```
i(t) = L^(-1){I(s)}
```

This gives exact exponential/sinusoidal expressions.

### 8. Plotting

All transient currents are plotted using Matplotlib.

## GUI Frontend (Tkinter)

Features:

- Drag & drop component placement
- Snap-to-grid system
- Wire drawing with automatic node merging
- Input values for each component
- Dependent source support (E, H)
- Exports clean `circuit.json` netlist

## Running the Project

### Create Virtual Environment
```bash
python -m venv .venv
```

### Activate Virtual Environment
```bash
.\.venv\Scripts\Activate.ps1
```

### Install Dependencies
```bash
pip install sympy numpy matplotlib networkx pandas
```

### Run Frontend
```bash
python frontend.py
```

### Run Backend
```bash
python circuit_analysis.py
```
