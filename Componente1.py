import osmnx as ox
import pyproj
import time
from math import sqrt

print("=== 1) Descargando mapa de Zapopan... ===")
inicio = time.time()

G = ox.graph_from_address(
    'Tec de Monterrey campus Guadalajara, Zapopan, Jalisco, 45201, México',
    dist=1000,
    network_type='drive'
)

tiempo_descarga = time.time() - inicio
print(f"Mapa descargado en {tiempo_descarga:.2f} segundos")
print()

# ================================================================

print("=== 2) Proyectando grafo a coordenadas planas... ===")
inicio = time.time()

G_proj = ox.project_graph(G)
nodes_proj = ox.graph_to_gdfs(G_proj, edges=False)

tiempo_proyeccion = time.time() - inicio
print(f"Grafo proyectado en {tiempo_proyeccion:.4f} segundos")
print()

# Mostrar ejemplo de nodos proyectados
print("Primeros nodos proyectados:")
print(nodes_proj.head(), "\n")

# Extraer listas de coordenadas y IDs
coords = list(zip(nodes_proj.geometry.x, nodes_proj.geometry.y))
node_ids = list(nodes_proj.index)

print(f"Total de nodos obtenidos: {len(coords)}")
print()

# =====================================================

class KDNode:
    """
    Nodo del árbol KD.
    - Si es hoja: guarda un punto (x, y, id)
    - Si es interno: guarda el valor de división y tiene hijos izq/der
    """
    def __init__(self, point=None, split_value=None, left=None, right=None):
        self.point = point            # (x, y, node_id) solo en hojas
        self.split_value = split_value # mediana (solo en nodos internos)
        self.left = left
        self.right = right


def build_kd_tree(points, depth=0):
    # Caso base: solo un punto → crear hoja
    if len(points) == 1:
        return KDNode(point=points[0])
    
    # Determinar eje de partición: par=x (eje 0), impar=y (eje 1)
    axis = depth % 2
    
    # Ordenar puntos según el eje actual
    points_sorted = sorted(points, key=lambda p: p[axis])
    
    # Calcular mediana
    median_idx = len(points_sorted) // 2
    median_value = points_sorted[median_idx][axis]
    
    # Dividir puntos en izquierda y derecha
    points_left = points_sorted[:median_idx]
    points_right = points_sorted[median_idx:]
    
    # Construir subárboles recursivamente
    left_child = build_kd_tree(points_left, depth + 1)
    right_child = build_kd_tree(points_right, depth + 1)
    
    # Crear y retornar nodo interno
    return KDNode(split_value=median_value, left=left_child, right=right_child)


# -----------------------------------------------------------

points = [(coords[i][0], coords[i][1], node_ids[i]) for i in range(len(coords))]

# -----------------------------------------------------------

print("===============================================")
print("3) Construyendo KD-Tree")
print("===============================================")

start = time.time()
kd_root = build_kd_tree(points)
end = time.time()

print(f"KD-tree construido en {end - start:.4f} segundos")
print()


# ============================================================

def kd_nearest_neighbor(node, target, depth=0, best=None):
    if node is None:
        return best
    
    axis = depth % 2
    
    # Si es hoja, evaluar este punto
    if node.point is not None:
        px, py, pid = node.point
        dist = sqrt((target[0] - px)**2 + (target[1] - py)**2)
        
        if best is None or dist < best[0]:
            return (dist, node.point)
        return best
    
    # Decidir qué rama explorar primero (la que contiene el punto)
    if target[axis] <= node.split_value:
        # El punto está del lado izquierdo
        first_branch = node.left
        second_branch = node.right
    else:
        # El punto está del lado derecho
        first_branch = node.right
        second_branch = node.left
    
    best = kd_nearest_neighbor(first_branch, target, depth + 1, best)
    
    
    if best is None:
        # Si no hemos encontrado nada, explorar la otra rama
        best = kd_nearest_neighbor(second_branch, target, depth + 1, best)
    else:
        # Calcular distancia perpendicular al plano de división
        dist_to_plane = abs(target[axis] - node.split_value)
        
        # Solo explorar la otra rama si el círculo con radio=best_dist intersecta el plano
        if dist_to_plane < best[0]:
            best = kd_nearest_neighbor(second_branch, target, depth + 1, best)
        # else: PODAMOS la rama - no puede tener vecinos más cercanos
    
    return best


# ============================================================

def exhaustive_search(points, target):
    mejor_distancia = float("inf")
    mejor_punto = None
    
    tx, ty = target
    
    for punto in points:
        x, y, pid = punto
        distancia = sqrt((tx - x)**2 + (ty - y)**2)
        
        if distancia < mejor_distancia:
            mejor_distancia = distancia
            mejor_punto = punto
    
    return mejor_distancia, mejor_punto


# ============================================================

print("===============================================")
print("4) Generando 20 coordenadas reales en Zapopan")
print("===============================================")

# Obtener el rango de coordenadas del mapa descargado
import random

# Extraer todas las latitudes y longitudes de los nodos del grafo
lats_grafo = [G.nodes[node]['y'] for node in G.nodes()]
lons_grafo = [G.nodes[node]['x'] for node in G.nodes()]

# Obtener los límites del mapa
lat_min = min(lats_grafo)
lat_max = max(lats_grafo)
lon_min = min(lons_grafo)
lon_max = max(lons_grafo)

print(f"Límites del mapa descargado:")
print(f"  Latitud:  {lat_min:.6f} a {lat_max:.6f}")
print(f"  Longitud: {lon_min:.6f} a {lon_max:.6f}")
print()

# Generar 20 coordenadas aleatorias dentro del rango del mapa
random.seed(42)  # Para reproducibilidad
sample_latlon = []

for i in range(20):
    lat = random.uniform(lat_min, lat_max)
    lon = random.uniform(lon_min, lon_max)
    sample_latlon.append((lat, lon))

print("Coordenadas generadas dentro del área del mapa:")
for i, (lat, lon) in enumerate(sample_latlon, 1):
    print(f"Punto {i}: lat={lat:.6f}, lon={lon:.6f}")
print()

# Transformar de lat/lon a coordenadas proyectadas (x, y) del grafo
print("===============================================")
print("5) Transformando coordenadas a proyección del grafo")
print("===============================================")

proj_crs = nodes_proj.crs
projector = pyproj.Transformer.from_crs("epsg:4326", proj_crs, always_xy=True)

sample_xy = []
for lat, lon in sample_latlon:
    # IMPORTANTE: pyproj con always_xy=True espera (lon, lat)
    x, y = projector.transform(lon, lat)
    sample_xy.append((x, y))

print("Ejemplo de transformación:")
print(f"LatLon: {sample_latlon[0]}")
print(f"Proyectado: {sample_xy[0]}")
print()


# ============================================================

print("===============================================")
print("6) Búsqueda de nodos más cercanos usando KD-tree")
print("===============================================")

start = time.time()
resultados_kd = []

for x, y in sample_xy:
    resultado = kd_nearest_neighbor(kd_root, (x, y))
    if resultado is not None:
        dist, punto = resultado
        px, py, pid = punto
        resultados_kd.append((dist, pid))

tiempo_kd = time.time() - start

print(f"Tiempo total KD-tree: {tiempo_kd:.6f} segundos")
print(f"Tiempo promedio por consulta: {tiempo_kd/len(resultados_kd):.6f} s")
print()

print("Primeras 5 coincidencias KD-tree:")
for i in range(min(5, len(resultados_kd))):
    dist, nodo = resultados_kd[i]
    print(f"Usuario {i+1}: Nodo={nodo}, Distancia={dist:.3f}")
print()


# ============================================================

print("===============================================")
print("7) Búsqueda exhaustiva (sin KD-tree)")
print("===============================================")

start = time.time()
resultados_exhaustivos = []

for x, y in sample_xy:
    dist, punto = exhaustive_search(points, (x, y))
    if punto is not None:
        px, py, pid = punto
        resultados_exhaustivos.append((dist, pid))

tiempo_exhaustivo = time.time() - start

print(f"Tiempo total EXHAUSTIVO: {tiempo_exhaustivo:.6f} segundos")
print(f"Tiempo promedio por consulta: {tiempo_exhaustivo/len(resultados_exhaustivos):.6f} s")
print()

print("Primeras 5 coincidencias exhaustivas:")
for i in range(min(5, len(resultados_exhaustivos))):
    dist, nodo = resultados_exhaustivos[i]
    print(f"Usuario {i+1}: Nodo={nodo}, Distancia={dist:.3f}")
print()


# ============================================================

print("===============================================")
print("8) Comparación final")
print("===============================================")

print(f"KD-tree total:       {tiempo_kd:.6f} s")
print(f"Exhaustiva total:    {tiempo_exhaustivo:.6f} s")

mejora = tiempo_exhaustivo / tiempo_kd if tiempo_kd > 0 else 0
print(f"Mejora relativa:     {mejora:.2f} veces más rápido")
print()

print("Proceso completado correctamente.")

# ============================================================

print("\n===============================================")
print("9) Generando visualización del mapa")
print("===============================================")

# Generar mapa interactivo HTML
try:
    import folium
    
    print("Generando mapa interactivo HTML...")
    
    # Calcular el centro del mapa usando los nodos
    lats = [G.nodes[node]['y'] for node in G.nodes()]
    lons = [G.nodes[node]['x'] for node in G.nodes()]
    center_lat = sum(lats) / len(lats)
    center_lon = sum(lons) / len(lons)
    
    # Crear mapa base
    m = folium.Map(
        location=[center_lat, center_lon],
        zoom_start=15,
        tiles='OpenStreetMap'
    )
    
    # Agregar todos los puntos de prueba y sus nodos más cercanos al mapa
    for i, (lat, lon) in enumerate(sample_latlon, 1):
        dist, nodo_id = resultados_kd[i-1]
        
        # Obtener las coordenadas del nodo más cercano
        nodo_lat = G.nodes[nodo_id]['y']
        nodo_lon = G.nodes[nodo_id]['x']
        
        # Marcador ROJO para el punto de consulta (ubicación del usuario)
        folium.Marker(
            location=[lat, lon],
            popup=f"<b>Punto de Consulta {i}</b><br>"
                  f"Lat: {lat:.6f}<br>"
                  f"Lon: {lon:.6f}<br>"
                  f"Distancia al nodo: {dist:.2f}m",
            tooltip=f"Consulta {i}",
            icon=folium.Icon(color='red', icon='user', prefix='fa')
        ).add_to(m)
        
        # Marcador AZUL para el nodo más cercano del grafo
        folium.Marker(
            location=[nodo_lat, nodo_lon],
            popup=f"<b>Nodo Más Cercano</b><br>"
                  f"ID: {nodo_id}<br>"
                  f"Lat: {nodo_lat:.6f}<br>"
                  f"Lon: {nodo_lon:.6f}<br>"
                  f"Para punto {i}",
            tooltip=f"Nodo {nodo_id}",
            icon=folium.Icon(color='blue', icon='map-marker', prefix='fa')
        ).add_to(m)
        
        # Línea conectando el punto de consulta con su nodo más cercano
        folium.PolyLine(
            locations=[[lat, lon], [nodo_lat, nodo_lon]],
            color='green',
            weight=2,
            opacity=0.7,
            popup=f"Distancia: {dist:.2f}m"
        ).add_to(m)
    
    # Agregar leyenda
    legend_html = '''
    <div style="position: fixed; 
                bottom: 50px; right: 50px; width: 250px; height: 140px; 
                background-color: white; border:2px solid grey; z-index:9999; 
                font-size:14px; padding: 10px">
    <p><b>Leyenda:</b></p>
    <p><i class="fa fa-user" style="color:red"></i> Punto de consulta (usuario)</p>
    <p><i class="fa fa-map-marker" style="color:blue"></i> Nodo más cercano (grafo)</p>
    <p><span style="color:green">—</span> Conexión (distancia)</p>
    </div>
    '''
    m.get_root().html.add_child(folium.Element(legend_html))
    
    # Guardar mapa
    m.save('mapa_interactivo.html')
    print("✓ Mapa interactivo guardado como: mapa_interactivo.html")
    print(f"  Muestra {len(sample_latlon)} puntos de consulta y sus nodos más cercanos")
    print("  Abre este archivo en tu navegador para ver el mapa interactivo")
    
except ImportError:
    print("⚠ folium no está instalado. Para mapas interactivos ejecuta:")
    print("  pip install folium")
except Exception as e:
    print(f"⚠ Error al generar mapa interactivo: {e}")

print("\n" + "="*50)
print("ARCHIVO GENERADO:")
print("  - mapa_interactivo.html")
print("="*50)