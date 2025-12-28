import streamlit as st
import pandas as pd
import plotly.express as px
from textblob import TextBlob
import pdfplumber
import re
import requests
from bs4 import BeautifulSoup

# --- Page Config ---
st.set_page_config(page_title="Forensic Engine Ultimate", layout="wide")
st.title("🕵️‍♂️ Forensic Risk Engine: Auto-Adaptive")
st.markdown("**Methodology:** Adaptive grouping (Binary vs Traffic Light) with Auto-Column Detection.")

# --- Sidebar ---
with st.sidebar:
    st.header("⚙️ Control Panel")
    app_mode = st.selectbox("Select Module", [
        "1. Quantitative Forensic Scorecard",
        "2. Single Company Auto-Analysis (PDF)",
        "3. Qualitative Sentiment Scanner"
    ])
    st.info("ℹ️ **Smart Logic:**\n- **N < 30:** Tool uses 2 Groups (Binary).\n- **N ≥ 30:** Tool uses 3 Groups (Traffic Light).")
    
    st.write("---")
    st.markdown("### 🔧 Data Settings")
    # Manual Header Row Selector
    header_row_val = st.number_input("Header Row Number (in Excel)", min_value=1, value=1, step=1, help="If columns aren't detecting, try changing this to 2 or 3.") - 1

# --- Helper: Extract Text from PDF ---
def extract_pdf_text(uploaded_file):
    all_text = ""
    with pdfplumber.open(uploaded_file) as pdf:
        for page in pdf.pages[:50]:
            text = page.extract_text()
            if text: all_text += text + "\n"
    return all_text

# --- Helper: Extract Text from URL ---
def extract_url_text(url):
    try:
        response = requests.get(url, timeout=10)
        soup = BeautifulSoup(response.content, 'html.parser')
        # Extract text from paragraphs to avoid menus/footers
        paragraphs = soup.find_all('p')
        text = " ".join([p.get_text() for p in paragraphs])
        return text
    except Exception as e:
        return f"Error: {e}"

# --- Helper: Regex Search ---
def find_value_in_text(text, keywords):
    for keyword in keywords:
        pattern = re.compile(rf"{keyword}[:\s\-\|]+([\d,]+\.?\d*)", re.IGNORECASE)
        match = pattern.search(text)
        if match:
            try: return float(match.group(1).replace(',', ''))
            except: continue
    return 0.0

# --- Helper: Smart Column Mapper (Sheet-Smart Version) ---
def smart_map_columns(df):
    # 1. Clean the headers (Remove spaces, newlines, and convert to string)
    df.columns = df.columns.astype(str).str.strip().str.replace('\n', ' ')
    
    mapping_rules = {
        'Company': ['company', 'entity', 'name', 'firm'],
        'Pledge_Pct': ['pledge', 'encumbered', 'promoter pledge', 'pledged'],
        'Sales': ['sales', 'revenue', 'turnover', 'income', 'top line'],
        'Receivables': ['receivables', 'debtors', 'trade receivables', 'accounts receivable'],
        'Inventory': ['inventory', 'stock', 'inventories'],
        'CFO': ['cfo', 'cf operations', 'operating cash', 'cash from operations', 'cash flow from operating'],
        'EBITDA': ['ebitda', 'operating profit', 'pbit', 'profit before interest', 'opm'],
        'Total_Assets': ['total assets', 'balance sheet total', 'assets'],
        'Non_Current_Assets': ['non current assets', 'fixed assets', 'long term assets'],
        'RPT_Vol': ['rpt', 'related party', 'related transaction']
    }
    
    new_columns = {}
    
    st.write("---")
    st.markdown("### 🧬 Auto-Column Detection")
    st.caption("Scanning headers... If incorrect, select manually below.")
    
    cols_ui = st.columns(3)
    
    for i, (standard_name, variations) in enumerate(mapping_rules.items()):
        match_found = None
        
        # Smart Search: Case-insensitive partial match
        for col in df.columns:
            if any(v in col.lower() for v in variations):
                match_found = col
                break
        
        # Fallback exact match
        if not match_found and standard_name in df.columns:
            match_found = standard_name
            
        with cols_ui[i % 3]:
            # Show the dropdown
            selected = st.selectbox(
                f"Map to '{standard_name}'", 
                options=["(Select Column)"] + list(df.columns),
                index=list(df.columns).index(match_found) + 1 if match_found else 0,
                key=f"map_{standard_name}"
            )
            
            if selected != "(Select Column)":
                new_columns[selected] = standard_name

    if new_columns:
        df_mapped = df.rename(columns=new_columns)
        # Ensure missing columns are added as 0 to prevent crashes
        for req in mapping_rules.keys():
            if req not in df_mapped.columns:
                df_mapped[req] = 0
        return df_mapped
    return df

# --- Helper: Adaptive Risk Calculation ---
def calculate_risk(df):
    cols = ['Sales', 'Receivables', 'Inventory', 'CFO', 'EBITDA', 'Pledge_Pct', 'Total_Assets', 'Non_Current_Assets', 'RPT_Vol']
    for c in cols:
        df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0)

    df['DSO'] = df.apply(lambda x: (x['Receivables'] / x['Sales'] * 365) if x['Sales'] > 0 else 0, axis=1).round(1)
    df['Cash_Quality'] = df.apply(lambda x: (x['CFO'] / x['EBITDA']) if x['EBITDA'] > 0 else 0, axis=1).round(2)
    df['AQI'] = df.apply(lambda x: (x['Non_Current_Assets'] / x['Total_Assets']) if x['Total_Assets'] > 0 else 0, axis=1).round(2)
    df['RPT_Intensity'] = df.apply(lambda x: (x['RPT_Vol'] / x['Sales'] * 100) if x['Sales'] > 0 else 0, axis=1).round(1)

    sample_size = len(df)
    if sample_size < 30:
        df['Risk_Group'] = df['Pledge_Pct'].apply(lambda x: "🔴 Critical (>50%)" if x > 50 else "🟢 Control (<50%)")
        grouping_method = "Binary (Small Sample Protocol)"
    else:
        def get_3_buckets(p):
            if p > 50: return "🔴 Critical (>50%)"
            elif p >= 10: return "🟡 Moderate (10-50%)"
            else: return "🟢 Safe (<10%)"
        df['Risk_Group'] = df['Pledge_Pct'].apply(get_3_buckets)
        grouping_method = "Traffic Light (Large Sample Protocol)"

    def get_detailed_analysis(row):
        score = 0
        obs = []
        verdict = "Low Risk"
        
        if row['Pledge_Pct'] > 50:
            score += 25
            obs.append(f"🔴 **Critical Pledge Pressure:** {row['Pledge_Pct']}% of shares are pledged.")
        elif row['Pledge_Pct'] > 20:
            score += 10
            obs.append(f"🟠 **Moderate Pledge:** {row['Pledge_Pct']}% pledged.")

        if row['Cash_Quality'] < 0.5:
            score += 30
            obs.append(f"🔴 **Fake Profit Alert:** Cash Quality is {row['Cash_Quality']}.")
        elif row['Cash_Quality'] < 0.8:
            score += 15
            obs.append(f"🟠 **Weak Cash Flow:** Cash conversion (CFO/EBITDA) is low.")

        if row['DSO'] > 120:
            score += 20
            obs.append(f"🔴 **Aggressive Revenue:** Sales take {row['DSO']} days to collect.")
        if row['RPT_Intensity'] > 10:
            score += 10
            obs.append(f"⚠️ **Leakage Risk:** {row['RPT_Intensity']}% sales with Related Parties.")

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
    
    input_type = st.radio("Select Data Source:", ["✍️ Manual Entry (Small Sample)", "📁 Upload Excel (Batch Analysis)"], horizontal=True)
    
    df_in = None
    
    if input_type == "✍️ Manual Entry (Small Sample)":
        st.info("Enter financial data manually below.")
        template = {
            'Company': ['Vedanta', 'L&T', 'Adani Ent', 'Tata Steel', 'Reliance'], 
            'Pledge_Pct': [99.0, 0.0, 25.0, 0.0, 0.0], 
            'Sales': [12000.0, 4000.0, 8000.0, 15000.0, 20000.0], 
            'Receivables': [3500.0, 400.0, 1200.0, 900.0, 1500.0],
            'Inventory': [1500.0, 300.0, 800.0, 2000.0, 2500.0], 
            'CFO': [2000.0, 3500.0, 500.0, 3000.0, 18000.0], 
            'EBITDA': [4000.0, 3800.0, 1500.0, 4500.0, 22000.0],
            'Total_Assets': [50000.0, 20000.0, 35000.0, 60000.0, 100000.0], 
            'Non_Current_Assets': [35000.0, 10000.0, 25000.0, 40000.0, 70000.0], 
            'RPT_Vol': [1200.0, 50.0, 500.0, 100.0, 200.0]
        }
        df_in = st.data_editor(pd.DataFrame(template), num_rows="dynamic", use_container_width=True)

    elif input_type == "📁 Upload Excel (Batch Analysis)":
        up_file = st.file_uploader("Upload Excel/CSV", type=['xlsx', 'csv'])
        
        if up_file:
            try:
                # --- NEW LOGIC: FIND THE RIGHT SHEET AUTOMATICALLY ---
                if up_file.name.endswith('.csv'):
                    raw_df = pd.read_csv(up_file, header=header_row_val)
                else:
                    # 1. Load the Excel file wrapper
                    xls = pd.ExcelFile(up_file)
                    target_sheet = None
                    
                    # 2. Iterate through ALL sheets to find the one with data
                    for sheet in xls.sheet_names:
                        df_check = pd.read_excel(xls, sheet_name=sheet, nrows=5, header=header_row_val)
                        # Check if this sheet has "Sales" or "Name" or "Pledge" columns
                        cols_lower = [str(c).lower() for c in df_check.columns]
                        if any('sales' in c for c in cols_lower) or any('pledge' in c for c in cols_lower) or any('company' in c for c in cols_lower):
                            target_sheet = sheet
                            break
                    
                    if target_sheet:
                        st.success(f"✅ Data detected in Sheet: '{target_sheet}' (Using Header Row {header_row_val + 1})")
                        raw_df = pd.read_excel(xls, sheet_name=target_sheet, header=header_row_val)
                    else:
                        st.warning("⚠️ Could not auto-detect data sheet. Loading the first sheet by default.")
                        raw_df = pd.read_excel(xls, sheet_name=0, header=header_row_val)

                # Run mapping
                df_in = smart_map_columns(raw_df)
                
            except Exception as e:
                st.error(f"❌ Error loading file: {e}")

    # --- SESSION STATE PERSISTENCE ---
    if st.button("Run Forensic Analysis"):
        if df_in is not None:
            res, method_used = calculate_risk(df_in)
            # Store results in Session State
            st.session_state['results'] = res
            st.session_state['method'] = method_used
            st.session_state['data_loaded'] = True
        else:
            st.error("Please provide valid data.")

    # --- DISPLAY RESULTS IF DATA IS LOADED ---
    if st.session_state.get('data_loaded'):
        res = st.session_state['results']
        method_used = st.session_state['method']
        
        st.write("---")
        st.subheader(f"1. Sample Overview (Method: {method_used})")
        
        counts = res['Risk_Group'].value_counts()
        cols = st.columns(len(counts) + 1)
        cols[0].metric("Total Samples", len(res))
        
        sorted_groups = sorted(counts.index.tolist(), reverse=True)
        for i, grp in enumerate(sorted_groups):
            cols[i+1].metric(grp, counts[grp])

        # --- NEW VISUALIZATION SECTION (TABS) ---
        st.write("---")
        st.subheader("2. Hypothesis Testing (Visualizer)")
        
        color_map = {
            "🔴 Critical (>50%)": "#FF4B4B",
            "🟡 Moderate (10-50%)": "#FFA500", 
            "🟢 Safe (<10%)": "#00CC96",
            "🟢 Control (<50%)": "#00CC96"
        }

        # Create Tabs for easier navigation
        tab1, tab2, tab3, tab4 = st.tabs(["⚪ Scatter Plot", "📦 Box Plot", "📊 Bar Chart", "📍 Strip Plot"])

        with tab1:
            st.markdown("**Scatter Plot:** Shows correlation between Pledge % and DSO.")
            fig1 = px.scatter(
                res, x="Pledge_Pct", y="DSO", color="Risk_Group",
                size="Sales", hover_name="Company", hover_data=["Forensic_Score"],
                color_discrete_map=color_map,
                title=f"Hypothesis Test: Pledge vs DSO (N={len(res)})"
            )
            fig1.add_hline(y=120, line_dash="dash", line_color="red", annotation_text="High Risk (120 Days)")
            st.plotly_chart(fig1, use_container_width=True)

        with tab2:
            st.markdown("**Box Plot:** Shows the spread and outliers in each risk group.")
            fig2 = px.box(
                res, x="Risk_Group", y="DSO", color="Risk_Group",
                color_discrete_map=color_map,
                points="all", 
                title="Distribution of DSO across Risk Groups",
                hover_data=["Company", "Sales"]
            )
            fig2.add_hline(y=120, line_dash="dash", line_color="red")
            st.plotly_chart(fig2, use_container_width=True)

        with tab3:
            st.markdown("**Bar Chart:** Shows the simple average DSO for each group.")
            avg_df = res.groupby("Risk_Group")['DSO'].mean().reset_index()
            fig3 = px.bar(
                avg_df, x="Risk_Group", y="DSO", color="Risk_Group",
                color_discrete_map=color_map,
                text_auto=True,
                title="Average DSO by Risk Group"
            )
            fig3.update_layout(yaxis_title="Average Days Sales Outstanding")
            fig3.add_hline(y=120, line_dash="dash", line_color="red")
            st.plotly_chart(fig3, use_container_width=True)
            
        with tab4:
            st.markdown("**Strip Plot:** Shows individual companies in vertical lanes.")
            fig4 = px.strip(
                res, x="Risk_Group", y="DSO", color="Risk_Group",
                color_discrete_map=color_map,
                hover_name="Company",
                title="Individual Company Risk Position (Jittered)",
                stripmode='overlay'
            )
            fig4.add_hline(y=120, line_dash="dash", line_color="red")
            st.plotly_chart(fig4, use_container_width=True)

        # B. DETAILED DRILL DOWN
        st.write("---")
        st.subheader("3. 🔍 Detailed Interpretation & Verdicts")
        st.info("Select a company below to read the AI-generated forensic interpretation.")
        
        # --- DROPDOWN LOGIC FIXED ---
        company_list = res['Company'].unique()
        selected_company = st.selectbox("Select Company for Deep Dive:", company_list)
        
        # Get data for selected company
        comp_data = res[res['Company'] == selected_company].iloc[0]
        
        with st.container():
            st.markdown(f"### 🏢 **{comp_data['Company']}**")
            
            score = comp_data['Forensic_Score']
            if score > 50:
                st.error(f"**Final Verdict:** {comp_data['Verdict']} (Score: {score}/100)")
            else:
                st.success(f"**Final Verdict:** {comp_data['Verdict']} (Score: {score}/100)")
                
            st.markdown("#### **📝 Interpretation of Results:**")
            if comp_data['Detailed_Report']:
                for line in comp_data['Detailed_Report']:
                    st.markdown(f"- {line}")
            else:
                st.markdown("- ✅ No critical anomalies detected in the quantitative data.")
                st.markdown("- ✅ Cash Quality and Working Capital cycles appear within healthy ranges.")
            
            k1, k2, k3, k4 = st.columns(4)
            k1.metric("Pledge %", f"{comp_data['Pledge_Pct']}%")
            k2.metric("DSO (Days)", comp_data['DSO'])
            k3.metric("Cash Quality", comp_data['Cash_Quality'])
            k4.metric("RPT Intensity", f"{comp_data['RPT_Intensity']}%")

        with st.expander("View Raw Data Table"):
            st.dataframe(res)

# ==========================================
# MODULE 2: PDF SCANNER
# ==========================================
elif app_mode == "2. Single Company Auto-Analysis (PDF)":
    st.header("⚡ Single Company Deep Dive")
    pdf_file = st.file_uploader("Upload Annual Report", type=["pdf"])
    if pdf_file:
        with st.spinner("Scanning..."):
            text = extract_pdf_text(pdf_file)
            st.success("PDF Scanned Successfully!")
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
            if st.button("Analyze PDF Data"):
                res, _ = calculate_risk(verified_df)
                row = res.iloc[0]
                st.write("---")
                score = row['Forensic_Score']
                if score > 50: st.error(f"**Verdict:** {row['Verdict']} (Score: {score})")
                else: st.success(f"**Verdict:** {row['Verdict']} (Score: {score})")
                
                st.markdown("#### **📝 Interpretation:**")
                if row['Detailed_Report']:
                    for line in row['Detailed_Report']: st.markdown(f"- {line}")
                else:
                    st.markdown("- ✅ Financials appear robust with no major red flags.")

# ==========================================
# MODULE 3: SENTIMENT SCANNER (UPDATED)
# ==========================================
elif app_mode == "3. Qualitative Sentiment Scanner":
    st.header("🧠 Qualitative Sentiment Scanner")
    st.info("Analyze the 'Tone' of Management Disclosures.")
    
    # 1. Input Method Toggle
    input_method = st.radio("Choose Input Method:", ["📝 Paste Text", "🌐 Paste URL"], horizontal=True)
    
    user_text = ""
    
    if input_method == "📝 Paste Text":
        user_text = st.text_area("Paste MD&A / Director's Report here:", height=200, placeholder="e.g. 'Despite headwinds, we remain optimistic...'")
        
    elif input_method == "🌐 Paste URL":
        url = st.text_input("Enter URL (News Article / Blog / Report):", placeholder="https://finance.yahoo.com/news/...")
        if url:
            if st.button("Fetch Text from URL"):
                with st.spinner("Scraping text..."):
                    user_text = extract_url_text(url)
                    if "Error" in user_text:
                        st.error(user_text)
                    else:
                        st.success("Text Fetched Successfully!")
                        with st.expander("View Fetched Text"):
                            st.write(user_text[:1000] + "...")

    # 2. Analysis Logic
    if st.button("Run Sentiment Analysis"):
        if len(user_text) > 50:
            blob = TextBlob(user_text)
            sent = blob.sentiment.polarity       # -1 to +1
            subj = blob.sentiment.subjectivity   # 0 to 1
            
            st.write("---")
            st.subheader("📝 Forensic Interpretation")
            
            # Robust Verdict Logic
            col1, col2 = st.columns(2)
            col1.metric("Positivity (Sentiment)", f"{sent:.2f}", help="-1 (Negative) to +1 (Positive)")
            col2.metric("Vagueness (Subjectivity)", f"{subj:.2f}", help="0 (Fact) to 1 (Opinion)")
            
            st.markdown("### **💡 AI Verdict:**")
            
            # Quadrant Analysis
            if subj > 0.5 and sent > 0.2:
                st.error("🔴 **Verdict: The Pollyanna Effect (High Risk)**")
                st.markdown("Management is using **highly vague** and **excessively optimistic** language. This is a classic sign of 'Sugarcoating' to hide poor performance.")
            
            elif subj > 0.5 and sent < -0.2:
                st.warning("🟠 **Verdict: Panicked Obfuscation (Moderate Risk)**")
                st.markdown("The text is negative and highly subjective. Management sounds emotional or defensive rather than sticking to hard facts.")
                
            elif subj < 0.4 and sent > 0.2:
                st.success("🟢 **Verdict: Strong & Objective (Low Risk)**")
                st.markdown("The optimism is grounded in low subjectivity. This suggests the good news is backed by facts/numbers.")
                
            elif subj < 0.4 and sent < -0.2:
                st.info("🔵 **Verdict: Honest Distress (Safe Narrative)**")
                st.markdown("The management is delivering bad news straightforwardly without trying to sugarcoat it. This indicates honesty.")
            
            else:
                st.info("⚪ **Verdict: Neutral / Balanced**")
                st.markdown("The text contains a standard mix of facts and opinions.")

        else:
            if input_method == "🌐 Paste URL" and not url:
                st.warning("Please enter a URL first.")
            elif input_method == "🌐 Paste URL" and url and not user_text:
                st.warning("Please click 'Fetch Text from URL' first.")
            else:
                st.warning("Please provide at least 50 characters of text for analysis.")
