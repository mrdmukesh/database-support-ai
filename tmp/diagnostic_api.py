import faulthandler
import sys
from pathlib import Path

import uvicorn


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
faulthandler.dump_traceback_later(60, repeat=True)
uvicorn.run("legacydb_copilot.main:app", host="127.0.0.1", port=8000)
