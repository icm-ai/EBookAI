from fastapi import FastAPI
from api.v1 import conversion, ai, typesetting

app = FastAPI(
    title="EBookAI API",
    description="A modern e-book processing platform integrated with AI capabilities",
    version="0.1.0"
)

# Include API routers
app.include_router(conversion.router)
app.include_router(ai.router)
app.include_router(typesetting.router)

@app.get("/")
async def root():
    return {"message": "Welcome to EBookAI API"}

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)