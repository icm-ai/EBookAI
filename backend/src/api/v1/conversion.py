from fastapi import APIRouter

router = APIRouter(
    prefix="/conversion",
    tags=["conversion"]
)

@router.post("/convert")
async def convert_format():
    """
    Format conversion endpoint
    """
    return {"message": "Format conversion endpoint"}

@router.get("/status/{task_id}")
async def get_conversion_status(task_id: str):
    """
    Get conversion status by task ID
    """
    return {"task_id": task_id, "status": "processing"}