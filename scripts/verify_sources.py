"""Verify the exported source files against the original experiment manifest."""
import hashlib
import json
from pathlib import Path

root = Path(__file__).resolve().parent.parent
manifest = json.loads((root / 'SOURCE_MANIFEST.json').read_text(encoding='utf-8'))
for entry in manifest['copied_files']:
    content = (root / entry['path']).read_bytes()
    if hashlib.sha256(content).hexdigest() != entry['export_sha256']:
        raise SystemExit('Source hash mismatch: ' + entry['path'])
print('Verified publication file hashes:', len(manifest['copied_files']))
