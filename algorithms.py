# ============================================================
#  TJ Simulator — Navigation Algorithms
#
#  SENSOR THRESHOLDS:
#    Pared directa  = 90mm  (CELL_SIZE_MM/2)
#    Pasillo libre  = 350mm (SENSOR_MAX_RANGE)
#    Umbral = 120mm
# ============================================================

from collections import deque
import heapq, random

OPEN_THR = 120

ALGORITHMS = [
    "Right Wall Follower",
    "Left Wall Follower",
    "Flood Fill (tiempo real)",
    "BFS (camino optimo)",
    "A* (A-Star)",
    "Tremaux",
    "Mano Derecha + Memoria",
    "Dead End Filling",
    "Pledge Algorithm",
    "Random Mouse",
    "Dijkstra",
    "Chain / Spiral",
]


def get_algorithm(name, robot, maze):
    algs = {
        "Right Wall Follower":         right_wall_follower,
        "Left Wall Follower":          left_wall_follower,
        "Flood Fill (tiempo real)":    flood_fill,
        "BFS (camino optimo)":         bfs_solver,
        "A* (A-Star)":                 astar_solver,
        "Tremaux":                     tremaux,
        "Mano Derecha + Memoria":      right_wall_with_memory,
        "Dead End Filling":            dead_end_filling,
        "Pledge Algorithm":            pledge_algorithm,
        "Random Mouse":                random_mouse,
        "Dijkstra":                    dijkstra_solver,
        "Chain / Spiral":              chain_spiral,
    }
    return algs.get(name, right_wall_follower)(robot, maze)


# ── Helpers ──────────────────────────────────────────────────
_DIR_IDX = {'N':0,'E':1,'S':2,'W':3}
_IDX_DIR = {0:'N',1:'E',2:'S',3:'W'}

def _rel_to_abs(heading, rel):
    return _IDX_DIR[(_DIR_IDX[heading] + {'F':0,'R':1,'B':2,'L':3}[rel]) % 4]

def _turns(cur, tgt):
    d = (_DIR_IDX[tgt]-_DIR_IDX[cur]) % 4
    return {0:[],1:['right'],2:['180'],3:['left']}[d]

def _walls(robot):
    L,C,R = robot.read_sensors()
    return L<=OPEN_THR, C<=OPEN_THR, R<=OPEN_THR

def _dir_from_delta(dc, dr):
    """Return compass direction from cell delta. Returns None if no movement."""
    if dr == -1: return 'N'
    if dr ==  1: return 'S'
    if dc ==  1: return 'E'
    if dc == -1: return 'W'
    return None


# ══════════════════════════════════════════════════════════════
#  1. RIGHT WALL FOLLOWER
#     Replica exacta del codigo ESP32.
#     Prioridad: frente > izq > der > 180.
#     Solo sensores. Puede quedar en loops.
# ══════════════════════════════════════════════════════════════
def right_wall_follower(robot, maze):
    for _ in range(maze.cols*maze.rows*8):
        if robot.is_at_goal(): break
        wL,wF,wR = _walls(robot)
        if   not wF: yield 'forward'
        elif not wL: yield 'left';  yield 'forward'
        elif not wR: yield 'right'; yield 'forward'
        else:        yield '180';   yield 'forward'
    yield 'done'


# ══════════════════════════════════════════════════════════════
#  2. LEFT WALL FOLLOWER
#     Prioridad invertida: izq > frente > der > 180.
# ══════════════════════════════════════════════════════════════
def left_wall_follower(robot, maze):
    for _ in range(maze.cols*maze.rows*8):
        if robot.is_at_goal(): break
        wL,wF,wR = _walls(robot)
        if   not wL: yield 'left';  yield 'forward'
        elif not wF: yield 'forward'
        elif not wR: yield 'right'; yield 'forward'
        else:        yield '180';   yield 'forward'
    yield 'done'


# ══════════════════════════════════════════════════════════════
#  3. FLOOD FILL (tiempo real)
#     Mapa LOCAL, solo paredes exteriores al inicio.
#     Descubre F/L/R al entrar a cada celda nueva.
#     Re-calcula BFS desde la meta en mapa local.
#     Garantiza llegar. Puede retroceder.
# ══════════════════════════════════════════════════════════════
def flood_fill(robot, maze):
    from maze import Maze
    cols,rows = maze.cols, maze.rows
    INF = cols*rows+1

    local = Maze(cols, rows)
    for r in range(rows):
        for c in range(cols):
            local.walls[r][c] = {d:False for d in 'NESW'}
    for r in range(rows):
        local.walls[r][0]['W']=True; local.walls[r][cols-1]['E']=True
    for c in range(cols):
        local.walls[0][c]['N']=True; local.walls[rows-1][c]['S']=True

    dist       = [[INF]*cols for _ in range(rows)]
    discovered = [[False]*cols for _ in range(rows)]

    def recompute():
        for r in range(rows):
            for c in range(cols): dist[r][c]=INF
        q = deque()
        for gc,gr in maze.goal_cells:
            dist[gr][gc]=0; q.append((gc,gr))
        while q:
            c,r=q.popleft()
            for d in Maze.DIR_LIST:
                nc,nr=local.next_cell(c,r,d)
                if local._valid(nc,nr) and local.can_move(c,r,d):
                    if dist[nr][nc]>dist[r][c]+1:
                        dist[nr][nc]=dist[r][c]+1; q.append((nc,nr))

    recompute()
    last_dir = None

    for _ in range(cols*rows*12):
        if robot.is_at_goal(): break
        c,r = robot.col, robot.row

        # Descubrir paredes SIEMPRE (no solo primera visita)
        # Esto evita que el robot se quede bloqueado si el mapa
        # local es inconsistente con el laberinto real
        L_mm,C_mm,R_mm = robot.read_sensors()
        aF=_rel_to_abs(robot.heading,'F'); aL=_rel_to_abs(robot.heading,'L')
        aR=_rel_to_abs(robot.heading,'R'); aB=_rel_to_abs(robot.heading,'B')
        changed=False
        wall_B = False if last_dir is not None else True
        for d,w in [(aF,C_mm<=OPEN_THR),(aL,L_mm<=OPEN_THR),
                    (aR,R_mm<=OPEN_THR),(aB,wall_B)]:
            if local.walls[r][c][d]!=w:
                local.set_wall(c,r,d,w); changed=True
        if changed: recompute()

        best_d,best_v = None, INF+1
        for d in Maze.DIR_LIST:
            nc,nr=local.next_cell(c,r,d)
            if local._valid(nc,nr) and local.can_move(c,r,d) and dist[nr][nc]<best_v:
                best_v=dist[nr][nc]; best_d=d

        if best_d is None:
            # Completamente atascado: resetear mapa local y recalcular
            for rr in range(rows):
                for cc in range(cols):
                    local.walls[rr][cc] = {dd:False for dd in 'NESW'}
            for rr in range(rows):
                local.walls[rr][0]['W']=True; local.walls[rr][cols-1]['E']=True
            for cc in range(cols):
                local.walls[0][cc]['N']=True; local.walls[rows-1][cc]['S']=True
            recompute(); continue

        for t in _turns(robot.heading, best_d): yield t
        yield 'forward'
        last_dir=best_d
    yield 'done'



# ══════════════════════════════════════════════════════════════
#  4. BFS (mapa completo)
#     Conoce todo el laberinto. Camino minimo garantizado.
#     Ideal para la 2da vuelta rapida.
# ══════════════════════════════════════════════════════════════
def bfs_solver(robot, maze):
    path = maze.solve()
    if not path: yield 'done'; return
    for tc,tr in path[1:]:
        dc=tc-robot.col; dr=tr-robot.row
        tdir = _dir_from_delta(dc, dr)
        for t in _turns(robot.heading,tdir): yield t
        yield 'forward'
        if robot.is_at_goal(): break
    yield 'done'


# ══════════════════════════════════════════════════════════════
#  5. A* (A-Star)
#     Heuristica Manhattan. Mapa completo.
#     Mas eficiente que BFS en laberintos grandes.
# ══════════════════════════════════════════════════════════════
def astar_solver(robot, maze):
    from maze import Maze
    goal_set  = set(maze.goal_cells)
    goal_list = list(goal_set)
    def h(c,r): return min(abs(c-gc)+abs(r-gr) for gc,gr in goal_list)
    start = maze.start
    openq = [(h(*start),0,start,None)]
    came  = {}; g_sc = {start:0}
    while openq:
        f,g,cur,par = heapq.heappop(openq)
        if cur in came: continue
        came[cur]=par
        if cur in goal_set:
            path=[]; node=cur
            while node: path.append(node); node=came[node]
            path.reverse()
            for tc,tr in path[1:]:
                dc=tc-robot.col; dr=tr-robot.row
                tdir=_dir_from_delta(dc, dr)
                if tdir is None: continue
                for t in _turns(robot.heading,tdir): yield t
                yield 'forward'
                if robot.is_at_goal(): break
            yield 'done'; return
        c,r=cur
        for d in Maze.DIR_LIST:
            nc,nr=maze.next_cell(c,r,d)
            if maze._valid(nc,nr) and maze.can_move(c,r,d):
                ng=g+1
                if (nc,nr) not in g_sc or ng<g_sc[(nc,nr)]:
                    g_sc[(nc,nr)]=ng; heapq.heappush(openq,(ng+h(nc,nr),ng,(nc,nr),cur))
    yield 'done'


# ══════════════════════════════════════════════════════════════
#  6. TREMAUX
#     Sin mapa. Marca pasillos 0-1-2.
#     Nunca cruza marca 2. Retrocede por el menos marcado.
#     Garantiza llegar. No optimo.
# ══════════════════════════════════════════════════════════════
def tremaux(robot, maze):
    from maze import Maze
    marks={}; prev_dir=None
    def gm(c,r,d): return marks.get((c,r,d),0)
    def am(c,r,d):
        marks[(c,r,d)]=marks.get((c,r,d),0)+1
        opp=Maze.OPPOSITE[d]; nc,nr=maze.next_cell(c,r,d)
        if maze._valid(nc,nr): marks[(nc,nr,opp)]=marks.get((nc,nr,opp),0)+1

    for _ in range(maze.cols*maze.rows*12):
        if robot.is_at_goal(): break
        c,r=robot.col,robot.row
        wL,wF,wR=_walls(robot)
        open_dirs=[]
        if not wF: open_dirs.append(_rel_to_abs(robot.heading,'F'))
        if not wL: open_dirs.append(_rel_to_abs(robot.heading,'L'))
        if not wR: open_dirs.append(_rel_to_abs(robot.heading,'R'))
        if prev_dir:
            back=Maze.OPPOSITE[prev_dir]
            if back not in open_dirs: open_dirs.append(back)
        if not open_dirs: yield 'done'; return
        zero=[d for d in open_dirs if gm(c,r,d)==0]
        if zero:
            chosen=prev_dir if (prev_dir and prev_dir in zero) else zero[0]
        else:
            back=Maze.OPPOSITE[prev_dir] if prev_dir else None
            single=[d for d in open_dirs if gm(c,r,d)<2]
            chosen = (back if back and back in single
                      else single[0] if single else open_dirs[0])
        am(c,r,chosen)
        for t in _turns(robot.heading,chosen): yield t
        yield 'forward'
        prev_dir=chosen
    yield 'done'


# ══════════════════════════════════════════════════════════════
#  7. MANO DERECHA + MEMORIA
#     Wall follower con contador de visitas.
#     Elige la direccion menos visitada para romper ciclos.
# ══════════════════════════════════════════════════════════════
def right_wall_with_memory(robot, maze):
    visits={}
    for _ in range(maze.cols*maze.rows*10):
        if robot.is_at_goal(): break
        c,r=robot.col,robot.row
        visits[(c,r)]=visits.get((c,r),0)+1
        wL,wF,wR=_walls(robot)
        cands=[]
        for rel,blocked in [('R',wR),('F',wF),('L',wL)]:
            if not blocked:
                ad=_rel_to_abs(robot.heading,rel)
                nc,nr=maze.next_cell(c,r,ad)
                if maze._valid(nc,nr): cands.append((ad,visits.get((nc,nr),0)))
        if not cands:
            ad=_rel_to_abs(robot.heading,'B')
            nc,nr=maze.next_cell(c,r,ad)
            if maze._valid(nc,nr): cands=[(ad,0)]
        if not cands: yield 'done'; return
        cands.sort(key=lambda x:x[1])
        for t in _turns(robot.heading,cands[0][0]): yield t
        yield 'forward'
    yield 'done'


# ══════════════════════════════════════════════════════════════
#  8. DEAD END FILLING
#     Pre-procesa el laberinto (mapa COMPLETO conocido).
#     Rellena callejones sin salida iterativamente.
#     Lo que queda es la ruta principal.
#     Muy visual: muestra que celdas son "callejones".
# ══════════════════════════════════════════════════════════════
def dead_end_filling(robot, maze):
    from maze import Maze
    cols,rows=maze.cols,maze.rows
    goal_set=set(maze.goal_cells)

    # Copiar estado de paredes en una matriz local
    blocked = [[False]*cols for _ in range(rows)]

    def open_count(c,r):
        if blocked[r][c]: return 0
        return sum(1 for d in Maze.DIR_LIST
                   if maze._valid(*maze.next_cell(c,r,d))
                   and maze.can_move(c,r,d)
                   and not blocked[maze.next_cell(c,r,d)[1]][maze.next_cell(c,r,d)[0]])

    # Llenar callejones iterativamente
    changed=True
    while changed:
        changed=False
        for r in range(rows):
            for c in range(cols):
                if (c,r)==maze.start or (c,r) in goal_set: continue
                if not blocked[r][c] and open_count(c,r)<=1:
                    blocked[r][c]=True; changed=True

    # Construir camino sobre celdas no bloqueadas con BFS
    start=maze.start
    queue=deque([(start,[start])]); seen={start}
    path=None
    while queue:
        (c,r),p=queue.popleft()
        if (c,r) in goal_set: path=p; break
        for d in Maze.DIR_LIST:
            nc,nr=maze.next_cell(c,r,d)
            if (nc,nr) not in seen and maze._valid(nc,nr) and maze.can_move(c,r,d) and not blocked[nr][nc]:
                seen.add((nc,nr)); queue.append(((nc,nr),p+[(nc,nr)]))

    if not path: path=maze.solve() or []
    for tc,tr in path[1:]:
        dc=tc-robot.col; dr=tr-robot.row
        tdir=_dir_from_delta(dc, dr)
        for t in _turns(robot.heading,tdir): yield t
        yield 'forward'
        if robot.is_at_goal(): break
    yield 'done'


# ══════════════════════════════════════════════════════════════
#  9. PLEDGE ALGORITHM
#     Soluciona el problema del wall follower en loops.
#     Mantiene un contador de giros totales (angulo acumulado).
#     Avanza recto hasta pared, luego sigue pared derecha
#     SOLO hasta que el contador de giros vuelva a 0.
#     Garantiza salir de loops cerrados.
# ══════════════════════════════════════════════════════════════
def pledge_algorithm(robot, maze):
    turn_count = 0   # +1 = giro derecha, -1 = giro izquierda
    MAX_STEPS = maze.cols * maze.rows * 10

    for _ in range(MAX_STEPS):
        if robot.is_at_goal(): break
        wL,wF,wR = _walls(robot)

        if turn_count == 0:
            # Modo libre: intentar avanzar recto
            if not wF:
                yield 'forward'
                continue
            # Chocamos con pared: iniciar seguimiento de pared
            # Girar izquierda hasta encontrar pasaje
            yield 'left'; turn_count -= 1
            continue

        # Modo seguimiento de pared derecha
        if not wR:
            # Pasaje a la derecha: girar derecha y avanzar
            yield 'right'; turn_count += 1
            yield 'forward'
        elif not wF:
            # Frente libre: avanzar
            yield 'forward'
        else:
            # Bloqueado: girar izquierda
            yield 'left'; turn_count -= 1

    yield 'done'


# ══════════════════════════════════════════════════════════════
#  10. RANDOM MOUSE
#     El robot elige una direccion aleatoria en cada celda
#     con preferencia a no retroceder.
#     No garantiza llegar en tiempo finito (pero siempre llega
#     en laberintos perfectos por probabilidad).
#     Util como baseline/comparacion de tiempo.
# ══════════════════════════════════════════════════════════════
def random_mouse(robot, maze):
    from maze import Maze
    rng = random.Random(42)
    MAX_STEPS = maze.cols * maze.rows * 50

    last_dir = None
    for _ in range(MAX_STEPS):
        if robot.is_at_goal(): break
        c,r=robot.col,robot.row
        # Pasillos abiertos
        avail=[]
        for d in Maze.DIR_LIST:
            nc,nr=maze.next_cell(c,r,d)
            if maze._valid(nc,nr) and maze.can_move(c,r,d):
                avail.append(d)
        if not avail: yield 'done'; return
        # Preferir no retroceder (si hay otra opcion)
        back = Maze.OPPOSITE[last_dir] if last_dir else None
        forward_opts = [d for d in avail if d!=back]
        opts = forward_opts if forward_opts else avail
        chosen = rng.choice(opts)
        for t in _turns(robot.heading, chosen): yield t
        yield 'forward'
        last_dir = chosen
    yield 'done'


# ══════════════════════════════════════════════════════════════
#  11. DIJKSTRA
#     Igual que BFS en laberintos no ponderados (todos los
#     pasos cuestan 1). Garantiza camino minimo.
#     Se incluye para comparacion didactica.
#     Mapa completo conocido.
# ══════════════════════════════════════════════════════════════
def dijkstra_solver(robot, maze):
    from maze import Maze
    goal_set=set(maze.goal_cells)
    start=maze.start
    dist_d={start:0}
    prev_d={start:None}
    pq=[(0,start)]
    while pq:
        d,cur=heapq.heappop(pq)
        if cur in goal_set:
            path=[]; node=cur
            while node: path.append(node); node=prev_d[node]
            path.reverse()
            for tc,tr in path[1:]:
                dc=tc-robot.col; dr=tr-robot.row
                tdir=_dir_from_delta(dc, dr)
                if tdir is None: continue
                for t in _turns(robot.heading,tdir): yield t
                yield 'forward'
                if robot.is_at_goal(): break
            yield 'done'; return
        c,r=cur
        for dir_ in Maze.DIR_LIST:
            nc,nr=maze.next_cell(c,r,dir_)
            if maze._valid(nc,nr) and maze.can_move(c,r,dir_):
                nd=d+1
                if (nc,nr) not in dist_d or nd<dist_d[(nc,nr)]:
                    dist_d[(nc,nr)]=nd; prev_d[(nc,nr)]=cur
                    heapq.heappush(pq,(nd,(nc,nr)))
    yield 'done'


# ══════════════════════════════════════════════════════════════
#  12. CHAIN / SPIRAL
#     Exploracion sistematica en espiral desde las paredes
#     hacia el centro. Util en laberintos con simetria.
#     Prioridad: derecha > frente > izq > 180.
#     Cambia a izquierda cuando detecta que ha girado mucho.
#     Hibrido entre wall follower y flood fill.
# ══════════════════════════════════════════════════════════════
def chain_spiral(robot, maze):
    visits={}; turn_budget=0
    for _ in range(maze.cols*maze.rows*12):
        if robot.is_at_goal(): break
        c,r=robot.col,robot.row
        visits[(c,r)]=visits.get((c,r),0)+1
        wL,wF,wR=_walls(robot)

        # Si hemos girado mucho seguido, intentar izquierda para "espiral"
        if turn_budget >= 3 and not wL:
            yield 'left'; turn_budget=0; yield 'forward'
        elif not wR:
            yield 'right'; turn_budget+=1; yield 'forward'
        elif not wF:
            yield 'forward'; turn_budget=0
        elif not wL:
            yield 'left'; turn_budget=0; yield 'forward'
        else:
            yield '180'; turn_budget=0; yield 'forward'
    yield 'done'


# ══════════════════════════════════════════════════════════════
#  Descripciones tecnicas
# ══════════════════════════════════════════════════════════════
ALGO_DESCRIPTIONS = {
    "Right Wall Follower": """\
  TIPO: Reactivo, sin memoria
  PRIORIDAD: Frente>Izq>Der>180
  SENSOR: Solo VL53L0X
  GARANTIA: NO (loops posibles)""",

    "Left Wall Follower": """\
  TIPO: Reactivo, sin memoria
  PRIORIDAD: Izq>Frente>Der>180
  SENSOR: Solo VL53L0X
  GARANTIA: NO (loops posibles)""",

    "Flood Fill (tiempo real)": """\
  TIPO: Mapeado incremental
  SENSOR: Descubre paredes en vivo
  MAPA: LOCAL, actualiza y retrocede
  GARANTIA: SI, siempre llega""",

    "BFS (camino optimo)": """\
  TIPO: Grafo, mapa completo
  MAPA: Conoce todo (2da vuelta)
  GARANTIA: SI + OPTIMO minimo
  BASE: Busqueda en anchura""",

    "A* (A-Star)": """\
  TIPO: Grafo heuristico
  HEURISTICA: Distancia Manhattan
  MAPA: Completo (2da vuelta)
  GARANTIA: SI + OPTIMO""",

    "Tremaux": """\
  TIPO: Marcado de pasillos
  REGLA: Nunca cruzar marca x2
  SENSOR: Solo VL53L0X
  GARANTIA: SI (no optimo)""",

    "Mano Derecha + Memoria": """\
  TIPO: Wall follower mejorado
  ANTI-LOOP: Elige menos visitada
  SENSOR: VL53L0X + tabla visitas
  GARANTIA: Mejor que pure WF""",

    "Dead End Filling": """\
  TIPO: Pre-proceso + BFS
  FASE 1: Llena callejones
  FASE 2: Sigue ruta principal
  GARANTIA: SI + casi optimo""",

    "Pledge Algorithm": """\
  TIPO: Wall follower mejorado
  CONTADOR: Acumula angulos giro
  FIX: Sigue pared hasta angulo=0
  GARANTIA: SI, resuelve loops""",

    "Random Mouse": """\
  TIPO: Exploracion aleatoria
  SEED: Reproducible (seed=42)
  PREFERENCIA: No retroceder
  GARANTIA: Si (tiempo variable)""",

    "Dijkstra": """\
  TIPO: Grafo ponderado
  IGUAL A BFS en mapa sin pesos
  MAPA: Completo (2da vuelta)
  GARANTIA: SI + OPTIMO""",

    "Chain / Spiral": """\
  TIPO: Wall follower hibrido
  PATRON: Espiral hacia el centro
  ANTI-LOOP: Budget de giros
  GARANTIA: Parcial""",
}