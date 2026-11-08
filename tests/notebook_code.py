"""Loads the code of the notebook, so that the tests run exactly what the notebook runs."""
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def notebook_path():
    folder = os.path.join(ROOT, 'notebooks')
    return os.path.join(folder, [f for f in os.listdir(folder) if f.endswith('.ipynb')][0])


def code_cells():
    nb = json.load(open(notebook_path(), encoding='utf-8'))
    return [''.join(c['source']) for c in nb['cells'] if c['cell_type'] == 'code']


def load_definitions(n_cells=3):
    """Executes the first n code cells (imports, inputs and functions) and returns their namespace."""
    namespace = {}
    for source in code_cells()[:n_cells]:
        exec(compile(source, notebook_path(), 'exec'), namespace)
    return namespace
