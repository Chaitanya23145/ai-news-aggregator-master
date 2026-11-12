import sys
import os

# Add the project root to the sys.path so modules under 'app' import cleanly
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from app.api import app

# Vercel ASGI entrypoint
handler = app

