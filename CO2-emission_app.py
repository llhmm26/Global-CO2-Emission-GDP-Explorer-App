import streamlit as st
import pandas as pd
import plotly.express as px
import os

# ---------------- CONFIG ----------------
st.set_page_config(page_title="Global CO2 & GDP Explorer (Local CSV)", layout="wide", page_icon="🌍")

# Path to your local CSV file (relative to repo root)
CSV_PATH = "gdp_co2_by_country_v2.csv"

# Load CSV
if os.path.exists(CSV_PATH):
    try:
        df = pd.read_csv(CSV_PATH)
        st.sidebar.success(f"Loaded local dataset: {CSV_PATH}")
    except Exception as e:
        st.sidebar.error(f"Failed to read CSV: {e}")
        df = pd.DataFrame()
else:
    st.sidebar.error(f"Dataset not found at: {CSV_PATH}")
    df = pd.DataFrame()
# Normalize column names to lowercase
if not df.empty:
    df.columns = [c.lower() for c in df.columns]

# ----------------- Helper column detection & calculations -----------------
# We'll try to detect common column names. If not present, create columns when possible.
if not df.empty:
    # ensure 'country' and 'year' exist
    if 'country' not in df.columns:
        # try variants
        for col in df.columns:
            if 'country' in col:
                df = df.rename(columns={col: 'country'})
                break
    if 'year' not in df.columns:
        for col in df.columns:
            if 'year' in col:
                df = df.rename(columns={col: 'year'})
                break

    # ensure numeric columns are proper dtype
    num_cols = df.select_dtypes(include=['number']).columns.tolist()
    # co2 column
    if 'co2' not in df.columns:
        for c in df.columns:
            if 'co2' == c or 'co2_' in c or c.endswith('co2'):
                df = df.rename(columns={c: 'co2'})
                break
    # population
    if 'population' not in df.columns:
        for c in df.columns:
            if 'pop' in c and c != 'co2_per_capita':
                df = df.rename(columns={c: 'population'})
                break
    # gdp
    if 'gdp' not in df.columns:
        for c in df.columns:
            if 'gdp' in c and 'per' not in c:
                df = df.rename(columns={c: 'gdp'})
                break
    # gdp_per_capita
    if 'gdp_per_capita' not in df.columns:
        for c in df.columns:
            if 'gdp_per_capita' in c or 'gdp_pc' in c:
                df = df.rename(columns={c: 'gdp_per_capita'})
                break
    # co2_per_capita
    if 'co2_per_capita' not in df.columns:
        for c in df.columns:
            if 'co2_per_capita' in c or c.endswith('per_capita') and 'co2' in c:
                df = df.rename(columns={c: 'co2_per_capita'})
                break

    # Convert columns to numeric where possible
    for c in ['co2','population','gdp','gdp_per_capita','co2_per_capita']:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors='coerce')

    # Compute derived columns safely
    # 1) co2 per capita: if missing, compute from co2 and population
    if 'co2_per_capita' not in df.columns and 'co2' in df.columns and 'population' in df.columns:
        df['co2_per_capita'] = df['co2'] / df['population']

    # 2) cumulative_co2 per country
    if 'cumulative_co2' not in df.columns and 'co2' in df.columns and 'country' in df.columns and 'year' in df.columns:
        df = df.sort_values(['country','year'])
        df['cumulative_co2'] = df.groupby('country')['co2'].cumsum()

    # 3) global total co2 per year for percentage
    if 'co2' in df.columns and 'year' in df.columns:
        df['global_total_co2'] = df.groupby('year')['co2'].transform('sum')
        # avoid division by zero
        df['co2_pct'] = (df['co2'] / df['global_total_co2'] * 100).fillna(0)

    # 4) GDP percent: country gdp / global gdp per year
    if 'gdp' in df.columns and 'year' in df.columns:
        df['global_total_gdp'] = df.groupby('year')['gdp'].transform('sum')
        df['gdp_pct'] = (df['gdp'] / df['global_total_gdp'] * 100).fillna(0)

    # 5) gdp per capita (if missing and population & gdp exist)
    if 'gdp_per_capita' not in df.columns and 'gdp' in df.columns and 'population' in df.columns:
        # assuming gdp is total GDP; if gdp is per capita already this will be wrong — user should verify
        df['gdp_per_capita'] = df['gdp'] / df['population']

    # 6) co2 per gdp
    if 'co2_per_gdp' not in df.columns and 'co2' in df.columns and 'gdp' in df.columns:
        # avoid division by zero
        df['co2_per_gdp'] = df['co2'] / df['gdp'].replace({0: pd.NA})

# ----------------- Sidebar (filters) -----------------
st.title("🌍 CO₂ Emission & Global GDP Explorer")
st.write("Select countries and year range, then choose which metric to display for CO₂ and GDP groups.")

st.sidebar.header("Filters")
if df.empty:
    st.sidebar.warning("Dataset empty — check LOCAL_DATASET_PATH and CSV format.")

# Country selector (multi-select)
if 'country' in df.columns and not df.empty:
    countries = sorted(df['country'].dropna().unique())
    selected_countries = st.sidebar.multiselect("Select countries (leave empty = All)", options=countries, default=countries[:3])
else:
    selected_countries = []

# Year range
if 'year' in df.columns and not df.empty:
    min_year = int(df['year'].min())
    max_year = int(df['year'].max())
    selected_years = st.sidebar.slider("Year range", min_value=min_year, max_value=max_year, value=(min_year, max_year))
else:
    selected_years = None

# Metric selection for the two groups
st.sidebar.header("Metric selectors")
co2_options = ['co2_pct','co2_per_capita','cumulative_co2']
available_co2 = [c for c in co2_options if c in df.columns]
selected_co2_metric = st.sidebar.selectbox("CO₂ metric to plot", options=available_co2 if available_co2 else ['(none available)'])

gdp_options = ['gdp_pct','gdp_per_capita','co2_per_gdp']
available_gdp = [c for c in gdp_options if c in df.columns]
selected_gdp_metric = st.sidebar.selectbox("GDP metric to plot", options=available_gdp if available_gdp else ['(none available)'])

# ----------------- Data filtering -----------------
filtered = df.copy()
if not filtered.empty:
    if selected_countries:
        filtered = filtered[filtered['country'].isin(selected_countries)]
    if selected_years and 'year' in filtered.columns:
        filtered = filtered[(filtered['year'] >= selected_years[0]) & (filtered['year'] <= selected_years[1])]

# ----------------- Plots -----------------
st.markdown("---")
col1, col2 = st.columns(2)

with col1:
    st.subheader("CO₂ Group")
    if filtered.empty or selected_co2_metric == '(none available)':
        st.info("CO₂ metric not available or no data selected.")
    else:
        fig = px.line(filtered.sort_values('year') if 'year' in filtered.columns else filtered,
                      x='year' if 'year' in filtered.columns else (filtered.index),
                      y=selected_co2_metric,
                      color='country' if 'country' in filtered.columns else None,
                      markers=True,
                      title=f"{selected_co2_metric} over time")
        st.plotly_chart(fig, use_container_width=True)

with col2:
    st.subheader("GDP Group")
    if filtered.empty or selected_gdp_metric == '(none available)':
        st.info("GDP metric not available or no data selected.")
    else:
        fig2 = px.line(filtered.sort_values('year') if 'year' in filtered.columns else filtered,
                       x='year' if 'year' in filtered.columns else (filtered.index),
                       y=selected_gdp_metric,
                       color='country' if 'country' in filtered.columns else None,
                       markers=True,
                       title=f"{selected_gdp_metric} over time")
        st.plotly_chart(fig2, use_container_width=True)

# ----------------- Master table -----------------
st.markdown("---")
st.subheader("Master table")

master_cols = ['country','year','co2_pct','co2_per_capita','cumulative_co2','gdp_pct','gdp_per_capita','co2_per_gdp']
existing_master_cols = [c for c in master_cols if c in df.columns]

if filtered.empty:
    st.write("No data to show in master table. Adjust filters or check data.")
else:
    master_df = filtered.copy()
    # ensure columns exist in master_df; if missing, create with NaN
    for c in master_cols:
        if c not in master_df.columns:
            master_df[c] = pd.NA
    master_df = master_df[master_cols]
    st.dataframe(master_df.reset_index(drop=True))
    csv = master_df.to_csv(index=False)
    st.download_button("Download master table (CSV)", data=csv, file_name="master_table.csv")

st.markdown("---")
st.caption("Notes: The app attempts to detect and compute derived metrics (percentages, per-capita, cumulative) when possible. Verify column meanings in your CSV for correctness.")






