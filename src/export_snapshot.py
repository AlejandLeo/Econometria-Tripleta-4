from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import snowflake.connector
from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ENV_FILE = PROJECT_ROOT / ".env"
DEFAULT_QUERY = PROJECT_ROOT / "sql" / "econometria.sql"
DEFAULT_OUTPUT = PROJECT_ROOT / "data" / "econometria_snapshot.csv"
EXPECTED_ROWS = 390


def load_environment(env_file: Path) -> None:
    """Carga un archivo .env sin reemplazar variables ya definidas en PowerShell."""
    if env_file.exists():
        load_dotenv(dotenv_path=env_file, override=False)
        print(f"Configuración cargada desde: {env_file}")
    else:
        print(
            f"No se encontró {env_file}; se usarán únicamente las variables "
            "definidas en el proceso del sistema."
        )


def connection_parameters() -> dict[str, str]:
    required = ["SNOWFLAKE_ACCOUNT", "SNOWFLAKE_USER", "SNOWFLAKE_WAREHOUSE"]
    missing = [name for name in required if not os.getenv(name)]
    if missing:
        raise RuntimeError("Faltan variables de entorno: " + ", ".join(missing))

    parameters = {
        "account": os.environ["SNOWFLAKE_ACCOUNT"],
        "user": os.environ["SNOWFLAKE_USER"],
        "warehouse": os.environ["SNOWFLAKE_WAREHOUSE"],
        "database": os.getenv("SNOWFLAKE_DATABASE", "NYC_DOT_DW"),
        "schema": os.getenv("SNOWFLAKE_SCHEMA", "GOLD_MARTS"),
    }
    authenticator = os.getenv("SNOWFLAKE_AUTHENTICATOR", "").strip()
    password = os.getenv("SNOWFLAKE_PASSWORD", "").strip()
    optional = {
        "authenticator": authenticator,
        "role": os.getenv("SNOWFLAKE_ROLE"),
    }
    if password and authenticator.lower() != "externalbrowser":
        optional["password"] = password
    parameters.update({key: value for key, value in optional.items() if value})
    return parameters


def fetch_dataframe(query_path: Path) -> pd.DataFrame:
    query = query_path.read_text(encoding="utf-8")
    connection = snowflake.connector.connect(**connection_parameters())
    try:
        cursor = connection.cursor()
        try:
            cursor.execute(query)
            rows = cursor.fetchall()
            columns = [column[0] for column in cursor.description]
        finally:
            cursor.close()
    finally:
        connection.close()

    frame = pd.DataFrame(rows, columns=columns)
    frame.columns = frame.columns.str.upper()
    accidents_by_month = frame.groupby(["ANIO", "MES"])["TOTAL_ACCIDENTES"].transform("sum")
    district_weight = frame["TOTAL_ACCIDENTES"] / accidents_by_month
    frame["ATENCIONES_MEDICAS"] = (frame["TOTAL_ATENCIONES_CIUDAD"] * district_weight).round(0)
    return frame.drop(columns=["TOTAL_ATENCIONES_CIUDAD"])


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description="Exporta el snapshot agregado del modelo econométrico.")
    parser.add_argument(
        "--env-file",
        type=Path,
        default=DEFAULT_ENV_FILE,
        help="Archivo de variables de entorno (predeterminado: .env en la raíz del proyecto).",
    )
    parser.add_argument("--query", type=Path, default=DEFAULT_QUERY)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    load_environment(args.env_file.resolve())
    frame = fetch_dataframe(args.query.resolve())
    if len(frame) != EXPECTED_ROWS:
        raise RuntimeError(
            f"El query devolvió {len(frame)} filas; se esperaban {EXPECTED_ROWS} para reproducir el modelo congelado."
        )
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(output, index=False, encoding="utf-8")

    metadata = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "rows": int(len(frame)),
        "columns": frame.columns.tolist(),
        "sha256": sha256(output),
        "query": str(args.query.resolve()),
    }
    metadata_path = output.with_suffix(".metadata.json")
    metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Snapshot generado: {output}")
    print(f"Filas: {len(frame)} | SHA-256: {metadata['sha256']}")


if __name__ == "__main__":
    main()

