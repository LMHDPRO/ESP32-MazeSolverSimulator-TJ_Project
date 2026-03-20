#!/usr/bin/env python3
"""
TJ Simulator v1.0 — Micromouse Competition Simulator
=====================================================
Run:  python main.py
Deps: pip install pygame numpy
"""
import sys
import os

# Ensure we can import from this directory
sys.path.insert(0, os.path.dirname(__file__))

try:
    import pygame
except ImportError:
    print("Error: pygame no instalado.")
    print("Instala con:  pip install pygame")
    sys.exit(1)

from simulator import TJSimulator

if __name__ == '__main__':
    app = TJSimulator()
    app.run()
