# Compatibility entry: scans all three repositories and first-party builds.
from pathlib import Path
import runpy
runpy.run_path(str(Path(__file__).with_name('security-scan.py')),run_name='__main__')
