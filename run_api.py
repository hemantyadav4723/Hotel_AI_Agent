"""Start the YADAV HOTEL FastAPI backend.

Usage from the Hotel_AI_Agent directory:
    python run_api.py
"""

import uvicorn


if __name__ == "__main__":
    uvicorn.run("api.app:app", host="127.0.0.1", port=8000, reload=False)
