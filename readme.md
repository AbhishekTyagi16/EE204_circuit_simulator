# ⚡️ EE 204 Circuit Simulator: The Tie-Set Method

**Course:** EE 204: Circuit Theory (3rd Semester)  
**Institution:** Indian Institute of Technology Guwahati (IIT Guwahati)

This repository contains an advanced Circuit Simulator capable of performing **DC Operating Point Analysis**, **Laplace Domain Analysis**, and **Time Domain Transient Analysis**.

Unlike standard Modified Nodal Analysis (MNA) solvers, this project utilizes a **Graph-Theoretic Tie-Set Matrix (Loop Analysis)** approach to robustly solve linear RLC circuits containing both independent and dependent sources.

---

## 🚀 Overview

This project implements a **fully functional linear circuit simulation framework**, consisting of a custom backend solver and a graphical frontend.

**Key Capabilities:**
* Draw circuits in an interactive GUI.
* Export a JSON netlist.
* Run DC & Laplace-domain analysis.
* Compute exact **symbolic** transient time-domain currents.
* Handle arbitrary circuit topologies with dependent sources.

Everything is implemented in **pure Python**, without reliance on external circuit-simulation libraries like SPICE.

### Supported Components

The engine solves any arbitrary linear circuit composed of the following:

| Symbol | Component | Supported |
| :---: | :--- | :---: |
| **R** | Resistor | ✅ |
| **L** | Inductor | ✅ |
| **C** | Capacitor | ✅ |
| **V** | Independent Voltage Source | ✅ |
| **I** | Independent Current Source | ✅ |
| **E** | VCVS (Voltage-Controlled Voltage Source) | ✅ |
| **H** | CCVS (Current-Controlled Voltage Source) | ✅ |
| **W** | Wire (Short Circuit) | ✅ |

### Supported Circuit Types
* General DC circuits
* RL / RC / LC / RLC circuits
* Multi-loop and multi-node topologies
* Circuits with **Dependent Sources (E, H)**
* Transient response analysis
* Symbolic Laplace-domain calculations

---

## 🛠️ Backend Architecture

The backend is a custom-built engine leveraging graph theory and symbolic mathematics.

### 1. Node Consolidation (Union-Find)
We use a disjoint-set data structure to automatically merge all wires into equivalent nodes, simplifying the topology before analysis.

### 2. Graph-Based Topology (NetworkX)


[Image of graph theory spanning tree]

* Automatically builds the circuit graph.
* Selects a **Minimum Spanning Tree (MST)**.
* Forces **Current Sources** to be links (avoiding singular matrices).
* Generates the **Tie-Set Matrix ($B$)**.

### 3. Loop Equation Formulation
Currents are solved using the fundamental loop impedance equation:

$$Z_{loop} \cdot I_{link} = V_{loop}$$

Where $Z$ is the branch impedance matrix.

### 4. Dependent Source Handling
VCVS and CCVS components are processed by dynamically modifying the impedance matrix based on the control parameters.

### 5. DC Analysis
* **Inductors** $\rightarrow$ Treated as Short Circuits.
* **Capacitors** $\rightarrow$ Treated as Open Circuits.

### 6. Laplace-Domain Analysis
The solver transforms components into the $s$-domain:
* **Inductor:** $Z_L = sL$
* **Capacitor:** $Z_C = \frac{1}{sC}$
* **Voltage Source:** $V(s) = \frac{V}{s}$
* **Current Source:** $I(s) = \frac{I}{s}$

*(Initial conditions for inductors are automatically included).*

### 7. Exact Time-Domain Response
Using `SymPy`, we perform the Inverse Laplace Transform to get exact equations:

$$i(t) = \mathcal{L}^{-1}\{I(s)\}$$

This yields precise exponential and sinusoidal expressions (e.g., $1.6 + 0.8e^{-2t}\sin(3t)$).

### 8. Visualization
All transient currents are plotted dynamically using `Matplotlib`.

---

## 🖥️ GUI Frontend (Tkinter)

The frontend provides a user-friendly interface for circuit design:
* **Drag & Drop:** Easy component placement.
* **Snap-to-Grid:** Keeps schematics clean.
* **Auto-Merging:** Drawing wires automatically merges nodes.
* **Netlist Export:** Generates a clean `circuit.json` for the backend.

---

## ⚙️ Installation & Usage

### 1. Setup Virtual Environment
```bash
python -m venv .venv
# Activate on Windows
.\.venv\Scripts\Activate.ps1
# Activate on Mac/Linux
source .venv/bin/activate


