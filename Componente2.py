import osmnx as ox
import networkx as nx
import time
import random
import math
import signal
import sys
from math import sqrt

from simpleai.search import SearchProblem, breadth_first, depth_first, uniform_cost, astar, limited_depth_first

def def_handler(sig, frame):
    print("\n\n[!] Saliendo del programa...\n")
    sys.exit(1)

signal.signal(signal.SIGINT, def_handler)

G = None
G_proj = None
nodes_data = None

# SIMPLEAI

class NavegadorVial(SearchProblem):
    # Adapta el grafo de OSMnx para poder ser usado con simpleai.
    def __init__(self, grafo, origen, destino):
        self.grafo = grafo
        self.destino = destino
        super().__init__(initial_state=origen)

    def actions(self, state):
        # Retorna una lista de los IDs de los nodos vecinos.
        return list(self.grafo.successors(state))

    def result(self, state, action):
        # Accion como movimiento al nodo vecino
        return action

    def cost(self, state, action, state2):
        # Costo de la arista en metros (length)
        edge_data = self.grafo.get_edge_data(state, state2)
        if edge_data:
            # Toma la longitud de la primera arista disponible
            return edge_data[0]['length']
        return 1

    def is_goal(self, state):
        return state == self.destino

    def heuristic(self, state):
        # Heuristica para A*: Distancia Euclidiana en línea recta al destino.
        x1, y1 = nodes_data[state]['x'], nodes_data[state]['y']
        x2, y2 = nodes_data[self.destino]['x'], nodes_data[self.destino]['y']
        return sqrt((x1 - x2)**2 + (y1 - y2)**2)

def start():
    global G, G_proj, nodes_data
    # GRAFO
    print("=== CARGANDO MAPA DE ZAPOPAN EN COMPONENTE 2 ===")
    ox.settings.use_cache = True 

    # Radio mayor (6000m) - puntos lejanos (>5km)
    G = ox.graph_from_address(
        'Tec de Monterrey campus Guadalajara, Zapopan, Jalisco, 45201, México',
        dist=6000, 
        network_type='drive'
    )

    # Distancias en metros
    G_proj = ox.project_graph(G)
    print(f"Grafo cargado: {len(G_proj.nodes)} nodos y {len(G_proj.edges)} aristas.\n")

    # Acceso rapido a coordenadas
    nodes_data = {n: data for n, data in G_proj.nodes(data=True)}

def custom_iterative_deepening(problem, graph_search=True):
    # Implementacion de Iterative Deepening (IDDFS) 
    MAX_LIMIT = 2000 
    
    for depth in range(MAX_LIMIT):
        # Probamos buscar con el limite de profundidad
        result = limited_depth_first(problem, depth_limit=depth, graph_search=graph_search)
        if result:
            return result
            
    return None

def get_random_pair(graph, min_dist, max_dist):
    # Encuentra dos nodos separados por una distancia euclidiana en el rango dado.
    nodes_list = list(graph.nodes())
    max_attempts = 1000
    
    for _ in range(max_attempts):
        u = random.choice(nodes_list)
        v = random.choice(nodes_list)
        
        if u == v: continue
        
        ux, uy = nodes_data[u]['x'], nodes_data[u]['y']
        vx, vy = nodes_data[v]['x'], nodes_data[v]['y']
        
        dist = sqrt((ux - vx)**2 + (uy - vy)**2)
        
        if min_dist <= dist <= max_dist:
            # Verifica la conectividad
            if nx.has_path(graph, u, v):
                return u, v, dist
                
    return None, None, 0

def evaluar_algoritmo(nombre, metodo, problema):
    # Ejecuta un algoritmo y mide el tiempo
    inicio = time.time()
    try:
        if nombre == "IDDFS":
             result = metodo(problema, graph_search=True)
        else:
             result = metodo(problema, graph_search=True)
             
        path = result.path() if result else []
        costo = result.cost if result else float('inf')
    except Exception as e:
        return None, float('inf'), 0
            
    fin = time.time()
    return fin - inicio, costo, len(path)

def main():
    start() # Inicializa

    # Distancias
    categorias = [
        ("Corta (< 1km)", 0, 1000),
        ("Media (1km - 5km)", 1000, 5000),
        ("Larga (> 5km)", 5000, 15000)
    ]

    # Lista de algoritmos a evaluar
    algoritmos = [
        ("BFS", breadth_first),
        ("DFS", depth_first),
        ("UCS", uniform_cost),      # UCS es equivalente a Dijkstra
        ("A*", astar),
        ("IDDFS", custom_iterative_deepening)
    ]

    print(f"{'CATEGORIA':<20} | {'ALGORITMO':<10} | {'TIEMPO (s)':<10} | {'COSTO (m)':<10} | {'NODOS':<6}")
    print("-" * 75)

    resultados_globales = {alg[0]: [] for alg in algoritmos}

    for nombre_cat, d_min, d_max in categorias:
        print(f"\n--- Evaluando: {nombre_cat} ---")
        
        # Selecciona hasta 5 parejas
        parejas = []
        intentos = 0
        while len(parejas) < 5 and intentos < 20:
            u, v, d = get_random_pair(G_proj, d_min, d_max)
            if u: parejas.append((u, v))
            intentos += 1
        
        for i, (origen, destino) in enumerate(parejas):
            print(f"  Pareja {i+1}: ID {origen} -> ID {destino}")
            
            problema = NavegadorVial(G_proj, origen, destino)
            
            for nombre_alg, metodo in algoritmos:
                t, costo, saltos = evaluar_algoritmo(nombre_alg, metodo, problema)
                
                if t is not None:
                    print(f"    {nombre_alg:<10}: {t:.4f} s | {costo:.1f} m | {saltos} pasos")
                    resultados_globales[nombre_alg].append(t)
                else:
                    print(f"    {nombre_alg:<10}: ERROR/TIMEOUT")

    print("\n" + "="*30)
    print("RESUMEN PROMEDIO DE TIEMPOS")
    print("="*30)
    mejor_algoritmo = ""
    mejor_tiempo = float('inf')

    for nombre, tiempos in resultados_globales.items():
        if tiempos:
            promedio = sum(tiempos) / len(tiempos)
            print(f"{nombre:<10}: {promedio:.4f} s")
            # DFS es rapido, pero genera rutas malas
            if promedio < mejor_tiempo and nombre != "DFS": 
                mejor_tiempo = promedio
                mejor_algoritmo = nombre
        else:
            print(f"{nombre:<10}: No completó pruebas")

    print("-" * 30)
    print(f"Algoritmo recomendado para el Planeador: {mejor_algoritmo}")

if __name__ == "__main__":
    main()
