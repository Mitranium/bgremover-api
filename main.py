from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import StreamingResponse
import io
from typing import List
import zipfile

app = FastAPI(title="BGRemover API – Quita fondos al instante")

# Flag para lazy load (carga rembg solo una vez)
rembg_loaded = False
remove_func = None

@app.post("/remove-bg/")
async def remove_background(file: UploadFile = File(...)):
    global rembg_loaded, remove_func
    if not rembg_loaded:
        from rembg import remove  # Import aquí: carga modelo en primer request
        remove_func = remove
        rembg_loaded = True
    
    if not file.content_type.startswith('image/'):
        raise HTTPException(status_code=400, detail="Solo imágenes, porfa (PNG/JPG)")
    
    contents = await file.read()
    if len(contents) == 0:
        raise HTTPException(status_code=400, detail="Archivo vacío o corrupto")
    
    output_bytes = remove_func(contents)
    return StreamingResponse(io.BytesIO(output_bytes), media_type="image/png", headers={"Content-Disposition": f"attachment; filename={file.filename.rsplit('.',1)[0]}_sin_fondo.png"})

# Batch (opcional, pero agrégalo si quieres)
@app.post("/remove-bg-batch/")
async def remove_batch(files: List[UploadFile] = File(...)):
    global rembg_loaded, remove_func
    if not rembg_loaded:
        from rembg import remove
        remove_func = remove
        rembg_loaded = True
    
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        for file in files:
            contents = await file.read()
            output_bytes = remove_func(contents)
            clean_name = f"{file.filename.rsplit('.',1)[0]}_sin_fondo.png"
            zf.writestr(clean_name, output_bytes)
    zip_buffer.seek(0)
    return StreamingResponse(zip_buffer, media_type="application/zip", headers={"Content-Disposition": "attachment; filename=imagenes_limpias.zip"})

# Health check para debug (opcional, Render lo usa)
@app.get("/health")
async def health():
    return {"status": "ok"}
