# ============================================================
#  TJ Telemetry  v3.0
#
#  Estrategia: grabar en WAYPOINTS (cada celda nueva + giros),
#  no por tiempo. Cada waypoint tiene fx/fy de posicion exacta.
#  El replay interpola VISUALMENTE entre waypoints consecutivos.
#
#  Para el ESP32 el formato es igual — enviar por Serial cuando
#  el robot llega a una nueva celda o gira:
#    TEL,<ts_ms>,<event>,<x>,<y>,<heading>,<ang>,<e1>,<e2>,<i>,<c>,<d>
# ============================================================
import csv, os, datetime
from pathlib import Path
from config import CELL_SIZE_MM

SESSIONS_DIR = Path(__file__).parent / 'sessions'
SESSIONS_DIR.mkdir(exist_ok=True)

CSV_HEADER = [
    'ts_ms','event','x','y','heading',
    'ang_z','enc1','enc2',
    'tof_izq','tof_cen','tof_der','extra'
]

# ─────────────────────────────────────────────────────────────
class TelemetryRecorder:
    def __init__(self, name=None):
        if name is None:
            name = datetime.datetime.now().strftime('sim_%Y%m%d_%H%M%S')
        self.path  = SESSIONS_DIR / f'{name}.csv'
        self._f    = open(self.path, 'w', newline='')
        self._w    = csv.writer(self._f)
        self._w.writerow(CSV_HEADER)
        self._f.flush()
        self.count = 0
        print(f'[TEL] Grabando -> {self.path.name}')

    def log(self, ts_ms, event, x, y, heading,
            ang_z=0.0, enc1=0, enc2=0,
            tof_izq=500, tof_cen=500, tof_der=500, extra=''):
        self._w.writerow([ts_ms, event, x, y, heading,
                          f'{ang_z:.1f}', enc1, enc2,
                          tof_izq, tof_cen, tof_der, extra])
        self._f.flush()
        self.count += 1

    def close(self):
        self._f.close()
        print(f'[TEL] Cerrado — {self.count} waypoints -> {self.path.name}')

# ─────────────────────────────────────────────────────────────
class TelemetrySession:
    def __init__(self, path):
        self.path = Path(path)
        self.rows = []
        self.idx  = 0
        self._load()

    def _load(self):
        with open(self.path, newline='') as f:
            rdr = csv.DictReader(f)
            for r in rdr:
                self.rows.append({
                    'ts_ms':   int(r['ts_ms']),
                    'event':   r['event'],
                    'x':       int(r['x']),
                    'y':       int(r['y']),
                    'heading': int(r['heading']),
                    'ang_z':   float(r['ang_z']),
                    'enc1':    int(r['enc1']),
                    'enc2':    int(r['enc2']),
                    'tof_izq': int(r['tof_izq']),
                    'tof_cen': int(r['tof_cen']),
                    'tof_der': int(r['tof_der']),
                    'extra':   r.get('extra',''),
                    # fx/fy = center of the cell (integer grid)
                    'fx': float(r['x']),
                    'fy': float(r['y']),
                })
        print(f'[TEL] Cargado: {self.path.name} — {len(self.rows)} waypoints')

    @property
    def total(self): return len(self.rows)
    @property
    def done(self):  return self.idx >= len(self.rows)
    @property
    def current(self): return self.rows[self.idx] if not self.done else None

    def next(self):
        r = self.rows[self.idx]; self.idx += 1; return r
    def reset(self): self.idx = 0

    def duration_ms(self):
        if len(self.rows) < 2: return 0
        return self.rows[-1]['ts_ms'] - self.rows[0]['ts_ms']

    def summary(self):
        events = [r['event'] for r in self.rows]
        return {
            'archivo':    self.path.name,
            'eventos':    len(self.rows),
            'avances':    sum(1 for e in events if e == 'FWD'),
            'giros':      sum(1 for e in events if 'TURN' in e),
            'metas':      events.count('GOAL'),
            'duracion_s': self.duration_ms() / 1000.0,
        }

# ─────────────────────────────────────────────────────────────
class ReplayController:
    """
    Reproduce una sesion waypoint a waypoint con interpolacion
    visual suave entre ellos.

    La velocidad funciona como factor de tiempo:
      speed=1  -> reproduce en tiempo real (segun ts_ms del CSV)
      speed=2  -> doble de rapido
      speed=10 -> 10x rapido
    """
    def __init__(self, session: TelemetrySession, robot, maze, ghost=False):
        self.session = session
        self.robot   = robot
        self.maze    = maze
        self.ghost   = ghost        # True = no tocar robot.col/row (modo fantasma)
        self._speed  = 1.0
        self.paused  = False
        self.finished= False
        self._t0     = None         # ts_ms del primer waypoint
        self._wall   = 0.0          # tiempo de simulacion acumulado (ms * speed)
        self._prev   = None
        self._next   = None
        self._load_next()

    def _load_next(self):
        if self.session.done:
            self.finished = True; return
        self._prev = self._next
        self._next = self.session.next()
        if self._t0 is None:
            self._t0 = self._next['ts_ms']

    def set_speed(self, s): self._speed = max(0.1, s)

    def tick(self, dt_ms: float):
        """Avanza la reproduccion. Retorna lista de waypoints que se cruzaron."""
        if self.paused or self.finished: return None
        self._wall += dt_ms * self._speed
        applied = []

        # Avanzar todos los waypoints cuyo tiempo relativo <= _wall
        while self._next and not self.finished:
            t_rel = self._next['ts_ms'] - self._t0
            if t_rel > self._wall: break
            applied.append(self._next)
            self._apply_discrete(self._next)
            self._load_next()

        # Interpolacion visual entre _prev y _next
        self._interpolate()
        return applied if applied else None

    def _interpolate(self):
        if not self._prev or not self._next: return
        t_prev = self._prev['ts_ms'] - self._t0
        t_next = self._next['ts_ms']  - self._t0
        span   = max(1, t_next - t_prev)
        alpha  = min(1.0, (self._wall - t_prev) / span)
        alpha  = 1.0 - (1.0 - alpha) ** 2   # ease-out

        fx = self._prev['fx'] + (self._next['fx'] - self._prev['fx']) * alpha
        fy = self._prev['fy'] + (self._next['fy'] - self._prev['fy']) * alpha

        # Interpolar angulo (ruta corta)
        a0 = self._prev['ang_z']; a1 = self._next['ang_z']
        da = ((a1 - a0 + 180) % 360) - 180
        fa = (a0 + da * alpha) % 360.0

        if self.ghost:
            # Actualizar solo atributos del fantasma (no toca el robot principal)
            self._fx = fx; self._fy = fy; self._fa = fa
        else:
            self.robot.fx     = fx
            self.robot.fy     = fy
            self.robot.fangle = fa

    def _apply_discrete(self, row):
        """Actualiza estado logico (celda, sensores). No toca fx/fy."""
        _H = {0:'N',1:'E',2:'S',3:'W'}
        heading = _H.get(row['heading'], 'N')
        if not self.ghost:
            self.robot.col     = row['x']
            self.robot.row     = row['y']
            self.robot.heading = heading
            self.robot._last_L = row['tof_izq']
            self.robot._last_C = row['tof_cen']
            self.robot._last_R = row['tof_der']
            self.robot.visited.add((row['x'], row['y']))
            if row['event'] == 'FWD':
                self.robot.steps         += 1
                self.robot.total_dist_mm += CELL_SIZE_MM
            elif 'TURN' in row['event']:
                self.robot.total_turns += 1

    # Ghost position accessors
    @property
    def gfx(self): return getattr(self,'_fx', self._next['fx'] if self._next else 0.)
    @property
    def gfy(self): return getattr(self,'_fy', self._next['fy'] if self._next else 0.)
    @property
    def gfa(self): return getattr(self,'_fa', self._next['ang_z'] if self._next else 0.)
    @property
    def gtof(self):
        r = self._prev or self._next
        return (r['tof_izq'],r['tof_cen'],r['tof_der']) if r else (500,500,500)

    def progress(self): return self.session.idx, self.session.total
    _apply = _apply_discrete   # compat


# ─────────────────────────────────────────────────────────────
class GhostState:
    """Simple container — ahora el ghost lo maneja ReplayController(ghost=True)."""
    def __init__(self):
        self.fx=0.; self.fy=0.; self.fangle=0.
        self.col=0; self.row=0; self.head='N'
        self.tof_izq=500; self.tof_cen=500; self.tof_der=500
        self.enc1=0; self.ang_z=0.

    def apply_row(self, row):
        _H={0:'N',1:'E',2:'S',3:'W'}
        self.col=row['x']; self.row=row['y']
        self.head=_H.get(row['heading'],'N')
        self.fx=row['fx']; self.fy=row['fy']
        self.fangle=row['ang_z']%360.
        self.tof_izq=row['tof_izq']
        self.tof_cen=row['tof_cen']
        self.tof_der=row['tof_der']
        self.enc1=row['enc1']
        self.ang_z=row['ang_z']

    def update_interp(self,p,n,a):
        pass  # handled by ReplayController(ghost=True)


def list_sessions():
    files = sorted(SESSIONS_DIR.glob('*.csv'), key=os.path.getmtime, reverse=True)
    return list(files)

SAMPLE_MS = 0   # legacy compat — no longer used