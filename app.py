import streamlit as st
import pandas as pd

st.set_page_config(page_title="Forecast Vertaaltool", layout="wide")
st.title("📊 Forecast Vertaaltool")
st.write("Upload een retailer-forecast en zet 'm om naar jouw eigen standaardformat.")

# ---------------------------------------------------------------------------
# 1. INSTELLINGEN PER RETAILER
# ---------------------------------------------------------------------------
# Dit is het hart van je product: per retailer leg je vast hoe hun kolommen,
# eenheden en tijdvakken zich verhouden tot jouw "eigen taal".
# Voeg hier simpelweg een nieuwe retailer toe zodra je die tegenkomt.

RETAILER_CONFIGS = {
    "Retailer A": {
        "format": "long",
        # Mapping: kolomnaam bij retailer -> kolomnaam in jouw standaardformat
        "column_mapping": {
            "Product Code": "SKU",
            "Week": "Periode",
            "Forecast (dozen)": "Forecast",
        },
        # Vermenigvuldigingsfactor om naar jouw standaardeenheid (bv. stuks) te gaan
        "unit_conversion_factor": 12,  # bv. 1 doos = 12 stuks
        "skip_rows": 0,
    },
    "Retailer B": {
        "format": "long",
        "column_mapping": {
            "ArtNr": "SKU",
            "Maand": "Periode",
            "Fcst_Units": "Forecast",
        },
        "unit_conversion_factor": 1,  # al in stuks
        "skip_rows": 0,
    },
    "Retailer C": {
        "format": "wide",  # weken als aparte kolommen naast elkaar
        "skip_rows": 1,  # eerste rij is een titel/rommelregel, niet de echte header
        "sku_column": "EAN",
        "columns_to_drop": ["Omschrijving"],
        "unit_conversion_factor": 6,  # dozen van 6 stuks
    },
}

# ---------------------------------------------------------------------------
# 2. TRANSFORMATIE-LOGICA
# ---------------------------------------------------------------------------

def vertaal_naar_eigen_taal(df: pd.DataFrame, retailer: str) -> pd.DataFrame:
    """Zet een ruwe retailer-forecast om naar het eigen standaardformat."""
    config = RETAILER_CONFIGS[retailer]

    if config["format"] == "long":
        # Eén rij per SKU per periode - simpel hernoemen en selecteren
        df = df.rename(columns=config["column_mapping"])
        kolommen = list(config["column_mapping"].values())
        df = df[kolommen]

    elif config["format"] == "wide":
        # Weken/periodes staan als losse kolommen naast elkaar (bv. WK27, WK28, ...)
        # Die "smelten" we naar het lange format: één rij per SKU per periode.
        df = df.drop(columns=config.get("columns_to_drop", []), errors="ignore")
        sku_col = config["sku_column"]
        periode_kolommen = [c for c in df.columns if c != sku_col]
        df = df.melt(
            id_vars=[sku_col],
            value_vars=periode_kolommen,
            var_name="Periode",
            value_name="Forecast",
        )
        df = df.rename(columns={sku_col: "SKU"})

    # Eenheden omrekenen naar jouw standaardeenheid
    if "Forecast" in df.columns:
        df["Forecast"] = df["Forecast"] * config["unit_conversion_factor"]

    return df


# ---------------------------------------------------------------------------
# 3. INTERFACE
# ---------------------------------------------------------------------------

retailer = st.selectbox("Van welke retailer komt dit bestand?", list(RETAILER_CONFIGS.keys()))
bestand = st.file_uploader("Upload de forecast (Excel)", type=["xlsx", "xls"])

if bestand is not None:
    try:
        skip_rows = RETAILER_CONFIGS[retailer].get("skip_rows", 0)
        df_ruw = pd.read_excel(bestand, skiprows=skip_rows)

        st.subheader("Ruwe data (zoals geüpload)")
        st.dataframe(df_ruw, use_container_width=True)

        df_vertaald = vertaal_naar_eigen_taal(df_ruw, retailer)

        st.subheader("Vertaald naar jouw eigen format")
        st.dataframe(df_vertaald, use_container_width=True)

        csv = df_vertaald.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="⬇️ Download vertaalde forecast",
            data=csv,
            file_name=f"forecast_vertaald_{retailer.replace(' ', '_')}.csv",
            mime="text/csv",
        )

    except KeyError as e:
        st.error(f"Kolom niet gevonden: {e}. Controleer of dit echt een {retailer}-bestand is, "
                  f"of pas de column_mapping in de code aan.")
    except Exception as e:
        st.error(f"Er ging iets mis: {e}")
else:
    st.info("Wachten op een geüpload bestand...")
