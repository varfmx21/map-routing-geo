import osmnx as ox
import networkx as nx
import folium
from scipy.spatial import cKDTree
import pandas as pd
import pyproj
import signal
import sys

def def_handler(sig, frame):
    print("\n\n[!] Saliendo del programa...\n")
    sys.exit(1)

signal.signal(signal.SIGINT, def_handler)

# Global
LUGAR = ''
G = None
G_proj = None
crs_proj = None
tags = {}
hosp = None
voronoi_tree = None


# Inicializa
def start():
    global LUGAR, G, G_proj, crs_proj, tags, hosp, voronoi_tree
    print("=== SERVICIO DE EMERGENCIAS (VORONOI) ===")
    LUGAR = 'Tec de Monterrey campus Guadalajara, Zapopan, Jalisco, 45201, México'

    print("Cargando datos")
    ox.settings.use_cache = True
    G = ox.graph_from_address(LUGAR, dist=5000, network_type='drive')
    G_proj = ox.project_graph(G)
    crs_proj = G_proj.graph['crs'] # Sistema de coordenadas

    # Hospitales
    tags = {'amenity': ['hospital', 'clinic', 'doctors', 'emergency']}
    hosp = ox.features_from_address(LUGAR, tags=tags, dist=5000)

    # Limpia las geometrias usando centroides para edificios
    hosp['geometry'] = hosp['geometry'].apply(
        lambda g: g.centroid if g.geom_type in ['Polygon', 'MultiPolygon'] else g
    )

    global hosp_proj, hosp_coords, hosp_names
    hosp_proj = hosp.to_crs(crs_proj)

    hosp_coords = []
    hosp_names = []
    for idx, row in hosp_proj.iterrows():
        hosp_coords.append((row.geometry.x, row.geometry.y))
        name = row.get('name', 'Centro de Salud')
        hosp_names.append(str(name) if not pd.isna(name) else "Centro de Salud")

    voronoi_tree = cKDTree(hosp_coords)

def obtener_hospital_voronoi(x, y):
    dist, idx = voronoi_tree.query((x, y))
    return idx, dist

def servicio_emergencia(lat, lon):
    print(f"\nUsuario en: {lat}, {lon}")
    
    # Transformador de coordenadas
    to_utm = pyproj.Transformer.from_crs("EPSG:4326", crs_proj, always_xy=True).transform
    to_latlon = pyproj.Transformer.from_crs(crs_proj, "EPSG:4326", always_xy=True).transform
    
    ux, uy = to_utm(lon, lat)
    
    # Voronoi: Busca al hospital mas cercano
    idx, dist = obtener_hospital_voronoi(ux, uy)
    h_name = hosp_names[idx]
    hx, hy = hosp_coords[idx]
    
    print(f"Asignado a: {h_name} (a {dist:.1f}m lineales)")
    
    # Ruteo
    n_orig = ox.distance.nearest_nodes(G_proj, ux, uy)
    n_dest = ox.distance.nearest_nodes(G_proj, hx, hy)
    
    try:
        ruta = nx.shortest_path(G_proj, n_orig, n_dest, weight='length')
        d_ruta = nx.shortest_path_length(G_proj, n_orig, n_dest, weight='length')
        print(f"Ruta calculada: {d_ruta:.1f} metros.")
    except:
        print("No se encontró ruta vial.")
        return

    m = folium.Map([lat, lon], zoom_start=13)
    
    h_lon, h_lat = to_latlon(hx, hy)
    folium.Marker([lat, lon], icon=folium.Icon(color='red', icon='user'), popup="Tú").add_to(m)
    folium.Marker([h_lat, h_lon], icon=folium.Icon(color='green', icon='plus'), popup=h_name).add_to(m)
    
    # Dibujar ruta
    route_points = []
    for nid in ruta:
        nx_x, nx_y = G_proj.nodes[nid]['x'], G_proj.nodes[nid]['y']
        plon, plat = to_latlon(nx_x, nx_y)
        route_points.append([plat, plon])
        
    folium.PolyLine(route_points, color="blue", weight=5, opacity=0.7).add_to(m)
    
    m.save('ruta_emergencia.html')
    print("[+] Mapa guardado: ruta_emergencia.html")

def main():
    start()
    servicio_emergencia(20.735, -103.435)

if __name__ == "__main__":
    main()
