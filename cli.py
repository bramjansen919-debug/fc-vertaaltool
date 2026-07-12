"""
Forecast Vertaaltool - command-line versie
Gebruikt dezelfde retailer_configs.json als app.py, zodat beide versies
altijd gelijk lopen.

Gebruik: python3 cli.py <pad-naar-bestand.xlsx> "<retailernaam>"
Voorbeeld: python3 cli.py voorbeeld.xlsx "Retailer A"
"""

import json
import sys
from pathlib import Path

import pandas as pd

CONFIG_PATH = Path(__file__).parent / "retailer_configs.json"

with open(CONFIG_PATH, "r", encoding="utf-8") as f:
    RETAILER_CONFIGS = json.load(f)


class VertaalFout(Exception):
    pass


def vertaal_naar_eigen_taal(df: pd.DataFrame, retailer: str):
    config = RETAILER_CONFIGS[retailer]

    if config["format"] == "long":
        vereiste_kolommen = list(config["column_mapping"].keys())
        ontbrekend = [k for k in vereiste_kolommen if k not in df.columns]
        if ontbrekend:
            raise VertaalFout(
                f"Deze verwachte kolommen ontbreken voor {retailer}: {', '.join(ontbrekend)}. "
                f"Gevonden kolommen: {', '.join(str(c) for c in df.columns)}."
            )
        df = df.rename(columns=config["column_mapping"])
        df = df[list(config["column_mapping"].values())]

    elif config["format"] == "wide":
        sku_col = config["sku_column"]
        if sku_col not in df.columns:
            raise VertaalFout(f"Kolom '{sku_col}' niet gevonden. Gevonden: {', '.join(str(c) for c in df.columns)}.")
        df = df.drop(columns=config.get("columns_to_drop", []), errors="ignore")
        periode_kolommen = [c for c in df.columns if c != sku_col]
        df = df.melt(id_vars=[sku_col], value_vars=periode_kolommen, var_name="Periode", value_name="Forecast")
        df = df.rename(columns={sku_col: "SKU"})

    else:
        raise VertaalFout(f"Onbekend format '{config['format']}' voor {retailer}.")

    niet_numeriek = pd.to_numeric(df["Forecast"], errors="coerce").isna()
    aantal_overgeslagen = int(niet_numeriek.sum())
    if aantal_overgeslagen > 0:
        df = df[~niet_numeriek].copy()

    df["Forecast"] = pd.to_numeric(df["Forecast"], errors="coerce") * config["unit_conversion_factor"]
    df = df.dropna(subset=["Forecast"])

    return df, aantal_overgeslagen


def main():
    if len(sys.argv) != 3:
        print("Gebruik: python3 cli.py <pad-naar-bestand.xlsx> \"<retailernaam>\"")
        print(f"Beschikbare retailers: {', '.join(RETAILER_CONFIGS.keys())}")
        sys.exit(1)

    pad = sys.argv[1]
    retailer = sys.argv[2]

    if retailer not in RETAILER_CONFIGS:
        print(f"Onbekende retailer '{retailer}'. Beschikbaar: {', '.join(RETAILER_CONFIGS.keys())}")
        sys.exit(1)

    skip_rows = RETAILER_CONFIGS[retailer].get("skip_rows", 0)
    print(f"Bestand inlezen: {pad} (skip_rows={skip_rows})")

    try:
        df_ruw = pd.read_excel(pad, skiprows=skip_rows)
        print("Ruwe data:")
        print(df_ruw.head())

        print(f"\nVertalen naar eigen format ({retailer})...")
        df_vertaald, aantal_overgeslagen = vertaal_naar_eigen_taal(df_ruw, retailer)
        print("Resultaat:")
        print(df_vertaald.head())
        if aantal_overgeslagen > 0:
            print(f"\nLet op: {aantal_overgeslagen} rij(en) overgeslagen (niet-numerieke forecast-waarde).")

        output_pad = pad.rsplit(".", 1)[0] + "_vertaald.csv"
        df_vertaald.to_csv(output_pad, index=False)
        print(f"\nKlaar! Weggeschreven naar: {output_pad}")

    except VertaalFout as e:
        print(f"\nFout: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
