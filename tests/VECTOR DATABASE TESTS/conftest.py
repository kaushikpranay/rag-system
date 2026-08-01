import os
import sys
import socket
import pytest
import psycopg2
import numpy as np
from dotenv import load_dotenv

load_dotenv(override=True)

# Ensure current directory and project root are in sys.path
TEST_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(TEST_DIR, "..", ".."))
if TEST_DIR not in sys.path:
    sys.path.insert(0, TEST_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# Tunnel auto-detection for local dev
TUNNEL_LOCAL_PORT = int(os.getenv("TUNNEL_LOCAL_PORT", "15432"))

def _check_port(port: int, host: str = "127.0.0.1") -> bool:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(1)
            return s.connect_ex((host, port)) == 0
    except Exception:
        return False

env_host = os.getenv("RDS_HOST", "").strip()
env_port = int(os.getenv("RDS_PORT", "5432"))

if _check_port(TUNNEL_LOCAL_PORT):
    os.environ["RDS_HOST"] = "127.0.0.1"
    os.environ["RDS_PORT"] = str(TUNNEL_LOCAL_PORT)
elif env_host and env_host not in ("localhost", "127.0.0.1") and _check_port(env_port, env_host):
    os.environ["RDS_HOST"] = env_host
    os.environ["RDS_PORT"] = str(env_port)
elif _check_port(env_port, "127.0.0.1"):
    os.environ["RDS_HOST"] = "127.0.0.1"
    os.environ["RDS_PORT"] = str(env_port)

def _get_config_vars():
    try:
        from app.utils.config import RDS_HOST, RDS_PORT, RDS_DB, RDS_USER, RDS_PASSWORD
        return RDS_HOST, RDS_PORT, RDS_DB, RDS_USER, RDS_PASSWORD
    except Exception:
        return None, 5432, "ragdb", "ragadmin", ""


def is_db_available() -> bool:
    RDS_HOST_CFG, RDS_PORT_CFG, RDS_DB_CFG, RDS_USER_CFG, RDS_PASSWORD_CFG = _get_config_vars()
    host = os.getenv("RDS_HOST", RDS_HOST_CFG or "localhost")
    port = os.getenv("RDS_PORT", RDS_PORT_CFG or 5432)
    try:
        conn = psycopg2.connect(
            host=host,
            port=port,
            dbname=RDS_DB_CFG,
            user=RDS_USER_CFG,
            password=RDS_PASSWORD_CFG,
            connect_timeout=3
        )
        conn.close()
        return True
    except Exception:
        return False


def skip_if_no_db():
    if not is_db_available():
        pytest.skip(f"PostgreSQL/pgvector database at {os.getenv('RDS_HOST', 'localhost')} is unavailable.")


@pytest.fixture(scope="session")
def db_session_init():
    if not is_db_available():
        pytest.skip("PostgreSQL database unavailable for session initialization.")
    try:
        init_db()
    except Exception as e:
        pytest.skip(f"Failed to initialize database schema: {e}")


@pytest.fixture(scope="function")
def db_conn(db_session_init):
    skip_if_no_db()
    conn = get_connection()
    try:
        yield conn
    finally:
        conn.close()


@pytest.fixture(scope="function")
def raw_db_conn():
    skip_if_no_db()
    RDS_HOST_CFG, RDS_PORT_CFG, RDS_DB_CFG, RDS_USER_CFG, RDS_PASSWORD_CFG = _get_config_vars()
    host = os.getenv("RDS_HOST", RDS_HOST_CFG or "localhost")
    port = os.getenv("RDS_PORT", RDS_PORT_CFG or 5432)
    conn = psycopg2.connect(
        host=host,
        port=port,
        dbname=RDS_DB_CFG,
        user=RDS_USER_CFG,
        password=RDS_PASSWORD_CFG,
        connect_timeout=5
    )
    try:
        yield conn
    finally:
        conn.close()


def vec_to_array(vec) -> np.ndarray:
    """Convert string, list, or pgvector.Vector object to numpy float32 array."""
    if isinstance(vec, str):
        return np.fromstring(vec.strip("[]"), sep=",", dtype=np.float32)
    elif hasattr(vec, "to_numpy"):
        return vec.to_numpy().astype(np.float32)
    elif isinstance(vec, (list, tuple)):
        return np.array(vec, dtype=np.float32)
    else:
        # Fallback for iterable or custom object
        try:
            return np.array(list(vec), dtype=np.float32)
        except TypeError:
            return np.fromstring(str(vec).strip("[]"), sep=",", dtype=np.float32)


def vec_to_str(vec) -> str:
    """Convert string, list, numpy array, or pgvector.Vector object to pgvector string format '[v1,v2,...]'."""
    if isinstance(vec, str):
        return vec
    arr = vec_to_array(vec)
    return "[" + ",".join(map(str, arr)) + "]"


def generate_random_vector(dim: int = 1024) -> list:
    """Generate a unit-normalized random float vector of given dimension."""
    vec = np.random.randn(dim).astype(np.float32)
    norm = np.linalg.norm(vec)
    if norm > 0:
        vec = vec / norm
    return vec.tolist()
