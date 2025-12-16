import streamlit as st
import pandas as pd
import plotly.express as px
from textblob import TextBlob
import pdfplumber
import re

# --- Page Config ---
st.set_page_config(page_title="Forensic Engine Ultimate", layout="wide")
st.title("🕵️‍♂️ Forensic Risk Engine: Auto-Adaptive")
st.markdown("**Methodology:** Adaptive grouping (Binary vs Traffic Light) with Detailed Interpretation.")

# --- Sidebar ---
with st.sidebar:
    st.header("⚙️ Control Panel")
    app_mode = st.selectbox("Select Module", [
        "1. Quantitative Forensic Scorecard",
        "2. Single Company Auto-Analysis (PDF)",
        "3. Qualitative Sentiment Scanner"
    ])
    st.info("ℹ️ **Smart Logic:**\n- **N < 30:** Tool uses 2 Groups (Binary).\n- **N ≥ 30:** Tool uses 3 Groups (Traffic Light).")

# --- Helper: Extract Text ---
def extract_pdf_text(uploaded_file):
    all_text = ""
    with pdfplumber.open(uploaded_file) as pdf:
        for page in pdf.pages[:50]:
            text = page.extract_text()
            if text: all_text += text + "\n"
    return all_text

# --- Helper: Regex Search ---
def find_value_in_text(text, keywords):
    for keyword in keywords:
        pattern = re.compile(rf"{keyword}[:\s\-\|]+([\d,]+\.?\d*)", re.IGNORECASE)
        match = pattern.search(text)
        if match:
            try: return float(match.group(1).replace(',', ''))
            except: continue
    return 0.0

# --- Helper: Adaptive Risk Calculation & Narrative ---
def calculate_risk(df):
    # 1. Clean Data
    cols = ['Sales', 'Receivables', 'Inventory', 'CFO', 'EBITDA', 'Pledge_Pct', 'Total_Assets', 'Non_Current_Assets', 'RPT_Vol']
    for c in cols:
        if c not in df.columns: df[c] = 0
        df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0)

    # 2. Calculate Ratios
    df['DSO'] = df.apply(lambda x: (x['Receivables'] / x['Sales'] * 365) if x['Sales'] > 0 else 0, axis=1).round(1)
    df['Cash_Quality'] = df.apply(lambda x: (x['CFO'] / x['EBITDA']) if x['EBITDA'] > 0 else 0, axis=1).round(2)
    df['AQI'] = df.apply(lambda x: (x['Non_Current_Assets'] / x['Total_Assets']) if x['Total_Assets'] > 0 else 0, axis=1).round(2)
    df['RPT_Intensity'] = df.apply(lambda x: (x['RPT_Vol'] / x['Sales'] * 100) if x['Sales'] > 0 else 0, axis=1).round(1)

    # 3. SMART GROUPING LOGIC
    sample_size = len(df)
    if sample_size < 30:
        # Binary Grouping
        df['Risk_Group'] = df['Pledge_Pct'].apply(lambda x: "🔴 Critical (>50%)" if x > 50 else "🟢 Control (<50%)")
        grouping_method = "Binary (Small Sample Protocol)"
    else:
        # Traffic Light Grouping
        def get_3_buckets(p):
            if p > 50: return "🔴 Critical (>50%)"
            elif p >= 10: return "🟡 Moderate (10-50%)"
            else: return "🟢 Safe (<10%)"
        df['Risk_Group'] = df['Pledge_Pct'].apply(get_3_buckets)
        grouping_method = "Traffic Light (Large Sample Protocol)"

    # 4. Scoring & Narrative Logic (Restored)
    def get_detailed_analysis(row):
        score = 0
        obs = []
        verdict = "Low Risk"
        
        # PLEDGE CHECK
        if row['Pledge_Pct'] > 50:
            score += 25
            obs.append(f"🔴 **Critical Pledge Pressure:** {row['Pledge_Pct']}% of shares are pledged. This creates a high incentive to manipulate earnings.")
        elif row['Pledge_Pct'] > 20:
            score += 10
            obs.append(f"🟠 **Moderate Pledge:** {row['Pledge_Pct']}% pledged.")

        # CASH CHECK
        if row['Cash_Quality'] < 0.5:
            score += 30
            obs.append(f"🔴 **Fake Profit Alert:** Cash Quality is {row['Cash_Quality']}. For every ₹1 profit, only ₹{row['Cash_Quality']} is collected in cash.")
        elif row['Cash_Quality'] < 0.8:
            score += 15
            obs.append(f"🟠 **Weak Cash Flow:** Cash conversion (CFO/EBITDA) is below the healthy 0.8 benchmark.")

        # ACCRUALS CHECK
        if row['DSO'] > 120:
            score += 20
            obs.append(f"🔴 **Aggressive Revenue:** Sales take {row['DSO']} days to collect (High DSO). Suggests channel stuffing.")
        if row['RPT_Intensity'] > 10:
            score += 10
            obs.append(f"⚠️ **Leakage Risk:** {row['RPT_Intensity']}% of sales are with Related Parties.")

        # FINAL VERDICT
        if score >= 60: verdict = "🚨 HIGH PROBABILITY OF MANIPULATION"
        elif score >= 35: verdict = "⚠️ MODERATE RISK - Monitor Closely"
        else: verdict = "✅ LOW RISK - Clean Health"
        
        return score, verdict, obs

    results = df.apply(get_detailed_analysis, axis=1)
    df['Forensic_Score'] = [x[0] for x in results]
    df['Verdict'] = [x[1] for x in results]
    df['Detailed_Report'] = [x[2] for x in results]
    
    return df, grouping_method

# ==========================================
# MODULE 1: QUANTITATIVE SCORECARD
# ==========================================
if app_mode == "1. Quantitative Forensic Scorecard":
    st.header("📊 Module 1: Quantitative Analysis")
    
    # Input Selection
    input_type = st.radio("Select Data Source:", ["✍️ Manual Entry (Small Sample)", "📁 Upload Excel (Batch Analysis)"], horizontal=True)
    
    df_in = None
    
    # --- OPTION A: MANUAL ENTRY ---
    if input_type == "✍️ Manual Entry (Small Sample)":
        st.info("Enter financial data manually below. Hover over columns for help.")
        template = {
            'Company': ['Vedanta', 'L&T'], 
            'Pledge_Pct': [99.0, 0.0], 
            'Sales': [12000.0, 4000.0], 
            'Receivables': [3500.0, 400.0],
            'Inventory': [1500.0, 300.0], 
            'CFO': [2000.0, 3500.0], 
            'EBITDA': [4000.0, 3800.0],
            'Total_Assets': [50000.0, 20000.0], 
            'Non_Current_Assets': [35000.0, 10000.0], 
            'RPT_Vol': [1200.0, 50.0]
        }
        
        df_in = st.data_editor(
            pd.DataFrame(template),
            num_rows="dynamic",
            use_container_width=True,
            column_config={
                "Company": st.column_config.TextColumn("Company", help="Name of the listed entity."),
                "Pledge_Pct": st.column_config.NumberColumn("Pledge %", help="Promoter Shareholding Encumbered (%)"),
                "Sales": st.column_config.NumberColumn("Sales", help="Revenue from Operations"),
                "CFO": st.column_config.NumberColumn("CFO", help="Net Cash from Operating Activities"),
                "EBITDA": st.column_config.NumberColumn("EBITDA", help="Operating Profit"),
                "RPT_Vol": st.column_config.NumberColumn("RPT Vol", help="Total Related Party Transactions Value")
            }
        )

    # --- OPTION B: EXCEL UPLOAD ---
    elif input_type == "📁 Upload Excel (Batch Analysis)":
        st.write("Upload your Excel file. The tool will auto-detect sample size and choose the grouping method.")
        up_file = st.file_uploader("Upload Excel/CSV", type=['xlsx', 'csv'])
        if up_file:
            if up_file.name.endswith('.csv'): df_in = pd.read_csv(up_file)
            else: df_in = pd.read_excel(up_file)
            req_cols = ['Company', 'Pledge_Pct', 'Sales', 'Receivables', 'CFO', 'EBITDA']
            if not all(c in df_in.columns for c in req_cols):
                st.error(f"Missing columns. Required: {req_cols}")
                df_in = None

    # --- RUN ANALYSIS ---
    if st.button("Run Forensic Analysis") and df_in is not None:
        res, method_used = calculate_risk(df_in)
        
        # A. Summary & Charts
        st.write("---")
        st.subheader(f"1. Sample Overview (Method: {method_used})")
        
        counts = res['Risk_Group'].value_counts()
        cols = st.columns(len(counts) + 1)
        cols[0].metric("Total Samples", len(res))
        
        sorted_groups = sorted(counts.index.tolist(), reverse=True)
        for i, grp in enumerate(sorted_groups):
            cols[i+1].metric(grp, counts[grp])

        st.subheader("2. Correlation Visualizer")
        color_map = {
            "🔴 Critical (>50%)": "#FF4B4B",
            "🟡 Moderate (10-50%)": "#FFA500", 
            "🟢 Safe (<10%)": "#00CC96",
            "🟢 Control (<50%)": "#00CC96"
        }
        fig = px.scatter(
            res, x="Pledge_Pct", y="DSO", color="Risk_Group",
            size="Sales", hover_name="Company", hover_data=["Forensic_Score"],
            color_discrete_map=color_map,
            title=f"Hypothesis Test: Does Pledging Increase DSO? (N={len(res)})"
        )
        fig.add_hline(y=120, line_dash="dash", annotation_text="Risk Threshold")
        st.plotly_chart(fig, use_container_width=True)

        # B. DETAILED DRILL DOWN (THE NEW FEATURE)
        st.write("---")
        st.subheader("3. 🔍 Detailed Interpretation & Verdicts")
        st.info("Select a company below to read the AI-generated forensic interpretation.")
        
        # Dropdown to pick a company
        selected_company = st.selectbox("Select Company for Deep Dive:", res['Company'].unique())
        
        # Filter data for that company
        comp_data = res[res['Company'] == selected_company].iloc[0]
        
        # Display the Narrative
        with st.container():
            st.markdown(f"### 🏢 **{comp_data['Company']}**")
            
            # 1. verdict Banner
            score = comp_data['Forensic_Score']
            if score > 50:
                st.error(f"**Final Verdict:** {comp_data['Verdict']} (Score: {score}/100)")
            else:
                st.success(f"**Final Verdict:** {comp_data['Verdict']} (Score: {score}/100)")
                
            # 2. Bullet Point Interpretation (The part you asked for)
            st.markdown("#### **📝 Interpretation of Results:**")
            if comp_data['Detailed_Report']:
                for line in comp_data['Detailed_Report']:
                    st.markdown(f"- {line}")
            else:
                st.markdown("- ✅ No critical anomalies detected in the quantitative data.")
                st.markdown("- ✅ Cash Quality and Working Capital cycles appear within healthy ranges.")
            
            # 3. Key Metrics
            k1, k2, k3, k4 = st.columns(4)
            k1.metric("Pledge %", f"{comp_data['Pledge_Pct']}%")
            k2.metric("DSO (Days)", comp_data['DSO'])
            k3.metric("Cash Quality", comp_data['Cash_Quality'])
            k4.metric("RPT Intensity", f"{comp_data['RPT_Intensity']}%")

        # C. Full Data Table (Plain, no color map to avoid error)
        with st.expander("View Raw Data Table"):
            st.dataframe(res)

# ==========================================
# MODULE 2: SINGLE PDF AUTO
# ==========================================
elif app_mode == "2. Single Company Auto-Analysis (PDF)":
    st.header("⚡ Single Company Deep Dive")
    pdf_file = st.file_uploader("Upload Annual Report", type=["pdf"])
    if pdf_file:
        with st.spinner("Scanning..."):
            text = extract_pdf_text(pdf_file)
            detected = {
                'Company': ['Detected Company'], 
                'Pledge_Pct': [find_value_in_text(text, ['Shares Pledged', 'Encumbered', 'Pledge'])],
                'Sales': [find_value_in_text(text, ['Revenue from Operations', 'Total Revenue'])],
                'Receivables': [find_value_in_text(text, ['Trade Receivables', 'Debtors'])],
                'Inventory': [find_value_in_text(text, ['Inventories', 'Stock-in-trade'])],
                'CFO': [find_value_in_text(text, ['Net Cash from Operating', 'Net cash generated'])],
                'EBITDA': [find_value_in_text(text, ['EBITDA', 'Operating Profit'])],
                'Total_Assets': [find_value_in_text(text, ['Total Assets'])],
                'Non_Current_Assets': [find_value_in_text(text, ['Non-current assets'])],
                'RPT_Vol': [find_value_in_text(text, ['Related Party', 'RPT'])]
            }
            verified_df = st.data_editor(pd.DataFrame(detected))
            if st.button("Analyze"):
                res, _ = calculate_risk(verified_df)
                row = res.iloc[0]
                
                st.write("---")
                # Verdict Banner
                score = row['Forensic_Score']
                if score > 50: st.error(f"**Verdict:** {row['Verdict']} (Score: {score})")
                else: st.success(f"**Verdict:** {row['Verdict']} (Score: {score})")
                
                # Detailed Interpretation
                st.markdown("#### **📝 Interpretation:**")
                if row['Detailed_Report']:
                    for line in row['Detailed_Report']: st.markdown(f"- {line}")
                else:
                    st.markdown("- ✅ Financials appear robust with no major red flags.")

# ==========================================
# MODULE 3: TEXT (Updated with Guidelines)
# ==========================================
elif app_mode == "3. Qualitative Sentiment Scanner":
    st.header("🧠 Qualitative Sentiment Scanner")
    
    st.info("💡 **What text should I paste here?**")
    st.markdown("""
    To get accurate results, do not paste financial tables. Paste text where management discusses the future or challenges.
    
    **Recommended Sources:**
    1. **Annual Report > Management Discussion & Analysis (MD&A):** Look for sub-sections titled *"Risks and Concerns"*, *"Threats"*, or *"Outlook"*.
    2. **Director's Report:** Look for the *"State of Company Affairs"* paragraph.
    3. **Earnings Call Transcripts:** Paste the CEO's opening remarks or answers to tough questions about debt.
    4. **Credit Rating Reports:** Paste the "Rationale" section from CRISIL/ICRA reports.
    """)
    
    txt = st.text_area("Paste Text Here", height=200, placeholder="Example: 'Despite the challenging market conditions and liquidity constraints...'")
    
    if st.button("Scan Text"):
        if len(txt) > 50:
            blob = TextBlob(txt)
            sent, subj = blob.sentiment.polarity, blob.sentiment.subjectivity
            
            st.write("---")
            st.subheader("📝 Textual Interpretation")
            
            # Logic for Interpretation
            interpretation = ""
            if subj > 0.5 and sent > 0.1:
                interpretation = "🔴 **The Pollyanna Effect:** Management is using highly **subjective (vague)** and **optimistic** language. In high-pledge firms, this often indicates an attempt to mask financial stress with 'fluff'."
            elif sent < -0.05:
                interpretation = "🟢 **Honest/Cautious:** The tone is negative or neutral, which typically suggests an honest disclosure of risks."
            else:
                interpretation = "🟡 **Neutral:** The language is balanced, neither suspiciously vague nor overly negative."
            
            st.markdown(f"**Analysis Verdict:** {interpretation}")
            
            c1, c2 = st.columns(2)
            c1.metric("Vagueness (Subjectivity)", f"{subj:.2f}", help=">0.5 is suspicious")
            c2.metric("Sentiment (Optimism)", f"{sent:.2f}")
        else:
            st.warning("Please paste at least 50 characters.")