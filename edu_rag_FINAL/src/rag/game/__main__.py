"""
Usage:
    python -m src.rag.game          # Launch game UI on :7861
    python -m src.rag.game --port 8080
"""
import sys

from .ui_game import main

if __name__ == "__main__":
    main()
