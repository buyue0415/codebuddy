import json
import os
import sqlite3
import subprocess
import sys
import time
import traceback
import threading
from datetime import datetime
from typing import Optional, Dict, Any, List

from fastapi import FastAPI, Request, Query, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse, Response, HTMLResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))
from env_paths import get_node, get_python, get_port
PORT = get_port(8766)
PYTHON = get_python()
NODE = get_node()

try:
    from fetchers.neodata import check_token as _check_neodata_token
    _NEODATA_AVAILABLE = _check_neodata_token()
except ImportError:
    _NEODATA_AVAILABLE = 'NOT_INSTALLED'

app = FastAPI(title="Stock Investment Manager API v2")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/v2/health")
def health():
    return {"status": "ok", "neodata": _NEODATA_AVAILABLE}


if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=PORT)
