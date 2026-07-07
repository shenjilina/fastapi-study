from typing import Annotated

from fastapi import APIRouter, File, UploadFile

router = APIRouter()


@router.post("/upload/")
async def create_upload_file(file: Annotated[UploadFile, File()]):
    return {"filename": file.filename}
