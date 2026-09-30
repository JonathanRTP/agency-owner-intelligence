import os
import json
from pathlib import Path

import pandas as pd
import streamlit as st


# ---------------------------------------------------------
# CONFIGURACIÓN GENERAL DE LA APLICACIÓN
# ---------------------------------------------------------

# Configuramos el título de la página, el ícono y el diseño
# para utilizar todo el ancho disponible.
st.set_page_config(
    page_title="Owner Intelligence",
    page_icon="◈",
    layout="wide"
)


# ---------------------------------------------------------
# UBICACIÓN DE LOS DATOS
# ---------------------------------------------------------

# Construimos la ruta al archivo CSV.
# El archivo activity.csv se encuentra dentro de la carpeta
# "data", ubicada junto al archivo app.py.
DATA = Path(__file__).parent / "data" / "activity.csv"


# ---------------------------------------------------------
# REGLAS DE NEGOCIO
# ---------------------------------------------------------

# Disposiciones que representan una interacción humana
# confirmada según las reglas definidas para el reto.
HUMAN_DISPOSITIONS = {"conversation", "appointment"}


# ---------------------------------------------------------
# CARGA Y PREPARACIÓN DE DATOS
# ---------------------------------------------------------

@st.cache_data
def load_data():
    """
    Carga el archivo CSV y prepara las columnas necesarias
    para aplicar las reglas de negocio y las métricas.
    """

    # Leemos el CSV y convertimos timestamp_utc a fecha/hora.
    df = pd.read_csv(
        DATA,
        parse_dates=["timestamp_utc"]
    )

    # Identificamos los registros correspondientes a personas.
    # "PBG Billing" se considera una cuenta y no una persona,
    # por lo que posteriormente se excluye de las métricas
    # de desempeño individual.
    df["is_person"] = df["agent"].ne("PBG Billing")


    # -----------------------------------------------------
    # REGLA PARA CONFIRMAR UNA CONVERSACIÓN
    # -----------------------------------------------------

    # Importante:
    # Que una llamada haya sido contestada (carrier_answered)
    # NO significa necesariamente que haya existido una
    # conversación real.
    #
    # Consideramos una interacción confirmada cuando:
    # 1. La disposición indica "conversation" o "appointment", O
    # 2. Existen al menos 4 turnos de conversación.
    df["confirmed_conversation"] = (
        df["disposition"].isin(HUMAN_DISPOSITIONS)
        | (df["speaker_turns"] >= 4)
    )


    # -----------------------------------------------------
    # IDENTIFICACIÓN DE POSIBLES INCONSISTENCIAS
    # -----------------------------------------------------

    # Detectamos registros donde existe suficiente actividad
    # conversacional (4 o más turnos), pero la disposición
    # original no indica "conversation" ni "appointment".
    #
    # Estos registros NO se corrigen automáticamente.
    # Se muestran como señales para que el usuario pueda
    # revisarlos.
    df["quality_flag"] = (
        (df["speaker_turns"] >= 4)
        & (~df["disposition"].isin(HUMAN_DISPOSITIONS))
    )


    # -----------------------------------------------------
    # REGLA PARA LAS CITAS
    # -----------------------------------------------------

    # Una cita solo se cuenta cuando appointment_type
    # tiene exactamente el valor "appointment".
    #
    # Los callbacks se mantienen separados y NO se consideran
    # automáticamente como citas.
    df["real_appointment_signal"] = (
        df["appointment_type"].eq("appointment")
    )

    return df


# ---------------------------------------------------------
# FUNCIONES DE FORMATO
# ---------------------------------------------------------

def money(x):
    """Formatea un número como valor monetario."""
    return f"${x:,.2f}"


def pct(x):
    """Convierte un número decimal en porcentaje."""
    return f"{x:.1%}"


# ---------------------------------------------------------
# CÁLCULO DE MÉTRICAS PRINCIPALES
# ---------------------------------------------------------

def build_metrics(df):
    """
    Calcula las métricas principales que se mostrarán
    al dueño de la agencia.
    """

    # Trabajamos únicamente con registros correspondientes
    # a personas para las métricas de desempeño.
    people = df[df.is_person].copy()

    # Filtramos las interacciones que cumplen la regla
    # de conversación confirmada.
    confirmed = people[people.confirmed_conversation]


    # -----------------------------------------------------
    # MÉTRICAS DEL NEGOCIO
    # -----------------------------------------------------

    sales = int(people.sales.sum())

    applications = int(people.applications.sum())

    spend = float(people.ad_spend.sum())

    dials = int(people.dials.sum())

    carrier = int(people.carrier_answered.sum())

    appointments = int(
        people.real_appointment_signal.sum()
    )


    # -----------------------------------------------------
    # RETORNO DE MÉTRICAS
    # -----------------------------------------------------

    return {
        "records": len(people),

        "dials": dials,

        "carrier_answered": carrier,

        "confirmed_interactions": len(confirmed),

        "applications": applications,

        "sales": sales,

        "ad_spend": spend,

        "appointments": appointments,

        # Ventas por interacción confirmada.
        # Evitamos división entre cero.
        "sales_per_confirmed": (
            sales / len(confirmed)
            if len(confirmed)
            else 0
        ),

        # Gasto publicitario por venta reportada.
        # No se calcula si no existen ventas.
        "ad_spend_per_sale": (
            spend / sales
            if sales
            else None
        ),

        # Cantidad de registros identificados como
        # posibles inconsistencias de calidad.
        "data_quality_flags": int(
            df.quality_flag.sum()
        ),

        # Cantidad de registros excluidos de las vistas
        # de desempeño individual.
        "excluded_non_person_records": int(
            (~df.is_person).sum()
        ),
    }


# ---------------------------------------------------------
# RESUMEN PARA EL DUEÑO
# ---------------------------------------------------------

def owner_brief(m):
    """
    Genera señales de negocio a partir de las métricas
    previamente calculadas.
    
    Esta función no recalcula métricas ni utiliza IA.
    """

    signals = []


    # Mostramos el gasto por venta solamente si existen
    # ventas reportadas.
    if m["ad_spend_per_sale"] is not None:

        signals.append(
            f"Ad spend per reported sale is "
            f"{money(m['ad_spend_per_sale'])}; "
            "this is not ROI because revenue is not provided."
        )


    # Mostramos posibles problemas de calidad de datos.
    signals.append(
        f"There are {m['data_quality_flags']} records "
        "where speaker activity (>=4 turns) conflicts "
        "with a non-human conversation disposition; "
        "these are surfaced, not silently corrected."
    )


    # Informamos cuántos registros cumplen la regla de cita.
    signals.append(
        f"{m['appointments']} records have "
        "appointment_type='appointment'; "
        "callbacks are not counted as appointments."
    )


    # Informamos los registros excluidos del análisis
    # de desempeño individual.
    signals.append(
        f"{m['excluded_non_person_records']} "
        "PBG Billing records are excluded from "
        "person-level performance views."
    )

    return signals


# ---------------------------------------------------------
# TABLA DE DESEMPEÑO POR AGENTE
# ---------------------------------------------------------

@st.cache_data
def agent_table(df):
    """
    Agrupa las métricas por agente para permitir
    comparar resultados individuales.
    """

    # Nuevamente excluimos PBG Billing de las métricas
    # de desempeño por persona.
    p = df[df.is_person].copy()


    # Agrupamos los registros por agente y sumamos
    # las principales métricas.
    g = p.groupby(
        "agent",
        as_index=False
    ).agg(
        dials=("dials", "sum"),
        carrier_answered=("carrier_answered", "sum"),
        confirmed_interactions=("confirmed_conversation", "sum"),
        applications=("applications", "sum"),
        sales=("sales", "sum"),
        ad_spend=("ad_spend", "sum"),
    )


    # Calculamos ventas por interacción confirmada.
    #
    # Se utiliza pd.NA para evitar divisiones entre cero.
    g["sales_per_confirmed"] = (
        g["sales"]
        / g["confirmed_interactions"].replace(0, pd.NA)
    )


    # Calculamos gasto publicitario por venta.
    g["ad_spend_per_sale"] = (
        g["ad_spend"]
        / g["sales"].replace(0, pd.NA)
    )


    # Ordenamos primero por ventas y después por aplicaciones.
    return g.sort_values(
        ["sales", "applications"],
        ascending=False
    )


# ---------------------------------------------------------
# EJECUCIÓN PRINCIPAL
# ---------------------------------------------------------

# Cargamos y procesamos los datos.
df = load_data()

# Calculamos las métricas generales.
m = build_metrics(df)


# ---------------------------------------------------------
# TÍTULO
# ---------------------------------------------------------

st.title("Owner Intelligence")

st.caption(
    "Decision-ready business view built on explicit "
    "data-confidence rules."
)


# ---------------------------------------------------------
# PANEL DE CONFIANZA DE LOS DATOS
# ---------------------------------------------------------

with st.sidebar:

    st.header("Data trust")

    # Indicamos que la regla de conversación está activa.
    st.success("Conversation rule applied")

    st.write(
        "Confirmed = human disposition "
        "(conversation/appointment) OR ≥4 speaker turns."
    )

    # Advertimos que "carrier_answered" por sí solo
    # no demuestra que haya existido una conversación.
    st.warning(
        "carrier_answered alone does not prove a conversation."
    )

    # Los callbacks no se contabilizan como citas.
    st.info(
        "Callbacks are not counted as appointments."
    )

    # Mostramos cuántos registros de PBG Billing
    # fueron excluidos de las métricas individuales.
    st.write(
        f"Excluded from person performance: "
        f"**{m['excluded_non_person_records']}** "
        "PBG Billing records."
    )


# ---------------------------------------------------------
# TARJETAS DE MÉTRICAS
# ---------------------------------------------------------

cols = st.columns(6)

items = [
    ("Reported sales", m["sales"]),
    ("Applications", m["applications"]),
    ("Confirmed interactions", m["confirmed_interactions"]),
    ("Appointments", m["appointments"]),
    ("Ad spend", money(m["ad_spend"])),
    ("Data flags", m["data_quality_flags"]),
]


# Creamos una tarjeta de Streamlit para cada métrica.
for c, (label, val) in zip(cols, items):
    c.metric(label, val)


st.divider()


# ---------------------------------------------------------
# SECCIÓN PRINCIPAL DEL DASHBOARD
# ---------------------------------------------------------

left, right = st.columns([1.35, 1])


# ---------------------------------------------------------
# TABLA DE AGENTES
# ---------------------------------------------------------

with left:

    st.subheader("Where should the owner look?")

    # Obtenemos la tabla agrupada por agente.
    t = agent_table(df).copy()


    # Convertimos el gasto por venta a formato monetario.
    t["Ad spend / sale"] = t[
        "ad_spend_per_sale"
    ].map(
        lambda x: money(x)
        if pd.notna(x)
        else "—"
    )


    # Convertimos ventas por interacción a porcentaje.
    t["Sales / confirmed"] = t[
        "sales_per_confirmed"
    ].map(
        lambda x: pct(x)
        if pd.notna(x)
        else "—"
    )


    # Seleccionamos únicamente las columnas necesarias
    # para la vista del dueño.
    display = t[
        [
            "agent",
            "sales",
            "applications",
            "confirmed_interactions",
            "ad_spend",
            "Sales / confirmed",
            "Ad spend / sale",
        ]
    ].rename(
        columns={
            "agent": "Agent",
            "sales": "Sales",
            "applications": "Apps",
            "confirmed_interactions": "Confirmed",
            "ad_spend": "Ad spend",
        }
    )


    # Mostramos la tabla en Streamlit.
    st.dataframe(
        display,
        use_container_width=True,
        hide_index=True
    )


# ---------------------------------------------------------
# RESUMEN PARA EL DUEÑO
# ---------------------------------------------------------

with right:

    st.subheader("Owner brief")


    # Mostramos las señales generadas a partir
    # de las métricas validadas.
    for s in owner_brief(m):
        st.write("• " + s)


    st.markdown(
        "**Recommended next actions**"
    )


    # Recomendaciones basadas en las señales encontradas.
    st.write(
        "1. Investigate high-spend / low-sale segments "
        "before changing budgets."
    )

    st.write(
        "2. Audit records where speaker turns "
        "conflict with disposition."
    )

    st.write(
        "3. Keep callbacks separate from appointment reporting."
    )

    st.write(
        "4. Do not calculate ROI until revenue is available and defined."
    )


st.divider()


# ---------------------------------------------------------
# SEÑALES DE CALIDAD DE DATOS
# ---------------------------------------------------------

st.subheader("Data quality signals")


# Filtramos únicamente los registros que presentan
# una posible inconsistencia.
flags = df[df.quality_flag].copy()


if flags.empty:

    # Si no existen inconsistencias, mostramos un mensaje
    # indicando que no se encontraron señales.
    st.success(
        "No conflicting interaction signals found."
    )

else:

    # Explicamos qué tipo de registros fueron encontrados.
    st.write(
        f"{len(flags)} records have ≥4 speaker turns "
        "but a disposition other than "
        "conversation/appointment. "
        "The app does not overwrite the source disposition."
    )


    # Mostramos los registros para permitir su revisión.
    st.dataframe(
        flags[
            [
                "timestamp_utc",
                "agent",
                "speaker_turns",
                "disposition",
                "appointment_type",
                "applications",
                "sales",
                "ad_spend",
            ]
        ],
        use_container_width=True,
        hide_index=True
    )


# ---------------------------------------------------------
# DEFINICIONES Y LIMITACIONES
# ---------------------------------------------------------

with st.expander("Metric definitions & limitations"):

    st.markdown(
        """
- **Confirmed interaction:** `disposition` is
  `conversation` or `appointment`, **OR**
  `speaker_turns >= 4`, following the challenge rule.

- **Appointment:** only
  `appointment_type == appointment`.
  `callback` is deliberately excluded.

- **Sales:** reported `sales` sum; this is a source
  metric, not an independently verified revenue event.

- **Ad spend / sale:** `ad_spend / sales`.
  It is **not ROI** because the dataset does not provide revenue.

- **Person performance:** excludes `PBG Billing`,
  documented in the supplied notes as a non-person account.

- **Premium screen:** not used as a business outcome because
  the supplied notes identify a Maria document/screen override;
  it should be treated as a field requiring domain validation
  before using it for decision-making.
"""
    )


# ---------------------------------------------------------
# CAPA OPCIONAL DE INTELIGENCIA ARTIFICIAL
# ---------------------------------------------------------

st.subheader("AI Owner Brief")

st.caption(
    "The AI layer is intentionally downstream of deterministic metrics. "
    "It explains validated signals; it does not calculate them."
)


# Buscamos la API Key de OpenAI en las variables de entorno.
api_key = os.getenv("OPENAI_API_KEY")


if api_key:

    # Si existe API Key, mostramos el botón para generar
    # el resumen mediante el modelo.
    if st.button("Generate AI brief"):

        try:

            # Importamos el cliente de OpenAI únicamente
            # cuando realmente se necesita.
            from openai import OpenAI

            client = OpenAI(api_key=api_key)


            # Enviamos a la IA únicamente métricas y señales
            # que ya fueron calculadas por nuestra aplicación.
            #
            # De esta forma, el modelo no es responsable
            # de calcular las métricas del negocio.
            payload = {
                "metrics": m,
                "signals": owner_brief(m)
            }


            # Instrucciones para el modelo.
            #
            # Se le indica explícitamente que:
            # - No invente información.
            # - No considere gasto/venta como ROI.
            # - Mencione limitaciones.
            # - Termine con acciones concretas.
            prompt = (
                "You are an executive analytics assistant. "
                "Summarize the supplied validated metrics in 4 short bullets. "
                "Do not invent facts. "
                "Do not call ad spend/sale ROI. "
                "Mention data-quality limitations when relevant. "
                "End with 2 concrete next actions.\n"
                + json.dumps(payload)
            )


            # Ejecutamos la solicitud al modelo.
            r = client.responses.create(
                model=os.getenv(
                    "OPENAI_MODEL",
                    "gpt-5-mini"
                ),
                input=prompt
            )


            # Mostramos la respuesta generada por la IA.
            st.write(r.output_text)


        except Exception as e:

            # Si ocurre un error con la API,
            # mostramos el mensaje sin detener toda la aplicación.
            st.error(
                f"AI brief unavailable: {e}"
            )

else:

    # La aplicación sigue funcionando aunque no exista
    # una API Key, ya que la IA es una funcionalidad opcional.
    st.info(
        "Set OPENAI_API_KEY to enable the optional AI summary. "
        "The core experience works without an LLM."
    )


# ---------------------------------------------------------
# PIE DE PÁGINA
# ---------------------------------------------------------

st.caption(
    "Synthetic challenge data only • "
    "Built as a 60-minute MVP • "
    "Deterministic metrics first, AI second"
)
