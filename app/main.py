from fastapi import FastAPI

from app.api.response_model import router as response_model_router


app = FastAPI(title="FastAPI Study")
app.include_router(response_model_router)


@app.get("/")
def read_root() -> dict[str, str]:
    return {"message": "FastAPI study project is ready."}


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}
