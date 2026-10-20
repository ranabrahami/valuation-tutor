"""Freeze the SaaS engine's inputs into the tutor package, for deploying.

    python scripts/export_snapshot.py

Copies the engine's config.yaml and the processed tables the SaaS sector reads
into src/valuation_tutor/sectors/saas/snapshot/, with a manifest saying when
and from which engine commit. Run it after refreshing the engine's data, then
commit the snapshot. Only public data goes in: SEC filings and market prices.
"""

import json
import shutil
import subprocess
from datetime import datetime, timezone

import pandas as pd
from saas_valuation.config import CONFIG_PATH, PROJECT_ROOT, load_config, project_path

from valuation_tutor.sectors.saas.adapter import SNAPSHOT_DIR, TABLES


def main() -> None:
    cfg = load_config()
    processed = project_path(cfg["data"]["processed_dir"])
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copy(CONFIG_PATH, SNAPSHOT_DIR / "config.yaml")
    for table in TABLES:
        shutil.copy(processed / f"{table}.csv", SNAPSHOT_DIR / f"{table}.csv")
    commit = subprocess.run(["git", "-C", str(PROJECT_ROOT), "rev-parse", "--short", "HEAD"],
                            capture_output=True, text=True).stdout.strip()
    market = pd.read_csv(processed / "market_data.csv")
    manifest = {"exported_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "engine_commit": commit, "market_data_date": str(market["fetched_at"].max())[:10],
                "tables": list(TABLES)}
    (SNAPSHOT_DIR / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    size = sum(f.stat().st_size for f in SNAPSHOT_DIR.iterdir()) / 1024
    print(f"Snapshot written to {SNAPSHOT_DIR.relative_to(SNAPSHOT_DIR.parents[4])} ({size:.0f} KB): {manifest}")


if __name__ == "__main__":
    main()
