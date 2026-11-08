import nbformat
import pytest

from notebook_code import notebook_path


def test_committed_notebook_is_valid_and_executed_without_errors():
    nb = nbformat.read(notebook_path(), as_version=4)
    nbformat.validate(nb)
    code = [c for c in nb.cells if c.cell_type == 'code']
    assert all(c.execution_count is not None for c in code), 'every code cell of the committed notebook was executed'
    assert sum(bool(c.outputs) for c in code) >= len(code) - 3  # only the cells of imports, inputs and functions print nothing
    assert not any(o.output_type == 'error' for c in code for o in c.outputs)


@pytest.mark.slow
def test_notebook_executes_end_to_end(tmp_path):
    from nbclient import NotebookClient
    nb = nbformat.read(notebook_path(), as_version=4)
    NotebookClient(nb, timeout=1800, kernel_name='python3', resources={'metadata': {'path': str(tmp_path)}}).execute()
    assert not any(o.output_type == 'error' for c in nb.cells if c.cell_type == 'code' for o in c.outputs)
