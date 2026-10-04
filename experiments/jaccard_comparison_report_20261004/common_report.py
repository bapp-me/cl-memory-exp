"""Shared report paths; existing experiment evidence remains immutable."""
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
OPT = REPO / 'experiments/agentic_optimization_20261004'
sys.path.insert(0, str(OPT))
from common_opt import read, save, sha, digest, jsonl, visible, TAGS, METHODS, OBS, NATIVE, BASE

