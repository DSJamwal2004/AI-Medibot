from fastapi import APIRouter

router = APIRouter()

@router.get("/status")
def health_check():
    return {
        "status": "OK",
        "service": "AI MediBot Backend"
    }
