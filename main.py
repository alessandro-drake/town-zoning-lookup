# main.py
# This is where we actually run all the files from---it tells python what to run where.

# main.py --------------------------------------------------------
"""
Launch script for the whole zoning-tool stack.
Run with:  python main.py   (or set as your IDE debug target)
"""

import os
from ordinance_finder import app      # the Flask app constructed there
#   (ordinance_finder already imported and registered analysis_api)

if __name__ == "__main__":
    host = os.getenv("FLASK_HOST", "0.0.0.0")
    port = int(os.getenv("FLASK_PORT", 8000))
    debug = bool(os.getenv("FLASK_DEBUG", "1") == "1")

    print(f"Starting Flask on http://{host}:{port}  (debug={debug})")
    app.run(host=host, port=port, debug=debug)
