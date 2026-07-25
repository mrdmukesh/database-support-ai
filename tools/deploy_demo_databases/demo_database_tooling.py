from pathlib import Path
import importlib.util

_path = Path(__file__).parents[1] / "deploy-demo-databases" / "demo_database_tooling.py"
_spec = importlib.util.spec_from_file_location("_demo_database_tooling", _path)
if _spec is None or _spec.loader is None:
    raise ImportError(f"Cannot load {_path}")
_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_module)

APPROVED_DATABASES = _module.APPROVED_DATABASES
INSTALL_ORDER = _module.INSTALL_ORDER
assert_approved_database = _module.assert_approved_database
redact = _module.redact
find_destructive_sql = _module.find_destructive_sql
validate_package = _module.validate_package
deployment_result = _module.deployment_result
