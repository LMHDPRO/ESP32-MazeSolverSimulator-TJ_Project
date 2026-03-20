# ============================================================
#  TJ Simulator — Maze Generator
#  DFS + sala 2x2 con UNA SOLA ENTRADA garantizada
#  + posicion de inicio configurable (cualquier esquina)
# ============================================================
import random
from maze import Maze


def _make_2x2_room(maze: Maze):
    """
    Abre los muros INTERNOS de la zona 2x2 para crear una sala.
    En un laberinto DFS perfecto (arbol generador), los 4 nodos
    de la sala tienen exactamente UNA conexion al exterior
    (propiedad del arbol generador). No se tocan muros externos.
    """
    gc, gr = maze.goal
    if gc+1 >= maze.cols or gr+1 >= maze.rows:
        return
    # Abrir los 4 muros internos de la sala
    maze.set_wall(gc,   gr,   'E', False)
    maze.set_wall(gc,   gr+1, 'E', False)
    maze.set_wall(gc,   gr,   'S', False)
    maze.set_wall(gc+1, gr,   'S', False)


def _verify_single_entrance(maze: Maze):
    """
    Verifica que la zona 2x2 tenga exactamente 1 entrada.
    Si hay mas de una (raro, pero posible al abrir internos),
    cierra las extras manteniendo conectividad.
    Devuelve numero de entradas encontradas.
    """
    gc, gr = maze.goal
    goal_set = {(gc,gr),(gc+1,gr),(gc,gr+1),(gc+1,gr+1)}

    def is_border(c, r, d):
        if d=='N' and r==0:              return True
        if d=='S' and r==maze.rows-1:   return True
        if d=='W' and c==0:             return True
        if d=='E' and c==maze.cols-1:   return True
        return False

    # Muros externos de la sala (hacia celdas fuera de la sala)
    external_open = []
    for (c,r) in goal_set:
        for d in ['N','E','S','W']:
            nc,nr = maze.next_cell(c,r,d)
            if (nc,nr) not in goal_set and not is_border(c,r,d):
                if not maze.has_wall(c,r,d):
                    external_open.append((c,r,d))

    # En un arbol DFS deberia haber exactamente 1. Si hay mas, cerrar extras.
    if len(external_open) > 1:
        # Keeper: el que da el camino mas corto desde el inicio (BFS)
        from collections import deque
        best_keeper = external_open[0]
        best_dist   = 9999
        for (c,r,d) in external_open:
            nc,nr = maze.next_cell(c,r,d)
            # BFS desde (nc,nr) hasta maze.start
            q = deque([(nc,nr,0)]); seen={(nc,nr)}
            dist = 9999
            while q:
                cx,cy,dd = q.popleft()
                if (cx,cy)==maze.start: dist=dd; break
                for dir2 in ['N','E','S','W']:
                    nx2,ny2 = maze.next_cell(cx,cy,dir2)
                    if (nx2,ny2) not in seen and maze._valid(nx2,ny2) and not maze.has_wall(cx,cy,dir2):
                        seen.add((nx2,ny2)); q.append((nx2,ny2,dd+1))
            if dist < best_dist:
                best_dist=dist; best_keeper=(c,r,d)

        # Cerrar los que no son el keeper
        for (c,r,d) in external_open:
            if (c,r,d) != best_keeper:
                maze.set_wall(c,r,d,True)

    return len(external_open)


def start_from_corner(maze: Maze, corner: str):
    """
    Posiciona el inicio en la esquina indicada.
    corner: 'bottom_left' | 'bottom_right' | 'top_left' | 'top_right'
    """
    cols, rows = maze.cols, maze.rows
    positions = {
        'bottom_left':  (0,        rows-1),
        'bottom_right': (cols-1,   rows-1),
        'top_left':     (0,        0     ),
        'top_right':    (cols-1,   0     ),
    }
    maze.start = positions.get(corner, (0, rows-1))


def generate(cols: int, rows: int,
             start_corner: str = 'bottom_left',
             goal=None,
             seed=None) -> Maze:
    """
    Genera laberinto perfecto (DFS) con:
    - Sala meta 2x2 con UNA SOLA ENTRADA
    - Inicio en la esquina elegida
    - seed para reproducibilidad
    """
    if seed is not None:
        random.seed(seed)

    maze = Maze(cols, rows)

    # DFS iterativo
    visited = [[False]*cols for _ in range(rows)]
    # Empezar desde la esquina que sera el inicio (para mejor exploracion)
    corner_map = {
        'bottom_left':  (0, rows-1),
        'bottom_right': (cols-1, rows-1),
        'top_left':     (0, 0),
        'top_right':    (cols-1, 0),
    }
    sc, sr = corner_map.get(start_corner, (0, rows-1))
    visited[sr][sc] = True
    stack = [(sc, sr)]

    while stack:
        c, r = stack[-1]
        nb = []
        for d in Maze.DIR_LIST:
            dr, dc = Maze.DIRS[d]
            nc, nr = c+dc, r+dr
            if 0<=nc<cols and 0<=nr<rows and not visited[nr][nc]:
                nb.append((d,nc,nr))
        if nb:
            d, nc, nr = random.choice(nb)
            maze.set_wall(c,r,d,False)
            visited[nr][nc] = True
            stack.append((nc,nr))
        else:
            stack.pop()

    # Paredes exteriores
    for r in range(rows):
        maze.walls[r][0]['W']       = True
        maze.walls[r][cols-1]['E']  = True
    for c in range(cols):
        maze.walls[0][c]['N']       = True
        maze.walls[rows-1][c]['S']  = True

    # Configurar inicio y meta
    if goal:
        maze.goal = goal
    else:
        # Meta cerca del centro, asegurar que no choque con el inicio
        gx = max(1, min(cols-3, cols//2-1))
        gy = max(1, min(rows-3, rows//2-1))
        maze.goal = (gx, gy)

    start_from_corner(maze, start_corner)

    # Crear sala 2x2
    _make_2x2_room(maze)

    # Verificar y forzar entrada unica
    n_entrances = _verify_single_entrance(maze)

    maze.compute_flood()
    return maze


def generate_open(cols: int, rows: int) -> Maze:
    maze = Maze(cols, rows)
    for r in range(rows):
        for c in range(cols):
            for d in 'NESW': maze.walls[r][c][d] = False
    for r in range(rows):
        maze.walls[r][0]['W']       = True
        maze.walls[r][cols-1]['E']  = True
    for c in range(cols):
        maze.walls[0][c]['N']       = True
        maze.walls[rows-1][c]['S']  = True
    maze.compute_flood()
    return maze