"""FLX4 Control — entry point."""
import sys
import os

# Ensure the project root is on the path when run directly
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from flx4control.gui import main

if __name__ == "__main__":
    sys.exit(main())
