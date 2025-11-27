import sys
import json
import numpy as np
import networkx as nx
import sympy as sp
import matplotlib.pyplot as plt

# Global symbols
s, t = sp.symbols('s'), sp.symbols('t', positive=True, real=True)

# ============================================================================
# PART 1: GRAPH INFRASTRUCTURE
# ============================================================================


class DisjointSetUnion:
    def __init__(self, size):
        self.parent = list(range(size))

    def find(self, i):
        if self.parent[i] != i:
            self.parent[i] = self.find(self.parent[i])
        return self.parent[i]

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[rb] = ra if ra < rb else ra


def consolidate_nodes(branches, max_node):
    """Merge wire-connected nodes and remove wire branches"""
    dsu = DisjointSetUnion(max_node + 1)

    for b in branches:
        if b["type"] == "W":
            dsu.union(b["node_pos"], b["node_neg"])

    cleaned, nodes = [], set()
    for b in branches:
        if b["type"] == "W":
            continue

        b_new = b.copy()
        b_new["node_pos"] = dsu.find(b["node_pos"])
        b_new["node_neg"] = dsu.find(b["node_neg"])

        if b_new["node_pos"] != b_new["node_neg"]:
            cleaned.append(b_new)
            nodes.add(b_new["node_pos"])
            nodes.add(b_new["node_neg"])

    return cleaned, len(nodes)


def load_circuit_data(filename="circuit.json"):
    try:
        with open(filename, "r") as f:
            branches = json.load(f)
    except Exception as e:
        print(f"ERROR: {e}")
        return None, 0, 0, None

    max_node = 0
    if branches:
        max_node = max(max(b["node_pos"], b["node_neg"]) for b in branches)

    cleaned, num_nodes = consolidate_nodes(branches, max_node)

    comp = {t: [] for t in ["R", "L", "C", "V", "I", "E", "H"]}
    for b in cleaned:
        if b["type"] in comp:
            comp[b["type"]].append(b)

    return cleaned, num_nodes, len(cleaned), comp


def pick_reference_node(branches):
    nodes = {b["node_pos"]
             for b in branches} | {b["node_neg"] for b in branches}
    if 0 in nodes:
        return 0
    G = nx.Graph()
    for b in branches:
        G.add_edge(b["node_pos"], b["node_neg"])
    return max(G.nodes, key=lambda n: G.degree[n])


def build_incidence_matrix(branches, ref):
    all_nodes = {b["node_pos"]
                 for b in branches} | {b["node_neg"] for b in branches}
    nonref = sorted(n for n in all_nodes if n != ref)
    node_to_row = {n: i for i, n in enumerate(nonref)}

    A = np.zeros((len(nonref), len(branches)), dtype=float)

    for col, b in enumerate(branches):
        p, q = b["node_pos"], b["node_neg"]
        if p != ref:
            A[node_to_row[p], col] = 1.0
        if q != ref:
            A[node_to_row[q], col] = -1.0

    return A, nonref


def partition_branches_graphical(branches, nonref_nodes):
    """
    Separates Tree and Links.
    CRITICAL: Current Sources ('I') are given HIGH weight so they are NOT picked 
    in the MST. This forces them to be Links, which simplifies solving.
    """
    G = nx.Graph()
    for n in nonref_nodes:
        G.add_node(n)

    for b in branches:
        u, v = b["node_pos"], b["node_neg"]
        if u != v:
            # Current sources are heavy -> Avoid putting in Tree -> Force to be Link
            w = 1000 if b['type'] == 'I' else 1
            G.add_edge(u, v, branch_id=b["branch_id"], weight=w)

    if not nx.is_connected(G):
        print("ERROR: Graph is not connected.")
        return None, None

    T = nx.minimum_spanning_tree(G, weight='weight')
    tree_ids = [d["branch_id"] for _, _, d in T.edges(data=True)]
    all_ids = [b["branch_id"] for b in branches]
    link_ids = [bid for bid in all_ids if bid not in tree_ids]

    return tree_ids, link_ids

# ============================================================================
# PART 2: PATH FINDING (Unchanged)
# ============================================================================


def get_tree_path_coeffs(branches, tree_ids, start_node, end_node):
    if start_node == end_node:
        return {}
    G_tree = nx.Graph()
    branch_map = {}

    for idx, b in enumerate(branches):
        if b['branch_id'] in tree_ids:
            u, v = b['node_pos'], b['node_neg']
            G_tree.add_edge(u, v)
            branch_map[tuple(sorted((u, v)))] = (idx, u, v)

    try:
        path = nx.shortest_path(G_tree, source=start_node, target=end_node)
    except nx.NetworkXNoPath:
        return {}

    coeffs = {}
    for i in range(len(path) - 1):
        u, v = path[i], path[i+1]
        key = tuple(sorted((u, v)))
        b_idx, def_u, def_v = branch_map[key]
        coeffs[b_idx] = 1.0 if u == def_u else -1.0

    return coeffs

# ============================================================================
# PART 3: SOLVER LOGIC (UPDATED FOR 'I' SOURCES)
# ============================================================================


def build_tie_set_matrix(A, branches, id_t, id_l):
    branch_id_to_col = {b['branch_id']: idx for idx, b in enumerate(branches)}
    cols_t = [branch_id_to_col[bid] for bid in id_t]
    cols_l = [branch_id_to_col[bid] for bid in id_l]

    A_t = A[:, cols_t]
    A_l = A[:, cols_l]

    try:
        F_lt = -(np.linalg.inv(A_t) @ A_l)
    except np.linalg.LinAlgError:
        F_lt = -(np.linalg.pinv(A_t) @ A_l)

    B = np.zeros((len(branches), len(id_l)), dtype=float)
    for i, r_idx in enumerate(cols_t):
        B[r_idx, :] = F_lt[i, :]
    for i, r_idx in enumerate(cols_l):
        B[r_idx, i] = 1.0

    # Align signs
    for col_idx, bid in enumerate(id_l):
        r = branch_id_to_col[bid]
        if B[r, col_idx] < 0:
            B[:, col_idx] *= -1.0

    return B


def solve_system_with_knowns(Z_loop, RHS_total, known_indices, known_values):
    """
    Solves Z * I = V when some I values are known (Current Sources).
    Algorithm: Partition matrix and move knowns to RHS.
    Z_uu * I_u + Z_uk * I_k = V_u
    Z_uu * I_u = V_u - Z_uk * I_k
    """
    n = Z_loop.shape[0]
    # Ensure indices are standard Python lists of integers
    unknown_indices = [int(i) for i in range(n) if i not in known_indices]
    known_indices = [int(i) for i in known_indices]

    if not known_indices:
        # Standard case
        try:
            return np.linalg.solve(Z_loop, RHS_total)
        except:
            if hasattr(Z_loop, 'inv'):  # SymPy
                return Z_loop.inv() * RHS_total
            return np.linalg.pinv(Z_loop) @ RHS_total

    # --- FIX START: Handle SymPy vs NumPy Slicing ---

    # Check if Z_loop is a SymPy Matrix
    is_sympy = hasattr(Z_loop, 'free_symbols') or hasattr(Z_loop, 'extract')

    if is_sympy:
        # SymPy slicing uses .extract(rows, cols) or straight list indexing
        Z_uu = Z_loop[unknown_indices, unknown_indices]
        Z_uk = Z_loop[unknown_indices, known_indices]
        V_u = RHS_total[unknown_indices, 0]

        # Calculate effective RHS
        # Cast known_values to SymPy Matrix for multiplication
        I_k = sp.Matrix(known_values)
        RHS_eff = V_u - Z_uk * I_k

        try:
            I_u = Z_uu.LUsolve(RHS_eff)
        except:
            I_u = Z_uu.inv() * RHS_eff

        I_full = sp.zeros(n, 1)
        for i, val in enumerate(known_values):
            I_full[known_indices[i]] = val
        for i, idx in enumerate(unknown_indices):
            I_full[idx] = I_u[i]

        return I_full

    else:
        # NumPy Slicing (using np.ix_)
        Z_uu = Z_loop[np.ix_(unknown_indices, unknown_indices)]
        Z_uk = Z_loop[np.ix_(unknown_indices, known_indices)]
        V_u = RHS_total[unknown_indices]

        # Numeric Calculation
        RHS_eff = V_u - Z_uk @ known_values
        try:
            I_u = np.linalg.solve(Z_uu, RHS_eff)
        except:
            I_u = np.linalg.pinv(Z_uu) @ RHS_eff

        I_full = np.zeros(n)
        for i, val in enumerate(known_values):
            I_full[known_indices[i]] = val
        for i, idx in enumerate(unknown_indices):
            I_full[idx] = I_u[i]

        return I_full
    # --- FIX END ---


def solve_dc(branches, B, tree_ids, link_ids):
    n_b = len(branches)
    Z = np.zeros((n_b, n_b))
    V_src = np.zeros(n_b)

    # Identify Known Links (Current Sources)
    known_link_indices = []
    known_link_values = []

    branch_map = {b['branch_id']: b for b in branches}

    # Populate Z and V
    for idx, b in enumerate(branches):
        typ = b['type']
        val = float(b['value'])

        if typ == 'R':
            Z[idx, idx] = val
        elif typ == 'L':
            Z[idx, idx] = 1e-9
        elif typ == 'C':
            Z[idx, idx] = 1e12
        elif typ == 'V':
            V_src[idx] = val  # Fixed Sign

    # Dependent Sources (VCVS)
    for idx, b in enumerate(branches):
        if b['type'] == 'E':
            gain = float(b['value'])
            coeffs = get_tree_path_coeffs(
                branches, tree_ids, b['ctrl_pos'], b['ctrl_neg'])
            for k_idx, direction in coeffs.items():
                Z[idx, k_idx] -= gain * Z[k_idx, k_idx] * direction

    # Identify Current Sources among Links
    for i, bid in enumerate(link_ids):
        b = branch_map[bid]
        if b['type'] == 'I':
            known_link_indices.append(i)
            # Check direction match with B matrix column
            # (If B[row, col] is +1, direction matches. If -1, inverted)
            b_idx = next(idx for idx, x in enumerate(
                branches) if x['branch_id'] == bid)
            sign = B[b_idx, i]  # Should be 1.0 due to normalization, but check
            known_link_values.append(float(b['value']) * sign)

    Z_loop = B.T @ Z @ B
    RHS = -(B.T @ V_src)

    i_link = solve_system_with_knowns(
        Z_loop, RHS, known_link_indices, np.array(known_link_values))
    return i_link, B @ i_link


def solve_laplace(branches, B, tree_ids, link_ids, ic=None):
    if ic is None:
        ic = {}
    n_b = len(branches)
    Z = sp.zeros(n_b, n_b)
    V_src = sp.zeros(n_b, 1)

    known_link_indices = []
    known_link_values = []
    branch_map = {b['branch_id']: b for b in branches}

    for idx, b in enumerate(branches):
        typ, val = b['type'], b['value']
        bid = b['branch_id']

        if typ == 'R':
            Z[idx, idx] = val
        elif typ == 'L':
            Z[idx, idx] = s * val
            # Fixed Sign (Positive for Drop convention on Source)
            V_src[idx] = val * ic.get(bid, 0)
        elif typ == 'C':
            Z[idx, idx] = 1 / (s * val)
        elif typ == 'V':
            V_src[idx] = val / s  # Fixed Sign

    # Dependent Sources
    for idx, b in enumerate(branches):
        if b['type'] == 'E':
            gain = b['value']
            coeffs = get_tree_path_coeffs(
                branches, tree_ids, b['ctrl_pos'], b['ctrl_neg'])
            for k_idx, direction in coeffs.items():
                Z[idx, k_idx] -= gain * Z[k_idx, k_idx] * direction

    # Identify Current Sources
    for i, bid in enumerate(link_ids):
        b = branch_map[bid]
        if b['type'] == 'I':
            known_link_indices.append(i)
            b_idx = next(idx for idx, x in enumerate(
                branches) if x['branch_id'] == bid)
            sign = B[b_idx, i]
            # Laplace of Current Source is I/s
            known_link_values.append((sp.sympify(b['value']) / s) * sign)

    B_sym = sp.Matrix(B)
    Z_loop = B_sym.T * Z * B_sym
    RHS = -(B_sym.T * V_src)

    i_link = solve_system_with_knowns(
        Z_loop, RHS, known_link_indices, known_link_values)
    return i_link, B_sym * i_link

# ============================================================================
# PART 4: OUTPUT UTILS
# ============================================================================


def inverse_laplace_vector(sym_vec):
    out = []
    print(f"[INFO] Calculating Inverse Laplace for {len(sym_vec)} branches...")
    for i, e in enumerate(sym_vec):
        try:
            e_simp = sp.simplify(e)
            res = sp.inverse_laplace_transform(e_simp, s, t)
            out.append(res)
        except Exception as err:
            out.append(sp.sympify(0))
    return sp.Matrix(out)


def plot_results(i_t, branches, filename="currents.png"):
    funcs = []
    # Create lambda functions
    for expr in i_t:
        try:
            f = sp.lambdify(t, expr, modules=[
                            'numpy', {'Heaviside': lambda x: np.heaviside(x, 1)}])
            funcs.append(f)
        except:
            funcs.append(lambda x: np.zeros_like(x))

    time = np.linspace(0, 5, 500)
    plt.figure(figsize=(10, 6))

    # Track if we plotted anything to avoid empty legend warnings
    plotted_any = False

    for i, f in enumerate(funcs):
        try:
            y = f(time)

            # --- SCALAR BROADCASTING FIX ---
            # Handle scalars/constants by broadcasting
            if np.isscalar(y) or (isinstance(y, np.ndarray) and y.ndim == 0):
                y = np.full_like(time, float(y))
            elif isinstance(y, np.ndarray) and y.shape != time.shape:
                y = np.full_like(time, y.item())

            # Only plot if current is significant (> 1 microamp)
            if np.max(np.abs(y)) > 1e-6:
                # Use component name from branch data
                comp_name = branches[i].get('name', f'B{i+1}')
                label_str = f'I({comp_name})'

                plt.plot(time, y, label=label_str, linewidth=1.5)
                plotted_any = True

        except Exception as e:
            print(f"[WARN] Could not plot Branch {i+1}: {e}")
            continue

    plt.title("Component Currents (Time Domain)", fontsize=14)
    plt.xlabel("Time (s)", fontsize=12)
    plt.ylabel("Current (A)", fontsize=12)

    if plotted_any:
        plt.legend(loc='upper right', fontsize=9)

    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(filename, dpi=150)
    print(f"[SUCCESS] Plot saved to {filename}")

# ============================================================================
# MAIN
# ============================================================================
# ============================================================================
# MAIN
# ============================================================================


if __name__ == "__main__":
    branches, num_nodes, num_branches, comp = load_circuit_data("circuit.json")

    if not branches:
        sys.exit(1)

    print(f"Circuit Loaded: {num_nodes} Nodes, {num_branches} Branches")

    ref_node = pick_reference_node(branches)
    A, nonref = build_incidence_matrix(branches, ref_node)

    tree_ids, link_ids = partition_branches_graphical(branches, nonref)

    B = build_tie_set_matrix(A, branches, tree_ids, link_ids)

    print("\n--- DC Analysis ---")
    i_l_dc, i_b_dc = solve_dc(branches, B, tree_ids, link_ids)

    # Print to console with names
    for idx, val in enumerate(i_b_dc):
        b_name = branches[idx].get('name', f'B{idx+1}')
        print(f"I({b_name}): {val:.6f} A")

    print("\n--- Laplace Analysis ---")
    ic_map = {}
    for idx, b in enumerate(branches):
        ic_map[b['branch_id']] = i_b_dc[idx]

    i_l_s, i_b_s = solve_laplace(branches, B, tree_ids, link_ids, ic=ic_map)

    i_b_t = inverse_laplace_vector(i_b_s)

    # Save Results to Text File with Names
    with open("results.txt", "w") as f:
        f.write("DC RESULTS:\n")
        f.write("-" * 30 + "\n")
        for i, val in enumerate(i_b_dc):
            name = branches[i].get('name', f"Branch {i+1}")
            f.write(f"I({name}): {val} A\n")

        f.write("\nTIME DOMAIN EQUATIONS:\n")
        f.write("-" * 30 + "\n")
        for i, val in enumerate(i_b_t):
            name = branches[i].get('name', f"Branch {i+1}")
            f.write(f"I({name})(t) = {val}\n")

    # Plot using names
    plot_results(i_b_t, branches)
