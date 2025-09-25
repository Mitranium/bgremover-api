from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse
import io
from typing import List
import zipfile
import logging  # Para logs

# Configura logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="BGRemover API – Quita fondos al instante")

# Flag para lazy load
rembg_loaded = False
remove_func = None

# Startup event: Intenta pre-cargar rembg (no crashea si falla)
@app.on_event("startup")
async def startup_event():
    global rembg_loaded, remove_func
    try:
        from rembg import remove
        remove_func = remove
        rembg_loaded = True
        logger.info("✅ rembg cargado en startup")
    except Exception as e:
        logger.error(f"❌ Error cargando rembg en startup: {e}")
        # No crashea: sigue sin él, pero endpoints fallarán graceful

# Health check mejorado
@app.get("/health")
async def health():
    global rembg_loaded
    status = "ok" if rembg_loaded else "partial (rembg pending)"
    return {"status": status, "rembg_loaded": rembg_loaded}

@app.post("/remove-bg/")
async def remove_background(file: UploadFile = File(...)):
    global rembg_loaded, remove_func
    
    # Lazy load con try-except full
    if not rembg_loaded:
        try:
            from rembg import remove
            remove_func = remove
            rembg_loaded = True
            logger.info("✅ rembg cargado en request")
        except Exception as e:
            logger.error(f"❌ Error cargando rembg: {e}")
            return JSONResponse(status_code=500, content={"error": f"Falló cargar el modelo: {str(e)}. Intenta de nuevo."})
    
    if not file.content_type.startswith('image/'):
        raise HTTPException(status_code=400, detail="Solo imágenes, porfa (PNG/JPG)")
    
    try:
        contents = await file.read()
        if len(contents) == 0:
            raise HTTPException(status_code=400, detail="Archivo vacío o corrupto")
        
        output_bytes = remove_func(contents)
        return StreamingResponse(io.BytesIO(output_bytes), media_type="image/png", 
                                 headers={"Content-Disposition": f"attachment; filename={file.filename.rsplit('.',1)[0]}_sin_fondo.png"})
    except Exception as e:
        logger.error(f"❌ Error procesando imagen: {e}")
        return JSONResponse(status_code=500, content={"error": f"Error en procesamiento: {str(e)}"})

# Batch similar, con mismo handling
@app.post("/remove-bg-batch/")
async def remove_batch(files: List[UploadFile] = File(...)):
    global rembg_loaded, remove_func
    
    if not rembg_loaded:
        try:
            from rembg import remove
            remove_func = remove
            rembg_loaded = True
            logger.info("✅ rembg cargado en batch request")
        except Exception as e:
            logger.error(f"❌ Error cargando rembg: {e}")
            return JSONResponse(status_code=500, content={"error": f"Falló cargar el modelo: {str(e)}"})
    
    try:
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
            for file in files:
                contents = await file.read()
                if len(contents) == 0:
                    continue  # Skip vacíos
                output_bytes = remove_func(contents)
                clean_name = f"{file.filename.rsplit('.',1)[0]}_sin_fondo.png"
                zf.writestr(clean_name, output_bytes)
                logger.info(f"✅ Procesada: {file.filename}")
        zip_buffer.seek(0)
        return StreamingResponse(zip_buffer, media_type="application/zip", 
                                 headers={"Content-Disposition": "attachment; filename=imagenes_limpias.zip"})
    except Exception as e:
        logger.error(f"❌ Error en batch: {e}")
        return JSONResponse(status_code=500, content={"error": f"Error en batch: {str(e)}"})
