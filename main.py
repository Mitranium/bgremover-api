from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse
import io
from typing import List
import zipfile
import logging  # Para logs en Render

# Configura logging verbose
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="BGRemover API – Quita fondos al instante")

# Flag para lazy load (solo en requests)
rembg_loaded = False
remove_func = None

# Health check (sin rembg, para que sea instantáneo)
@app.get("/health")
async def health():
    global rembg_loaded
    status = "ok (ready to load rembg on first request)" if not rembg_loaded else "ok (rembg loaded)"
    logger.info(f"Health check: {status}")
    return {"status": status, "rembg_loaded": rembg_loaded}

@app.post("/remove-bg/")
async def remove_background(file: UploadFile = File(...)):
    global rembg_loaded, remove_func
    
    # Lazy load con logs y try-except
    if not rembg_loaded:
        try:
            logger.info("🔄 Cargando rembg por primera vez...")
            from rembg import remove  # Import directo
            remove_func = remove
            rembg_loaded = True
            logger.info("✅ rembg cargado exitosamente con u2netp")
        except Exception as e:
            logger.error(f"❌ Error cargando rembg: {e}")
            return JSONResponse(status_code=500, content={"error": f"Falló cargar el modelo: {str(e)}. Intenta de nuevo en unos segs."})
    
    if not file.content_type.startswith('image/'):
        raise HTTPException(status_code=400, detail="Solo imágenes, porfa (PNG/JPG)")
    
    try:
        logger.info(f"Procesando imagen: {file.filename}")
        contents = await file.read()
        if len(contents) == 0:
            raise HTTPException(status_code=400, detail="Archivo vacío o corrupto")
        
        # Usa remove directo con modelo liviano (no session)
        output_bytes = remove_func(contents, model_name='u2netp')
        logger.info(f"✅ Procesada: {file.filename}")
        return StreamingResponse(io.BytesIO(output_bytes), media_type="image/png", 
                                 headers={"Content-Disposition": f"attachment; filename={file.filename.rsplit('.',1)[0]}_sin_fondo.png"})
    except Exception as e:
        logger.error(f"❌ Error procesando {file.filename}: {e}")
        return JSONResponse(status_code=500, content={"error": f"Error en procesamiento: {str(e)}"})

# Batch igual, lazy
@app.post("/remove-bg-batch/")
async def remove_batch(files: List[UploadFile] = File(...)):
    global rembg_loaded, remove_func
    
    if not rembg_loaded:
        try:
            logger.info("🔄 Cargando rembg para batch...")
            from rembg import remove
            remove_func = remove
            rembg_loaded = True
            logger.info("✅ rembg cargado para batch con u2netp")
        except Exception as e:
            logger.error(f"❌ Error cargando rembg: {e}")
            return JSONResponse(status_code=500, content={"error": f"Falló cargar el modelo: {str(e)}"})
    
    try:
        logger.info(f"Procesando batch de {len(files)} archivos")
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
            for file in files:
                contents = await file.read()
                if len(contents) == 0:
                    logger.warning(f"Skip: {file.filename} vacío")
                    continue
                # Usa remove directo con modelo liviano
                output_bytes = remove_func(contents, model_name='u2netp')
                clean_name = f"{file.filename.rsplit('.',1)[0]}_sin_fondo.png"
                zf.writestr(clean_name, output_bytes)
                logger.info(f"✅ Batch: {file.filename}")
        zip_buffer.seek(0)
        logger.info("✅ Batch completado")
        return StreamingResponse(zip_buffer, media_type="application/zip", 
                                 headers={"Content-Disposition": "attachment; filename=imagenes_limpias.zip"})
    except Exception as e:
        logger.error(f"❌ Error en batch: {e}")
        return JSONResponse(status_code=500, content={"error": f"Error en batch: {str(e)}"})
