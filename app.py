import json
import io
from pathlib import Path

import pandas as pd
import streamlit as st

# ---------------------------------------------------------------------------
# PAGINA-INSTELLINGEN & STYLING
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="Forecast Vertaaltool",
    page_icon="📊",
    layout="centered",
)

CUSTOM_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

html, body, [class*="css"] {
    font-family: 'Inter', sans-serif;
}

.main .block-container {
    max-width: 780px;
    padding-top: 2.5rem;
}

/* Header */
.app-header {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    margin-bottom: 0.25rem;
}
.app-header .icon {
    font-size: 2.2rem;
}
.app-header h1 {
    font-size: 1.9rem;
    font-weight: 700;
    margin: 0;
    color: #1A2B4C;
}
.app-subtitle {
    color: #5B6B85;
    font-size: 1.02rem;
    margin-bottom: 2rem;
}

/* Kaarten */
.info-card {
    background: #F4F6FB;
    border: 1px solid #E3E8F2;
    border-radius: 10px;
    padding: 1rem 1.25rem;
    margin-bottom: 1.5rem;
    font-size: 0.92rem;
    color: #3B4664;
}

/* Retailer-badge */
.retailer-badge {
    display: inline-block;
    background: #EAF0FF;
    color: #2A4CB5;
    border-radius: 6px;
    padding: 0.15rem 0.6rem;
    font-size: 0.85rem;
    font-weight: 600;
    margin-left: 0.4rem;
}

/* Knoppen */
.stButton>button, .stDownloadButton>button {
    border-radius: 8px;
    font-weight: 600;
    border: none;
    background-color: #2A4CB5;
    color: white;
}
.stButton>button:hover, .stDownloadButton>button:hover {
    background-color: #1E3A8F;
    color: white;
}

/* Footer */
.app-footer {
    margin-top: 3rem;
    padding-top: 1rem;
    border-top: 1px solid #E3E8F2;
    color: #8B94A8;
    font-size: 0.82rem;
    text-align: center;
}
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

st.markdown(
    """
    <div class="app-header">
        <div class="icon">📊</div>
        <h1>Forecast Vertaaltool</h1>
    </div>
    <div class="app-subtitle">Upload een retailer-forecast en zet 'm om naar jouw eigen standaardformat — automatisch, in enkele seconden.</div>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# CONFIGURATIE INLADEN
# ---------------------------------------------------------------------------

CONFIG_PATH = Path(__file__).parent / "retailer_configs.json"


@st.cache_data
def laad_configuraties():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


try:
    RETAILER_CONFIGS = laad_configuraties()
except Exception as e:
    st.error(f"Kon retailer_configs.json niet laden: {e}")
    st.stop()

# ---------------------------------------------------------------------------
# TRANSFORMATIE-LOGICA
# ---------------------------------------------------------------------------

class VertaalFout(Exception):
    """Nette, aan de gebruiker te tonen foutmelding."""
    pass


def vertaal_naar_eigen_taal(df: pd.DataFrame, retailer: str) -> pd.DataFrame:
    config = RETAILER_CONFIGS[retailer]

    if config["format"] == "long":
        vereiste_kolommen = list(config["column_mapping"].keys())
        ontbrekend = [k for k in vereiste_kolommen if k not in df.columns]
        if ontbrekend:
            raise VertaalFout(
                f"Deze verwachte kolommen ontbreken voor {retailer}: {', '.join(ontbrekend)}. "
                f"Gevonden kolommen in je bestand: {', '.join(str(c) for c in df.columns)}. "
                f"Controleer of je de juiste retailer hebt gekozen."
            )
        df = df.rename(columns=config["column_mapping"])
        df = df[list(config["column_mapping"].values())]

    elif config["format"] == "wide":
        sku_col = config["sku_column"]
        if sku_col not in df.columns:
            raise VertaalFout(
                f"Kolom '{sku_col}' (het productnummer) niet gevonden voor {retailer}. "
                f"Gevonden kolommen: {', '.join(str(c) for c in df.columns)}. "
                f"Mogelijk moet je het aantal over te slaan rijen (skip_rows) aanpassen."
            )
        df = df.drop(columns=config.get("columns_to_drop", []), errors="ignore")
        periode_kolommen = [c for c in df.columns if c != sku_col]
        if not periode_kolommen:
            raise VertaalFout(f"Geen periode/weekkolommen gevonden voor {retailer}.")
        df = df.melt(
            id_vars=[sku_col],
            value_vars=periode_kolommen,
            var_name="Periode",
            value_name="Forecast",
        )
        df = df.rename(columns={sku_col: "SKU"})

    else:
        raise VertaalFout(f"Onbekend format '{config['format']}' voor {retailer}.")

    # Validatie: forecast-kolom moet numeriek zijn
    niet_numeriek = pd.to_numeric(df["Forecast"], errors="coerce").isna()
    aantal_overgeslagen = int(niet_numeriek.sum())
    if aantal_overgeslagen > 0:
        df = df[~niet_numeriek].copy()

    df["Forecast"] = pd.to_numeric(df["Forecast"], errors="coerce") * config["unit_conversion_factor"]
    df = df.dropna(subset=["Forecast"])

    return df, aantal_overgeslagen


def naar_excel_bytes(df: pd.DataFrame) -> bytes:
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Forecast")
    return buffer.getvalue()


# ---------------------------------------------------------------------------
# INTERFACE
# ---------------------------------------------------------------------------

with st.container():
    retailer = st.selectbox("Van welke retailer komt dit bestand?", list(RETAILER_CONFIGS.keys()))
    unit_label = RETAILER_CONFIGS[retailer].get("unit_label", "")
    st.markdown(
        f'<div class="info-card">Geselecteerd: <span class="retailer-badge">{retailer}</span>'
        f'&nbsp;&nbsp;·&nbsp;&nbsp;Eenheidconversie: <b>{unit_label}</b></div>',
        unsafe_allow_html=True,
    )

    bestand = st.file_uploader("Upload de forecast (Excel)", type=["xlsx", "xls"])

if bestand is not None:
    skip_rows = RETAILER_CONFIGS[retailer].get("skip_rows", 0)
    try:
        with st.spinner("Bestand wordt verwerkt..."):
            df_ruw = pd.read_excel(bestand, skiprows=skip_rows)

            if df_ruw.empty:
                raise VertaalFout("Dit bestand bevat geen data (het is leeg na het inlezen).")

            df_vertaald, aantal_overgeslagen = vertaal_naar_eigen_taal(df_ruw, retailer)

        if df_vertaald.empty:
            st.warning(
                "Er kwam geen bruikbare data uit dit bestand. Controleer of je de juiste "
                "retailer hebt geselecteerd en of het bestand data bevat."
            )
        else:
            st.success(f"Bestand succesvol vertaald naar het eigen format.")

            col1, col2, col3 = st.columns(3)
            col1.metric("Rijen verwerkt", len(df_vertaald))
            col2.metric("Unieke SKU's", df_vertaald["SKU"].nunique())
            col3.metric("Overgeslagen rijen", aantal_overgeslagen)

            if aantal_overgeslagen > 0:
                st.info(
                    f"{aantal_overgeslagen} rij(en) overgeslagen omdat de forecast-waarde "
                    f"niet numeriek was (bijv. lege cel of tekst)."
                )

            with st.expander("Bekijk de vertaalde data"):
                st.dataframe(df_vertaald, use_container_width=True)

            dl_col1, dl_col2 = st.columns(2)
            with dl_col1:
                st.download_button(
                    "⬇️ Download als Excel",
                    data=naar_excel_bytes(df_vertaald),
                    file_name=f"forecast_vertaald_{retailer.replace(' ', '_')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True,
                )
            with dl_col2:
                st.download_button(
                    "⬇️ Download als CSV",
                    data=df_vertaald.to_csv(index=False).encode("utf-8"),
                    file_name=f"forecast_vertaald_{retailer.replace(' ', '_')}.csv",
                    mime="text/csv",
                    use_container_width=True,
                )

    except VertaalFout as e:
        st.error(f"⚠️ {e}")
    except Exception as e:
        st.error(
            f"Er ging iets onverwachts mis bij het verwerken van dit bestand. "
            f"Technische details: {e}"
        )
else:
    st.markdown(
        '<div class="info-card">Wachten op een geüpload bestand — kies eerst de juiste retailer hierboven.</div>',
        unsafe_allow_html=True,
    )

st.markdown(
    '<div class="app-footer">Forecast Vertaaltool · interne testversie</div>',
    unsafe_allow_html=True,
)
