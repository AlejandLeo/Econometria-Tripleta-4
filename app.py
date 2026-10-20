from __future__ import annotations

import csv
import io
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

from src.model_io import file_sha256, load_json
from src.simulation import Intervention, calculate_all_scenarios


PROJECT_ROOT = Path(__file__).resolve().parent
MODEL_PATH = PROJECT_ROOT / "data" / "modelo_hc3.json"
DATA_PATH = PROJECT_ROOT / "data" / "econometria_snapshot.csv"


st.set_page_config(
    page_title="Simulador de beneficio social vial",
    page_icon="🚦",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    [data-testid="stAppViewContainer"] {
        background:
            radial-gradient(circle at 95% 5%, rgba(246,196,69,.20), transparent 28rem),
            #f4f2ec;
    }
    [data-testid="stSidebar"] { background: #17212b; }
    [data-testid="stSidebar"] * { color: #f8f6ef; }
    [data-testid="stSidebar"] input { color: #17212b !important; }
    .block-container { max-width: 1320px; padding-top: 2rem; padding-bottom: 4rem; }
    .hero {
        padding: 2.25rem 2.5rem;
        border-radius: 22px;
        color: #fff;
        background: linear-gradient(115deg, #17212b 0%, #243848 70%, #375466 100%);
        box-shadow: 0 18px 40px rgba(23,33,43,.18);
        margin-bottom: 1.25rem;
    }
    .eyebrow { color: #f6c445; font-size: .78rem; font-weight: 800; letter-spacing: .14em; }
    .hero h1 { color: #fff; font-size: clamp(2.1rem, 4vw, 4rem); line-height: 1.02; margin: .6rem 0 1rem; }
    .hero p { color: #dfe7eb; max-width: 760px; font-size: 1.08rem; margin: 0; }
    .method-note {
        border-left: 5px solid #f6c445;
        background: rgba(255,255,255,.72);
        padding: .9rem 1.1rem;
        border-radius: 8px 14px 14px 8px;
        margin: .7rem 0 1.2rem;
    }
    div[data-testid="stMetric"] {
        background: rgba(255,255,255,.75);
        border: 1px solid rgba(23,33,43,.08);
        padding: 1rem 1.1rem;
        border-radius: 16px;
        box-shadow: 0 8px 24px rgba(23,33,43,.06);
    }
    h2, h3 { color: #17212b; }
    .small-caps { text-transform: uppercase; letter-spacing: .08em; font-size: .72rem; font-weight: 800; color: #64727d; }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_data
def load_model() -> dict:
    return load_json(MODEL_PATH)


@st.cache_data
def load_source_data(path: str) -> pd.DataFrame:
    return pd.read_csv(path)


def usd(value: float) -> str:
    return f"USD {value:,.0f}".replace(",", ".")


def compact_usd(value: float) -> str:
    absolute = abs(value)
    if absolute >= 1_000_000_000:
        return f"USD {value / 1_000_000_000:.2f} mil M"
    if absolute >= 1_000_000:
        return f"USD {value / 1_000_000:.1f} M"
    if absolute >= 1_000:
        return f"USD {value / 1_000:.1f} mil"
    return f"USD {value:,.0f}"


def scenario_csv(results: dict, intervention: Intervention) -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["escenario", "beneficio_bruto_mensual_usd", "costo_mensual_usd", "beneficio_neto_mensual_usd", "beneficio_neto_horizonte_usd"])
    for result in results.values():
        writer.writerow([
            result.scenario,
            f"{result.monthly_gross_benefit:.2f}",
            f"{result.monthly_program_cost:.2f}",
            f"{result.monthly_net_benefit:.2f}",
            f"{result.horizon_net_benefit:.2f}",
        ])
    writer.writerow([])
    writer.writerow(["horizonte_meses", intervention.horizon_months])
    writer.writerow(["semaforos_reparados_por_mes", intervention.repaired_signals])
    writer.writerow(["luminarias_reparadas_por_mes", intervention.repaired_lights])
    return buffer.getvalue().encode("utf-8-sig")


model = load_model()
source_data = load_source_data(str(DATA_PATH)) if DATA_PATH.exists() else None

st.markdown(
    """
    <section class="hero">
      <div class="eyebrow">NYC · DECISIONES DE MANTENIMIENTO VIAL</div>
      <h1>¿Cuánto beneficio social podría generar reparar hoy?</h1>
      <p>Simula un ritmo mensual de intervención y observa al instante el beneficio potencial asociado, el costo del programa y su balance neto.</p>
    </section>
    """,
    unsafe_allow_html=True,
)

with st.sidebar:
    st.markdown("## Configurar escenario")
    st.caption("Las cantidades representan un ritmo operativo que se repite cada mes.")
    repaired_signals = st.slider("Semáforos reparados por mes", 0, 500, 50, 5)
    repaired_lights = st.slider("Luminarias reparadas por mes", 0, 1000, 100, 10)
    horizon = st.select_slider("Horizonte", options=[1, 3, 6, 12], value=12, format_func=lambda value: f"{value} meses")

    st.markdown("### Conversión a quejas evitadas")
    st.caption("Supuesto explícito y editable; el notebook no estima esta conversión.")
    signal_factor = st.number_input("Por semáforo reparado", min_value=0.0, max_value=10.0, value=1.0, step=0.1)
    light_factor = st.number_input("Por luminaria reparada", min_value=0.0, max_value=10.0, value=1.0, step=0.1)

    with st.expander("Costos del programa", expanded=True):
        fixed_cost = st.number_input(
            "Costo operativo referencial editable (USD/mes)",
            min_value=0.0,
            value=1_850_000.0,
            step=50_000.0,
        )
        signal_unit_cost = st.number_input("Costo por semáforo (USD)", min_value=0.0, value=0.0, step=100.0)
        light_unit_cost = st.number_input("Costo por luminaria (USD)", min_value=0.0, value=0.0, step=100.0)

intervention = Intervention(
    repaired_signals=repaired_signals,
    repaired_lights=repaired_lights,
    complaints_per_signal=signal_factor,
    complaints_per_light=light_factor,
    fixed_monthly_cost=fixed_cost,
    signal_unit_cost=signal_unit_cost,
    light_unit_cost=light_unit_cost,
    horizon_months=horizon,
)
results = calculate_all_scenarios(intervention, model)
central = results["Central"]

st.markdown(
    """
    <div class="method-note"><strong>Lectura responsable:</strong> el resultado es un beneficio social potencial asociado con menos quejas equivalentes. No constituye ahorro fiscal garantizado ni demuestra causalidad.</div>
    """,
    unsafe_allow_html=True,
)

st.markdown('<div class="small-caps">Escenario central · resultado mensual</div>', unsafe_allow_html=True)
metric_columns = st.columns(4)
metric_columns[0].metric("Beneficio social bruto", usd(central.monthly_gross_benefit))
metric_columns[1].metric("Costo del programa", usd(central.monthly_program_cost))
metric_columns[2].metric("Beneficio social neto", usd(central.monthly_net_benefit))
metric_columns[3].metric(
    "Relación beneficio/costo",
    f"{central.benefit_cost_ratio:.2f}×" if central.benefit_cost_ratio is not None else "Sin costo",
)

if central.benefit_cost_ratio is not None:
    decision_sentence = (
        f"Por cada USD 1 de costo operativo, el escenario central asocia "
        f"USD {central.benefit_cost_ratio:.2f} de beneficio social bruto."
    )
else:
    decision_sentence = "No se ingresaron costos; la relación beneficio/costo no puede calcularse."

baseline_monthly = None
if source_data is not None:
    baseline_monthly = float(
        source_data.groupby(["ANIO", "MES"])["COSTO_SOCIAL_MENSUAL"].sum().mean()
    )
    reduction_share = central.monthly_gross_benefit / baseline_monthly if baseline_monthly else 0.0
    baseline_sentence = (
        f" Esto equivale al {reduction_share:.2%} del costo social mensual histórico promedio "
        f"de NYC ({compact_usd(baseline_monthly)})."
    )
else:
    baseline_sentence = ""

st.markdown(
    f"""
    <div style="background:#17212b;color:#fff;padding:1.15rem 1.35rem;border-radius:16px;margin:1rem 0 1.5rem;">
      <span style="color:#f6c445;font-weight:800;letter-spacing:.06em;">LECTURA EJECUTIVA</span><br>
      <span style="font-size:1.16rem;line-height:1.55;">{decision_sentence}{baseline_sentence}</span>
    </div>
    """,
    unsafe_allow_html=True,
)

st.markdown("## Rango de resultados")
scenario_rows = []
for name, result in results.items():
    scenario_rows.extend(
        [
            {"Escenario": name, "Concepto": "Beneficio bruto", "Monto": result.monthly_gross_benefit},
            {"Escenario": name, "Concepto": "Costo del programa", "Monto": -result.monthly_program_cost},
            {"Escenario": name, "Concepto": "Beneficio neto", "Monto": result.monthly_net_benefit},
        ]
    )
scenario_frame = pd.DataFrame(scenario_rows)
scenario_label_offset = max(scenario_frame["Monto"].abs().max() * 0.045, 1.0)
scenario_frame["Etiqueta"] = scenario_frame["Monto"].map(compact_usd)
scenario_frame["EtiquetaY"] = scenario_frame["Monto"].apply(
    lambda value: value + scenario_label_offset if value >= 0 else value - scenario_label_offset
)
scenario_bars = (
    alt.Chart(scenario_frame)
    .mark_bar(cornerRadiusTopLeft=4, cornerRadiusTopRight=4)
    .encode(
        x=alt.X("Escenario:N", title=None, sort=["Conservador", "Central", "Favorable"]),
        y=alt.Y("Monto:Q", title="USD por mes", axis=alt.Axis(format="~s")),
        xOffset="Concepto:N",
        color=alt.Color(
            "Concepto:N",
            scale=alt.Scale(
                domain=["Beneficio bruto", "Costo del programa", "Beneficio neto"],
                range=["#2B7A5B", "#C85C45", "#315E7D"],
            ),
            legend=alt.Legend(orient="bottom", title=None),
        ),
        tooltip=["Escenario", "Concepto", alt.Tooltip("Monto:Q", format="$,.0f")],
    )
)
scenario_labels = (
    alt.Chart(scenario_frame)
    .mark_text(fontSize=11, fontWeight="bold")
    .encode(
        x=alt.X("Escenario:N", sort=["Conservador", "Central", "Favorable"]),
        xOffset="Concepto:N",
        y=alt.Y("EtiquetaY:Q"),
        text="Etiqueta:N",
        color=alt.value("#17212B"),
    )
)
scenario_chart = (scenario_bars + scenario_labels).properties(height=360)
st.altair_chart(scenario_chart, width="stretch")
st.caption("Conservador y favorable usan los límites del intervalo robusto HC3 al 95 %. El costo se representa debajo de cero.")

bridge_col, contribution_col = st.columns(2, gap="large")
with bridge_col:
    st.markdown("### Balance mensual desde cero")
    bridge = pd.DataFrame(
        [
            {
                "Paso": "1. Beneficio bruto",
                "Inicio": 0.0,
                "Fin": central.monthly_gross_benefit,
                "Monto": central.monthly_gross_benefit,
                "Tipo": "Beneficio",
            },
            {
                "Paso": "2. Costo operativo",
                "Inicio": 0.0,
                "Fin": -central.monthly_program_cost,
                "Monto": -central.monthly_program_cost,
                "Tipo": "Costo",
            },
            {
                "Paso": "3. Beneficio neto",
                "Inicio": 0.0,
                "Fin": central.monthly_net_benefit,
                "Monto": central.monthly_net_benefit,
                "Tipo": "Neto",
            },
        ]
    )
    bridge_label_offset = max(bridge[["Inicio", "Fin"]].abs().to_numpy().max() * 0.06, 1.0)
    bridge["Etiqueta"] = bridge["Monto"].map(compact_usd)
    bridge["EtiquetaY"] = bridge["Fin"].apply(
        lambda value: value + bridge_label_offset if value >= 0 else value - bridge_label_offset
    )
    bridge_bars = (
        alt.Chart(bridge)
        .mark_bar(cornerRadius=5, size=58)
        .encode(
            x=alt.X("Paso:N", title=None, sort=list(bridge["Paso"]), axis=alt.Axis(labelAngle=0)),
            y=alt.Y("Inicio:Q", title="USD por mes", axis=alt.Axis(format="~s")),
            y2="Fin:Q",
            color=alt.Color(
                "Tipo:N",
                scale=alt.Scale(domain=["Beneficio", "Costo", "Neto"], range=["#2B7A5B", "#C85C45", "#315E7D"]),
                legend=None,
            ),
            tooltip=["Paso", alt.Tooltip("Monto:Q", format="$,.0f")],
        )
    )
    bridge_labels = (
        alt.Chart(bridge)
        .mark_text(fontSize=11, fontWeight="bold")
        .encode(
            x=alt.X("Paso:N", sort=list(bridge["Paso"])),
            y="EtiquetaY:Q",
            text="Etiqueta:N",
            color=alt.value("#17212B"),
        )
    )
    zero_line = alt.Chart(pd.DataFrame({"Cero": [0]})).mark_rule(color="#64727D", strokeWidth=1).encode(y="Cero:Q")
    bridge_chart = (bridge_bars + bridge_labels + zero_line).properties(height=320)
    st.altair_chart(bridge_chart, width="stretch")

with contribution_col:
    st.markdown("### ¿De dónde surge el beneficio?")
    signal_value = repaired_signals * signal_factor * model["variables"]["traffic_signal_complaints"]["coefficient"]
    light_value = repaired_lights * light_factor * model["variables"]["street_light_complaints"]["coefficient"]
    contribution = pd.DataFrame(
        {
            "Infraestructura": ["Semáforos", "Luminarias"],
            "Beneficio": [signal_value, light_value],
        }
    )
    contribution["Etiqueta"] = contribution["Beneficio"].map(compact_usd)
    contribution_arcs = (
        alt.Chart(contribution)
        .mark_arc(innerRadius=70, outerRadius=125)
        .encode(
            theta=alt.Theta("Beneficio:Q"),
            color=alt.Color(
                "Infraestructura:N",
                scale=alt.Scale(domain=["Semáforos", "Luminarias"], range=["#F6C445", "#315E7D"]),
                legend=alt.Legend(orient="bottom", title=None),
            ),
            tooltip=["Infraestructura", alt.Tooltip("Beneficio:Q", format="$,.0f")],
        )
    )
    contribution_labels = (
        alt.Chart(contribution)
        .mark_text(radius=99, fontSize=11, fontWeight="bold", color="white")
        .encode(theta=alt.Theta("Beneficio:Q", stack=True), text="Etiqueta:N")
    )
    contribution_chart = (contribution_arcs + contribution_labels).properties(height=320)
    st.altair_chart(contribution_chart, width="stretch")

st.markdown(f"## Proyección a {horizon} meses")
projection_columns = st.columns(3)
projection_columns[0].metric("Beneficio bruto acumulado", usd(central.horizon_gross_benefit))
projection_columns[1].metric("Costo acumulado", usd(central.horizon_program_cost))
projection_columns[2].metric("Beneficio neto acumulado", usd(central.horizon_net_benefit))
st.caption(f"Supone el mismo ritmo de {repaired_signals} semáforos y {repaired_lights} luminarias en cada uno de los {horizon} meses; no capitaliza beneficios ni aplica inflación.")

trajectory_rows = []
for month in range(1, horizon + 1):
    for name, result in results.items():
        trajectory_rows.append(
            {
                "Mes": month,
                "Escenario": name,
                "Beneficio neto acumulado": result.monthly_net_benefit * month,
            }
        )
trajectory = pd.DataFrame(trajectory_rows)
trajectory["Etiqueta"] = trajectory["Beneficio neto acumulado"].map(compact_usd)
trajectory_lines = (
    alt.Chart(trajectory)
    .mark_line(point=True, strokeWidth=3)
    .encode(
        x=alt.X("Mes:O", title="Mes de ejecución"),
        y=alt.Y("Beneficio neto acumulado:Q", title="Beneficio neto acumulado (USD)", axis=alt.Axis(format="~s")),
        color=alt.Color(
            "Escenario:N",
            scale=alt.Scale(domain=["Conservador", "Central", "Favorable"], range=["#7D8A91", "#315E7D", "#2B7A5B"]),
            legend=alt.Legend(orient="bottom", title=None),
        ),
        tooltip=["Mes", "Escenario", alt.Tooltip("Beneficio neto acumulado:Q", format="$,.0f")],
    )
    .interactive(bind_y=False)
)
trajectory_end = trajectory[trajectory["Mes"].eq(horizon)]
trajectory_labels = (
    alt.Chart(trajectory_end)
    .mark_text(align="right", dx=-8, dy=-10, fontWeight="bold")
    .encode(
        x=alt.X("Mes:O"),
        y=alt.Y("Beneficio neto acumulado:Q"),
        text="Etiqueta:N",
        color=alt.Color(
            "Escenario:N",
            scale=alt.Scale(domain=["Conservador", "Central", "Favorable"], range=["#7D8A91", "#315E7D", "#2B7A5B"]),
            legend=None,
        ),
    )
)
trajectory_chart = (trajectory_lines + trajectory_labels).properties(
    height=350, title="Cómo se acumula el beneficio potencial"
)
st.altair_chart(trajectory_chart, width="stretch")

left, right = st.columns([1.05, 0.95], gap="large")
with left:
    st.markdown("## Cómo se obtiene")
    breakdown = pd.DataFrame(
        {
            "Componente": ["Semáforos", "Luminarias"],
            "Activos reparados/mes": [repaired_signals, repaired_lights],
            "Quejas evitadas equivalentes": [repaired_signals * signal_factor, repaired_lights * light_factor],
            "Beneficio central USD/mes": [signal_value, light_value],
        }
    )
    st.dataframe(
        breakdown,
        hide_index=True,
        width="stretch",
        column_config={"Beneficio central USD/mes": st.column_config.NumberColumn(format="$ %.0f")},
    )

with right:
    st.markdown("## Exportar escenario")
    st.write("Descarga las tres estimaciones y los parámetros usados para documentar la decisión.")
    st.download_button(
        "Descargar escenario CSV",
        data=scenario_csv(results, intervention),
        file_name="escenario_mantenimiento_vial.csv",
        mime="text/csv",
        width="stretch",
    )

with st.expander("Evidencia, datos y limitaciones", expanded=False):
    evidence_columns = st.columns(4)
    evidence_columns[0].metric("Observaciones", f"{model['observations']}")
    evidence_columns[1].metric("R²", f"{model['metrics']['r_squared']:.3f}")
    evidence_columns[2].metric("RMSE de prueba", "51 % de la media")
    evidence_columns[3].metric("Periodo", f"{model['observation_period']['start']} — {model['observation_period']['end']}")
    st.write(
        "El modelo controla lluvia y nieve, presenta heterocedasticidad y utiliza inferencia robusta HC3. "
        "No incorpora una identificación causal ni coeficientes específicos por distrito."
    )

    if source_data is not None:
        st.success(f"Snapshot disponible: {len(source_data):,} filas · SHA-256 {file_sha256(DATA_PATH)[:12]}…")
        monthly_history = (
            source_data.groupby(["ANIO", "MES"], as_index=False)["COSTO_SOCIAL_MENSUAL"].sum()
        )
        monthly_history["Fecha"] = pd.to_datetime(
            monthly_history["ANIO"].astype(str) + "-" + monthly_history["MES"].astype(str) + "-01"
        )
        monthly_history["Etiqueta"] = monthly_history["COSTO_SOCIAL_MENSUAL"].map(compact_usd)
        history_area = (
            alt.Chart(monthly_history)
            .mark_area(line={"color": "#315E7D"}, color=alt.Gradient(
                gradient="linear",
                stops=[alt.GradientStop(color="#315E7D", offset=0), alt.GradientStop(color="#DCE6EC", offset=1)],
                x1=1,
                x2=1,
                y1=1,
                y2=0,
            ))
            .encode(
                x=alt.X("Fecha:T", title="Mes"),
                y=alt.Y("COSTO_SOCIAL_MENSUAL:Q", title="Costo social total NYC", axis=alt.Axis(format="~s")),
                tooltip=[alt.Tooltip("Fecha:T", title="Mes", format="%Y-%m"), alt.Tooltip("COSTO_SOCIAL_MENSUAL:Q", title="Costo", format="$,.0f")],
            )
            .interactive(bind_y=False)
        )
        latest_history = monthly_history.sort_values("Fecha").tail(1)
        history_label = (
            alt.Chart(latest_history)
            .mark_text(align="right", dx=-8, dy=-12, fontWeight="bold", color="#17212B")
            .encode(x="Fecha:T", y="COSTO_SOCIAL_MENSUAL:Q", text="Etiqueta:N")
        )
        history_point = (
            alt.Chart(latest_history)
            .mark_point(size=85, filled=True, color="#F6C445", stroke="#17212B")
            .encode(x="Fecha:T", y="COSTO_SOCIAL_MENSUAL:Q")
        )
        history_chart = (history_area + history_point + history_label).properties(
            height=300, title="Contexto histórico del costo social mensual en NYC"
        )
        st.altair_chart(history_chart, width="stretch")
        st.download_button(
            "Descargar datos agregados del modelo",
            data=DATA_PATH.read_bytes(),
            file_name=DATA_PATH.name,
            mime="text/csv",
        )
        st.dataframe(source_data.head(20), hide_index=True, width="stretch")
    else:
        st.warning(
            "El snapshot completo todavía no fue generado. El simulador funciona con el modelo congelado; "
            "ejecute `src/export_snapshot.py` en un entorno autenticado para habilitar la auditoría y descarga de las 390 filas."
        )

st.divider()
st.caption(
    "Modelo econométrico académico · Cobertura global de NYC · Los montos expresan costo social potencial, no una transferencia presupuestaria garantizada."
)
