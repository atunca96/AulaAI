import os
import shutil
import logging
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse

from services import pipeline_v2
from services import legacy

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = FastAPI(title="PDF Curriculum Extraction Pipeline")

os.makedirs("temp", exist_ok=True)

async def _handle_pdf_upload(file: UploadFile, processor_func, pipeline_name: str):
    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")
        
    temp_file_path = f"temp/{file.filename}"
    
    try:
        # Save uploaded file to temp path
        with open(temp_file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        logger.info(f"PIPELINE: {pipeline_name}")
        result = processor_func(temp_file_path)
            
        return JSONResponse(content=result)
        
    except RuntimeError as e:
        logger.error(f"RuntimeError processing {file.filename}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    except ValueError as e:
        logger.error(f"ValueError processing {file.filename}: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error processing {file.filename}: {e}")
        raise e
    finally:
        # Clean up temp file
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)

@app.post("/process-pdf")
async def api_process_pdf_legacy(file: UploadFile = File(...)):
    return await _handle_pdf_upload(file, legacy.process, "LEGACY")

@app.post("/v2/process-pdf")
async def api_process_pdf_v2(file: UploadFile = File(...)):
    return await _handle_pdf_upload(file, pipeline_v2.process, "V2")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
