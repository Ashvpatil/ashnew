# Heathrow Lost-Baggage VRP (Integer Programming Coursework)

This document is self-contained and provides:

* **Part A – LP-SOLVE models** (Stage 1 and Stage 2).
* **Part B – Excel Solver implementation** (layout, formulas, settings, and subtour elimination via cuts).
* **Part C – Interpretation** (expected results and feasibility explanation).

The travel-time matrix is included in the models and in the spreadsheet instructions. **Return-to-Heathrow times are set to 0** for all non-depot nodes, as required.

---

## Part A – LP-SOLVE Models (Complete .lp Files)

Two complete, executable lp_solve models are provided in the repository:

* `heathrow_stage1.lp` – Stage 1: minimize number of vans.
* `heathrow_stage2.lp` – Stage 2: minimize maximum route time given the minimum number of vans.

### How to run (two-stage optimization)

1. **Stage 1**: Solve `heathrow_stage1.lp` to get the minimum number of vans (sum of `delta_k`).
2. **Stage 2**: Set `VMIN` in `heathrow_stage2.lp` to the Stage 1 optimal value, then solve.

Both models include:

* Assignment, linking, depot usage, flow/degree, time limit, MTZ subtour elimination, symmetry breaking.
* All binary declarations (`x`, `y`, `delta`) and integer MTZ variables (`u`).

---

## Part B – Excel Solver Implementation

This section gives a **direct spreadsheet layout**, formulas, and Solver settings.

### 1) Spreadsheet Layout (exact placement)

Use one workbook with these sheets:

#### Sheet **`Data`**

**A1:O1** — column headers: `1,2,3,…,15`

**A2:A16** — row headers: `1,2,3,…,15`

**B2:O16** — travel time matrix (minutes). **Override return-to-Heathrow:** set all `c(i,1)=0` for `i=2..15` (cells `B3:B16` are zero). Keep `c(1,1)=0`.

Matrix (symmetric, in minutes):
```
0  20 25 35 65 90 85 80 86 25 35 20 44 35 82
20 0  15 35 60 55 57 85 90 25 35 30 37 20 40
25 15 0  30 50 70 55 50 65 10 25 15 24 20 90
35 35 30 0  45 60 53 55 47 12 22 20 12 10 21
65 60 50 45 0  46 15 45 75 25 11 19 15 25 25
90 55 70 60 46 0  15 15 25 45 65 53 43 63 70
85 57 55 53 15 15 0  17 25 41 25 33 27 45 30
80 85 50 55 45 15 17 0  25 40 34 32 20 30 10
86 90 65 47 75 25 25 25 0  65 70 72 61 45 13
25 25 10 12 25 45 41 40 65 0  20 8  7  15 25
35 35 25 22 11 65 25 34 70 20 0  5  12 45 65
20 30 15 20 19 53 33 32 72 8  5  0  14 34 56
44 37 24 12 15 43 27 20 61 7  12 14 0  30 40
35 20 20 10 25 63 45 30 45 15 45 34 30 0  27
82 40 90 21 25 70 30 10 13 25 65 56 40 27 0
```

#### Sheet **`Vars`**

**Decision variables** laid out as blocks of 0/1 values.

**x(i,j,k)**
* For each van `k=1..6`, create a 15×15 block (rows i=1..15, columns j=1..15).
* Example: place van 1 block in `B2:P16`, van 2 in `B18:P32`, etc.
* Cells are binary.

**y(i,k)**
* 14×6 block (i=2..15 by k=1..6). Example in `R2:W15`.

**δ(k)**
* 1×6 row. Example in `R17:W17`.

**u(i,k)** (MTZ ordering)
* 14×6 block (i=2..15 by k=1..6). Example in `R19:W32`. Integer 0..14.

#### Sheet **`Calc`**

Create formulas to compute constraints and objectives.

### 2) Key Formulas

Assume:
* `Data!B2:O16` is the c_ij matrix.
* Van `k` x-block is `Vars!B2:P16` for k=1, `Vars!B18:P32` for k=2, etc.

**(a) Route time for van k**

For each van block `x_k`, compute:
```
=SUMPRODUCT(Data!B2:O16, x_k)
```
Example for van 1 in `Calc!B2`:
```
=SUMPRODUCT(Data!B2:O16, Vars!B2:P16)
```

**(b) Assignment (for each customer i=2..15)**

For customer i in row (say row r):
```
=SUM(Vars!Rr:W r)
```
Set equal to 1.

**(c) Linking y(i,k) ≤ δ(k)**

For each i,k:
```
=Vars!Rr - Vars!R$17
```
Constrain ≤ 0.

**(d) Depot usage**

For each van k:

* Leaving Heathrow (row i=1):
```
=SUM(x_k row 1, columns 2..15)
```
Equals δ(k).

* Returning to Heathrow (column j=1):
```
=SUM(x_k column 1, rows 2..15)
```
Equals δ(k).

**(e) Flow/degree for customer j (one in, one out)**

Inbound (sum over i≠j):
```
=SUM(x_k column j, rows 1..15) - x_k(j,j)
```
Equals y(j,k).

Outbound (sum over i≠j):
```
=SUM(x_k row j, columns 1..15) - x_k(j,j)
```
Equals y(j,k).

**(f) Time limit**

For each van k:
```
=SUMPRODUCT(Data!B2:O16, x_k) <= 120
```

**(g) MTZ constraints (for all i≠j, i,j in 2..15)**

Let `u(i,k)` be in `Vars!R19:W32` aligned with customers.
For each k, i, j:
```
=u(i,k) - u(j,k) + 14*x(i,j,k) <= 13
```
Also enforce:
```
u(i,k) >= y(i,k)
u(i,k) <= 14*y(i,k)
```

**(h) Symmetry breaking**

For each k=1..5:
```
SUM(y(:,k)) >= SUM(y(:,k+1))
```

### 3) Solver Settings (Excel Solver)

**Stage 1:**

* Objective cell: `Z1` = `SUM(δ(k))`.
* Minimize.
* Changing cells: all x, y, δ, u blocks.
* Constraints:
  * Assignment sums = 1.
  * Linking y ≤ δ.
  * Depot usage constraints.
  * Flow/degree constraints.
  * Time limit per van.
  * MTZ constraints.
  * Symmetry breaking.
  * Binary: x, y, δ.
  * Integer: u.

**Stage 2:**

* Add `Tmax` cell, e.g., `Z2`.
* Objective: minimize `Tmax`.
* Add constraints:
  * `SUM(δ(k)) = VMIN` (value from Stage 1).
  * For each van k: `RouteTime(k) <= Tmax`.

### 4) Two-stage optimization in Excel

1. Solve Stage 1 to obtain `VMIN = SUM(δ(k))`.
2. Fix `SUM(δ(k)) = VMIN` and solve Stage 2 with objective `Tmax`.

### 5) Subtour detection and cutting-plane (Excel Solver)

Because Excel Solver does not natively enforce subtour elimination, use a **cutting-plane loop**:

1. Solve the model **without** MTZ constraints.
2. Read each van’s `x(i,j,k)` solution and identify subtours (cycles that do not include node 1).
3. For each subtour S (subset of customers), add a cut:
   
   **Subtour cut (for van k):**
   
   `SUM_{i in S} SUM_{j in S} x(i,j,k) <= |S| - 1`
4. Re-solve. Repeat until no subtours appear.

This method mirrors classical branch-and-cut: add violated subtour constraints iteratively until the route for each van is connected to the depot.

---

## Part C – Interpretation (Expected Results)

Using an exact dynamic-programming partitioning of optimal paths, the **expected optimal outcomes** are:

* **Minimum number of vans:** **2**
* **Minimum possible maximum route time (given 2 vans):** **100 minutes**

A feasible partition of customers that attains these values (one of many) is:

* **Van A**: nodes {4, 8, 9, 13, 14, 15} with an optimal path length **100** minutes (starting at Heathrow and returning at zero cost).
* **Van B**: nodes {2, 3, 5, 6, 7, 10, 11, 12} with an optimal path length **99** minutes.

These routes satisfy all constraints:

* **Assignment**: each customer is visited exactly once.
* **Depot usage**: each used van leaves Heathrow once and returns once.
* **Flow/degree**: exactly one incoming and outgoing arc for each visited customer.
* **Time limit**: each route time ≤ 120 minutes.
* **Subtour elimination**: MTZ constraints enforce connectivity to the depot.
* **Symmetry breaking**: non-increasing number of assigned customers by van index.

---

## Files Delivered

* `heathrow_stage1.lp` – lp_solve Stage 1 model.
* `heathrow_stage2.lp` – lp_solve Stage 2 model (set `VMIN` from Stage 1).
* `solution.md` – this document.
