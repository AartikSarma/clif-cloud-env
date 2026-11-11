"""Run the whole analysis with one command:

    uv run run.py                   # this site's CLIF data (from the site config)
    uv run run.py --synthetic 3.0   # synthetic CLIF 3.0 data
    uv run run.py --synthetic 2.1   # synthetic CLIF 2.1 data
"""

import sys

from clifkit.cli import main

if __name__ == "__main__":
    sys.exit(main(["run", *sys.argv[1:]]))
