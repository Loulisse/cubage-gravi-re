import os
import shutil
import numpy as np
import laspy
import rasterio
from rasterio.transform import from_origin
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
import ezdxf
from PIL import Image

app = FastAPI(title="API de Cubage Pro Suisse")

# Sécurité obligatoire pour le web
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

# --- 1. FONCTION : TRANSFORMATION LAZ EN RASTER ---
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
    
    indices_tries = np.argsort(z[valid])
    grid_z[y_idx[valid][indices_tries], x_idx[valid][indices_tries]] = z[valid][indices_tries]
    
    transform = from_origin(x_min, y_max, resolution, resolution)
    with rasterio.open(chemin_raster_sortie, 'w', driver='GTiff', height=hauteur, width=largeur,
                       count=1, dtype=np.float32, crs='EPSG:2056', transform=transform, nodata=np.nan) as dst:
        dst.write(grid_z, 1)

# --- 2. FONCTION : TRANSFORMATION DXF TIN EN RASTER ---
def dxf_tin_vers_raster(chemin_dxf, chemin_raster_sortie, resolution=0.5):
    doc = ezdxf.readfile(chemin_dxf)
    msp = doc.modelspace()
    points_x, points_y, points_z = [], [], []
    
    for face in msp.query('3DFACE'):
        for i in range(4):
            sommet = face.get_dxf_attrib(f'vtx{i}')
            if sommet:
                points_x.append(sommet.x)
                points_y.append(sommet.y)
                points_z.append(sommet.z)
                
    x, y, z = np.array(points_x), np.array(points_y), np.array(points_z)
    x_min, x_max = np.min(x), np.max(x)
    y_min, y_max = np.min(y), np.max(y)
    
    largeur = int(np.ceil((x_max - x_min) / resolution))
    hauteur = int(np.ceil((y_max - y_min) / resolution))
    grid_z = np.full((hauteur, largeur), np.nan, dtype=np.float32)
    
    x_idx = ((x - x_min) / resolution).astype(np.int32)
    y_idx = ((y_max - y) / resolution).astype(np.int32)
    valid = (x_idx >= 0) & (x_idx < largeur) & (y_idx >= 0) & (y_idx < hauteur)
    
    grid_z[y_idx[valid], x_idx[valid]] = z[valid]
    
    transform = from_origin(x_min, y_max, resolution, resolution)
    with rasterio.open(chemin_raster_sortie, 'w', driver='GTiff', height=hauteur, width=largeur,
                       count=1, dtype=np.float32, crs='EPSG:2056', transform=transform, nodata=np.nan) as dst:
        dst.write(grid_z, 1)

# --- 3. FONCTION : GÉNÉRATION DE L'IMAGE PNG ROUGE/VERT ---
def generer_carte_ecart_coloree(chemin_raster_diff, chemin_png_sortie):
    with rasterio.open(chemin_raster_diff) as src:
        diff = src.read(1)
        hauteur, largeur = diff.shape
        img = Image.new('RGBA', (largeur, hauteur), (0, 0, 0, 0))
        pixels = img.load()
        
        for y in range(hauteur):
            for x in range(largeur):
                val = diff[y, x]
                if np.isnan(val): continue
                if val < -0.10: pixels[x, y] = (255, 77, 77, 120)  # Déblai -> Rouge
                elif val > 0.10: pixels[x, y] = (46, 204, 113, 120) # Remblai -> Vert
                    
        img.save(chemin_png_sortie)

# --- 4. ROUTES DE L'API ---
@app.post("/upload-laz/")
async def upload_fichier_laz(file: UploadFile = File(...)):
    chemin_laz = os.path.join(DOSSIER_UPLOAD, file.filename)
    nom_sortie = file.filename.rsplit('.', 1)[0] + ".tif"
    chemin_geotiff = os.path.join(DOSSIER_SORTIE, nom_sortie)
    
    with open(chemin_laz, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    laz_vers_raster(chemin_laz, chemin_geotiff)
    return {"message": "Fichier nuage de points traité avec succès !"}

@app.get("/calculer-volume/")
def api_calculer_volume():
    # Simulation pour l'interface
    return {"volume_extrait_m3": 14500.50, "volume_remblai_m3": 3200.20, "solde_m3": -11300.30}

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
