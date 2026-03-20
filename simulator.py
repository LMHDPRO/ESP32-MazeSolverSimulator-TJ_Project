# ============================================================
#  TJ Simulator v1.0 — Main Application
# ============================================================

import pygame
import pygame.gfxdraw
import sys, os, math, time
import tkinter as tk
from tkinter import filedialog, simpledialog, messagebox

from config import *
from config import START_POSITIONS
from maze import Maze
from maze_gen import generate, generate_open
from robot import Robot
from algorithms import (ALGORITHMS, ALGO_DESCRIPTIONS, get_algorithm)

pygame.init()
pygame.font.init()

# ── Fonts ────────────────────────────────────────────────────
def load_font(size, bold=False):
    for name in ('Consolas','Courier New','Lucida Console',
                 'DejaVu Sans Mono','monospace'):
        try:
            f = pygame.font.SysFont(name, size, bold=bold)
            if f: return f
        except Exception: pass
    return pygame.font.SysFont(None, size, bold=bold)

FONT_LG = load_font(17, bold=True)
FONT_MD = load_font(15)
FONT_SM = load_font(14)
FONT_XS = load_font(13)
FONT_TJ = load_font(24, bold=True)

_tk_root = tk.Tk()
_tk_root.withdraw()


# ═════════════════════════════════════════════════════════════
#  WIDGETS
# ═════════════════════════════════════════════════════════════
class Button:
    def __init__(self, rect, label, color=None, text_color=None, small=False):
        self.rect    = pygame.Rect(rect)
        self.label   = label
        self.color   = color or C_CARD
        self.hcolor  = tuple(min(255, v+28) for v in self.color)
        self.dcolor  = tuple(max(0,   v-30) for v in self.color)
        self.tcolor  = text_color or C_TEXT_H
        self.hovered = False
        self.pressed = False
        self.enabled = True
        self.font    = FONT_XS if small else FONT_XS

    def draw(self, surf):
        col = (self.dcolor if not self.enabled or self.pressed
               else self.hcolor if self.hovered else self.color)
        pygame.draw.rect(surf, col,      self.rect, border_radius=4)
        pygame.draw.rect(surf, C_BORDER, self.rect, 1, border_radius=4)
        tc = self.tcolor if self.enabled else C_TEXT_L
        s  = self.font.render(self.label, True, tc)
        surf.blit(s, s.get_rect(center=self.rect.center))

    def handle_event(self, event):
        if not self.enabled: return False
        if event.type == pygame.MOUSEMOTION:
            self.hovered = self.rect.collidepoint(event.pos)
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.rect.collidepoint(event.pos):
                self.pressed = True; return True
        if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            self.pressed = False
        return False


class Slider:
    def __init__(self, rect, label, options, current=1):
        self.rect     = pygame.Rect(rect)
        self.label    = label
        self.options  = options
        self.idx      = current
        self.dragging = False

    @property
    def value(self): return self.options[self.idx]

    def draw(self, surf):
        # Label inline, left of track
        lbl = FONT_XS.render(f"{self.label}:", True, C_TEXT_L)
        surf.blit(lbl, (self.rect.x, self.rect.y - 1))
        val_s = FONT_XS.render(self.value, True, C_TEXT_H)
        surf.blit(val_s, (self.rect.x + lbl.get_width() + 4, self.rect.y - 1))

        ty = self.rect.y + 16
        pygame.draw.rect(surf, C_CARD,   (self.rect.x, ty, self.rect.w, 10), border_radius=3)
        pygame.draw.rect(surf, C_BORDER, (self.rect.x, ty, self.rect.w, 10), 1, border_radius=3)
        n = len(self.options)
        fw = int(self.rect.w * (self.idx+1)/n)
        if fw > 0:
            pygame.draw.rect(surf, C_RED_D, (self.rect.x, ty, fw, 10), border_radius=3)
        tx = self.rect.x + fw - 6
        pygame.draw.circle(surf, C_RED,    (tx, ty+5), 7)
        pygame.draw.circle(surf, C_TEXT_H, (tx, ty+5), 2)

    def handle_event(self, event):
        ty = self.rect.y + 16
        track = pygame.Rect(self.rect.x, ty, self.rect.w, 10)
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if track.inflate(0, 10).collidepoint(event.pos):
                self.dragging = True; self._set(event.pos[0])
        if event.type == pygame.MOUSEBUTTONUP:   self.dragging = False
        if event.type == pygame.MOUSEMOTION and self.dragging: self._set(event.pos[0])

    def _set(self, x):
        n = len(self.options)
        t = (x - self.rect.x) / self.rect.w
        self.idx = max(0, min(n-1, int(t*n)))


class DropDown:
    def __init__(self, rect, options, current=0):
        self.rect    = pygame.Rect(rect)
        self.options = options
        self.idx     = current
        self.open    = False
        self.hovered_item = -1

    @property
    def value(self): return self.options[self.idx]

    def draw(self, surf):
        col = C_CARD if not self.open else C_BORDER
        pygame.draw.rect(surf, col,      self.rect, border_radius=4)
        pygame.draw.rect(surf, C_BORDER, self.rect, 1, border_radius=4)
        ax = self.rect.right - 14
        ay = self.rect.centery
        pygame.draw.polygon(surf, C_TEXT_M, [(ax-5,ay-3),(ax+5,ay-3),(ax,ay+4)])
        s = FONT_XS.render(self.options[self.idx], True, C_TEXT_H)
        surf.blit(s, (self.rect.x+7, self.rect.y+5))
        if self.open:
            ih = 22
            mr = pygame.Rect(self.rect.x, self.rect.bottom, self.rect.w, ih*len(self.options))
            shadow = pygame.Surface((mr.w+4, mr.h+4), pygame.SRCALPHA)
            shadow.fill((0,0,0,110))
            surf.blit(shadow, (mr.x-2, mr.y-2))
            pygame.draw.rect(surf, C_PANEL, mr, border_radius=4)
            pygame.draw.rect(surf, C_BORDER, mr, 1, border_radius=4)
            for i, opt in enumerate(self.options):
                ir = pygame.Rect(mr.x, mr.y+i*ih, mr.w, ih)
                if i == self.hovered_item:
                    pygame.draw.rect(surf, C_CARD, ir)
                if i == self.idx:
                    pygame.draw.rect(surf, C_RED_D, ir.inflate(-4,-2), border_radius=3)
                surf.blit(FONT_XS.render(opt, True, C_TEXT_H), (ir.x+7, ir.y+4))

    def handle_event(self, event):
        changed = False
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.rect.collidepoint(event.pos):
                self.open = not self.open
            elif self.open:
                ih = 22
                mr = pygame.Rect(self.rect.x, self.rect.bottom, self.rect.w, ih*len(self.options))
                if mr.collidepoint(event.pos):
                    idx = (event.pos[1]-mr.y)//ih
                    if 0 <= idx < len(self.options):
                        self.idx = idx; changed = True
                self.open = False
        if event.type == pygame.MOUSEMOTION and self.open:
            ih = 22
            mr = pygame.Rect(self.rect.x, self.rect.bottom, self.rect.w, ih*len(self.options))
            self.hovered_item = (event.pos[1]-mr.y)//ih if mr.collidepoint(event.pos) else -1
        return changed


# ═════════════════════════════════════════════════════════════
#  MAZE RENDERER
# ═════════════════════════════════════════════════════════════
class MazeRenderer:
    WALL_W = 3

    def __init__(self, maze_rect):
        self.maze_rect      = pygame.Rect(maze_rect)
        self.show_flood     = False
        self.show_solution  = False
        self.show_sensors   = True
        self.show_visited   = True
        self.solution_path  = None
        self.offset         = [0, 0]

    def cell_size(self, maze):
        cw = (self.maze_rect.w - 16) // maze.cols
        ch = (self.maze_rect.h - 16) // maze.rows
        return max(12, min(cw, ch))

    def origin(self, maze):
        cs = self.cell_size(maze)
        ox = self.maze_rect.x + (self.maze_rect.w - cs*maze.cols)//2
        oy = self.maze_rect.y + (self.maze_rect.h - cs*maze.rows)//2
        return ox, oy, cs

    def draw(self, surf, maze, robot):
        pygame.draw.rect(surf, C_MAZE_BG, self.maze_rect)
        x0, y0, cs = self.origin(maze)
        goal_set = set(maze.goal_cells)

        # Cell fills
        for r in range(maze.rows):
            for c in range(maze.cols):
                px, py = x0+c*cs, y0+r*cs
                if (c,r) in goal_set:             col = C_GOAL_CELL
                elif (c,r) == maze.start:          col = C_START_CELL
                elif self.show_flood and maze.flood[r][c] < 9999:
                    col = self._fc(maze.flood[r][c], maze)
                elif self.show_visited and (c,r) in robot.visited:
                    col = C_VISITED
                else:                              col = C_FLOOR
                pygame.draw.rect(surf, col, (px+1, py+1, cs-1, cs-1))

        # Goal label
        if cs >= 16:
            gc, gr = maze.goal
            lbl = FONT_XS.render("META", True, C_GREEN)
            surf.blit(lbl, lbl.get_rect(center=(x0+gc*cs+cs, y0+gr*cs+cs)))

        # Solution
        if self.show_solution and self.solution_path:
            pts = [(x0+sc*cs+cs//2, y0+sr*cs+cs//2) for sc,sr in self.solution_path]
            if len(pts) > 1:
                pygame.draw.lines(surf, C_GREEN, False, pts, 3)
            for pt in pts:
                pygame.draw.circle(surf, C_GREEN, pt, 3)

        # Walls
        for r in range(maze.rows):
            for c in range(maze.cols):
                px, py = x0+c*cs, y0+r*cs
                if maze.walls[r][c]['N']: pygame.draw.line(surf,C_WALL,(px,py),(px+cs,py),self.WALL_W)
                if maze.walls[r][c]['W']: pygame.draw.line(surf,C_WALL,(px,py),(px,py+cs),self.WALL_W)
                if r==maze.rows-1 and maze.walls[r][c]['S']:
                    pygame.draw.line(surf,C_WALL,(px,py+cs),(px+cs,py+cs),self.WALL_W)
                if c==maze.cols-1 and maze.walls[r][c]['E']:
                    pygame.draw.line(surf,C_WALL,(px+cs,py),(px+cs,py+cs),self.WALL_W)

        # Corner posts
        for r in range(maze.rows+1):
            for c in range(maze.cols+1):
                pygame.draw.rect(surf,(180,180,185),(x0+c*cs-2,y0+r*cs-2,4,4))

        # Start label
        if cs >= 18:
            sc2, sr2 = maze.start
            surf.blit(FONT_XS.render("S",True,C_BLUE),(x0+sc2*cs+2,y0+sr2*cs+2))

        # Sensors
        if self.show_sensors: self._draw_sensors(surf, maze, robot, x0, y0, cs)

        # Robot
        self._draw_robot(surf, maze, robot, x0, y0, cs)

        # Flood numbers
        if self.show_flood and cs >= 28:
            for r in range(maze.rows):
                for c in range(maze.cols):
                    v = maze.flood[r][c]
                    if v < 9999:
                        ts = FONT_XS.render(str(v),True,C_TEXT_L)
                        surf.blit(ts,(x0+c*cs+cs//2-ts.get_width()//2,
                                      y0+r*cs+cs//2-ts.get_height()//2))

    def _fc(self, val, maze):
        mx = maze.cols*maze.rows
        t  = min(1.0, val/max(1,mx))
        return tuple(int(C_FLOOD_LO[i]+t*(C_FLOOD_HI[i]-C_FLOOD_LO[i])) for i in range(3))

    def _draw_sensors(self, surf, maze, robot, x0, y0, cs):
        from robot import _rel_to_abs
        L, C, R = robot.read_sensors()
        dv = {'N':(0,-1),'S':(0,1),'E':(1,0),'W':(-1,0)}
        rx = x0+robot.col*cs+cs//2
        ry = y0+robot.row*cs+cs//2
        for rel, d in [('L',L),('F',C),('R',R)]:
            ad = _rel_to_abs(robot.heading, rel)
            dp = int(d/CELL_SIZE_MM*cs)
            ex, ey = rx+dv[ad][0]*dp, ry+dv[ad][1]*dp
            bm = pygame.Surface(surf.get_size(), pygame.SRCALPHA)
            pygame.draw.line(bm,(*C_SENSOR_BEAM,155),(rx,ry),(ex,ey),2)
            pygame.draw.circle(bm,(*C_SENSOR_BEAM,200),(ex,ey),4)
            surf.blit(bm,(0,0))

    def _draw_robot(self, surf, maze, robot, x0, y0, cs):
        t    = min(1.0, robot.anim_t)
        ease = t*t*(3-2*t)
        fc   = robot.anim_from_c+(robot.col-robot.anim_from_c)*ease
        fr   = robot.anim_from_r+(robot.row-robot.anim_from_r)*ease
        rx   = int(x0+fc*cs+cs/2)
        ry   = int(y0+fr*cs+cs/2)
        half = max(6, int(cs*0.45))//2
        ad   = {'N':270,'E':0,'S':90,'W':180}
        ang  = math.radians(ad[robot.heading])
        pts  = []
        for dx,dy in [(-half,-half),(half,-half),(half,half),(-half,half)]:
            pts.append((int(rx+dx*math.cos(ang)-dy*math.sin(ang)),
                        int(ry+dx*math.sin(ang)+dy*math.cos(ang))))
        pygame.draw.polygon(surf, C_ROBOT_BODY, pts)
        pygame.draw.polygon(surf, C_ROBOT_ACCENT, pts, 2)
        fx = int(rx+half*0.85*math.cos(ang))
        fy = int(ry+half*0.85*math.sin(ang))
        pygame.draw.line(surf, C_RED, (rx,ry),(fx,fy),3)
        pygame.draw.circle(surf, C_RED,(fx,fy),3)

    def px_to_cell(self, px, py, maze):
        x0,y0,cs = self.origin(maze)
        c=(px-x0)//cs; r=(py-y0)//cs
        return (int(c),int(r)) if 0<=c<maze.cols and 0<=r<maze.rows else None

    def nearest_wall(self, px, py, maze):
        x0,y0,cs = self.origin(maze)
        m = cs*0.28
        for r in range(maze.rows):
            for c in range(maze.cols):
                cx,cy=x0+c*cs,y0+r*cs
                if abs(py-cy)<m and cx<px<cx+cs:         return c,r,'N'
                if abs(py-(cy+cs))<m and cx<px<cx+cs:    return c,r,'S'
                if abs(px-cx)<m and cy<py<cy+cs:          return c,r,'W'
                if abs(px-(cx+cs))<m and cy<py<cy+cs:     return c,r,'E'
        return None


# ═════════════════════════════════════════════════════════════
#  CONSOLE
# ═════════════════════════════════════════════════════════════
class Console:
    MAX_LINES = 200
    def __init__(self, rect):
        self.rect   = pygame.Rect(rect)
        self.lines  = []
        self.scroll = 0

    def log(self, msg, color=None):
        for line in str(msg).split('\n'):
            self.lines.append((line, color or C_TEXT_M))
        if len(self.lines) > self.MAX_LINES:
            self.lines = self.lines[-self.MAX_LINES:]
        self.scroll = 0

    def clear(self): self.lines = []

    def draw(self, surf):
        pygame.draw.rect(surf, C_BG, self.rect)
        pygame.draw.line(surf, C_BORDER, (self.rect.x,self.rect.y),(self.rect.right,self.rect.y),1)
        lh = 14
        vis = (self.rect.h-6)//lh
        start = max(0, len(self.lines)-vis-self.scroll)
        for i,(line,col) in enumerate(self.lines[start:start+vis]):
            surf.blit(FONT_XS.render(line,True,col),(self.rect.x+8, self.rect.y+4+i*lh))

    def handle_event(self, event):
        if event.type == pygame.MOUSEWHEEL:
            if self.rect.collidepoint(pygame.mouse.get_pos()):
                self.scroll = max(0, min(len(self.lines), self.scroll-event.y*2))


# ═════════════════════════════════════════════════════════════
#  PANEL LAYOUT CONSTANTS
# ═════════════════════════════════════════════════════════════
# All sections and their heights (pixels)
BH = 26   # button height
BH2 = 24  # small button height
SH = 16   # section header height
GAP = 5   # gap between rows
SEP = 8   # gap between sections


# ═════════════════════════════════════════════════════════════
#  MAIN SIMULATOR
# ═════════════════════════════════════════════════════════════
class TJSimulator:
    def __init__(self):
        self.screen = pygame.display.set_mode((SCREEN_W, SCREEN_H), pygame.RESIZABLE)
        pygame.display.set_caption(TITLE)
        self.clock   = pygame.time.Clock()
        self.running = True

        self.maze  = generate(DEFAULT_COLS, DEFAULT_ROWS)
        self.robot = Robot(self.maze)

        self.sim_running = False
        self.sim_paused  = False
        self.algo_gen    = None
        self.algo_name   = ALGORITHMS[0]
        self.elapsed_ms  = 0
        self.start_time  = None
        self.edit_mode   = False
        self.step_timer  = 0

        self.solution_path = self.maze.solve()

        W, H = SCREEN_W, SCREEN_H
        self.renderer = MazeRenderer(
            pygame.Rect(0, HEADER_H, W-PANEL_W, H-HEADER_H-CONSOLE_H))
        self.renderer.solution_path = self.solution_path
        self.console = Console(pygame.Rect(0, H-CONSOLE_H, W-PANEL_W, CONSOLE_H))

        self._create_widgets()
        self._layout(W, H)

        self.console.log("TJ Simulator v1.0 -- Micromouse", C_RED)
        self.console.log(f"Laberinto {DEFAULT_COLS}x{DEFAULT_ROWS} generado. Meta: zona 2x2.", C_GREEN)
        self.console.log("Presiona [Space] para iniciar.", C_TEXT_L)

    def _create_widgets(self):
        # Maze
        self.btn_gen      = Button((0,0,1,1), "GENERAR")
        self.btn_load     = Button((0,0,1,1), "CARGAR")
        self.btn_save     = Button((0,0,1,1), "GUARDAR")
        self.btn_edit     = Button((0,0,1,1), "EDITAR")
        self.btn_set_goal = Button((0,0,1,1), "SET META")
        # Algorithm
        self.dd_algo  = DropDown((0,0,1,1), ALGORITHMS, 0)
        # Speed
        self.sl_speed = Slider((0,0,1,1), "Velocidad", list(SPEEDS.keys()), 1)
        # Control
        self.btn_run   = Button((0,0,1,1), ">> RUN",   C_RED, C_TEXT_H)
        self.btn_pause = Button((0,0,1,1), "|| PAUSE")
        self.btn_step  = Button((0,0,1,1), ">| STEP")
        self.btn_reset = Button((0,0,1,1), "<> RESET")
        # Visualize
        self.btn_flood   = Button((0,0,1,1), "Flood Fill", small=True)
        self.btn_sol     = Button((0,0,1,1), "Solucion",   small=True)
        self.btn_sensors = Button((0,0,1,1), "Sensores",   small=True)
        self.btn_visited = Button((0,0,1,1), "Visitadas",  small=True)
        # Start position
        self.dd_start = DropDown((0,0,1,1), list(START_POSITIONS.keys()), 0)
        # Console clear
        self.btn_clear = Button((0,0,1,1), "Limpiar consola", small=True)

    def _layout(self, W, H):
        """Compute all widget rects from scratch to fit in H."""
        px  = W - PANEL_W + 8
        pw  = PANEL_W - 16          # usable width
        bw  = (pw - 4) // 2         # half width

        panel_top    = HEADER_H + 6
        panel_bottom = H - CONSOLE_H - 4
        avail        = panel_bottom - panel_top

        # Fixed heights for each section:
        # LABERINTO: SH + BH + GAP + BH + GAP + BH + SEP
        # ALGORITMO: SH + BH + GAP + 3*13 + SEP   (algo desc 3 lines)
        # VELOCIDAD: SH + 30 + SEP
        # CONTROL:   SH + BH + GAP + BH + SEP
        # VISUALIZAR:SH + BH + GAP + BH + SEP
        # ROBOT:     SH + rest

        maze_h  = SH + BH + GAP + BH + GAP + BH + SEP
        algo_h  = SH + BH + GAP + 3*13 + GAP + SEP
        speed_h = SH + 30 + SEP
        ctrl_h  = SH + BH + GAP + BH + SEP
        vis_h   = SH + BH + GAP + BH + SEP
        fixed_h = maze_h + algo_h + speed_h + ctrl_h + vis_h
        robot_h = max(0, avail - fixed_h)

        y = panel_top

        # ── LABERINTO ────────────────────────────────────────
        y += SH
        self.btn_gen.rect      = pygame.Rect(px, y, pw, BH);          y += BH+GAP
        self.btn_load.rect     = pygame.Rect(px,    y, bw, BH)
        self.btn_save.rect     = pygame.Rect(px+bw+4, y, bw, BH);     y += BH+GAP
        self.btn_edit.rect     = pygame.Rect(px,    y, bw, BH)
        self.btn_set_goal.rect = pygame.Rect(px+bw+4, y, bw, BH);     y += BH+GAP
        self.dd_start.rect     = pygame.Rect(px, y, pw, BH);           y += BH+SEP

        # ── ALGORITMO ────────────────────────────────────────
        y += SH
        self.dd_algo.rect  = pygame.Rect(px, y, pw, BH);              y += BH+GAP
        self._algo_desc_y  = y
        y += 3*13 + GAP + SEP

        # ── VELOCIDAD ────────────────────────────────────────
        y += SH
        self.sl_speed.rect = pygame.Rect(px, y, pw, 1);               y += 30+SEP

        # ── CONTROL ──────────────────────────────────────────
        y += SH
        self.btn_run.rect   = pygame.Rect(px,     y, bw, BH)
        self.btn_pause.rect = pygame.Rect(px+bw+4, y, bw, BH);        y += BH+GAP
        self.btn_step.rect  = pygame.Rect(px,     y, bw, BH)
        self.btn_reset.rect = pygame.Rect(px+bw+4, y, bw, BH);        y += BH+SEP

        # ── VISUALIZAR ───────────────────────────────────────
        y += SH
        self.btn_flood.rect   = pygame.Rect(px,     y, bw, BH2)
        self.btn_sol.rect     = pygame.Rect(px+bw+4, y, bw, BH2);     y += BH2+GAP
        self.btn_sensors.rect = pygame.Rect(px,     y, bw, BH2)
        self.btn_visited.rect = pygame.Rect(px+bw+4, y, bw, BH2);     y += BH2+SEP

        # ── ROBOT / SENSORES (remaining space) ───────────────
        self._robot_y     = y
        self._robot_bot   = panel_bottom
        self._px          = px
        self._pw          = pw

        # Clear button at very bottom of panel
        self.btn_clear.rect = pygame.Rect(px, H-CONSOLE_H+4, pw, 22)

    # ── Main loop ─────────────────────────────────────────────
    def run(self):
        while self.running:
            dt = self.clock.tick(FPS)
            self._handle_events()
            self._update(dt)
            self._draw()
        pygame.quit()
        sys.exit()

    # ── Events ───────────────────────────────────────────────
    def _handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT: self.running = False
            if event.type == pygame.VIDEORESIZE:
                W, H = event.w, event.h
                self.renderer.maze_rect = pygame.Rect(0,HEADER_H,W-PANEL_W,H-HEADER_H-CONSOLE_H)
                self.console.rect       = pygame.Rect(0,H-CONSOLE_H,W-PANEL_W,CONSOLE_H)
                self._layout(W, H)
            if event.type == pygame.KEYDOWN: self._handle_key(event)
            self._handle_ui_event(event)
            if self.edit_mode: self._handle_editor(event)
            self.console.handle_event(event)

    def _handle_key(self, event):
        if event.key == pygame.K_SPACE: self._toggle_run()
        elif event.key == pygame.K_r:   self._do_reset()
        elif event.key == pygame.K_e:   self._toggle_edit()
        elif event.key == pygame.K_s and not (event.mod & pygame.KMOD_CTRL): self._do_step()
        elif event.key == pygame.K_s and (event.mod & pygame.KMOD_CTRL):     self._do_save()
        elif event.key == pygame.K_o and (event.mod & pygame.KMOD_CTRL):     self._do_load()

    def _handle_ui_event(self, event):
        if self.btn_run.handle_event(event):     self._toggle_run()
        if self.btn_pause.handle_event(event):   self._toggle_pause()
        if self.btn_step.handle_event(event):    self._do_step()
        if self.btn_reset.handle_event(event):   self._do_reset()
        if self.btn_gen.handle_event(event):     self._do_generate()
        if self.btn_load.handle_event(event):    self._do_load()
        if self.btn_save.handle_event(event):    self._do_save()
        if self.btn_clear.handle_event(event):   self.console.clear()
        if self.btn_edit.handle_event(event):    self._toggle_edit()
        if self.btn_set_goal.handle_event(event):
            self.console.log("Clic-Der: mover inicio | Shift+Clic-Der: mover meta", C_YELLOW)
            self.edit_mode = True
        if self.btn_flood.handle_event(event):   self.renderer.show_flood    = not self.renderer.show_flood
        if self.btn_sol.handle_event(event):     self.renderer.show_solution = not self.renderer.show_solution
        if self.btn_sensors.handle_event(event): self.renderer.show_sensors  = not self.renderer.show_sensors
        if self.btn_visited.handle_event(event): self.renderer.show_visited  = not self.renderer.show_visited
        if self.dd_start.handle_event(event):
            pass  # applied on next generate
        if self.dd_algo.handle_event(event):
            self.algo_name = self.dd_algo.value
            if self.sim_running: self._do_reset()
            self.console.log(f"Algoritmo: {self.algo_name}", C_YELLOW)
            W, H = self.screen.get_size()
            self._layout(W, H)
        self.sl_speed.handle_event(event)

    def _handle_editor(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.renderer.maze_rect.collidepoint(event.pos):
                res = self.renderer.nearest_wall(*event.pos, self.maze)
                if res:
                    c,r,d = res
                    self.maze.toggle_wall(c,r,d)
                    self.maze.compute_flood()
                    self.solution_path = self.maze.solve()
                    self.renderer.solution_path = self.solution_path
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 3:
            if self.renderer.maze_rect.collidepoint(event.pos):
                cell = self.renderer.px_to_cell(*event.pos, self.maze)
                if cell:
                    if pygame.key.get_mods() & pygame.KMOD_SHIFT:
                        gc, gr = cell
                        if gc+1 < self.maze.cols and gr+1 < self.maze.rows:
                            self.maze.goal = cell
                            self.console.log(f"Meta (2x2) -> {cell}", C_GREEN)
                        else:
                            self.console.log("Meta muy cerca del borde.", C_YELLOW)
                    else:
                        self.maze.start = cell
                        self.robot.col, self.robot.row = cell
                        self.console.log(f"Inicio -> {cell}", C_BLUE)
                    self.maze.compute_flood()
                    self.solution_path = self.maze.solve()
                    self.renderer.solution_path = self.solution_path

    def _toggle_edit(self):
        self.edit_mode = not self.edit_mode
        self.console.log(f"Modo edicion: {'ON' if self.edit_mode else 'OFF'}", C_YELLOW)

    # ── Simulation ────────────────────────────────────────────
    def _toggle_run(self):
        if not self.sim_running: self._start_sim()
        else: self.sim_running = False

    def _toggle_pause(self):
        self.sim_paused = not self.sim_paused
        self.console.log("Pausado" if self.sim_paused else "Reanudado", C_TEXT_M)

    def _start_sim(self):
        self.sim_running = True
        self.sim_paused  = False
        self.start_time  = time.time()
        self.algo_gen    = get_algorithm(self.algo_name, self.robot, self.maze)
        self.console.log(f">> {self.algo_name}", C_RED)

    def _do_step(self):
        if self.algo_gen is None:
            self.algo_gen = get_algorithm(self.algo_name, self.robot, self.maze)
        self._execute_one_step()

    def _do_reset(self):
        self.sim_running = False
        self.sim_paused  = False
        self.algo_gen    = None
        self.robot.reset()
        self.elapsed_ms  = 0
        self.start_time  = None
        self.console.log("Reset.", C_TEXT_L)

    def _do_generate(self):
        self._do_reset()
        try:
            ans = simpledialog.askstring("Generar laberinto",
                "Tamano (ColsxRows), ej: 10x10:",
                initialvalue=f"{self.maze.cols}x{self.maze.rows}", parent=_tk_root)
            if ans:
                parts = ans.lower().replace(',','x').split('x')
                cols = max(4, min(32, int(parts[0].strip())))
                rows = max(4, min(32, int(parts[-1].strip())))
            else: cols, rows = self.maze.cols, self.maze.rows
        except Exception: cols, rows = DEFAULT_COLS, DEFAULT_ROWS

        corner_key = self.dd_start.value
        corner = START_POSITIONS[corner_key]
        self.maze  = generate(cols, rows, start_corner=corner)
        self.robot = Robot(self.maze)
        self.solution_path = self.maze.solve()
        self.renderer.solution_path = self.solution_path
        W, H = self.screen.get_size()
        self._layout(W, H)
        self.console.log(f"Laberinto {cols}x{rows} generado.", C_GREEN)
        if self.solution_path:
            self.console.log(f"Solucion optima: {len(self.solution_path)-1} pasos.", C_TEXT_M)

    def _do_load(self):
        self._do_reset()
        path = filedialog.askopenfilename(title="Cargar laberinto",
            filetypes=[("Texto","*.txt"),("Todos","*.*")], parent=_tk_root)
        if not path: return
        try:
            with open(path,'r') as f: text = f.read()
            if '+' in text and '-' in text:
                self.maze = Maze.from_map_format(text); fmt = "Map"
            else:
                self.maze = Maze.from_num_format(text);  fmt = "Num"
            self.robot = Robot(self.maze)
            self.solution_path = self.maze.solve()
            self.renderer.solution_path = self.solution_path
            W, H = self.screen.get_size()
            self._layout(W, H)
            self.console.log(f"Cargado ({fmt}): {self.maze.cols}x{self.maze.rows}", C_GREEN)
        except Exception as e:
            self.console.log(f"Error: {e}", C_RED)

    def _do_save(self):
        path = filedialog.asksaveasfilename(title="Guardar laberinto",
            defaultextension=".txt", filetypes=[("Texto","*.txt")], parent=_tk_root)
        if not path: return
        fmt = simpledialog.askstring("Formato","'map' o 'num':", initialvalue="map", parent=_tk_root)
        try:
            text = self.maze.to_num_format() if (fmt and fmt.lower()=='num') else self.maze.to_map_format()
            with open(path,'w') as f: f.write(text)
            self.console.log(f"Guardado: {os.path.basename(path)}", C_GREEN)
        except Exception as e:
            self.console.log(f"Error: {e}", C_RED)

    def _execute_one_step(self):
        if self.algo_gen is None: return
        try:
            action = next(self.algo_gen)
            if   action == 'forward': self.robot.move_forward(); self.console.log(f"  -> ({self.robot.col},{self.robot.row})",C_TEXT_M); self.robot.is_at_goal() and self._on_goal()
            elif action == 'left':    self.robot.turn_left();  self.console.log(f"  << izq [{self.robot.heading}]",C_TEXT_L)
            elif action == 'right':   self.robot.turn_right(); self.console.log(f"  >> der [{self.robot.heading}]",C_TEXT_L)
            elif action == '180':     self.robot.turn_180();   self.console.log(f"  <> 180 [{self.robot.heading}]",C_TEXT_L)
            elif action == 'done':    self._on_done()
        except StopIteration: self._on_done()

    def _on_goal(self):
        el = time.time()-self.start_time if self.start_time else 0
        self.sim_running = False
        self.console.log("",C_TEXT_M)
        self.console.log("+---------------------------------+",C_GREEN)
        self.console.log("|   ** META ALCANZADA! **         |",C_GREEN)
        self.console.log(f"|  Tiempo:    {el:8.3f} s           |",C_GREEN)
        self.console.log(f"|  Pasos:     {self.robot.steps:5d}               |",C_GREEN)
        self.console.log(f"|  Giros:     {self.robot.total_turns:5d}               |",C_GREEN)
        self.console.log(f"|  Distancia: {self.robot.total_dist_mm/1000:.3f} m          |",C_GREEN)
        self.console.log("+---------------------------------+",C_GREEN)

    def _on_done(self):
        self.sim_running = False
        if not self.robot.is_at_goal():
            self.console.log("Algoritmo termino sin llegar a la meta.", C_YELLOW)
        self.algo_gen = None

    # ── Update ───────────────────────────────────────────────
    def _update(self, dt):
        if self.robot.anim_t < 1.0:
            self.robot.anim_t = min(1.0, self.robot.anim_t + dt/110.0)
        if self.sim_running and not self.sim_paused:
            self.step_timer += dt
            if self.step_timer >= SPEEDS[self.sl_speed.value]:
                self.step_timer = 0
                self._execute_one_step()
        if self.start_time and self.sim_running:
            self.elapsed_ms = int((time.time()-self.start_time)*1000)

    # ── Draw ─────────────────────────────────────────────────
    def _draw(self):
        W, H = self.screen.get_size()
        self.screen.fill(C_BG)
        self._draw_header(W)
        self.renderer.draw(self.screen, self.maze, self.robot)
        if self.edit_mode:
            bar_h = 24
            bar_y = self.renderer.maze_rect.bottom - bar_h
            bar_r = pygame.Rect(self.renderer.maze_rect.x, bar_y,
                                self.renderer.maze_rect.w, bar_h)
            pygame.draw.rect(self.screen, (45, 38, 0), bar_r)
            pygame.draw.line(self.screen, C_YELLOW,
                             (bar_r.x, bar_r.y), (bar_r.right, bar_r.y), 2)
            msg = ("[ MODO EDICION ]   Click-Izq = toggle pared   |   "
                   "Click-Der = mover inicio   |   "
                   "Shift+Click-Der = mover meta   |   E = salir")
            ts = FONT_XS.render(msg, True, C_YELLOW)
            self.screen.blit(ts, (bar_r.x + 10, bar_r.y + 5))
        self._draw_panel(W, H)
        self.console.draw(self.screen)
        pygame.display.flip()

    def _draw_header(self, W):
        pygame.draw.rect(self.screen, C_PANEL, (0,0,W,HEADER_H))
        pygame.draw.line(self.screen, C_BORDER, (0,HEADER_H-1),(W,HEADER_H-1),1)
        t1 = FONT_TJ.render("TJ", True, C_RED)
        t2 = FONT_TJ.render(" Simulator", True, C_TEXT_H)
        self.screen.blit(t1,(14,10)); self.screen.blit(t2,(14+t1.get_width(),10))
        if self.sim_running and not self.sim_paused: stxt,sc = "[ RUNNING ]",C_GREEN
        elif self.sim_paused:                        stxt,sc = "[ PAUSED  ]",C_YELLOW
        elif self.robot.is_at_goal():                stxt,sc = "[  GOAL!  ]",C_GREEN
        else:                                        stxt,sc = "[ STOPPED ]",C_TEXT_L
        self.screen.blit(FONT_MD.render(stxt,True,sc),(215,13))
        ms=self.elapsed_ms; mins=ms//60000; secs=(ms%60000)//1000; cent=(ms%1000)//10
        self.screen.blit(FONT_MD.render(f"{mins:02d}:{secs:02d}.{cent:02d}",True,C_TEXT_M),(370,13))
        info = f"{self.maze.cols}x{self.maze.rows}  |  {self.algo_name}"
        ti = FONT_XS.render(info,True,C_TEXT_L)
        self.screen.blit(ti,(W-ti.get_width()-14,15))

    def _draw_panel(self, W, H):
        pygame.draw.rect(self.screen, C_PANEL, (W-PANEL_W,HEADER_H,PANEL_W,H-HEADER_H))
        pygame.draw.line(self.screen, C_BORDER, (W-PANEL_W,HEADER_H),(W-PANEL_W,H),1)

        px = self._px

        def section(label, y):
            s = FONT_XS.render(label, True, C_TEXT_L)
            self.screen.blit(s,(px,y))
            pygame.draw.line(self.screen, C_DIVIDER, (px,y+14),(W-10,y+14),1)

        def lbl(text, x, y, col=None):
            self.screen.blit(FONT_XS.render(text,True,col or C_TEXT_M),(x,y))

        # Compute Y of each section from stored rects
        y_maze  = self.btn_gen.rect.y - SH
        y_algo  = self.dd_algo.rect.y - SH
        y_speed = self.sl_speed.rect.y - SH - 1
        y_ctrl  = self.btn_run.rect.y - SH
        y_vis   = self.btn_flood.rect.y - SH
        y_robot = self._robot_y

        section("  LABERINTO", y_maze)
        self.btn_gen.draw(self.screen)
        self.btn_load.draw(self.screen); self.btn_save.draw(self.screen)
        c_orig = self.btn_edit.color
        if self.edit_mode: self.btn_edit.color = C_RED_D
        self.btn_edit.draw(self.screen)
        self.btn_edit.color = c_orig
        self.btn_set_goal.draw(self.screen)
        self.dd_start.rect.y = self.btn_edit.rect.bottom + GAP
        # dd_start drawn last (on top)

        section("  ALGORITMO", y_algo)
        # dd drawn last (on top)
        y = self._algo_desc_y
        desc = ALGO_DESCRIPTIONS.get(self.algo_name,"")
        for line in [l for l in desc.strip().split('\n') if l.strip()][:3]:
            lbl(line, px+2, y, C_TEXT_L); y += 13

        section("  VELOCIDAD", y_speed)
        self.sl_speed.draw(self.screen)

        section("  CONTROL", y_ctrl)
        self.btn_run.draw(self.screen); self.btn_pause.draw(self.screen)
        self.btn_step.draw(self.screen); self.btn_reset.draw(self.screen)

        section("  VISUALIZAR", y_vis)
        for btn, active in [(self.btn_flood, self.renderer.show_flood),
                            (self.btn_sol,   self.renderer.show_solution),
                            (self.btn_sensors, self.renderer.show_sensors),
                            (self.btn_visited, self.renderer.show_visited)]:
            btn.color = C_RED_D if active else C_CARD
            btn.draw(self.screen)

        # Robot / Sensores — only text, no bars
        if y_robot + SH + 10 < self._robot_bot:
            section("  ROBOT / SENSORES", y_robot)
            y = y_robot + SH + 4
            L, C_mm, R = self.robot.read_sensors()
            color_val  = self.robot.read_color()
            hdg        = self.robot.imu_heading_deg
            dirs8      = ['N','NE','E','SE','S','SO','O','NO']
            dname      = dirs8[int((hdg+22.5)%360//45)]

            lines = [
                (f"TOF-IZQ  {L:4d} mm",   C_RED   if L<=120 else C_GREEN),
                (f"TOF-CEN  {C_mm:4d} mm",C_RED   if C_mm<=120 else C_GREEN),
                (f"TOF-DER  {R:4d} mm",   C_RED   if R<=120 else C_GREEN),
                ("",None),
                (f"ENC1  {self.robot.enc1:+9d} p",    C_TEAL),
                (f"ENC2  {self.robot.enc2:+9d} p",    C_TEAL),
                ("",None),
                (f"IMU   {hdg:6.1f} deg  ({dname})", C_YELLOW),
                ("",None),
                (f"COLOR {color_val:3d}  {'** META **' if color_val==255 else 'suelo negro'}",
                 C_GREEN if color_val==255 else C_TEXT_M),
                ("",None),
                (f"Pasos {self.robot.steps:4d}   Giros {self.robot.total_turns:3d}", C_TEXT_M),
                (f"Dist  {self.robot.total_dist_mm/1000:.3f} m", C_TEXT_M),
            ]
            for text, col in lines:
                if y+13 > self._robot_bot: break
                if text: lbl(text, px, y, col)
                y += 13

        # Clear + shortcuts
        self.btn_clear.draw(self.screen)
        ks = FONT_XS.render("Space:Run  R:Reset  E:Edit  S:Step", True, C_TEXT_L)
        self.screen.blit(ks,(px, H-14))

        # Dropdowns always on top
        self.dd_start.draw(self.screen)
        self.dd_algo.draw(self.screen)


# ═════════════════════════════════════════════════════════════
if __name__ == '__main__':
    app = TJSimulator()
    app.run()