# Pipe Dream Lab

A local research application for ordinary reduced pipe dreams of
`w₀,₂ = [1, 2, N−2, N−3, …, 3, N−1, N]`, for `5 ≤ N ≤ 1000`.

## Run

Run `main.py` with the PyCharm Run button, then visit **http://127.0.0.1:8000**.
Alternatively, from the project directory in PowerShell:

```powershell
.\.venv\Scripts\python.exe main.py
```

Python 3.10+; no third-party packages or frontend build step required.
Use `--port 8001` to change the port, or `--db path.sqlite3` for another database.
The server binds only to your computer. Stop it with Ctrl+C or PyCharm's Stop button.

## Use

1. Set N, **Number of random moves** (0–100,000; default 1,000), **Move family**, and optionally a seed, then generate. **General ladder + chute** is the default and includes longer rectangles and inverses. **Elementary 2×2 only** retains the faster, restricted sampler. The count is successful moves in total. Zero gives the bottom diagram. Every generated diagram is independently validated.
2. Left-click a tile to highlight it and display both participating pipe numbers and their directions. Boundary arcs without a numbered pipe are labeled explicitly. Dragging pans the diagram without changing tile selection. Right-click a strand to color or inspect it. At a cross, right-click near the horizontal or vertical strand to select that pipe. Pipe inspection reports every turn and fills the five-turn input when applicable.
3. Right-click a tile or axis index, choose a color directly in the context menu, then click **Color pipe**, **Color row**, or **Color column**. The context menu also includes tile flipping and pipe inspection; there is no separate sidebar color picker.
4. Wheel to zoom; drag to pan. **Fit** shows the whole staircase, **Tile view** returns to readable tiles at the upper-left. Below six pixels per tile the display is a cross/elbow overview, not a detailed strand rendering.
5. Enter a name and save. Saved diagrams include tile coordinates (compact row encoding), colors, seed, and validation. Load from the library, or export/import JSON.
6. Prescribe a pipe by its left entrance number and exactly five `[row,column]` turns, ordered along its path. **Search seconds** defaults to 180 and accepts 0.1–3,600 seconds (one hour). The elapsed-time display runs while the request is active. **Cancel search** stops an active completion search; the current diagram remains unchanged. The time limit and cancellation apply to finding a completion, not the subsequent random-move batch. Only a verified completion replaces the current diagram.
7. Click **Apply moves to current diagram** to run the selected number of additional moves from the selected family on the displayed diagram. Colors and viewport are retained; Undo restores the previous diagram. The result shows requested/applied counts, forward ladder/chute and inverse totals, and the number using rectangles larger than 2×2. If no legal move exists (for example at N=5), it explicitly reports that no moves were available.

For prescribed-pipe generation, the requested moves run after a completion is found and preserve that pipe. Its lock survives saving/loading and JSON export/import. Manual tile edits release this lock. Older saved diagrams without constraint metadata have no pipe lock. Randomization requires a valid reduced diagram.

The same starting board, seed, move count, move family, and pipe constraint reproduce the same walk. Inverse moves can undo earlier moves, so the move count is not the number of distinct diagrams visited or the number of tiles that differ at the end. More moves do not guarantee a more uniformly random result.

**Try separated turns:** Generate with N=12, seed=1, 2,000 moves, and General mode. Inspect pipe 8: its turns are `[[8,1],[6,1],[6,3],[4,3],[4,5]]`. All consecutive turns are two squares apart. This example is covered by a regression test.

Flipping one tile generally changes the permutation or reducedness. Such diagrams remain editable and saveable, with an explicit invalid badge. **Ctrl+Z** (or **Cmd+Z** on macOS) and the **Undo** button restore up to 20 changes: tile flips, pipe/row/column coloring, clearing colors, and randomization batches. In text inputs the shortcut keeps its normal text-editing behavior. Undo is disabled while a backend action is running. Generating, loading, or importing a diagram starts a new undo history. The staircase's antidiagonal elbows cannot be flipped: they form its boundary.

## Mathematical conventions

### Axis labels and coordinate input

The **Axis labels** selector offers **Both** (default), **Black · pipe connections**, and **Blue · triangulation edges**. With both visible, black is the outer bar and blue is the inner bar on each axis.

| Labels | X axis, left to right | Y axis, top to bottom |
|---|---|---|
| Black pipe connections | `1, 2, N−2, N−3, …, 3, N−1, N` for a valid target diagram | `1, 2, …, N` |
| Blue triangulation edges | `1, 2, …, N` | `N, N−1, …, 1` |

Black top labels are computed from the actual routed pipes, so they also reflect connectivity after manual tile edits. Label text stays black or blue even when a row, column, or pipe is colored. Zooming out thins the displayed labels to avoid overlap; zoom in to see every index.

Right-click a black label to color/inspect its connected pipe or color the corresponding grid row/column. Right-click a blue label to color its grid row/column. Both refer to the same grid; switching views preserves colors, tile edits, zoom and undo history. Tile inspection and pipe-turn inspection report grid, black-axis, and blue-axis coordinates together.

Prescribed turns have a separate **Turn coordinates** selector: grid `(row,column)`, black `(Y,X)`, or blue `(Y,X)`. Choose the format before pasting coordinates; changing this selector converts existing valid input. For grid coordinate `(r,c)`, blue coordinates are `(N+1−r,c)` and black coordinates for the target are `(r,w₀,₂(c))`. Prescribed black coordinates always refer to the target permutation, even if the current displayed diagram is an invalid draft. The **Entrance pipe** field uses the black pipe number and is automatically derived from the first turn when generating a prescribed diagram: Y for grid/black, or N+1−Y for blue. It can still be entered manually for pipe inspection. Submission reads the visible coordinate selector directly. Loading a saved prescribed diagram restores its turns in the selected format and restores its entrance pipe. The backend and saved/exported diagrams continue to use canonical grid coordinates; view selection does not reinterpret saved data.

### Grid and tiles

Rows are numbered downwards and columns rightwards, both starting at 1.
The staircase contains `(r,c)` with `r+c ≤ N+1`; its row lengths are N through 1.
Pipes enter from the west in rows 1 through N and leave through the north.
A cross connects west–east and south–north. An elbow connects west–north and south–east. The outer antidiagonal's second arc belongs outside the N tracked pipes and is omitted in the strand view.

A reduced pipe dream has no pair of pipes crossing twice. For this target it has exactly
`(N−4)(N−5)/2` crosses. The validator reads crosses row by row, right to left, using the adjacent transposition `s_(r+c−1)`, then compares the product to the target. Reducedness is independently tested by comparing cross count to the product's inversion count. This agrees with physical pipe tracing in the tests; the target is an involution.

These are ordinary pipe dreams, not bumpless pipe dreams (which use a different tile set).
See the definitions and local moves in [Gold et al., Crystal Chute Moves on Pipe Dreams](https://fpsac2024.rub.de/public/extended_abstracts/gold.pdf).

## Design

| Component | Responsibility |
|---|---|
| `pipedream/model.py` | Generation, exact constraints, tracing, serialization, independent validation |
| `pipedream/moves.py` | General ladder/chute rectangle enumeration and incremental move index |
| `pipedream/server.py` | Loopback JSON API, input validation, SQLite persistence |
| `static/app.js` | Canvas rendering, viewport, routing labels, hit testing and annotation |
| `main.py` | Application entry point |
| `tests/` | Mathematical, persistence, HTTP and scale checks |

Boards use triangular byte arrays internally. JSON rows are strings, with `1` for a cross and `0` for an elbow. Thus coordinate `(r,c)` is `rows[r−1][c−1]`. A size-1000 board contains 500,500 tiles, taking about 0.5 MB before compression. SQLite stores compressed JSON snapshots using parameterized statements and explicit connection cleanup.

The browser stores strand identities in typed arrays and draws only visible tiles at detailed zoom. At overview scale it caches a raster. Pan/zoom redraws run through animation frames. Backend generation is limited to one active request; bounded constrained search keeps other HTTP requests available.

### Algorithms and limitations

**Random generation:** Start from the bottom reduced pipe dream, whose crosses in row r occupy columns `1,…,N−r−2` for `3 ≤ r ≤ N−3`. Apply the requested number M of successful moves. Each step chooses uniformly among indexed legal moves; samples of diagrams are not uniform.

**General mode:** A ladder rectangle has two adjacent columns and any height of at least two. NW and SE are elbows, every interior row is two crosses, and exactly one of SW/NE is a cross. A forward ladder move moves the SW cross to NE; its inverse reverses that exchange. A chute rectangle is the transpose: two adjacent rows and any width of at least two, with the forward move from NE to SW. All lengths and both directions are included. The shared 2×2 case is indexed only once, as a ladder/inverse ladder move. These moves preserve the represented permutation and reducedness. A global index is built in O(N²); after each move only affected adjacent row/column strips are rescanned. Expected walk time is O(N² + MN), with O(N²) board/index storage. This is slower than elementary mode, but avoids rescanning the entire board at every step.

**Elementary mode:** Only 2×2 rectangles are allowed. This preserves antidiagonal cross counts and can never leave the elementary-move component of its starting diagram, regardless of the count. Its incremental square index gives O(N² + M) expected time. Both modes stop early only if no legal move exists. Returned seeds, move counts and mode make runs reproducible for this implementation.

**Sampling is biased.** General ladder moves can connect the bottom diagram to every reduced pipe dream of the same permutation when no pipe is locked; see [Weigandt, Theorem 2.4](https://numdam.org/item/10.5802/alco.27.pdf). A finite random walk is not guaranteed to visit every diagram or produce separated turns on every run. Locking a prescribed pipe can restrict reachability. Choosing uniformly among legal moves does not sample diagrams uniformly; do not interpret sample frequencies as uniform combinatorial probabilities.

**Prescribed pipe:** Turn geometry fixes elbow tiles at turns and crosses along straight segments, including entrance and exit segments. Completion runs in three stages:

1. Return the bottom diagram if it already contains the fixed pipe.
2. Try greedy completion in both staircase-word directions, in a seed-selected order. At each free tile, take a cross whenever its adjacent swap removes an inversion; respect all forced elbows/crosses. The reversed pass is valid here because the target permutation is an involution. Each pass is O(N²). Greedy failure does not imply impossibility.
3. If both passes fail, run exact iterative backtracking. Prefer an available cross, while retaining the elbow alternative for backtracking. Reject branches when the number of needed crosses exceeds the available suffix capacity, is smaller than the number of mandatory suffix crosses, or when a completed row leaves a permutation position incorrect that future rows can no longer change. This last check rejects doomed branches much earlier. The old rule that randomly skipped available crosses 10% of the time has been removed.

The solver starts with the target residual permutation and removes a transposition only at a descent, so every chosen cross decreases inversion count. A successful pass satisfies every fixed tile and reduces the residual to the identity. The server independently validates the returned diagram before displaying it. Cancellation and deadlines are checked during greedy and backtracking passes. Timeout/cancellation return an unknown result, never a false impossibility claim. Exhausting the exact search proves that no completion exists.

After completion, the requested random moves preserve the fixed pipe. The seed controls the initial greedy direction and the later random walk; completion is not uniform conditional sampling.

**Regression benchmark:** N=100, pipe=39, turns `[[39,19],[19,19],[19,39],[1,39],[1,62]]` timed out after 180 seconds in the original solver. The improved solver completed and validated this prescription for two seeds in about 0.005 seconds total on the development machine. This is completion time, excluding HTTP and subsequent random moves; other prescriptions may remain difficult.

The constrained solver is exact when it returns a solution or finishes exhaustively. Its fallback still has exponential worst-case runtime. It accepts N=1000, but **arbitrary prescribed-pipe generation at that size is not guaranteed to finish**, even with the longer budget. A timeout is explicitly reported as unknown, never as impossible.

**Editing:** This is a research editor, so invalid drafts are retained intentionally. A single tile toggle cannot generally stay in the same reduced-permutation class; a future validity-preserving edit mode would expose multi-tile moves.

The server is a single-user local application, not a production public hosting service. There is no authentication or multi-user editing synchronization.

## API

| Method/path | Input/result |
|---|---|
| `POST /api/generate` | `{n, seed?, moves?, mode?}`; add `{pipe, turns, seconds?}` for constraints |
| `POST /api/randomize` | Document plus `{moves, seed?, mode?}` → validated diagram with colors and prescribed-pipe lock retained |
| `POST /api/cancel` | `{}` → `{cancel_requested: boolean}` for the currently active completion search |
| `POST /api/validate` | `{n, rows, annotations?}` → validated document |
| `POST /api/toggle` | Document plus `{row,column}` → edited validated document |
| `POST /api/trace` | Document plus `{pipe}` → cells, turns and exit |
| `POST /api/save` | Document plus `{name}` → saved ID |
| `GET /api/saved` | Saved diagram metadata |
| `GET /api/saved/{id}` | Saved document |

Bad inputs return 400; constrained timeout returns 408 with `status: "unknown"`; cancellation returns 409 with `status: "cancelled"`; a concurrent generation also returns 409. `seconds` defaults to 180 and must be a number from 0.1 to 3,600. Existing diagrams remain unchanged on generation failure or cancellation. Cancellation is for the active search of this single-user local application.

Generation/randomization responses contain `randomization: {requested, applied, ladder, chute, inverse, inverse_ladder, inverse_chute, non_elementary, stalled, mode}` describing the last batch, and `constraint: {pipe, turns}` (or null). `ladder + chute + inverse = applied`; `inverse` includes both inverse categories. `non_elementary` counts moves in either direction with rectangles larger than 2×2. Save/load retains this metadata. `moves` defaults to 1,000 and must be an integer from 0 to 100,000. `mode` is `general` (default) or `elementary`.

## Verification

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Tests cover physical routing versus the target, seeded variety, multiple sizes, every one-cross graph and every geometric five-turn prescription at N=6, constrained successes at N=7, invalid edits/inputs, database round trips, HTTP operations, and N=1000. General-move tests compare the full reachable component at N=7 with exhaustive independent enumeration, validate moves and their inverses, compare incremental indexes to fresh enumeration, and verify escape from the elementary component. With 1,000 general moves at N=1000, generation/validation/serialization took about 1.24 seconds on the development machine; this is not a browser latency measurement. Large move counts can take substantially longer.

Browser automation was unavailable during implementation. The UI still needs a hands-on visual check of hit testing, colors, zoom and pan in your browser.
`tests/frontend.cjs` also checks JavaScript routing and both rendering modes using a minimal DOM/canvas stand-in. With Node installed and the server running, execute `node tests/frontend.cjs`.
