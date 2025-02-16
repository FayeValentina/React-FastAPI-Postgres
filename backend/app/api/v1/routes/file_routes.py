from fastapi import APIRouter, File, Form, UploadFile
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
from typing import Annotated, List, Optional
from datetime import datetime

from app.schemas import (
    FileUploadResponse,
    MultipleFilesResponse,
    FileWithMetadataResponse
)

router = APIRouter(prefix="/files", tags=["files"])

@router.post("/upload", response_model=FileUploadResponse)
async def upload_file(
    file: Annotated[UploadFile, File(description="A file read as UploadFile")],
    description: Annotated[Optional[str], Form(description="File description")] = None,
    tags: Annotated[str, Form(description="Comma separated tags")] = "",
) -> JSONResponse:
    """上传单个文件"""
    contents = await file.read()
    file_size = len(contents)
    await file.seek(0)
    
    tag_list = [tag.strip() for tag in tags.split(",") if tag.strip()]
    
    file_info = {
        "filename": file.filename,
        "content_type": file.content_type,
        "file_size": file_size,
        "description": description,
        "tags": tag_list,
        "upload_time": datetime.now(),
        "file_metadata": {
            "headers": dict(file.headers),
            "content_type": file.content_type,
            "size": file_size,
            "extension": file.filename.split(".")[-1] if "." in file.filename else None
        }
    }
    
    json_compatible_data = jsonable_encoder(
        file_info,
        exclude_unset=True,
        custom_encoder={
            datetime: lambda dt: dt.strftime("%Y-%m-%d %H:%M:%S"),
            bytes: lambda b: b.decode("utf-8", errors="ignore")
        }
    )
    
    return JSONResponse(content=json_compatible_data)

@router.post("/upload-files", response_model=MultipleFilesResponse)
async def upload_files(
    files: Annotated[List[bytes], File(description="Multiple files as bytes")],
    fileb: Annotated[bytes, File(description="Single file as bytes")],
) -> MultipleFilesResponse:
    """上传多个文件"""
    return {
        "file_sizes": [len(file) for file in files],
        "fileb_size": len(fileb),
        "message": f"Successfully uploaded {len(files) + 1} files",
        "total_size": sum(len(file) for file in files) + len(fileb)
    }

@router.post("/upload-with-metadata", response_model=FileWithMetadataResponse)
async def upload_file_with_metadata(
    file: Annotated[bytes, File()],
    filename: Annotated[str, Form()],
    content_type: Annotated[str, Form()] = "application/octet-stream",
    description: Annotated[Optional[str], Form()] = None
) -> FileWithMetadataResponse:
    """上传带元数据的文件"""
    return {
        "filename": filename,
        "content_type": content_type,
        "description": description,
        "file_size": len(file),
        "first_bytes": file[:10].hex(),
        "message": "File successfully processed"
    } 