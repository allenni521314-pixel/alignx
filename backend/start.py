"""Start AlignX backend with env vars."""
import os, sys

# Read key from command line arg
if len(sys.argv) > 1:
    os.environ["SCRAPERAPI_KEY"] = sys.argv[1]

from app.main import app
