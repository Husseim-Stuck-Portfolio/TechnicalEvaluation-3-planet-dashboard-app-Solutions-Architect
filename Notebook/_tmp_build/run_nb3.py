"""Execute the code cells of a notebook in one namespace (no Jupyter needed) and store the outputs in the .ipynb.

usage: python run_nb3.py <notebook.ipynb>   (run from the notebook's folder, so relative paths behave as in Jupyter)
"""
import base64, contextlib, io, json, sys, time, traceback
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

path = sys.argv[1]
nb = json.load(open(path))
ns = {"__name__": "__main__"}
count = 0


class Display:
    def __init__(self):
        self.events, self.buf = [], io.StringIO()

    def flush(self):
        text = self.buf.getvalue()
        if text:
            self.events.append({"output_type": "stream", "name": "stdout", "text": text.splitlines(keepends=True)})
        self.buf = io.StringIO()

    def __call__(self, obj):
        self.flush()
        data = {"text/plain": repr(obj).splitlines(keepends=True)}
        if hasattr(obj, "_repr_html_"):
            data["text/html"] = obj._repr_html_().splitlines(keepends=True)
        self.events.append({"output_type": "display_data", "data": data, "metadata": {}})


for cell in nb["cells"]:
    if cell["cell_type"] != "code":
        continue
    src = "".join(cell["source"])
    cell["outputs"], cell["execution_count"] = [], None
    if not src.strip():
        continue
    count += 1
    d = Display()
    ns["display"] = d
    t0 = time.time()
    with contextlib.redirect_stdout(d.buf):
        exec(compile(src, f"<cell {count}>", "exec"), ns)
    d.flush()
    for num in plt.get_fignums():
        fig = plt.figure(num)
        png = io.BytesIO()
        fig.savefig(png, format="png", dpi=72, bbox_inches="tight")
        d.events.append({"output_type": "display_data", "metadata": {},
                         "data": {"image/png": base64.b64encode(png.getvalue()).decode(), "text/plain": ["<Figure>"]}})
    plt.close("all")
    cell["outputs"], cell["execution_count"] = d.events, count
    print(f"cell {count} ok ({time.time() - t0:.1f}s, {len(d.events)} outputs)", file=sys.stderr)

with open(path, "w") as fh:
    json.dump(nb, fh, indent=1, ensure_ascii=False)
    fh.write("\n")
