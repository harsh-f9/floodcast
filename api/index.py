import sys
import os

# Add backend directory to path so main.py and modules can be imported
backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from main import app

# Expose app for Vercel serverless function execution
app = app
