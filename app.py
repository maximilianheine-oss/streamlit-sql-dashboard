import os
import time
import pandas as pd
import numpy as np
import streamlit as st
from sqlalchemy import create_engine, text
import plotly.express as px
import plotly.graph_objects as go

st.set_page_config(page_title="Zeiterfassung Dashboard", layout="wide")

st.title("Zeiterfassung Dashboard")

# Konfiguration
st.sidebar.header("Konfiguration")

# Verbindung über DATABASE_URL oder einzelne Variablen
db_url = st.secrets.get("DATABASE_URL", "")
if not db_url:
    dialect = st.secrets.get("DB_DIALECT", "postgresql")  # postgresql, mysql, mssql
    user = st.secrets.get("DB_USER", "")
    password = st.secrets.get("DB_PASSWORD", "")
    host = st.secrets.get("DB_HOST", "localhost")
    port = st.secrets.get("DB_PORT", "")
    name = st.secrets.get("DB_NAME", "")
    if dialect == "postgresql":
        port = port or "5432"
        db_url = f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{name}"
    elif dialect == "mysql":
        port = port or "3306"
        db_url = f"mysql+pymysql://{user}:{password}@{host}:{port}/{name}"
    elif dialect in ["mssql", "sqlserver"]:
        port = port or "1433"
        # pymssql
        db_url = f"mssql+pymssql://{user}:{password}@{host}:{port}/{name}"
    else:
        st.error("Unbekannter DB Dialekt. Nutze postgresql, mysql oder mssql.")
        st.stop()

# Tabellennamen und Spalten Mapping
# Passe diese Namen an eure MFR SQL Ansicht an
TABLE_NAME = st.secrets.get("TABLE_NAME", "time_events")
COLS = {
    "employee": st.secrets.get("COL_EMPLOYEE", "employee_name"),
    "start": st.secrets.get("COL_START", "start_time"),
    "end": st.secrets.get("COL_END", "end_time"),
    "work_hours": st.secrets.get("COL_WORK_H", "work_hours"),
    "travel_hours": st.secrets.get("COL_TRAVEL_H", "travel_hours"),
    "plant_hours": st.secrets.get("COL_PLANT_H", "plant_hours"),
    "vacation": st.secrets.get("COL_VAC", "vacation_flag"),
    "sick": st.secrets.get("COL_SICK", "sick_flag"),
    "project": st.secrets.get("COL_PROJECT", "project_name"),
    "team": st.secrets.get("COL_TEAM", "team_name"),
}

BASE_SQL = f'''
SELECT
  {COLS["employee"]}   AS employee,
  {COLS["start"]}      AS start_time,
  {COLS["end"]}        AS end_time,
  {COLS["work_hours"]}   AS work_hours,
  {COLS["travel_hours"]} AS travel_hours,
  {COLS["plant_hours"]}  AS plant_hours,
  {COLS["vacation"]}     AS vacation,
  {COLS["sick"]}         AS sick,
  {COLS["project"]}      AS project,
  {COLS["team"]}         AS team
FROM {TABLE_NAME}
WHERE {COLS["start"]} IS NOT NULL
  AND {COLS["end"]} IS NOT NULL
'''

@st.cache_data(ttl=300)
def load_data():
    engine = create_engine(db_url, pool_pre_ping=True)
    with engine.connect() as conn:
        df = pd.read_sql(text(BASE_SQL), conn)
    # Typen
    df["start_time"] = pd.to_datetime(df["start_time"], errors="coerce")
    df["end_time"] = pd.to_datetime(df["end_time"], errors="coerce")
    for c in ["work_hours","travel_hours","plant_hours"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    # Fallback gesamt
    if {"work_hours","travel_hours","plant_hours"}.issubset(df.columns):
        df["total_hours"] = df[["work_hours","travel_hours","plant_hours"]].sum(axis=1, min_count=1)
    else:
        # Fallback auf Differenz
        df["total_hours"] = (df["end_time"] - df["start_time"]).dt.total_seconds()/3600.0
    df["date"] = df["start_time"].dt.date
    df["month"] = df["start_time"].dt.to_period("M").astype(str)
    df["hour"] = df["start_time"].dt.hour
    df["weekday_num"] = df["start_time"].dt.weekday  # 0 Montag
    de_names = ["Montag","Dienstag","Mittwoch","Donnerstag","Freitag","Samstag","Sonntag"]
    df["weekday"] = df["weekday_num"].map({i:n for i,n in enumerate(de_names)})
    # Flags als int
    for c in ["vacation","sick"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0).astype(int)
    return df

with st.spinner("Lade Daten aus SQL..."):
    df = load_data()

if df.empty:
    st.warning("Keine Daten gefunden. Prüfe Tabellenname, Spalten und Rechte.")
    st.stop()

# Filter
st.sidebar.subheader("Filter")
min_date, max_date = df["date"].min(), df["date"].max()
date_range = st.sidebar.date_input("Zeitraum", value=(min_date, max_date))
employees = sorted(df["employee"].dropna().unique().tolist())
emp_sel = st.sidebar.multiselect("Mitarbeiter", employees, default=employees)
teams = sorted([t for t in df.get("team", pd.Series(dtype=str)).dropna().unique().tolist()])
team_sel = st.sidebar.multiselect("Team", teams, default=teams) if teams else []

df_f = df.copy()
if isinstance(date_range, tuple) and len(date_range) == 2:
    df_f = df_f[(df_f["date"] >= date_range[0]) & (df_f["date"] <= date_range[1])]
if emp_sel:
    df_f = df_f[df_f["employee"].isin(emp_sel)]
if team_sel:
    df_f = df_f[df_f["team"].isin(team_sel)]

# KPI Kacheln
col1, col2, col3, col4 = st.columns(4)
col1.metric("Gesamtstunden", f"{df_f['total_hours'].sum():.1f} h")
col2.metric("Tage gesamt", f"{df_f['date'].nunique()}")
col3.metric("Urlaubstage", f"{int(df_f.get('vacation', pd.Series(0)).sum())}")
col4.metric("Krankheitstage", f"{int(df_f.get('sick', pd.Series(0)).sum())}")

st.markdown("---")

# 1) Gesamtstunden pro Monat und Mitarbeiter
group_month = df_f.groupby(["month","employee"], as_index=False)["total_hours"].sum()
fig1 = px.bar(group_month, x="month", y="total_hours", color="employee",
              title="Gesamtstunden pro Monat und Mitarbeiter", barmode="group")
st.plotly_chart(fig1, use_container_width=True)

# 2) Tagesverlauf letzte 30 Tage
if len(df_f["date"].unique()) > 0:
    last_date = pd.to_datetime(df_f["date"].max())
    start_30 = (last_date - pd.Timedelta(days=30)).date()
    df_30 = df_f[df_f["date"] >= start_30]
    by_day = df_30.groupby(["date","employee"], as_index=False)["total_hours"].sum()
    fig2 = px.bar(by_day, x="date", y="total_hours", color="employee",
                  title="Gesamtstunden pro Tag letzte 30 Tage", barmode="stack")
    st.plotly_chart(fig2, use_container_width=True)

# 3) Komponenten pro Monat
if {"work_hours","travel_hours","plant_hours"}.issubset(df_f.columns):
    comp = df_f.groupby("month")[["work_hours","travel_hours","plant_hours"]].sum().reset_index()
    comp = comp.melt(id_vars="month", var_name="Komponente", value_name="Stunden")
    fig3 = px.bar(comp, x="month", y="Stunden", color="Komponente",
                  title="Arbeits, Fahrt und Werkzeit je Monat", barmode="stack")
    st.plotly_chart(fig3, use_container_width=True)

# 4) Timeline letzte 7 Tage
last_date = pd.to_datetime(df_f["date"].max())
start_7 = (last_date - pd.Timedelta(days=7)).date()
tl = df_f[(df_f["date"] >= start_7) & df_f["end_time"].notna() & df_f["start_time"].notna()]\
        .sort_values(["employee","start_time"])
if not tl.empty:
    fig4 = px.timeline(tl, x_start="start_time", x_end="end_time", y="employee", color="employee",
                       title="Timeline der Zeitereignisse letzte 7 Tage")
    fig4.update_yaxes(autorange="reversed")
    st.plotly_chart(fig4, use_container_width=True)

# 5) Heatmap Wochentag x Stunde
heat = df_f.copy()
if "hour" in heat.columns:
    heat_pivot = heat.pivot_table(index="weekday", columns="hour", values="total_hours", aggfunc="sum", fill_value=0.0)
    heat_pivot = heat_pivot.reindex(["Montag","Dienstag","Mittwoch","Donnerstag","Freitag","Samstag","Sonntag"])
    fig5 = go.Figure(data=go.Heatmap(z=heat_pivot.values, x=[str(c) for c in heat_pivot.columns], y=heat_pivot.index))
    fig5.update_layout(title="Heatmap Stunden nach Wochentag und Startstunde")
    st.plotly_chart(fig5, use_container_width=True)

# 6) Detailtabelle
st.subheader("Detailtabelle")
show_cols = ["employee","start_time","end_time","total_hours","work_hours","travel_hours","plant_hours","project","team","vacation","sick"]
show_cols = [c for c in show_cols if c in df_f.columns]
st.dataframe(df_f[show_cols].sort_values("start_time", ascending=False), use_container_width=True)