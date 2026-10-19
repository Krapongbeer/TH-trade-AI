import os
import sys
from pathlib import Path

# Ensure project root is in sys.path
root_dir = Path(__file__).resolve().parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from app import web_app

# Expose web_app directly as ASGI application
app = web_app
application = web_app

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8555))
    uvicorn.run(web_app, host="0.0.0.0", port=port, log_level="info")
