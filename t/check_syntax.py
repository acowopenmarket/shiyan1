import ast
from pathlib import Path
ast.parse(Path(__file__).with_name('run_experiment.py').read_text(encoding='utf-8'))
print('syntax OK')
