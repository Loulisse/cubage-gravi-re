import os
import shutil
import numpy as np
import laspy
import rasterio
from rasterio.transform import from_origin
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="API de Cubage Suisse")

# ⚠️ Sécurité Web obligatoire pour que la page HTML puisse parler au Python en ligne
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DOSSIER_UPLOAD = "./fichiers_recus"
DOSSIER_SORTIE = "./fichiers_generes"
os.makedirs(DOSSIER_UPLOAD, exist_ok=True)
os.makedirs(DOSSIER_SORTIE, exist_ok=True)

# (Les fonctions de traitement restent les mêmes)
def laz_vers_raster(chemin_laz, chemin_raster_sortie, resolution=0.5):
    las = laspy.read(chemin_laz)
    x, y, z = las.x, las.y, las.z
    x_min, x_max = np.min(x), np.max(x)
    y_min, y_max = np.min(y), np.max(y)
    largeur = int(np.ceil((x_max - x_min) / resolution))
    hauteur = int(np.ceil((y_max - y_min) / resolution))
    grid_z = np.full((hauteur, largeur), np.nan, dtype=np.float32)
    x_idx = ((x - x_min) / resolution).astype(np.int32)
    y_idx = ((y_max - y) / resolution).astype(np.int32)
    valid = (x_idx >= 0) & (x_idx < largeur) & (y_idx >= 0) & (y_idx < hauteur)
    x_idx, y_idx, z_valid = x_idx[valid], y_idx[valid], z[valid]
    indices_tries = np.argsort(z_valid)
    grid_z[y_idx[indices_tries], x_idx[indices_tries]] = z_valid[indices_tries]
    transform = from_origin(x_min, y_max, resolution, resolution)
    with rasterio.open(chemin_raster_sortie, 'w', driver='GTiff', height=hauteur, width=largeur,
                       count=1, dtype=np.float32, crs='EPSG:2056', transform=transform, nodata=np.nan) as dst:
        dst.write(grid_z, 1)

@app.post("/upload-laz/")
async def upload_fichier_laz(file: UploadFile = File(...)):
    chemin_laz = os.path.join(DOSSIER_UPLOAD, file.filename)
    nom_sortie = file.filename.rsplit('.', 1)[0] + ".tif"
    chemin_geotiff = os.path.join(DOSSIER_SORTIE, nom_sortie)
    with open(chemin_laz, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    laz_vers_raster(chemin_laz, chemin_geotiff)
    return {"message": "Fichier traité avec succès !"}

@app.get("/calculer-volume/")
def api_calculer_volume():
    # Simulation pour l'affichage de l'interface
    return {"volume_extrait_m3": 14500.50, "volume_remblai_m3": 3200.20, "solde_m3": -11300.30}

# ⚠️ Code modifié pour Render
if __name__ == "__main__":
    import uvicorn
    # Render donne un port automatique via la variable d'environnement PORT
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
from fastapi.responses import HTMLResponse

@app.get("/", response_class=HTMLResponse)
def lire_index():
    with open("index.html", "r", encoding="utf-8") as f:
        return f.read()