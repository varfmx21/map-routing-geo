import streamlit as st
from streamlit_folium import st_folium
import folium
from scipy.spatial import Voronoi
import numpy as np
import pyproj
from shapely.geometry import Polygon as ShapelyPolygon, Point as ShapelyPoint
from shapely.ops import unary_union

# Importar funciones del componente 3
import Componente3 as c3

# Configuración de la página
st.set_page_config(
    page_title="Sistema de Emergencias - Voronoi",
    page_icon="🚑",
    layout="wide"
)

# Título principal
st.title("🚑 Sistema de Emergencias - Voronoi")
st.markdown("---")

# Inicializar session_state PRIMERO (antes de cualquier botón)
if 'clicked_lat' not in st.session_state:
    st.session_state.clicked_lat = None
if 'clicked_lon' not in st.session_state:
    st.session_state.clicked_lon = None
if 'resultado_ruta' not in st.session_state:
    st.session_state.resultado_ruta = None
if 'calcular_ahora' not in st.session_state:
    st.session_state.calcular_ahora = False

# Inicializar el sistema (cachear para que solo se ejecute una vez)
@st.cache_resource
def inicializar_sistema():
    """Carga los datos del mapa y hospitales"""
    with st.spinner("Cargando mapa y hospitales..."):
        c3.start()
    return True

# Sidebar con controles
st.sidebar.header("⚙️ Configuración")

# Inicializar sistema
if inicializar_sistema():
    st.sidebar.success("✅ Sistema listo")

# Coordenadas del centro del mapa (solo para visualización inicial)
centro_lat = 20.735
centro_lon = -103.435

# Opciones de entrada
st.sidebar.subheader("📍 Ubicación de Emergencia")
st.sidebar.info("👆 Haz click en el mapa para seleccionar la ubicación de emergencia")

# Variable para controlar si hay ubicación seleccionada
ubicacion_seleccionada = False
lat_input = centro_lat  # Valores por defecto
lon_input = centro_lon

# Verificar si hay un click guardado en session_state
if st.session_state.get('clicked_lat') is not None:
    lat_input = st.session_state.clicked_lat
    lon_input = st.session_state.clicked_lon
    ubicacion_seleccionada = True
    
    # Mostrar coordenadas seleccionadas
    st.sidebar.success(f"📍 Ubicación seleccionada:")
    st.sidebar.text(f"Lat: {lat_input:.6f}")
    st.sidebar.text(f"Lon: {lon_input:.6f}")

# Opciones de visualización
st.sidebar.subheader("🗺️ Visualización")
mostrar_hospitales = st.sidebar.checkbox("Mostrar todos los hospitales", value=True)
mostrar_voronoi = st.sidebar.checkbox("Mostrar diagrama de Voronoi", value=False)
radio_busqueda = st.sidebar.slider(
    "Radio de visualización (km)",
    min_value=1,
    max_value=10,
    value=5,
    help="Ajusta el área visible en el mapa"
)

# Botón para calcular ruta
if st.sidebar.button("🚨 Calcular Ruta de Emergencia", type="primary", use_container_width=True):
    st.session_state.calcular_ahora = True

# Botón para limpiar ruta
if st.session_state.get('resultado_ruta') is not None:
    if st.sidebar.button("🗑️ Limpiar Ruta", use_container_width=True):
        st.session_state.resultado_ruta = None
        st.session_state.calcular_ahora = False
        st.rerun()

# Layout principal
col_mapa, col_info = st.columns([2, 1])

with col_mapa:
    st.subheader("🗺️ Mapa Interactivo")
    
    # Crear mapa base
    mapa = folium.Map(
        location=[centro_lat, centro_lon],
        zoom_start=13,
        tiles="OpenStreetMap"
    )
    
    # Agregar todos los hospitales si está activado
    if mostrar_hospitales and c3.hosp_coords:
        to_latlon = pyproj.Transformer.from_crs(
            c3.crs_proj, "EPSG:4326", always_xy=True
        ).transform
        
        for i, (hx, hy) in enumerate(c3.hosp_coords):
            h_lon, h_lat = to_latlon(hx, hy)
            folium.Marker(
                [h_lat, h_lon],
                icon=folium.Icon(color='lightgray', icon='plus-sign'),
                popup=c3.hosp_names[i],
                tooltip=c3.hosp_names[i]
            ).add_to(mapa)
    
    # Dibujar diagrama de Voronoi si está activado
    if mostrar_voronoi and c3.hosp_coords:
        try:
            # Paleta de colores para distinguir regiones
            colors = [
                '#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#FFEAA7',
                '#DFE6E9', '#74B9FF', '#A29BFE', '#FD79A8', '#FDCB6E',
                '#6C5CE7', '#00B894', '#E17055', '#0984E3', '#FF7675'
            ]
            
            to_latlon = pyproj.Transformer.from_crs(
                c3.crs_proj, "EPSG:4326", always_xy=True
            ).transform
            to_utm = pyproj.Transformer.from_crs(
                "EPSG:4326", c3.crs_proj, always_xy=True
            ).transform
            
            # Calcular el centro del mapa y el radio en metros (del slider)
            center_x, center_y = to_utm(centro_lon, centro_lat)
            radius_meters = radio_busqueda * 1000  # Convertir km a metros
            
            def point_in_circle(x, y):
                """Verifica si un punto está dentro del círculo de visualización"""
                dist = np.sqrt((x - center_x)**2 + (y - center_y)**2)
                return dist <= radius_meters
            
            # FILTRAR hospitales dentro del radio ANTES de calcular Voronoi
            hospitals_in_radius = []
            hospital_indices = []  # Guardar índices originales para colores y nombres
            
            for idx, (hx, hy) in enumerate(c3.hosp_coords):
                if point_in_circle(hx, hy):
                    hospitals_in_radius.append([hx, hy])
                    hospital_indices.append(idx)
            
            # Verificar que haya suficientes hospitales para Voronoi
            if len(hospitals_in_radius) < 3:
                st.sidebar.warning(f"⚠️ Solo hay {len(hospitals_in_radius)} hospital(es) en el radio. Se necesitan al menos 3 para el diagrama de Voronoi.")
            else:
                # Crear diagrama de Voronoi SOLO con hospitales dentro del radio
                points = np.array(hospitals_in_radius)
                vor = Voronoi(points)
                
                # Crear círculo de clipping con Shapely
                circle = ShapelyPoint(center_x, center_y).buffer(radius_meters)
                
                # Función mejorada para cerrar regiones infinitas de Voronoi
                def voronoi_regions_with_bounds(vor, radius):
                    """
                    Reconstruye las regiones de Voronoi incluyendo las infinitas.
                    Usa un radio para cerrar las regiones infinitas.
                    """
                    center = np.array([center_x, center_y])
                    
                    # Crear un factor de escala grande para puntos infinitos
                    new_regions = []
                    new_vertices = vor.vertices.tolist()
                    
                    for pointidx, region_idx in enumerate(vor.point_region):
                        region = vor.regions[region_idx]
                        
                        if not region or len(region) == 0:
                            new_regions.append([])
                            continue
                        
                        if -1 not in region:
                            # Región finita, mantener como está
                            new_regions.append(region)
                        else:
                            # Región infinita, necesitamos cerrarla
                            # Obtener las aristas que tocan este punto
                            ridges = []
                            for (p1, p2), (v1, v2) in zip(vor.ridge_points, vor.ridge_vertices):
                                if p1 == pointidx or p2 == pointidx:
                                    ridges.append((p1, p2, v1, v2))
                            
                            # Construir el polígono cerrado
                            # Encontrar vértices finitos ordenados
                            finite_verts = [i for i in region if i >= 0]
                            
                            if len(finite_verts) < 2:
                                new_regions.append([])
                                continue
                            
                            # Para cerrar, necesitamos encontrar las direcciones infinitas
                            # y crear puntos en esas direcciones
                            infinite_verts = []
                            
                            for ridge in ridges:
                                p1, p2, v1, v2 = ridge
                                if v1 == -1 or v2 == -1:
                                    # Esta arista es infinita
                                    finite_vert = v1 if v2 == -1 else v2
                                    other_point = p2 if p1 == pointidx else p1
                                    
                                    # Calcular dirección perpendicular a la arista entre puntos
                                    t = points[other_point] - points[pointidx]
                                    t = t / np.linalg.norm(t)
                                    n = np.array([-t[1], t[0]])  # Normal perpendicular
                                    
                                    # Crear punto lejano en dirección de la normal
                                    midpoint = vor.vertices[finite_vert]
                                    direction = np.sign(np.dot(midpoint - center, n)) * n
                                    # Usar un factor más grande para asegurar que se extienda lo suficiente
                                    far_point = midpoint + direction * radius * 5
                                    
                                    new_vertices.append(far_point.tolist())
                                    infinite_verts.append((finite_vert, len(new_vertices) - 1))
                            
                            # Reconstruir región ordenada
                            # Ordenar vértices por ángulo
                            point_center = points[pointidx]
                            all_verts_with_angles = []
                            
                            for v in finite_verts:
                                vert = vor.vertices[v]
                                angle = np.arctan2(vert[1] - point_center[1], 
                                                 vert[0] - point_center[0])
                                all_verts_with_angles.append((angle, v))
                            
                            for finite_v, infinite_v in infinite_verts:
                                vert = new_vertices[infinite_v]
                                angle = np.arctan2(vert[1] - point_center[1], 
                                                 vert[0] - point_center[0])
                                all_verts_with_angles.append((angle, infinite_v))
                            
                            all_verts_with_angles.sort()
                            new_region = [v for _, v in all_verts_with_angles]
                            new_regions.append(new_region)
                    
                    return new_regions, np.array(new_vertices)
                
                # Obtener regiones cerradas
                closed_regions, closed_vertices = voronoi_regions_with_bounds(vor, radius_meters)
                
                # Procesar cada región
                for local_idx, region in enumerate(closed_regions):
                    # Obtener el índice original del hospital
                    original_idx = hospital_indices[local_idx]
                    
                    # Saltar regiones vacías
                    if not region or len(region) < 3:
                        continue
                    
                    # Construir polígono con los vértices cerrados
                    polygon_vertices = [closed_vertices[i] for i in region]
                    
                    # Crear polígono con Shapely
                    try:
                        shapely_polygon = ShapelyPolygon(polygon_vertices)
                        
                        # Si el polígono no es válido, intentar arreglarlo
                        if not shapely_polygon.is_valid:
                            shapely_polygon = shapely_polygon.buffer(0)
                        
                        # Si después del buffer sigue siendo inválido, saltar
                        if not shapely_polygon.is_valid or shapely_polygon.is_empty:
                            continue
                        
                        # Intersectar con el círculo de visualización
                        clipped_polygon = shapely_polygon.intersection(circle)
                        
                        # Si la intersección es vacía, saltar (eliminé el filtro de área mínima)
                        if clipped_polygon.is_empty:
                            continue
                        
                        # Convertir de vuelta a coordenadas lat/lon
                        # Manejar MultiPolygon (intersección puede generar múltiples polígonos)
                        if clipped_polygon.geom_type == 'Polygon':
                            polygons_to_draw = [clipped_polygon]
                        elif clipped_polygon.geom_type == 'MultiPolygon':
                            polygons_to_draw = list(clipped_polygon.geoms)
                        else:
                            continue
                        
                        # Dibujar cada polígono resultante
                        for poly in polygons_to_draw:
                            # Obtener coordenadas exteriores
                            coords = list(poly.exterior.coords)
                            
                            # Convertir a lat/lon
                            polygon_points = []
                            for x, y in coords:
                                lon, lat = to_latlon(x, y)
                                polygon_points.append([lat, lon])
                            
                            if len(polygon_points) >= 3:
                                # Elegir color basado en índice ORIGINAL del hospital
                                color = colors[original_idx % len(colors)]
                                
                                folium.Polygon(
                                    locations=polygon_points,
                                    color='black',
                                    weight=2,
                                    fill=True,
                                    fillColor=color,
                                    fillOpacity=0.4,
                                    opacity=0.8,
                                    popup=f"<b>{c3.hosp_names[original_idx]}</b>"
                                ).add_to(mapa)
                    
                    except Exception as e:
                        # Si falla la creación del polígono, continuar con el siguiente
                        # Esto puede pasar con regiones mal formadas
                        import traceback
                        print(f"Error procesando región {original_idx} ({c3.hosp_names[original_idx]}): {str(e)}")
                        print(traceback.format_exc())
                        continue
                
                # Dibujar círculo de límite de visualización
                circle_points = []
                angles = np.linspace(0, 2*np.pi, 100)
                for angle in angles:
                    cx = center_x + radius_meters * np.cos(angle)
                    cy = center_y + radius_meters * np.sin(angle)
                    clon, clat = to_latlon(cx, cy)
                    circle_points.append([clat, clon])
                
                folium.PolyLine(
                    locations=circle_points,
                    color='gray',
                    weight=2,
                    opacity=0.5,
                    dashArray='5, 5',
                    popup=f"Límite de visualización ({radio_busqueda} km)"
                ).add_to(mapa)
                
                # Dibujar marcadores de hospitales dentro del radio con colores correspondientes
                for local_idx, original_idx in enumerate(hospital_indices):
                    hx, hy = hospitals_in_radius[local_idx]
                    h_lon, h_lat = to_latlon(hx, hy)
                    color = colors[original_idx % len(colors)]
                    
                    folium.CircleMarker(
                        [h_lat, h_lon],
                        radius=7,
                        color='black',
                        fill=True,
                        fillColor=color,
                        fillOpacity=0.9,
                        weight=2,
                        popup=f"<b>{c3.hosp_names[original_idx]}</b><br>Centro Voronoi"
                    ).add_to(mapa)
                
        except Exception as e:
            st.sidebar.warning(f"No se pudo generar Voronoi: {str(e)[:100]}")

    
    # Si el usuario hizo click en el mapa, mostrar marcador
    if st.session_state.clicked_lat is not None:
        folium.Marker(
            [st.session_state.clicked_lat, st.session_state.clicked_lon],
            icon=folium.Icon(color='red', icon='user'),
            popup=f"📍 Ubicación de emergencia<br>Lat: {st.session_state.clicked_lat:.6f}<br>Lon: {st.session_state.clicked_lon:.6f}",
            tooltip="Ubicación de emergencia"
        ).add_to(mapa)
    
    # Si hay un resultado de ruta calculado, dibujarlo en el mapa principal
    if st.session_state.resultado_ruta is not None:
        resultado = st.session_state.resultado_ruta
        
        # Agregar marcador del hospital asignado
        h_lat, h_lon = resultado['hospital_coords']
        folium.Marker(
            [h_lat, h_lon],
            icon=folium.Icon(color='green', icon='plus', prefix='fa'),
            popup=f"<b>{resultado['hospital']}</b><br>Distancia: {resultado['distancia_ruta']:.0f}m",
            tooltip=resultado['hospital']
        ).add_to(mapa)
        
        # Dibujar la ruta calculada
        import pyproj
        to_latlon = pyproj.Transformer.from_crs(c3.crs_proj, "EPSG:4326", always_xy=True).transform
        
        route_points = []
        for nid in resultado['ruta']:
            nx_x, nx_y = c3.G_proj.nodes[nid]['x'], c3.G_proj.nodes[nid]['y']
            plon, plat = to_latlon(nx_x, nx_y)
            route_points.append([plat, plon])
        
        folium.PolyLine(
            route_points,
            color="blue",
            weight=5,
            opacity=0.8,
            popup=f"Ruta: {resultado['distancia_ruta']:.0f}m"
        ).add_to(mapa)
    
    # Mostrar mapa y capturar clicks
    mapa_data = st_folium(
        mapa,
        width=None,
        height=500,
        returned_objects=["last_clicked"]
    )
    
    # Capturar coordenadas del click y guardar en session_state
    if mapa_data["last_clicked"]:
        new_lat = mapa_data["last_clicked"]["lat"]
        new_lon = mapa_data["last_clicked"]["lng"]
        
        # Solo actualizar si cambió la ubicación
        if (st.session_state.clicked_lat != new_lat or 
            st.session_state.clicked_lon != new_lon):
            st.session_state.clicked_lat = new_lat
            st.session_state.clicked_lon = new_lon
            # Limpiar resultado previo y flag de cálculo al hacer click en nueva ubicación
            st.session_state.resultado_ruta = None
            st.session_state.calcular_ahora = False
            # Solo hacer rerun si NO hay un cálculo pendiente
            if not st.session_state.calcular_ahora:
                st.rerun()
    
    # Mostrar información del click si existe
    if st.session_state.clicked_lat is not None:
        st.info(f"📍 Ubicación seleccionada en el mapa")

with col_info:
    st.subheader("📊 Información")
    
    # Mostrar coordenadas solo si están seleccionadas
    if ubicacion_seleccionada:
        st.metric("Latitud", f"{lat_input:.6f}")
        st.metric("Longitud", f"{lon_input:.6f}")
    else:
        st.warning("⚠️ Selecciona una ubicación")
        st.info("Ingresa coordenadas o haz click en el mapa")
    
    # Mostrar información de la ruta si existe
    if st.session_state.resultado_ruta is not None:
        st.markdown("---")
        st.markdown("### 🏥 Ruta Calculada")
        resultado = st.session_state.resultado_ruta
        
        st.metric("Hospital", resultado['hospital'])
        st.metric("📏 Distancia Lineal", f"{resultado['distancia_lineal']:.0f} m")
        st.metric("🛣️ Distancia por Ruta", f"{resultado['distancia_ruta']:.0f} m")
        
        tiempo_estimado = resultado['distancia_ruta'] / 1000 * 3
        st.metric("⏱️ Tiempo Estimado", f"{tiempo_estimado:.1f} min")
        
        factor = resultado['distancia_ruta'] / resultado['distancia_lineal']
        st.info(f"📊 Factor: **{factor:.2f}x** la distancia lineal")
    
    # Información del sistema
    if c3.hosp_coords:
        st.markdown("---")
        st.info(f"🏥 **{len(c3.hosp_coords)}** hospitales en el área")
    
    st.markdown("---")
    st.markdown("### 📝 Instrucciones")
    st.markdown("""
    1. **Selecciona ubicación:**
       - Ingresa coordenadas manualmente
       - O haz click en el mapa
    
    2. **Personaliza visualización:**
       - Mostrar hospitales
       - Dibujar diagrama Voronoi
    
    3. **Calcula ruta:**
       - Presiona el botón "Calcular Ruta"
       - El sistema usa **A*** con heurística
    
    4. **Resultado:**
       - Hospital más cercano (Voronoi)
       - Ruta óptima en azul
       - Distancias y estadísticas
    """)

# Calcular ruta si se activó el flag
if st.session_state.calcular_ahora:
    # Validar que haya una ubicación seleccionada
    if not ubicacion_seleccionada:
        st.error("❌ Por favor selecciona una ubicación primero")
        st.info("💡 Ingresa coordenadas manualmente o haz click en el mapa")
        st.session_state.calcular_ahora = False
    else:
        with st.spinner("🚨 Calculando ruta de emergencia..."):
            resultado = c3.servicio_emergencia(lat_input, lon_input, guardar_html=False)
        
        if resultado:
            # Guardar el resultado en session_state para mostrarlo en el mapa principal
            st.session_state.resultado_ruta = resultado
            # Limpiar el flag ANTES de rerun
            st.session_state.calcular_ahora = False
            st.success("✅ Ruta calculada exitosamente - Mira el mapa para ver la ruta")
            st.info("💡 La ruta azul muestra el camino al hospital más cercano")
            # Forzar rerun para actualizar el mapa con la ruta
            st.rerun()
            
        else:
            st.error("❌ No se pudo calcular la ruta. Intenta con otra ubicación.")
            st.session_state.calcular_ahora = False

# Footer
st.markdown("---")
st.markdown("""
<div style='text-align: center; color: gray;'>
    <small>
    Sistema de Emergencias con Partición de Voronoi y Algoritmo A* | 
    Desarrollado con Streamlit, OSMnx y NetworkX
    </small>
</div>
""", unsafe_allow_html=True)
