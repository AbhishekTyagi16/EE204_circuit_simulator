import sys
from numpy import *
from pandas import *
from matplotlib.pyplot import *
from tkinter import *
from tkinter import simpledialog, messagebox
import json

GRID = 20
NAMES = {'R': 'Resistor', 'C': 'Capacitor', 'L': 'Inductor',
         'V': 'Voltage', 'I': 'Current', 'W': 'Wire', 'E': 'VCVS', 'H': 'CCVS'}

class Design:
    def __init__(self, root):
        self.root = root
        self.comps = []
        self.mode = None
        self.start = None
        self.line = None
        self.counts = {k: 0 for k in NAMES}

        # Tools
        frm = Frame(root, bd=1)
        frm.pack(fill=X)
        for k, v in NAMES.items():
            Button(frm, text=f"{v} ({k})", command=lambda m=k: self.set_mode(m)).pack(side=LEFT)

        Button(frm, text="Export", command=self.save).pack(side=RIGHT)
        Button(frm, text="Clear", command=self.clear).pack(side=RIGHT)

        # Canvas & Grid
        self.cv = Canvas(root, bg="white", width=800, height=600)
        self.cv.pack(fill=BOTH, expand=True)
        self.cv.bind("<Button-1>", self.on_click)
        self.cv.bind("<Motion>", self.on_move)

    def clear(self):
        self.cv.delete("all")
        self.comps = []
        self.counts = {k: 0 for k in NAMES}

    def save(self):
        nodes = {}
        branches = []

        for i, c in enumerate(self.comps):
            n1 = nodes.setdefault(c['p1'], len(nodes) + 1)
            n2 = nodes.setdefault(c['p2'], len(nodes) + 1)

            data = {
                'name': c['name'],
                'type': c['type'],
                'branch_id': i + 1,
                'node_pos': n1,
                'node_neg': n2,
                'value': float(c['val']) if c['val'] else 0.0
            }

            # Add control info for dependent sources
            if c['type'] == 'E' and 'ctrl_pos' in c:
                data['ctrl_pos'] = c['ctrl_pos']
                data['ctrl_neg'] = c['ctrl_neg']
            elif c['type'] == 'H' and 'ctrl_branch' in c:
                data['ctrl_branch'] = c['ctrl_branch']

            branches.append(data)

        output_filename = "circuit.json"
        try:
            with open(output_filename, "w") as f:
                json.dump(branches, f, indent=4)
            messagebox.showinfo("Saved", f"Structured data saved to {output_filename}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save JSON: {e}")

    def set_mode(self, m):
        self.mode = m
        self.start = None

    def get_component_nodes(self, comp_name):
        """Get node_pos and node_neg for a given component name"""
        nodes = {}
        for c in self.comps:
            nodes.setdefault(c['p1'], len(nodes) + 1)
            nodes.setdefault(c['p2'], len(nodes) + 1)
            if c['name'] == comp_name:
                return nodes[c['p1']], nodes[c['p2']]
        return None, None

    def get_component_id(self, comp_name):
        """Get branch_id for a given component name"""
        for i, c in enumerate(self.comps):
            if c['name'] == comp_name:
                return i + 1
        return None

    def on_click(self, e):
        if not self.mode:
            return
        x, y = (round(e.x / GRID) * GRID), (round(e.y / GRID) * GRID)

        if not self.start:
            self.start = (x, y)
        else:
            val = "0"
            comp_data = {'type': self.mode, 'p1': self.start, 'p2': (x, y)}

            if self.mode != 'W':
                val = simpledialog.askstring("Value", f"Value for {self.mode} (gain if E/H):")
                if val is None:
                    return self.reset_click()

            # Handle VCVS (E)
            if self.mode == 'E':
                # Show available components
                comp_list = ', '.join([c['name'] for c in self.comps])
                if not comp_list:
                    messagebox.showwarning("No Components", "Please add components first!")
                    return self.reset_click()
                
                ctrl_name = simpledialog.askstring("VCVS Control", 
                    f"Available: {comp_list}\nEnter controlling component (e.g., R1):")
                if not ctrl_name:
                    return self.reset_click()
                
                ctrl_pos, ctrl_neg = self.get_component_nodes(ctrl_name)
                if ctrl_pos is None:
                    messagebox.showerror("Error", f"Component {ctrl_name} not found!")
                    return self.reset_click()
                
                comp_data['ctrl_pos'] = ctrl_pos
                comp_data['ctrl_neg'] = ctrl_neg

            # Handle CCVS (H)
            elif self.mode == 'H':
                comp_list = ', '.join([c['name'] for c in self.comps])
                if not comp_list:
                    messagebox.showwarning("No Components", "Please add components first!")
                    return self.reset_click()
                
                ctrl_name = simpledialog.askstring("CCVS Control", 
                    f"Available: {comp_list}\nEnter controlling component (e.g., R1):")
                if not ctrl_name:
                    return self.reset_click()
                
                ctrl_id = self.get_component_id(ctrl_name)
                if ctrl_id is None:
                    messagebox.showerror("Error", f"Component {ctrl_name} not found!")
                    return self.reset_click()
                
                comp_data['ctrl_branch'] = ctrl_id

            self.counts[self.mode] += 1
            comp_data['name'] = f"{self.mode}{self.counts[self.mode]}"
            comp_data['val'] = val
            
            self.comps.append(comp_data)
            self.draw_comp(self.comps[-1])
            self.reset_click()

    def on_move(self, e):
        if self.start:
            if self.line:
                self.cv.delete(self.line)
            self.line = self.cv.create_line(self.start[0], self.start[1], 
                round((e.x / GRID) * GRID), round((e.y / GRID) * GRID), dash=(4, 2))

    def reset_click(self):
        self.start = None
        if self.line:
            self.cv.delete(self.line)

    def draw_comp(self, c):
        w = 3
        mx, my = (c['p1'][0] + c['p2'][0]) / 2, (c['p1'][1] + c['p2'][1]) / 2
        self.cv.create_line(*c['p1'], *c['p2'], fill="black", width=w)
        for x, y in (c['p1'], c['p2']):
            self.cv.create_oval(x-3, y-3, x+3, y+3, fill="black")
        if c['type'] != 'W':
            # Different color for dependent sources
            fill_color = "lightblue" if c['type'] in ['E', 'H'] else "white"
            self.cv.create_rectangle(mx-15, my-15, mx+15, my+15, 
                fill=fill_color, outline="black")
            self.cv.create_text(mx, my, text=f"{c['name']}\n{c['val']}", 
                fill="black", font=("Arial", 10, "bold"))

root = Tk()
root.geometry("900x600")
f1 = Frame(root, bg="grey", borderwidth=1)
f1.pack()
root.title("EE204 Project - Circuit Designer")
name = Label(f1, text="Design the circuit here", font=("Helvetica", 16, "bold"))
name.pack()
Design(root)
root.mainloop()