from app import web_app as app
from app import web_app

if __name__ == "__main__":
    import os
    import uvicorn
    port = int(os.environ.get("PORT", 8555))
    uvicorn.run(web_app, host="0.0.0.0", port=port)
