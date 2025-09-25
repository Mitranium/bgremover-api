from fastapi import FastAPI, File, UploadFile, HTTPException
from rembg import remove
import io

app = FastAPI(title="BGRemover API – Quita fondos al instante")

@app.post("/remove-bg/")
async def remove_background(file: UploadFile = File(...)):
    if not file.content_type.startswith('image/'):
        raise HTTPException(status_code=400, detail="Solo imágenes, porfa (PNG/JPG)")
    
    # Lee bytes
    contents = await file.read()
    if len(contents) == 0:
        raise HTTPException(status_code=400, detail="Archivo vacío o corrupto")
    
    # Procesa
    output_bytes = remove(contents)
    
    # Devuelve como file (o JSON con base64 si prefieres)
    return StreamingResponse(io.BytesIO(output_bytes), media_type="image/png", headers={"Content-Disposition": f"attachment; filename={file.filename.rsplit('.',1)[0]}_sin_fondo.png"})

# Para batch: Añade esto después si quieres
@app.post("/remove-bg-batch/")
async def remove_batch(files: list[UploadFile] = File(...)):
    results = []
    for file in files:
        # Mismo proceso...
        output_bytes = remove(await file.read())
        results.append({"filename": file.filename, "data": output_bytes})  # O genera ZIP
    # Lógica para ZIP si son muchos
    return {"message": "Batch procesado", "count": len(results)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
