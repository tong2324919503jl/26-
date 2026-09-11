"""Problem 3 entry point, independent of the caller's working directory."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from problem3.run import main

if __name__ == '__main__':
    raise SystemExit(main(3))
