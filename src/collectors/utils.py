import json
import subprocess
from pathlib import Path
import yaml

# Root path for finding config and fallback directories
ROOT_DIR = Path(__file__).parent.parent.parent
CONFIG_PATH = ROOT_DIR / "config.yaml"

# Load global config once
with open(CONFIG_PATH) as f:
    CONFIG = yaml.safe_load(f)

def get_config_value(client_cfg, collector_type, key, default=None):
    """Helper to get config value from client_cfg or global CONFIG.
    
    collector_type should be 'reddit' or 'discord'.
    """
    # Check client-specific section first (e.g., client_cfg['reddit']['skills_dir'])
    if client_cfg and collector_type in client_cfg:
        if key in client_cfg[collector_type]:
            return client_cfg[collector_type][key]
    
    # Check global collector_global section (e.g., CONFIG['reddit_global']['skills_dir'])
    global_section = f"{collector_type}_global"
    if global_section in CONFIG:
        if key in CONFIG[global_section]:
            return CONFIG[global_section][key]
            
    # Fallback to old global section (e.g., CONFIG['reddit']['skills_dir'])
    if collector_type in CONFIG:
        if key in CONFIG[collector_type]:
            return CONFIG[collector_type][key]
            
    return default

def run_cli(args, collector_type="reddit", timeout=60, client_cfg=None):
    """Run a collector CLI (like reddit-skills) and return parsed JSON output.
    
    Currently supports 'reddit' via the reddit-skills package.
    """
    skills_dir = get_config_value(client_cfg, collector_type, "skills_dir")
    if not skills_dir:
        # Consistency check: fallback to scripts if not configured
        skills_dir = ROOT_DIR / "scripts"
        
    backend = get_config_value(client_cfg, collector_type, "backend")
    proxy_secret_id = get_config_value(client_cfg, collector_type, "proxy_secret_id")
    headless = get_config_value(client_cfg, collector_type, "headless", True)

    full_args = [
        "uv", "run",
        "--directory", str(skills_dir),
        "python", "cli.py",
    ]
    
    if backend:
        full_args += ["--backend", backend]
    if proxy_secret_id:
        full_args += ["--proxy-secret-id", proxy_secret_id]
    if not headless:
        full_args += ["--headed"]
        
    full_args += args

    result = subprocess.run(full_args, capture_output=True, text=True, timeout=timeout)
    if result.returncode != 0:
        print(f"  ✗ {collector_type}-skills error: {result.stderr[:200]}")
        return None

    try:
        if result.stdout.strip():
            return json.loads(result.stdout)
        return None
    except json.JSONDecodeError:
        print(f"  ⚠ Could not parse output: {result.stdout[:200]}")
        return None
