# ============================================================
#  TJ Simulator v2.3 — Main
# ============================================================
import pygame, pygame.gfxdraw
import sys, os, math, time
import tkinter as tk
from tkinter import filedialog, simpledialog

from config import *
import robot_config as RC
from maze import Maze
from maze_gen import generate
from robot import Robot
from algorithms import ALGORITHMS, ALGO_DESCRIPTIONS, get_algorithm

pygame.init()
pygame.font.init()

def load_font(size, bold=False):
    for name in ('Consolas','Courier New','Lucida Console','monospace'):
        try:
            f = pygame.font.SysFont(name, size, bold=bold)
            if f: return f
        except Exception: pass
    return pygame.font.SysFont(None, size, bold=bold)

FONT_LG = load_font(17, bold=True)
FONT_MD = load_font(15)
FONT_XS = load_font(13)
FONT_TJ = load_font(24, bold=True)

_tk_root = tk.Tk(); _tk_root.withdraw()

BH=26; BH2=24; SH=16; GAP=5; SEP=8

# ─────────────────────────────────────────────────────────────
#  WIDGETS
# ─────────────────────────────────────────────────────────────
class Button:
    def __init__(self, rect, label, color=None, text_color=None):
        self.rect=pygame.Rect(rect); self.label=label
        self.color=color or C_CARD
        self.hcolor=tuple(min(255,v+28) for v in self.color)
        self.dcolor=tuple(max(0,v-30) for v in self.color)
        self.tcolor=text_color or C_TEXT_H
        self.hovered=False; self.pressed=False; self.enabled=True

    def draw(self, surf):
        col=(self.dcolor if not self.enabled or self.pressed
             else self.hcolor if self.hovered else self.color)
        pygame.draw.rect(surf,col,self.rect,border_radius=4)
        pygame.draw.rect(surf,C_BORDER,self.rect,1,border_radius=4)
        s=FONT_XS.render(self.label,True,self.tcolor if self.enabled else C_TEXT_L)
        surf.blit(s,s.get_rect(center=self.rect.center))

    def handle_event(self, ev):
        if not self.enabled: return False
        if ev.type==pygame.MOUSEMOTION: self.hovered=self.rect.collidepoint(ev.pos)
        if ev.type==pygame.MOUSEBUTTONDOWN and ev.button==1:
            if self.rect.collidepoint(ev.pos): self.pressed=True; return True
        if ev.type==pygame.MOUSEBUTTONUP and ev.button==1: self.pressed=False
        return False


class Slider:
    def __init__(self, rect, label, options, current=1):
        self.rect=pygame.Rect(rect); self.label=label
        self.options=options; self.idx=current; self.dragging=False

    @property
    def value(self): return self.options[self.idx]

    def draw(self, surf):
        surf.blit(FONT_XS.render(f"{self.label}:",True,C_TEXT_L),(self.rect.x,self.rect.y-1))
        surf.blit(FONT_XS.render(self.value,True,C_TEXT_H),(self.rect.x+72,self.rect.y-1))
        ty=self.rect.y+16
        pygame.draw.rect(surf,C_CARD,(self.rect.x,ty,self.rect.w,10),border_radius=3)
        pygame.draw.rect(surf,C_BORDER,(self.rect.x,ty,self.rect.w,10),1,border_radius=3)
        fw=int(self.rect.w*(self.idx+1)/len(self.options))
        if fw: pygame.draw.rect(surf,C_RED_D,(self.rect.x,ty,fw,10),border_radius=3)
        tx=self.rect.x+fw-6
        pygame.draw.circle(surf,C_RED,(tx,ty+5),7)
        pygame.draw.circle(surf,C_TEXT_H,(tx,ty+5),2)

    def handle_event(self, ev):
        ty=self.rect.y+16
        tr=pygame.Rect(self.rect.x,ty,self.rect.w,10)
        if ev.type==pygame.MOUSEBUTTONDOWN and ev.button==1:
            if tr.inflate(0,12).collidepoint(ev.pos): self.dragging=True; self._set(ev.pos[0])
        if ev.type==pygame.MOUSEBUTTONUP: self.dragging=False
        if ev.type==pygame.MOUSEMOTION and self.dragging: self._set(ev.pos[0])

    def _set(self, x):
        n=len(self.options)
        self.idx=max(0,min(n-1,int((x-self.rect.x)/self.rect.w*n)))


class DropDown:
    def __init__(self, rect, options, current=0, open_up=False):
        self.rect=pygame.Rect(rect); self.options=options
        self.idx=current; self.open=False; self.hovered_item=-1
        self.open_up=open_up  # True = menu opens upward

    @property
    def value(self): return self.options[self.idx]

    def _menu_rect(self):
        ih=22
        if self.open_up:
            return pygame.Rect(self.rect.x, self.rect.y-ih*len(self.options),
                               self.rect.w, ih*len(self.options))
        return pygame.Rect(self.rect.x,self.rect.bottom,self.rect.w,ih*len(self.options))

    def draw(self, surf):
        col=C_CARD if not self.open else C_BORDER
        pygame.draw.rect(surf,col,self.rect,border_radius=4)
        pygame.draw.rect(surf,C_BORDER,self.rect,1,border_radius=4)
        ax,ay=self.rect.right-14,self.rect.centery
        # Arrow direction
        if self.open_up:
            pygame.draw.polygon(surf,C_TEXT_M,[(ax-5,ay+3),(ax+5,ay+3),(ax,ay-4)])
        else:
            pygame.draw.polygon(surf,C_TEXT_M,[(ax-5,ay-3),(ax+5,ay-3),(ax,ay+4)])
        surf.blit(FONT_XS.render(self.options[self.idx],True,C_TEXT_H),(self.rect.x+7,self.rect.y+5))
        if self.open:
            ih=22; mr=self._menu_rect()
            sh=pygame.Surface((mr.w+4,mr.h+4),pygame.SRCALPHA); sh.fill((0,0,0,120))
            surf.blit(sh,(mr.x-2,mr.y-2))
            pygame.draw.rect(surf,C_PANEL,mr,border_radius=4)
            pygame.draw.rect(surf,C_BORDER,mr,1,border_radius=4)
            for i,opt in enumerate(self.options):
                ir=pygame.Rect(mr.x,mr.y+i*ih,mr.w,ih)
                if i==self.hovered_item: pygame.draw.rect(surf,C_CARD,ir)
                if i==self.idx: pygame.draw.rect(surf,C_RED_D,ir.inflate(-4,-2),border_radius=3)
                surf.blit(FONT_XS.render(opt,True,C_TEXT_H),(ir.x+7,ir.y+4))

    def handle_event(self, ev):
        changed=False
        if ev.type==pygame.MOUSEBUTTONDOWN and ev.button==1:
            if self.rect.collidepoint(ev.pos): self.open=not self.open
            elif self.open:
                mr=self._menu_rect()
                if mr.collidepoint(ev.pos):
                    ih=22; idx=(ev.pos[1]-mr.y)//ih
                    if 0<=idx<len(self.options): self.idx=idx; changed=True
                self.open=False
        if ev.type==pygame.MOUSEMOTION and self.open:
            mr=self._menu_rect(); ih=22
            self.hovered_item=(ev.pos[1]-mr.y)//ih if mr.collidepoint(ev.pos) else -1
        return changed


# ─────────────────────────────────────────────────────────────
#  NUMBER FIELD (for config panel)
# ─────────────────────────────────────────────────────────────
class NumberField:
    def __init__(self, rect, label, value, fmt="{:.1f}", min_v=0, max_v=9999):
        self.rect=pygame.Rect(rect); self.label=label; self.value=value
        self.fmt=fmt; self.min_v=min_v; self.max_v=max_v
        self.active=False; self._text=fmt.format(value)

    def draw(self, surf):
        col=C_RED_D if self.active else C_CARD
        brd=C_RED if self.active else C_BORDER
        pygame.draw.rect(surf,col,self.rect,border_radius=3)
        pygame.draw.rect(surf,brd,self.rect,1,border_radius=3)
        lbl=FONT_XS.render(self.label+":",True,C_TEXT_L)
        surf.blit(lbl,(self.rect.x-lbl.get_width()-4,self.rect.y+3))
        txt=FONT_XS.render(self._text,True,C_TEXT_H if self.active else C_TEXT_M)
        surf.blit(txt,(self.rect.x+4,self.rect.y+3))

    def handle_event(self, ev):
        if ev.type==pygame.MOUSEBUTTONDOWN and ev.button==1:
            prev=self.active; self.active=self.rect.collidepoint(ev.pos)
            if self.active: self._text=self.fmt.format(self.value)
        if not self.active: return False
        if ev.type==pygame.KEYDOWN:
            if ev.key in (pygame.K_RETURN, pygame.K_TAB, pygame.K_KP_ENTER):
                try:
                    v=float(self._text)
                    self.value=max(self.min_v,min(self.max_v,v))
                except ValueError: pass
                self._text=self.fmt.format(self.value)
                self.active=False; return True
            elif ev.key==pygame.K_BACKSPACE: self._text=self._text[:-1]
            elif ev.unicode in '0123456789.-': self._text+=ev.unicode
        return False


# ─────────────────────────────────────────────────────────────
#  ROBOT CONFIG PANEL  (schematic + tooltips + Enter=recalc)
# ─────────────────────────────────────────────────────────────
class RobotConfigPanel:
    W = 720; H = 500

    # Tooltips for derived values
    TIPS = {
        "RPM efectivos": "MOTOR_RPM_RATED × (Voltaje_real / Voltaje_nom)",
        "Vel max":       "RPM_eff × π × Diámetro / 60   [mm/s]",
        "Celda real":    "Cell_size / (Vel_max × PWM_explore/255)  [s]",
        "Giro90 real":   "(π × Track/2) / (Vel_max × PWM_giro/255)  [s]",
        "CPR M1":        "PPR × Gear × 4  (cuadratura, 2 canales)",
        "CPR M2":        "PPR × Gear × 2  (un canal)",
        "mm/cnt":        "π × Diámetro / CPR_M1",
        "Pulsos/casilla":"Cell_size / mm_per_count",
        "Pulsos/giro90": "(π × Track/2) / mm_per_count",
    }

    def __init__(self, sw, sh):
        self.visible = False
        self.sw = sw; self.sh = sh
        self._hover_tip = ""
        self._tip_timer = 0
        self._tip_pos   = (0, 0)
        self._build()

    def _build(self):
        x0 = (self.sw - self.W) // 2
        y0 = (self.sh - self.H) // 2
        self.bg = pygame.Rect(x0, y0, self.W, self.H)

        # Field column: x0+130, row spacing 30
        lw = 128; fw = 82; fh = 20
        fx = x0 + lw + 14; y = y0 + 46; gap = 30

        def F(label, attr, row, fmt="{:.1f}", mn=0, mx=9999):
            return [NumberField(pygame.Rect(fx, y+row*gap, fw, fh),
                                label, getattr(RC, attr), fmt, mn, mx), attr]

        self.fields = [
            F("RPM nominales",  'MOTOR_RPM_RATED',   0, "{:.0f}", 1, 10000),
            F("Voltaje nom V",  'MOTOR_VOLT_RATED',  1, "{:.1f}", 1, 24),
            F("Voltaje real V", 'MOTOR_VOLT_SUPPLY', 2, "{:.1f}", 0.5, 24),
            F("Gear ratio",     'MOTOR_GEAR_RATIO',  3, "{:.0f}", 1, 1000),
            F("PPR Hall",       'MOTOR_PPR',         4, "{:.0f}", 1, 100),
            F("Rueda diam mm",  'WHEEL_DIAMETER_MM', 5, "{:.1f}", 10, 200),
            F("Track mm",       'ROBOT_TRACK_MM',    6, "{:.1f}", 20, 200),
            F("Ancho robot mm", 'ROBOT_WIDTH_MM',    7, "{:.0f}", 20, 100),
            F("Largo robot mm", 'ROBOT_LENGTH_MM',   8, "{:.0f}", 20, 100),
            F("Offset rueda Y", 'WHEEL_OFFSET_Y_MM', 9, "{:.1f}", -50, 50),
            F("Sensor front mm", 'SENSOR_FRONT_X_MM',10, "{:.1f}", 0, 100),
            F("Sensor side X mm",'SENSOR_SIDE_X_MM', 11, "{:.1f}", -50, 80),
            F("Sensor side Y mm",'SENSOR_SIDE_Y_MM', 12, "{:.1f}", 10, 80),
        ]

        bw = 100; by = y0 + self.H - 42; bx = x0 + 12
        self.btn_apply  = Button(pygame.Rect(bx,          by, bw, 28), "APLICAR",  C_RED, C_TEXT_H)
        self.btn_cancel = Button(pygame.Rect(bx+bw+6,     by, bw, 28), "CERRAR")
        self.btn_save   = Button(pygame.Rect(bx+2*(bw+6), by, bw, 28), "GUARDAR")
        self.btn_load   = Button(pygame.Rect(bx+3*(bw+6), by, bw, 28), "CARGAR")
        self._status = ""
        # Schematic area
        self._schema_rect = pygame.Rect(x0 + 380, y0 + 36, 310, 220)

    # ── Derived info lines with (key, value, tooltip_key) ────
    def _derived(self):
        RC.recompute()  # always fresh
        eff = RC.MOTOR_RPM_EFFECTIVE
        spd = eff * RC.WHEEL_CIRCUM_MM / 60.0
        return [
            ("RPM efectivos",  f"{eff:.1f} rpm"),
            ("Vel max",        f"{spd:.0f} mm/s"),
            ("Celda real",     f"{RC.MS_PER_CELL/1000:.2f} s"),
            ("Giro90 real",    f"{RC.MS_PER_90/1000:.2f} s"),
            ("CPR M1",         f"{RC.CPR_M1}  M2: {RC.CPR_M2}"),
            ("mm/cnt",         f"{RC.MM_PER_CNT_M1:.4f} mm"),
            ("Pulsos/casilla", f"{RC.PULSOS_CASILLA_M1}"),
            ("Pulsos/giro90",  f"{RC.PULSOS_GIRO_90_M1}"),
        ]

    # ── Draw robot schematic ─────────────────────────────────
    def _draw_schematic(self, surf):
        r = self._schema_rect
        pygame.draw.rect(surf, (25,25,30), r, border_radius=6)
        pygame.draw.rect(surf, C_DIVIDER, r, 1, border_radius=6)

        # Robot body scaled to fit
        W_mm = RC.ROBOT_WIDTH_MM; L_mm = RC.ROBOT_LENGTH_MM
        scale = min((r.w - 80) / max(W_mm, 1), (r.h - 80) / max(L_mm, 1))
        bw2 = int(W_mm * scale / 2); bh2 = int(L_mm * scale / 2)
        cx = r.x + r.w // 2; cy = r.y + r.h // 2 + 10

        # Body
        body = pygame.Rect(cx-bw2, cy-bh2, bw2*2, bh2*2)
        pygame.draw.rect(surf, C_ROBOT_BODY, body, border_radius=4)
        pygame.draw.rect(surf, C_ROBOT_ACCENT, body, 1, border_radius=4)

        # Direction arrow (North)
        pygame.draw.line(surf, C_RED, (cx, cy), (cx, cy-bh2-8), 2)
        pygame.draw.polygon(surf, C_RED, [(cx,cy-bh2-14),(cx-5,cy-bh2-6),(cx+5,cy-bh2-6)])

        # Wheels (rectangles on sides, centered at axle)
        tr_mm = RC.ROBOT_TRACK_MM; wl_mm = RC.WHEEL_DIAMETER_MM * 0.8
        track_px = int(tr_mm * scale / 2)
        ww_px = max(3, int(4 * scale)); wh_px = max(5, int(wl_mm * scale))
        off_y = int(RC.WHEEL_OFFSET_Y_MM * scale)   # longitudinal offset (affects turn center)
        for side in [-1, 1]:
            wx = cx + track_px * side
            wheel = pygame.Rect(wx - ww_px, cy - wh_px//2, ww_px*2, wh_px)
            pygame.draw.rect(surf, (18,18,22), wheel, border_radius=2)
            pygame.draw.rect(surf, (90,90,100), wheel, 1, border_radius=2)

        # Sensors — positioned per robot_config
        front_x = int(RC.SENSOR_FRONT_X_MM * scale)
        front_y = int(RC.SENSOR_FRONT_Y_MM * scale)
        side_x  = int(RC.SENSOR_SIDE_X_MM  * scale)  # forward offset
        side_y  = int(RC.SENSOR_SIDE_Y_MM  * scale)  # lateral distance
        # Front sensor
        pygame.draw.circle(surf, C_SENSOR_BEAM, (cx+front_y, cy-front_x), 5)
        # Side sensors (left and right, offset forward)
        for s in [-1, 1]:
            pygame.draw.circle(surf, C_SENSOR_BEAM,
                               (cx + s*side_y, cy - side_x), 4)
        # Show turn center offset due to wheel Y position
        if abs(RC.WHEEL_OFFSET_Y_MM) > 1:
            turn_y = int(RC.WHEEL_OFFSET_Y_MM * scale)
            pygame.draw.circle(surf, C_YELLOW, (cx, cy - turn_y), 4)
            surf.blit(FONT_XS.render('CG giro', True, C_YELLOW), (cx+6, cy-turn_y-7))
        # Beam lines from sensors
        pygame.draw.line(surf, (*C_SENSOR_BEAM[:3], 80) if True else C_SENSOR_BEAM,
                         (cx+front_y, cy-front_x),
                         (cx+front_y, cy-front_x-12), 1)

        # Dimension labels
        def dim_line(x1,y1,x2,y2,label,lx,ly):
            pygame.draw.line(surf, C_TEXT_L, (x1,y1),(x2,y2), 1)
            pygame.draw.line(surf, C_TEXT_L, (x1-3,y1),(x1+3,y1), 1)
            pygame.draw.line(surf, C_TEXT_L, (x2-3,y2),(x2+3,y2), 1)
            surf.blit(FONT_XS.render(label,True,C_TEXT_M),(lx,ly))

        dim_line(cx-bw2-12, cy-bh2, cx-bw2-12, cy+bh2,
                 f"{L_mm:.0f}mm", cx-bw2-52, cy-6)
        dim_line(cx-bw2, cy+bh2+10, cx+bw2, cy+bh2+10,
                 f"{W_mm:.0f}mm", cx-16, cy+bh2+14)
        dim_line(cx-track_px, cy+bh2+22, cx+track_px, cy+bh2+22,
                 f"T:{tr_mm:.0f}", cx-14, cy+bh2+26)

        # Title
        surf.blit(FONT_XS.render("ESQUEMA ROBOT", True, C_TEXT_L),
                  (r.x + r.w//2 - 50, r.y + 6))
        # Legend — two columns below schema, inside panel
        ly = r.bottom + 8
        legends = [
            ((200,20,20),  "Sensor frontal"),
            ((255,90,0),   "Sensores laterales"),
            ((255,200,0),  "Centro de giro (Y)"),
            ((140,140,150),"Eje de rueda"),
        ]
        col_w = r.w // 2
        for i, (c, txt) in enumerate(legends):
            lx = r.x + 6 + (i % 2) * col_w
            row = ly + (i // 2) * 15
            pygame.draw.circle(surf, c, (lx + 4, row + 5), 4)
            surf.blit(FONT_XS.render(txt, True, C_TEXT_L), (lx + 12, row))

    def draw(self, surf):
        if not self.visible: return
        # Overlay
        ov = pygame.Surface((self.sw, self.sh), pygame.SRCALPHA)
        ov.fill((0,0,0,150)); surf.blit(ov,(0,0))
        # Panel bg
        pygame.draw.rect(surf, C_PANEL, self.bg, border_radius=8)
        pygame.draw.rect(surf, C_BORDER, self.bg, 2, border_radius=8)
        # Title
        surf.blit(FONT_LG.render("CONFIG ROBOT FISICO", True, C_RED),
                  (self.bg.x+14, self.bg.y+10))
        surf.blit(FONT_XS.render("Max: 100×100mm  |  Edita y presiona ENTER por campo, luego APLICAR",
                                  True, C_TEXT_L),
                  (self.bg.x+14, self.bg.y+28))

        # Fields
        for fld, _ in self.fields:
            fld.draw(surf)

        # Derived values column (hover for tooltip)
        ix = self.bg.x + 240; iy = self.bg.y + 46
        mouse_pos = pygame.mouse.get_pos()
        for i, (key, val) in enumerate(self._derived()):
            row_rect = pygame.Rect(ix-2, iy+i*28, 130, 22)
            if row_rect.collidepoint(mouse_pos):
                pygame.draw.rect(surf, (40,40,50), row_rect, border_radius=3)
                self._hover_tip = self.TIPS.get(key, "")
                self._tip_pos   = (mouse_pos[0]+12, mouse_pos[1]-20)
            kcol = C_TEAL; vcol = C_TEXT_H
            surf.blit(FONT_XS.render(key+":", True, kcol), (ix, iy+i*28))
            surf.blit(FONT_XS.render(val, True, vcol),     (ix+4, iy+i*28+13))

        # Schematic
        self._draw_schematic(surf)

        # Buttons
        for b in [self.btn_apply, self.btn_cancel, self.btn_save, self.btn_load]:
            b.draw(surf)

        # Status
        if self._status:
            surf.blit(FONT_XS.render(self._status, True, C_GREEN),
                      (self.bg.x+14, self.bg.y+self.H-14))

        # Tooltip (drawn last, on top)
        if self._hover_tip:
            tw = FONT_XS.render(self._hover_tip, True, C_TEXT_H)
            tp = pygame.Rect(self._tip_pos[0], self._tip_pos[1],
                             tw.get_width()+10, 20)
            # Keep on screen
            if tp.right > self.sw: tp.x = self.sw - tp.w - 4
            if tp.bottom > self.sh: tp.y = self._tip_pos[1] - 24
            pygame.draw.rect(surf, (40,40,55), tp, border_radius=3)
            pygame.draw.rect(surf, C_BORDER, tp, 1, border_radius=3)
            surf.blit(tw, (tp.x+5, tp.y+3))
            self._hover_tip = ""  # reset each frame

    def handle_event(self, ev, console):
        if not self.visible: return False
        changed = False
        for fld, attr in self.fields:
            if fld.handle_event(ev):
                # Enter was pressed on a field: update RC attr and recompute
                setattr(RC, attr, fld.value)
                RC.recompute()
                changed = True

        if self.btn_apply.handle_event(ev):
            # Apply all field values at once
            for fld, attr in self.fields:
                setattr(RC, attr, fld.value)
            RC.recompute()
            self._build()
            self.visible = False
            console.log("Config robot aplicada.", C_GREEN)
            console.log(f"  RPM={RC.MOTOR_RPM_EFFECTIVE:.0f}  "
                        f"celda={RC.MS_PER_CELL/1000:.2f}s  "
                        f"giro={RC.MS_PER_90/1000:.2f}s", C_TEAL)
            return True

        if self.btn_cancel.handle_event(ev):
            self._build(); self.visible = False; return True

        if self.btn_save.handle_event(ev):
            r2 = tk.Tk(); r2.withdraw()
            path = filedialog.asksaveasfilename(
                title="Guardar config robot", defaultextension=".ini",
                filetypes=[("Config","*.ini")], parent=r2)
            if path:
                with open(path, 'w') as f:
                    for fld, attr in self.fields:
                        f.write(f"{attr}={fld.value}\n")
                self._status = "Guardado"
                console.log(f"Config guardada: {path}", C_GREEN)
            r2.destroy(); return True

        if self.btn_load.handle_event(ev):
            r2 = tk.Tk(); r2.withdraw()
            path = filedialog.askopenfilename(
                title="Cargar config robot",
                filetypes=[("Config","*.ini")], parent=r2)
            if path:
                try:
                    with open(path) as f:
                        for line in f:
                            if '=' in line:
                                k, v = line.strip().split('=', 1)
                                if hasattr(RC, k.strip()):
                                    setattr(RC, k.strip(), float(v))
                    RC.recompute(); self._build()
                    self._status = "Cargado"
                    console.log(f"Config cargada: {path}", C_GREEN)
                except Exception as e:
                    self._status = f"Error: {e}"
            r2.destroy(); return True

        # Close on click outside
        if (ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1
                and not self.bg.collidepoint(ev.pos)):
            self._build(); self.visible = False; return True
        return changed

# ─────────────────────────────────────────────────────────────
#  MAZE RENDERER
# ─────────────────────────────────────────────────────────────
class MazeRenderer:
    WALL_W=3
    def __init__(self, maze_rect):
        self.maze_rect=pygame.Rect(maze_rect)
        self.show_flood=False; self.show_solution=False
        self.show_sensors=True; self.show_visited=True
        self.solution_path=None

    def cell_size(self, maze):
        cw=(self.maze_rect.w-16)//maze.cols
        ch=(self.maze_rect.h-16)//maze.rows
        return max(12,min(cw,ch))

    def origin(self, maze):
        cs=self.cell_size(maze)
        return (self.maze_rect.x+(self.maze_rect.w-cs*maze.cols)//2,
                self.maze_rect.y+(self.maze_rect.h-cs*maze.rows)//2, cs)

    def _prox(self, robot, maze):
        prox=robot.wall_proximity()
        w_set=set(); d_set=set()
        col=max(0,min(maze.cols-1,int(robot.fx)))
        row=max(0,min(maze.rows-1,int(robot.fy)))
        for d,(dist,hw) in prox.items():
            if not hw: continue
            if   dist<COLLISION_DANGER_DIST: d_set.add((col,row,d))
            elif dist<COLLISION_WARN_DIST:   w_set.add((col,row,d))
        return w_set,d_set

    def draw(self, surf, maze, robot):
        pygame.draw.rect(surf,C_MAZE_BG,self.maze_rect)
        x0,y0,cs=self.origin(maze)
        gs=set(maze.goal_cells)
        ww,dw=self._prox(robot,maze)

        for r in range(maze.rows):
            for c in range(maze.cols):
                px,py=x0+c*cs,y0+r*cs
                if   (c,r) in gs:     col=C_GOAL_CELL
                elif (c,r)==maze.start: col=C_START_CELL
                elif self.show_flood and maze.flood[r][c]<9999:
                    t=min(1.0,maze.flood[r][c]/max(1,maze.cols*maze.rows))
                    col=tuple(int(C_FLOOD_LO[i]+t*(C_FLOOD_HI[i]-C_FLOOD_LO[i])) for i in range(3))
                elif self.show_visited and (c,r) in robot.visited: col=C_VISITED
                else: col=C_FLOOR
                pygame.draw.rect(surf,col,(px+1,py+1,cs-1,cs-1))

        if cs>=16:
            gc,gr=maze.goal
            lbl=FONT_XS.render("META",True,C_GREEN)
            surf.blit(lbl,lbl.get_rect(center=(x0+gc*cs+cs,y0+gr*cs+cs)))

        if self.show_solution and self.solution_path:
            pts=[(x0+sc*cs+cs//2,y0+sr*cs+cs//2) for sc,sr in self.solution_path]
            if len(pts)>1: pygame.draw.lines(surf,C_GREEN,False,pts,3)
            for pt in pts: pygame.draw.circle(surf,C_GREEN,pt,3)

        for r in range(maze.rows):
            for c in range(maze.cols):
                px,py=x0+c*cs,y0+r*cs
                for d,(x1,y1,x2,y2) in [
                    ('N',(px,py,px+cs,py)),('S',(px,py+cs,px+cs,py+cs)),
                    ('W',(px,py,px,py+cs)),('E',(px+cs,py,px+cs,py+cs))]:
                    if not maze.walls[r][c][d]: continue
                    if   (c,r,d) in dw: wc=C_WALL_DANGER; wt=self.WALL_W+2
                    elif (c,r,d) in ww: wc=C_WALL_WARN;   wt=self.WALL_W+1
                    else:               wc=C_WALL;         wt=self.WALL_W
                    pygame.draw.line(surf,wc,(x1,y1),(x2,y2),wt)

        for r in range(maze.rows+1):
            for c in range(maze.cols+1):
                pygame.draw.rect(surf,(170,170,175),(x0+c*cs-2,y0+r*cs-2,4,4))

        if cs>=18:
            sc2,sr2=maze.start
            surf.blit(FONT_XS.render("S",True,C_BLUE),(x0+sc2*cs+2,y0+sr2*cs+2))

        if self.show_sensors: self._draw_sensors(surf,robot,x0,y0,cs)
        self._draw_robot(surf,robot,x0,y0,cs)

        if self.show_flood and cs>=28:
            for r in range(maze.rows):
                for c in range(maze.cols):
                    v=maze.flood[r][c]
                    if v<9999:
                        ts=FONT_XS.render(str(v),True,C_TEXT_L)
                        surf.blit(ts,(x0+c*cs+cs//2-ts.get_width()//2,
                                      y0+r*cs+cs//2-ts.get_height()//2))

    def _draw_sensors(self, surf, robot, x0, y0, cs):
        rx=x0+robot.fx*cs+cs/2; ry=y0+robot.fy*cs+cs/2
        bm=pygame.Surface(surf.get_size(),pygame.SRCALPHA)
        for off,dist,alpha in [(-90,robot._beam_L/CELL_SIZE_MM,160),
                                (  0,robot._beam_C/CELL_SIZE_MM,200),
                                ( 90,robot._beam_R/CELL_SIZE_MM,160)]:
            ang=math.radians((robot.fangle+off)%360)
            dx=math.sin(ang); dy=-math.cos(ang)
            dp=dist*cs
            ex,ey=int(rx+dx*dp),int(ry+dy*dp)
            pygame.draw.line(bm,(*C_SENSOR_BEAM,alpha),(int(rx),int(ry)),(ex,ey),2)
            pygame.draw.circle(bm,(*C_SENSOR_BEAM,230),(ex,ey),4)
            pygame.draw.circle(bm,(*C_SENSOR_BEAM,40),(ex,ey),9)
        surf.blit(bm,(0,0))

    def _draw_robot(self, surf, robot, x0, y0, cs):
        rx=x0+robot.fx*cs+cs/2; ry=y0+robot.fy*cs+cs/2
        half=max(7,int(cs*0.42))//2
        rad=math.radians(robot.fangle)
        dx=math.sin(rad); dy=-math.cos(rad)
        px=-dy;           py=dx

        # Shadow
        sh=pygame.Surface(surf.get_size(),pygame.SRCALPHA)
        spts=[(int(rx+(lx*px-ly*dx)*half+2),int(ry+(lx*py-ly*dy)*half+2))
              for lx,ly in [(-1,-1),(1,-1),(1,1),(-1,1)]]
        pygame.draw.polygon(sh,(0,0,0,50),spts)
        surf.blit(sh,(0,0))

        # Body
        pts=[(int(rx+(lx*px-ly*dx)*half),int(ry+(lx*py-ly*dy)*half))
             for lx,ly in [(-1,-1),(1,-1),(1,1),(-1,1)]]
        pygame.draw.polygon(surf,C_ROBOT_BODY,pts)
        pygame.draw.polygon(surf,C_ROBOT_ACCENT,pts,2)

        # Direction arrow
        tip_x=rx+dx*half; tip_y=ry+dy*half
        tri=[(int(tip_x+dx*half*0.55),int(tip_y+dy*half*0.55)),
             (int(tip_x+px*half*0.38),int(tip_y+py*half*0.38)),
             (int(tip_x-px*half*0.38),int(tip_y-py*half*0.38))]
        pygame.draw.polygon(surf,C_RED,tri)

        # Wheels (rectangles on sides, centered on axle)
        if cs>=20:
            ww=max(2,half//4); wh=max(3,int(half*0.85))
            for side in [-1,1]:
                wcx=rx+px*half*side; wcy=ry+py*half*side
                wp=[(int(wcx+px*lf+dx*lt),int(wcy+py*lf+dy*lt))
                    for lf,lt in [(-ww,-wh),(ww,-wh),(ww,wh),(-ww,wh)]]
                pygame.draw.polygon(surf,(18,18,22),wp)
                pygame.draw.polygon(surf,(70,70,80),wp,1)
                pygame.draw.circle(surf,(55,55,65),(int(wcx),int(wcy)),max(2,ww-1))

        pygame.draw.circle(surf,C_TEXT_H,(int(rx),int(ry)),2)

        # Trail
        if robot.state=='moving' and robot.move_progress<0.88:
            fx=x0+robot.move_from_fx*cs+cs/2; fy=y0+robot.move_from_fy*cs+cs/2
            tr=pygame.Surface(surf.get_size(),pygame.SRCALPHA)
            al=int(90*(1.0-robot.move_progress))
            pygame.draw.line(tr,(*C_ROBOT_ACCENT,al),(int(fx),int(fy)),(int(rx),int(ry)),3)
            surf.blit(tr,(0,0))

        # Rotation arc
        elif robot.state=='rotating' and abs(robot.rot_to-robot.rot_from)>5:
            arc=pygame.Surface(surf.get_size(),pygame.SRCALPHA)
            ar=int(half*1.5)
            a1=math.radians(robot.rot_from-90); a2=math.radians(robot.fangle-90)
            amin,amax=min(a1,a2),max(a1,a2)
            if amax-amin>0.05:
                try:
                    pygame.draw.arc(arc,(*C_YELLOW,100),
                                    (int(rx)-ar,int(ry)-ar,ar*2,ar*2),amin,amax,2)
                except Exception: pass
            surf.blit(arc,(0,0))

    def px_to_cell(self, px, py, maze):
        x0,y0,cs=self.origin(maze)
        c=(px-x0)//cs; r=(py-y0)//cs
        return (int(c),int(r)) if 0<=c<maze.cols and 0<=r<maze.rows else None

    def nearest_wall(self, px, py, maze):
        x0,y0,cs=self.origin(maze); m=cs*0.28
        for r in range(maze.rows):
            for c in range(maze.cols):
                cx,cy=x0+c*cs,y0+r*cs
                if abs(py-cy)<m    and cx<px<cx+cs: return c,r,'N'
                if abs(py-(cy+cs))<m and cx<px<cx+cs: return c,r,'S'
                if abs(px-cx)<m    and cy<py<cy+cs: return c,r,'W'
                if abs(px-(cx+cs))<m and cy<py<cy+cs: return c,r,'E'
        return None


# ─────────────────────────────────────────────────────────────
#  CONSOLE
# ─────────────────────────────────────────────────────────────
class Console:
    MAX=200
    def __init__(self, rect):
        self.rect=pygame.Rect(rect); self.lines=[]; self.scroll=0

    def log(self, msg, color=None):
        for line in str(msg).split('\n'):
            self.lines.append((line,color or C_TEXT_M))
        if len(self.lines)>self.MAX: self.lines=self.lines[-self.MAX:]
        self.scroll=0

    def clear(self): self.lines=[]

    def draw(self, surf):
        pygame.draw.rect(surf,C_BG,self.rect)
        pygame.draw.line(surf,C_BORDER,(self.rect.x,self.rect.y),(self.rect.right,self.rect.y),1)
        lh=14; vis=(self.rect.h-6)//lh
        start=max(0,len(self.lines)-vis-self.scroll)
        for i,(line,col) in enumerate(self.lines[start:start+vis]):
            surf.blit(FONT_XS.render(line,True,col),(self.rect.x+8,self.rect.y+4+i*lh))

    def handle_event(self, ev):
        if ev.type==pygame.MOUSEWHEEL:
            if self.rect.collidepoint(pygame.mouse.get_pos()):
                self.scroll=max(0,min(len(self.lines),self.scroll-ev.y*2))


# ─────────────────────────────────────────────────────────────
#  SIMULATOR
# ─────────────────────────────────────────────────────────────
class TJSimulator:
    def __init__(self):
        self.screen=pygame.display.set_mode((SCREEN_W,SCREEN_H),pygame.RESIZABLE)
        pygame.display.set_caption(TITLE)
        self.clock=pygame.time.Clock(); self.running=True

        self.maze=generate(DEFAULT_COLS,DEFAULT_ROWS)
        self.robot=Robot(self.maze)

        self.sim_running=False; self.sim_paused=False
        self.algo_gen=None; self.algo_name=ALGORITHMS[0]
        self.elapsed_ms=0; self.start_time=None
        self.sim_robot_ms=0; self._step_acc=0.0
        self._peeked=None
        self.edit_mode=False

        self.solution_path=self.maze.solve()
        W,H=SCREEN_W,SCREEN_H
        self.renderer=MazeRenderer(pygame.Rect(0,HEADER_H,W-PANEL_W,H-HEADER_H-CONSOLE_H))
        self.renderer.solution_path=self.solution_path
        self.console=Console(pygame.Rect(0,H-CONSOLE_H,W-PANEL_W,CONSOLE_H))

        self._build_widgets(); self._layout(W,H)
        self._rcfg=RobotConfigPanel(W,H)

        self.console.log("TJ Simulator v2.3 — Micromouse",C_RED)
        self.console.log(f"Motor: {RC.MOTOR_RPM_EFFECTIVE:.0f} RPM eff  "
                         f"Celda real: {RC.MS_PER_CELL/1000:.2f}s",C_TEXT_M)

    def _build_widgets(self):
        self.btn_gen=Button((0,0,1,1),"GENERAR")
        self.btn_load=Button((0,0,1,1),"CARGAR")
        self.btn_save=Button((0,0,1,1),"GUARDAR")
        self.btn_edit=Button((0,0,1,1),"EDITAR",C_CARD)
        self.btn_robot_cfg=Button((0,0,1,1),"Config Robot",C_CARD)
        self.dd_algo=DropDown((0,0,1,1),ALGORITHMS,0)
        self.sl_speed=Slider((0,0,1,1),"Velocidad",list(RC.PHYSICS_SPEEDS.keys()),1)
        self.btn_run=Button((0,0,1,1),">> RUN",C_RED,C_TEXT_H)
        self.btn_pause=Button((0,0,1,1),"|| PAUSE")
        self.btn_step=Button((0,0,1,1),">| STEP")
        self.btn_reset=Button((0,0,1,1),"<> RESET")
        self.btn_flood=Button((0,0,1,1),"Flood Fill")
        self.btn_sol=Button((0,0,1,1),"Solucion")
        self.btn_sensors=Button((0,0,1,1),"Sensores")
        self.btn_visited=Button((0,0,1,1),"Visitadas")
        self.btn_clear=Button((0,0,1,1),"Limpiar consola")

    def _layout(self, W, H):
        px=W-PANEL_W+8; pw=PANEL_W-16; bw=(pw-4)//2
        bot=H-CONSOLE_H-4; y=HEADER_H+6

        y+=SH  # LABERINTO
        self.btn_gen.rect=pygame.Rect(px,y,pw,BH); y+=BH+GAP
        self.btn_load.rect=pygame.Rect(px,y,bw,BH)
        self.btn_save.rect=pygame.Rect(px+bw+4,y,bw,BH); y+=BH+GAP
        self.btn_edit.rect=pygame.Rect(px,y,bw,BH)
        self.btn_robot_cfg.rect=pygame.Rect(px+bw+4,y,bw,BH); y+=BH+GAP
        y+=SEP

        y+=SH  # ALGORITMO
        self.dd_algo.rect=pygame.Rect(px,y,pw,BH); y+=BH+GAP
        self._algo_desc_y=y; y+=3*13+GAP+SEP

        y+=SH  # VELOCIDAD
        self.sl_speed.rect=pygame.Rect(px,y,pw,1); y+=30+SEP

        y+=SH  # CONTROL
        self.btn_run.rect=pygame.Rect(px,y,bw,BH)
        self.btn_pause.rect=pygame.Rect(px+bw+4,y,bw,BH); y+=BH+GAP
        self.btn_step.rect=pygame.Rect(px,y,bw,BH)
        self.btn_reset.rect=pygame.Rect(px+bw+4,y,bw,BH); y+=BH+SEP

        y+=SH  # VISUALIZAR
        self.btn_flood.rect=pygame.Rect(px,y,bw,BH2)
        self.btn_sol.rect=pygame.Rect(px+bw+4,y,bw,BH2); y+=BH2+GAP
        self.btn_sensors.rect=pygame.Rect(px,y,bw,BH2)
        self.btn_visited.rect=pygame.Rect(px+bw+4,y,bw,BH2); y+=BH2+SEP

        self._robot_y=y; self._robot_bot=bot; self._px=px; self._pw=pw
        self.btn_clear.rect=pygame.Rect(px,H-CONSOLE_H+4,pw,22)

    def run(self):
        while self.running:
            dt=self.clock.tick(FPS)
            self._events()
            self._update(dt)
            self._draw()
        pygame.quit(); sys.exit()

    def _events(self):
        for ev in pygame.event.get():
            if ev.type==pygame.QUIT: self.running=False
            if ev.type==pygame.VIDEORESIZE:
                W,H=ev.w,ev.h
                self.renderer.maze_rect=pygame.Rect(0,HEADER_H,W-PANEL_W,H-HEADER_H-CONSOLE_H)
                self.console.rect=pygame.Rect(0,H-CONSOLE_H,W-PANEL_W,CONSOLE_H)
                self._layout(W,H)
                self._rcfg.sw=W; self._rcfg.sh=H; self._rcfg._build()

            # Config panel eats events first when visible
            if self._rcfg.visible:
                self._rcfg.handle_event(ev,self.console)
                continue   # don't pass to rest of UI

            if ev.type==pygame.KEYDOWN: self._key(ev)
            self._ui(ev)
            if self.edit_mode: self._editor(ev)
            self.console.handle_event(ev)

    def _key(self, ev):
        if   ev.key==pygame.K_SPACE: self._toggle_run()
        elif ev.key==pygame.K_r:     self._do_reset()
        elif ev.key==pygame.K_e:     self.edit_mode=not self.edit_mode
        elif ev.key==pygame.K_s and not(ev.mod&pygame.KMOD_CTRL): self._do_step()
        elif ev.key==pygame.K_s and(ev.mod&pygame.KMOD_CTRL): self._do_save()
        elif ev.key==pygame.K_o and(ev.mod&pygame.KMOD_CTRL): self._do_load()

    def _ui(self, ev):
        # When a dropdown is open, let ONLY that dropdown handle the event
        if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
            for dd in [self.dd_algo]:
                if dd.open:
                    dd.handle_event(ev)
                    return   # eat click so buttons below don't fire

        # All widget handlers
        if self.btn_run.handle_event(ev):     self._toggle_run()
        if self.btn_pause.handle_event(ev):   self._toggle_pause()
        if self.btn_step.handle_event(ev):    self._do_step()
        if self.btn_reset.handle_event(ev):   self._do_reset()
        if self.btn_gen.handle_event(ev):     self._do_gen()
        if self.btn_load.handle_event(ev):    self._do_load()
        if self.btn_save.handle_event(ev):    self._do_save()
        if self.btn_clear.handle_event(ev):   self.console.clear()

        # EDITAR — toggles edit mode directly
        if self.btn_edit.handle_event(ev):
            self.edit_mode = not self.edit_mode
            if self.edit_mode:
                self.console.log(
                    "EDITAR ON  |  Click-Izq=toggle pared  "
                    "Click-Der=mover inicio  Shift+Click-Der=mover meta  "
                    "E=salir", C_YELLOW)
            else:
                self.console.log("Modo edicion OFF", C_TEXT_L)

        if self.btn_robot_cfg.handle_event(ev):
            W,H=self.screen.get_size()
            self._rcfg.sw=W; self._rcfg.sh=H; self._rcfg._build()
            self._rcfg.visible=True

        if self.btn_flood.handle_event(ev):   self.renderer.show_flood    = not self.renderer.show_flood
        if self.btn_sol.handle_event(ev):     self.renderer.show_solution = not self.renderer.show_solution
        if self.btn_sensors.handle_event(ev): self.renderer.show_sensors  = not self.renderer.show_sensors
        if self.btn_visited.handle_event(ev): self.renderer.show_visited  = not self.renderer.show_visited

        # Algorithm dropdown
        if self.dd_algo.handle_event(ev):
            self.algo_name = self.dd_algo.value
            if self.sim_running: self._do_reset()
            self.console.log(f"Algoritmo: {self.algo_name}", C_YELLOW)
            W,H = self.screen.get_size(); self._layout(W,H)


        self.sl_speed.handle_event(ev)

    def _handle_edit_modal_click(self, ev):
        return False  # deprecated
        if ev.type==pygame.MOUSEBUTTONDOWN and ev.button==1:
            if hasattr(self,'_tgl_rect') and self._tgl_rect.collidepoint(ev.pos):
                self.edit_mode=not self.edit_mode
                if self.edit_mode:
                    self.console.log("Paredes: ON — Click izq para toggle",C_YELLOW)
                return True
        return False

    def _editor(self, ev):
        if ev.type==pygame.MOUSEBUTTONDOWN and ev.button==1:
            if self.renderer.maze_rect.collidepoint(ev.pos):
                res=self.renderer.nearest_wall(*ev.pos,self.maze)
                if res:
                    self.maze.toggle_wall(*res); self.maze.compute_flood()
                    self.solution_path=self.maze.solve()
                    self.renderer.solution_path=self.solution_path
        if ev.type==pygame.MOUSEBUTTONDOWN and ev.button==3:
            if self.renderer.maze_rect.collidepoint(ev.pos):
                cell=self.renderer.px_to_cell(*ev.pos,self.maze)
                if cell:
                    if pygame.key.get_mods()&pygame.KMOD_SHIFT:
                        gc,gr=cell
                        if gc+1<self.maze.cols and gr+1<self.maze.rows:
                            self.maze.goal=cell
                            self.console.log(f"Meta -> {cell}",C_GREEN)
                    else:
                        self.maze.start=cell
                        self.robot.col,self.robot.row=cell
                        self.robot.fx=float(cell[0]); self.robot.fy=float(cell[1])
                        self.console.log(f"Inicio -> {cell}",C_BLUE)
                    self.maze.compute_flood()
                    self.solution_path=self.maze.solve()
                    self.renderer.solution_path=self.solution_path

    # ── Simulation ────────────────────────────────────────────
    def _boot_sequence(self):
        import robot_config as _RC
        self.console.log("", C_TEXT_L)
        self.console.log("ESP-ROM:esp32s3-20210327", C_TEXT_L)
        self.console.log("rst:0x1 (POWERON),boot:0x9 (SPI_FAST_FLASH_BOOT)", C_TEXT_L)
        self.console.log("[TJ SYSTEM] Booting...", C_GREEN)
        self.console.log("[INIT] VL53L0X ......... DER OK | CEN OK | IZQ OK", C_GREEN)
        self.console.log("[INIT] ENCODERS ........ A OK | B OK", C_GREEN)
        self.console.log("[INIT] GY-91 ........... OK  (Norte virtual calibrado)", C_GREEN)
        self.console.log("[INIT] COLOR SENSOR .... OK", C_GREEN)
        self.console.log("[SYS] All systems OK", C_GREEN)
        self.console.log(
            f"[SYS] RPM={_RC.MOTOR_RPM_EFFECTIVE:.0f}  "
            f"celda={_RC.MS_PER_CELL/1000:.2f}s  "
            f"giro={_RC.MS_PER_90/1000:.2f}s", C_TEAL)
        self.console.log(
            f"[SYS] {self.maze.cols}x{self.maze.rows}  "
            f"start={self.maze.start}  algo={self.algo_name}", C_TEAL)
        self.console.log("[READY] >> Iniciando run...", C_RED)
        self.console.log("", C_TEXT_L)

    def _toggle_run(self):
        if not self.sim_running:
            self._boot_sequence()
            self.sim_running=True; self.sim_paused=False
            self.start_time=time.time(); self._step_acc=0.0; self._peeked=None
            self.algo_gen=get_algorithm(self.algo_name,self.robot,self.maze)
        else: self.sim_running=False

    def _toggle_pause(self):
        self.sim_paused=not self.sim_paused

    def _do_reset(self):
        self.sim_running=False; self.sim_paused=False
        self.algo_gen=None; self.robot.reset()
        self.elapsed_ms=0; self.start_time=None
        self.sim_robot_ms=0; self._step_acc=0.0; self._peeked=None
        self.console.log("Reset.",C_TEXT_L)

    def _do_step(self):
        if self.algo_gen is None:
            self.algo_gen=get_algorithm(self.algo_name,self.robot,self.maze)
        self._exec()

    def _do_gen(self):
        self._do_reset()
        try:
            ans=simpledialog.askstring("Generar","Tamano (ColsxRows):",
                initialvalue=f"{self.maze.cols}x{self.maze.rows}",parent=_tk_root)
            if ans:
                p=ans.lower().replace(',','x').split('x')
                cols=max(4,min(32,int(p[0].strip())))
                rows=max(4,min(32,int(p[-1].strip())))
            else: cols,rows=self.maze.cols,self.maze.rows
        except Exception: cols,rows=DEFAULT_COLS,DEFAULT_ROWS
        corner='bottom_left'
        self.maze=generate(cols,rows,start_corner=corner)
        self.robot=Robot(self.maze)
        self.solution_path=self.maze.solve()
        self.renderer.solution_path=self.solution_path
        W,H=self.screen.get_size(); self._layout(W,H)
        self.console.log(f"Laberinto {cols}x{rows} ({corner})",C_GREEN)

    def _do_load(self):
        self._do_reset()
        path=filedialog.askopenfilename(title="Cargar",
            filetypes=[("txt","*.txt"),("Todos","*.*")],parent=_tk_root)
        if not path: return
        try:
            with open(path) as f: text=f.read()
            self.maze=(Maze.from_map_format(text) if '+' in text and '-' in text
                       else Maze.from_num_format(text))
            self.robot=Robot(self.maze); self.solution_path=self.maze.solve()
            self.renderer.solution_path=self.solution_path
            W,H=self.screen.get_size(); self._layout(W,H)
            self.console.log(f"Cargado: {self.maze.cols}x{self.maze.rows}",C_GREEN)
        except Exception as e: self.console.log(f"Error: {e}",C_RED)

    def _do_save(self):
        path=filedialog.asksaveasfilename(title="Guardar",defaultextension=".txt",
            filetypes=[("txt","*.txt")],parent=_tk_root)
        if not path: return
        fmt=simpledialog.askstring("Formato","'map' o 'num':",initialvalue="map",parent=_tk_root)
        try:
            text=(self.maze.to_num_format() if fmt and fmt.lower()=='num'
                  else self.maze.to_map_format())
            with open(path,'w') as f: f.write(text)
            self.console.log(f"Guardado: {os.path.basename(path)}",C_GREEN)
        except Exception as e: self.console.log(f"Error: {e}",C_RED)

    def _exec_action(self, action):
        """Apply one action directly."""
        if action == 'forward':
            ok = self.robot.move_forward()
            if ok:
                self.sim_robot_ms += RC.MS_PER_CELL
                self.console.log(f"  -> ({self.robot.col},{self.robot.row})", C_TEXT_M)
                if self.robot.is_at_goal(): self._on_goal()
        elif action in ('left', 'right', '180'):
            if action == 'left':   self.robot.turn_left()
            elif action == 'right': self.robot.turn_right()
            else:                   self.robot.turn_180()
            self.sim_robot_ms += RC.MS_PER_90 * (2 if action == '180' else 1)
            self.console.log(f"  {action} [{self.robot.heading}]", C_TEXT_L)
        elif action == 'done':
            self._on_done()

    def _exec(self):
        """Execute one logical action (used by _do_step)."""
        if self.algo_gen is None: return
        if self._peeked is not None:
            action = self._peeked; self._peeked = None
        else:
            try: action = next(self.algo_gen)
            except StopIteration: self._on_done(); return
        self._exec_action(action)

    def _on_goal(self):
        rms=self.sim_robot_ms; ws=int((time.time()-self.start_time)*1000) if self.start_time else 0
        self.sim_running=False
        self.console.log("",C_TEXT_M)
        self.console.log("+------------------------------------------+",C_GREEN)
        self.console.log("|        ** META ALCANZADA! **             |",C_GREEN)
        self.console.log(f"| Tiempo robot real: {rms//60000:02d}:{(rms%60000)//1000:02d}.{(rms%1000)//10:02d}           |",C_GREEN)
        self.console.log(f"| Tiempo sim ({self.sl_speed.value:6s}):  {ws//60000:02d}:{(ws%60000)//1000:02d}.{(ws%1000)//10:02d}           |",C_TEXT_M)
        self.console.log(f"| Pasos: {self.robot.steps:4d}   Giros: {self.robot.total_turns:3d}          |",C_GREEN)
        self.console.log(f"| Dist:  {self.robot.total_dist_mm/1000:.3f} m                       |",C_GREEN)
        self.console.log("+------------------------------------------+",C_GREEN)

    def _on_done(self):
        self.sim_running=False
        if not self.robot.is_at_goal():
            self.console.log("Algoritmo termino.",C_YELLOW)
        self.algo_gen=None

    # ── Update ────────────────────────────────────────────────
    def _update(self, dt):
        if not self.sim_paused:
            self.robot.update_physics(dt/1000., self.sl_speed.value)
        # RT flood fill: recompute every frame when visible
        if self.renderer.show_flood:
            self.maze.compute_flood()
        if self.start_time and self.sim_running:
            self.elapsed_ms=int((time.time()-self.start_time)*1000)

        # Real-time flood fill visualization: recompute distances each frame
        if self.renderer.show_flood and self.sim_running and not self.sim_paused:
            self.maze.compute_flood()

        if not self.sim_running or self.sim_paused or self.algo_gen is None:
            return

        # ── Logical timer + continuous straight movement ─────
        # Forwards chain at 30% progress = no pause between cells
        # Turns wait for full idle = no diagonal glitch
        interval = RC.STEP_MS.get(self.sl_speed.value, 1000)
        self._step_acc += dt

        if self._peeked is None:
            try: self._peeked = next(self.algo_gen)
            except StopIteration: self._on_done(); return

        action = self._peeked

        if action in ('left', 'right', '180'):
            # Turns always wait for full idle
            if not self.robot.is_busy():
                self._step_acc = 0.0
                self._peeked = None
                self._exec_action(action)

        elif action == 'forward':
            # Chain at 30% so straight runs are truly continuous
            can_fire = (not self.robot.is_busy() or
                        (self.robot.state == 'moving' and
                         self.robot.move_progress >= 0.30))
            if can_fire:
                self._step_acc = 0.0
                self._peeked = None
                self._exec_action('forward')

        elif action == 'done':
            self._peeked = None; self._on_done()

    # ── Draw ─────────────────────────────────────────────────
    def _draw(self):
        W,H=self.screen.get_size()
        self.screen.fill(C_BG)
        self._draw_header(W)
        self.renderer.draw(self.screen,self.maze,self.robot)
        if self.edit_mode:
            bh=24; by=self.renderer.maze_rect.bottom-bh
            bar=pygame.Rect(self.renderer.maze_rect.x,by,self.renderer.maze_rect.w,bh)
            pygame.draw.rect(self.screen,(45,38,0),bar)
            pygame.draw.line(self.screen,C_YELLOW,(bar.x,bar.y),(bar.right,bar.y),2)
            self.screen.blit(FONT_XS.render(
                "[ EDICION ]  Click-Izq=pared  Click-Der=inicio  Shift+Click-Der=meta  E=salir",
                True,C_YELLOW),(bar.x+8,bar.y+5))
        # Flood fill overlay when stopped
        if self.renderer.show_flood and not self.sim_running:
            self._draw_flood_overlay(W, H)
        self._draw_panel(W,H)
        self.console.draw(self.screen)
        self._rcfg.draw(self.screen)   # always on top
        pygame.display.flip()

    def _draw_header(self, W):
        pygame.draw.rect(self.screen,C_PANEL,(0,0,W,HEADER_H))
        pygame.draw.line(self.screen,C_BORDER,(0,HEADER_H-1),(W,HEADER_H-1),1)
        t1=FONT_TJ.render("TJ",True,C_RED); t2=FONT_TJ.render(" Simulator",True,C_TEXT_H)
        self.screen.blit(t1,(14,10)); self.screen.blit(t2,(14+t1.get_width(),10))

        if self.sim_running and not self.sim_paused:
            stxt,sc=f"[ {self.robot.state.upper():<8} ]",C_GREEN
        elif self.sim_paused: stxt,sc="[ PAUSED   ]",C_YELLOW
        elif self.robot.is_at_goal(): stxt,sc="[  GOAL!   ]",C_GREEN
        else: stxt,sc="[ STOPPED  ]",C_TEXT_L
        self.screen.blit(FONT_MD.render(stxt,True,sc),(215,13))

        # Robot real time
        rms=self.sim_robot_ms
        self.screen.blit(FONT_MD.render(
            f"{rms//60000:02d}:{(rms%60000)//1000:02d}.{(rms%1000)//10:02d}",
            True,C_TEXT_H),(370,13))

        # Sim wall-clock
        ms=self.elapsed_ms; cur=self.sl_speed.value
        scol=C_YELLOW if cur=='Turbo' else C_TEXT_L
        self.screen.blit(FONT_XS.render(
            f"sim {ms//60000:02d}:{(ms%60000)//1000:02d}.{(ms%1000)//10:02d} ({cur})",
            True,scol),(475,16))

        # Always sync algo_name from dropdown (defensive)
        self.algo_name = self.dd_algo.value
        info=f"{self.maze.cols}x{self.maze.rows}  |  {self.algo_name}"
        ti=FONT_XS.render(info,True,C_TEXT_L)
        self.screen.blit(ti,(W-ti.get_width()-14,15))

    def _draw_edit_modal(self, surf, W, H):
        """Inline modal with edit options: toggle walls, set spawn corner, set goal."""
        px=self._px; pw=self._pw; bw=(pw-4)//2
        # Position: right under btn_lab
        my = self.btn_lab.rect.bottom + 2 if hasattr(self,"btn_lab") else self.btn_gen.rect.bottom
        # Background
        mr = pygame.Rect(px-4, my, pw+8, 96)
        pygame.draw.rect(surf, (22,22,28), mr, border_radius=4)
        pygame.draw.rect(surf, C_RED_D if self.edit_mode else C_BORDER, mr, 1, border_radius=4)

        y = my + 6
        # Toggle wall edit
        ec = C_RED_D if self.edit_mode else C_CARD
        surf.blit(FONT_XS.render("Paredes:",True,C_TEXT_L),(px,y))
        tgl_r = pygame.Rect(px+56, y, pw-56, 18)
        pygame.draw.rect(surf, ec, tgl_r, border_radius=3)
        pygame.draw.rect(surf, C_BORDER, tgl_r, 1, border_radius=3)
        surf.blit(FONT_XS.render("ON  Click=toggle pared" if self.edit_mode else "OFF  Click para activar",
                                  True,C_TEXT_H), (tgl_r.x+4,tgl_r.y+2))
        if hasattr(self,'_tgl_rect'): pass
        self._tgl_rect = tgl_r

        y += 24
        # Spawn corner label + current value
        surf.blit(FONT_XS.render("Spawn:",True,C_TEXT_L),(px,y+2))

        y += 24
        # Hint
        surf.blit(FONT_XS.render(
            "Click-Der=inicio  Shift+Click-Der=meta",True,C_TEXT_L),(px,y))


    def _draw_flood_overlay(self, W, H):
        """Overlay flood fill info when simulation is stopped."""
        maze = self.maze
        robot = self.robot
        # Find min distance from start
        sc,sr = maze.start
        dist_from_start = maze.flood[sr][sc]
        # Find min dist (goal cells = 0)
        goal_cells = maze.goal_cells
        if dist_from_start >= 9999:
            info = "Sin solucion encontrada"
            col  = C_WALL_DANGER
        else:
            info = f"Camino optimo: {dist_from_start} pasos  |  ~{dist_from_start * RC.MS_PER_CELL // 1000}s real"
            col  = C_GREEN

        # Small bar at top of maze
        mr = self.renderer.maze_rect
        bar = pygame.Rect(mr.x, mr.y, mr.w, 22)
        pygame.draw.rect(self.screen, (20,20,28), bar)
        pygame.draw.line(self.screen, col, (bar.x, bar.bottom), (bar.right, bar.bottom), 1)
        self.screen.blit(FONT_XS.render(
            f"FLOOD FILL — {info}  |  Robot en ({robot.col},{robot.row})"
            f" distancia={maze.flood[robot.row][robot.col]}",
            True, col), (bar.x+8, bar.y+4))

    def _draw_panel(self, W, H):
        pygame.draw.rect(self.screen,C_PANEL,(W-PANEL_W,HEADER_H,PANEL_W,H-HEADER_H))
        pygame.draw.line(self.screen,C_BORDER,(W-PANEL_W,HEADER_H),(W-PANEL_W,H),1)
        px=self._px

        def sec(label,y):
            self.screen.blit(FONT_XS.render(label,True,C_TEXT_L),(px,y))
            pygame.draw.line(self.screen,C_DIVIDER,(px,y+14),(W-10,y+14),1)

        def lbl(text,x,y,col=None):
            self.screen.blit(FONT_XS.render(text,True,col or C_TEXT_M),(x,y))

        y_maze=self.btn_gen.rect.y-SH
        y_algo=self.dd_algo.rect.y-SH
        y_spd=self.sl_speed.rect.y-SH-1
        y_ctrl=self.btn_run.rect.y-SH
        y_vis=self.btn_flood.rect.y-SH
        y_robot=self._robot_y

        sec("  LABERINTO",y_maze)
        self.btn_gen.draw(self.screen)
        self.btn_load.draw(self.screen); self.btn_save.draw(self.screen)
        # Editar Laberinto: highlight when active
        self.btn_edit.color = C_RED_D if self.edit_mode else C_CARD
        self.btn_edit.draw(self.screen)
        self.btn_robot_cfg.draw(self.screen)

        sec("  ALGORITMO",y_algo)
        y=self._algo_desc_y
        for line in [l for l in ALGO_DESCRIPTIONS.get(self.algo_name,"").strip().split('\n') if l.strip()][:3]:
            lbl(line,px+2,y,C_TEXT_L); y+=13

        sec("  VELOCIDAD",y_spd)
        self.sl_speed.draw(self.screen)
        spd=RC.PHYSICS_SPEEDS[self.sl_speed.value]
        lbl(f"  {spd['move']:.2f} c/s  {spd['rot']:.0f} deg/s",
            px,self.sl_speed.rect.y+28,C_TEXT_L)

        sec("  CONTROL",y_ctrl)
        self.btn_run.draw(self.screen); self.btn_pause.draw(self.screen)
        self.btn_step.draw(self.screen); self.btn_reset.draw(self.screen)

        sec("  VISUALIZAR",y_vis)
        for btn,active in [(self.btn_flood,self.renderer.show_flood),
                           (self.btn_sol,  self.renderer.show_solution),
                           (self.btn_sensors,self.renderer.show_sensors),
                           (self.btn_visited,self.renderer.show_visited)]:
            btn.color=C_RED_D if active else C_CARD; btn.draw(self.screen)

        if y_robot+SH+10<self._robot_bot:
            sec("  ROBOT / SENSORES",y_robot)
            y=y_robot+SH+4
            for line in self.robot.status_lines():
                if y+13>self._robot_bot: break
                if '**' in line: c=C_GREEN
                elif 'TOF' in line: c=C_TEAL
                elif 'Enc' in line: c=C_TEAL
                elif 'IMU' in line or 'Ang' in line: c=C_YELLOW
                elif 'PID' in line: c=C_ORANGE
                else: c=C_TEXT_M
                lbl(line,px,y,c); y+=13

        self.btn_clear.rect.y=H-CONSOLE_H+4
        self.btn_clear.draw(self.screen)
        self.screen.blit(FONT_XS.render("Space:Run  R:Reset  E:Edit  S:Step",True,C_TEXT_L),(px,H-14))

        # Dropdowns on top
        self.dd_algo.draw(self.screen)


if __name__=='__main__':
    app=TJSimulator(); app.run()