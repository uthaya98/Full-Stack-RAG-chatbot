import os
from app.chat_main import app
from mangum import Mangum

# Create the Lambda handler (used only in AWS Lambda)
handler = Mangum(app)

# When running locally, use FastAPI's built-in server (Uvicorn)
if os.getenv("ENV") == "local":
    import uvicorn
    if __name__ == "__main__":
        print("🚀 Running FastAPI locally on http://0.0.0.0:8000")
        uvicorn.run(app, host="0.0.0.0", port=8000)
