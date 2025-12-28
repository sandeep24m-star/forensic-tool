import streamlit as st
import pandas as pd
import plotly.express as px
from textblob import TextBlob
import pdfplumber
import re
import requests
from bs4 import BeautifulSoup
import io
import openai
import json

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
    
    st.write("---")
    st.markdown("### 🧠 GenAI Settings (Module 2)")
    openai_api_key = st.text_input("OpenAI API Key (Optional)", type="password", help="Paste your key here for Smart Extraction. If empty, tool uses Advanced Regex.")
    
    st.write("---")
    st.markdown("### 🔧 Data Settings")
    header_row_val = st.number_input("Header Row Number (in Excel)", min_value=1, value=1, step=1) - 1

# --- Helper: Extract Text from PDF Upload ---
def extract_pdf_text(uploaded_file):
    all_text = ""
    with pdfplumber.open(uploaded_file) as pdf:
        # Scan first 25 pages (usually enough for Financial Highlights)
        for page in pdf.pages[:25]:
            text = page.extract_text()
            if text: all_text += text + "\n"
    return all_text

# --- Helper: GPT EXTRACTION (SMART AI) ---
def extract_data_with_gpt(text, api_key):
    client = openai.OpenAI(api_key=api_key)
    # Truncate to save tokens (First 15k chars is usually MD&A + Tables)
    truncated_text = text[:15000]
    
    prompt = f"""
    You are a Forensic Accounting AI. Extract specific consolidated financial figures from the text below for the LATEST available year.
    Return ONLY a JSON object. No markdown, no explanations.
    
    Fields to Extract:
    1. Sales (Revenue from Operations)
    2. EBITDA (Operating Profit)
    3. CFO (Net Cash from Operating Activities)
    4. Receivables (Trade Receivables)
    5. Inventory
    6. Total_Assets
    7. Non_Current_Assets
    8. Pledge_Pct (Promoter Shares Pledged %) - Default to 0 if not found.
    9. RPT_Vol (Total Related Party Transactions Value) - Default to 0 if not found.
    
    Text Dump:
    {truncated_text}
    
    Output Format (JSON):
    {{
        "Company": "Extracted Name",
        "Sales": 0.0,
        "EBITDA": 0.0,
        "CFO": 0.0,
        "Receivables": 0.0,
        "Inventory": 0.0,
        "Total_Assets": 0.0,
        "Non_Current_Assets": 0.0,
        "Pledge_Pct": 0.0,
        "RPT_Vol": 0.0
    }}
    """
    
    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo", 
            messages=[
                {"role": "system", "content": "You are a helpful financial assistant. Output strict JSON."},
                {"role": "user", "content": prompt}
            ],
            temperature=0
        )
        content = response.choices[0].message.content
        # Clean any markdown backticks if GPT adds them
        content = content.replace("```json", "").replace("```", "")
        return json.loads(content)
    except Exception as e:
        return {"Error": str(e)}

# --- Helper: ROBUST REGEX FINDER (V4 FALLBACK) ---
def find_value_regex(text, keywords):
    lines = text.split('\n')
    candidates = []
    
    for keyword in keywords:
        for i, line in enumerate(lines):
            if keyword.lower() in line.lower():
                # Look at this line AND the next line
                search_text = line
                if i + 1 < len(lines): search_text += " " + lines[i+1]
                
                # Find numbers (e.g. 50,000.00 or 500)
                numbers = re.findall(r'(?<!Note\s)(?<!\d)[\d,]+\.\d{2}|(?<!Note\s)(?<!\d)[\d,]{3,}', search_text)
                
                for num_str in numbers:
                    try:
                        val = float(num_str.replace(',', ''))
                        # Filter out Years and Note Numbers
                        if val > 100 and val not in [2022, 2023, 2024, 2025]:
                            candidates.append(val)
                    except: continue
                    
    if candidates: return max(candidates)
    return 0.0

# --- Helper: Risk Logic ---
def calculate_risk(df):
    cols = ['Sales', 'Receivables', 'Inventory', 'CFO', 'EBITDA', 'Pledge_Pct', 'Total_Assets', 'Non_Current_Assets', 'RPT_Vol']
    for c in cols: df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0)
    
    df['DSO'] = df.apply(lambda x: (x['Receivables']/x['Sales']*365) if x['Sales']>0 else 0, axis=1).round(1)
    df['Cash_Quality'] = df.apply(lambda x: (x['CFO']/x['EBITDA']) if x['EBITDA']>0 else 0, axis=1).round(2)
    df['RPT_Intensity'] = df.apply(lambda x: (x['RPT_Vol']/x['Sales']*100) if x['Sales']>0 else 0, axis=1).round(1)
    
    df['Risk_Group'] = df['Pledge_Pct'].apply(lambda x: "🔴 Critical" if x>50 else "🟢 Safe")

    def analyze(row):
        score, obs = 0, []
        verdict = "Low Risk"
        if row['Pledge_Pct'] > 50: score += 25; obs.append(f"🔴 Critical Pledge: {row['Pledge_Pct']}%")
        if row['DSO'] > 120: score += 20; obs.append(f"🔴 Aggressive Sales (DSO {row['DSO']})")
        if row['Cash_Quality'] < 0.8: score += 15; obs.append(f"🟠 Weak Cash Flow ({row['Cash_Quality']})")
        
        if score >= 50: verdict = "🚨 HIGH RISK"
        elif score >= 20: verdict = "⚠️ MODERATE RISK"
        else: verdict = "✅ LOW RISK"
        return score, verdict, obs
    
    res = df.apply(analyze, axis=1)
    df['Forensic_Score'] = [x[0] for x in res]
    df['Verdict'] = [x[1] for x in res]
    df['Detailed_Report'] = [x[2] for x in res]
    return df, "Standard"

# --- Helper: Extract URL Text (For Module 3) ---
def extract_url_text(url):
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(response.content, 'html.parser')
        for el in soup(['script', 'style', 'nav', 'footer']): el.decompose()
        content = soup.find('main') or soup.body
        if content:
            text = content.get_text(separator=' ', strip=True)
            return text if len(text) > 100 else "⚠️ Text too short."
        return "⚠️ No content found."
    except Exception as e: return f"⚠️ Error: {e}"

# --- Helper: Smart Column Mapper (For Module 1) ---
def smart_map_columns(df):
    df.columns = df.columns.astype(str).str.strip().str.replace('\n', ' ')
    mapping_rules = {
        'Company': ['company', 'entity', 'name'],
        'Pledge_Pct': ['pledge', 'encumbered'],
        'Sales': ['sales', 'revenue', 'turnover'],
        'Receivables': ['receivables', 'debtors'],
        'Inventory': ['inventory', 'stock'],
        'CFO': ['cfo', 'operating cash'],
        'EBITDA': ['ebitda', 'operating profit'],
        'Total_Assets': ['total assets', 'balance sheet total'],
        'Non_Current_Assets': ['non current assets', 'fixed assets'],
        'RPT_Vol': ['rpt', 'related party']
    }
    new_cols = {}
    st.write("---")
    st.markdown("### 🧬 Auto-Column Detection")
    cols_ui = st.columns(3)
    for i, (std, vars_) in enumerate(mapping_rules.items()):
        match = None
        for col in df.columns:
            if any(v in col.lower() for v in vars_): match = col; break
        if not match and std in df.columns: match = std
        with cols_ui[i % 3]:
            sel = st.selectbox(f"Map '{std}'", ["(Select)"] + list(df.columns), index=list(df.columns).index(match) + 1 if match else 0, key=f"map_{std}")
            if sel != "(Select)": new_cols[sel] = std
    if new_cols:
        df = df.rename(columns=new_cols)
        for req in mapping_rules: 
            if req not in df.columns: df[req] = 0
    return df


# ==========================================
# MODULE 1: QUANTITATIVE SCORECARD
# ==========================================
if app_mode == "1. Quantitative Forensic Scorecard":
    st.header("📊 Module 1: Quantitative Analysis")
    input_type = st.radio("Select Data Source:", ["✍️ Manual Entry (Small Sample)", "📁 Upload Excel (Batch Analysis)"], horizontal=True)
    df_in = None
    
    if input_type == "✍️ Manual Entry (Small Sample)":
        st.info("Enter financial data manually below.")
        template = { 'Company': ['Vedanta', 'L&T', 'Adani Ent', 'Tata Steel', 'Reliance'], 'Pledge_Pct': [99.0, 0.0, 25.0, 0.0, 0.0], 'Sales': [12000.0, 4000.0, 8000.0, 15000.0, 20000.0], 'Receivables': [3500.0, 400.0, 1200.0, 900.0, 1500.0], 'Inventory': [1500.0, 300.0, 800.0, 2000.0, 2500.0], 'CFO': [2000.0, 3500.0, 500.0, 3000.0, 18000.0], 'EBITDA': [4000.0, 3800.0, 1500.0, 4500.0, 22000.0], 'Total_Assets': [50000.0, 20000.0, 35000.0, 60000.0, 100000.0], 'Non_Current_Assets': [35000.0, 10000.0, 25000.0, 40000.0, 70000.0], 'RPT_Vol': [1200.0, 50.0, 500.0, 100.0, 200.0] }
        df_in = st.data_editor(pd.DataFrame(template), num_rows="dynamic", use_container_width=True)
    
    elif input_type == "📁 Upload Excel (Batch Analysis)":
        up_file = st.file_uploader("Upload Excel/CSV", type=['xlsx', 'csv'])
        if up_file:
            try:
                if up_file.name.endswith('.csv'): raw_df = pd.read_csv(up_file, header=header_row_val)
                else:
                    xls = pd.ExcelFile(up_file)
                    raw_df = pd.read_excel(xls, sheet_name=0, header=header_row_val)
                df_in = smart_map_columns(raw_df)
            except Exception as e: st.error(f"❌ Error: {e}")

    if st.button("Run Forensic Analysis"):
        if df_in is not None:
            res, _ = calculate_risk(df_in)
            st.write("---")
            st.subheader("Results Overview")
            st.dataframe(res)
            
            # Simple Chart
            fig = px.scatter(res, x="Pledge_Pct", y="DSO", color="Risk_Group", size="Sales", title="Pledge vs DSO")
            fig.add_hline(y=120, line_dash="dash", line_color="red")
            st.plotly_chart(fig, use_container_width=True)
            
        else: st.error("Please provide data.")

# ==========================================
# MODULE 2: PDF SCANNER (GenAI + Regex Hybrid)
# ==========================================
elif app_mode == "2. Single Company Auto-Analysis (PDF)":
    st.header("⚡ Single Company Deep Dive (AI Powered)")
    
    if not openai_api_key:
        st.warning("⚠️ **Rule-Based Mode:** Using V4 Regex (Free). For higher accuracy, enter OpenAI API Key in Sidebar.")
    else:
        st.success("🟢 **GenAI Mode Active:** Using GPT-3.5 for Semantic Extraction.")

    pdf_file = st.file_uploader("Upload Annual Report", type=["pdf"])
    
    if pdf_file:
        with st.spinner("Analyzing PDF..."):
            text = extract_pdf_text(pdf_file)
            extracted_data = {}
            
            # --- HYBRID LOGIC ---
            if openai_api_key:
                # 1. Try GenAI
                try:
                    gpt_response = extract_data_with_gpt(text, openai_api_key)
                    if "Error" in gpt_response:
                        st.error(f"OpenAI Error: {gpt_response['Error']}")
                        st.stop()
                    # Format for DataFrame
                    for k, v in gpt_response.items(): extracted_data[k] = [v]
                except Exception as e:
                    st.error(f"AI Failed: {e}")
            else:
                # 2. Fallback to Robust V4 Regex
                detected = {
                    'Company': ['Detected Company'], 
                    'Pledge_Pct': [find_value_regex(text, ['Shares Pledged', 'Encumbered', 'Promoter Pledge'])],
                    'Sales': [find_value_regex(text, ['Revenue from Operations', 'Total Income', 'Turnover'])],
                    'Receivables': [find_value_regex(text, ['Trade Receivables', 'Debtors'])],
                    'Inventory': [find_value_regex(text, ['Inventories', 'Stock-in-trade'])],
                    'CFO': [find_value_regex(text, ['Net Cash from Operating'])],
                    'EBITDA': [find_value_regex(text, ['EBITDA', 'Operating Profit'])],
                    'Total_Assets': [find_value_regex(text, ['Total Assets', 'Total Equity'])],
                    'Non_Current_Assets': [find_value_regex(text, ['Non-current assets'])],
                    'RPT_Vol': [find_value_regex(text, ['Related Party', 'RPT'])]
                }
                extracted_data = detected

            st.success("Extraction Complete! Verify values below.")
            verified_df = st.data_editor(pd.DataFrame(extracted_data))
            
            if st.button("Analyze Data"):
                res, _ = calculate_risk(verified_df)
                row = res.iloc[0]
                st.write("---")
                score = row['Forensic_Score']
                if score > 50: st.error(f"**Verdict:** {row['Verdict']} (Score: {score})")
                else: st.success(f"**Verdict:** {row['Verdict']} (Score: {score})")
                st.markdown("#### **📝 Interpretation:**")
                if row['Detailed_Report']:
                    for line in row['Detailed_Report']: st.markdown(f"- {line}")
                else: st.markdown("- ✅ Financials appear robust.")

# ==========================================
# MODULE 3: SENTIMENT SCANNER (RESTORED)
# ==========================================
elif app_mode == "3. Qualitative Sentiment Scanner":
    st.header("🧠 Qualitative Sentiment Scanner")
    if 'sentiment_text' not in st.session_state: st.session_state['sentiment_text'] = ""
    
    input_method = st.radio("Input:", ["Paste Text", "Paste URL"], horizontal=True)
    
    if input_method == "Paste Text":
        val = st.text_area("Text:", value=st.session_state['sentiment_text'], height=200)
        if val: st.session_state['sentiment_text'] = val
        
    elif input_method == "Paste URL":
        url = st.text_input("URL:")
        if st.button("Fetch"):
            txt = extract_url_text(url)
            st.session_state['sentiment_text'] = txt
            st.success("Fetched!")
            
    if st.button("Run Analysis"):
        txt = st.session_state['sentiment_text']
        if len(txt) > 50:
            blob = TextBlob(txt)
            sent = blob.sentiment.polarity
            subj = blob.sentiment.subjectivity
            st.write("---")
            col1, col2 = st.columns(2)
            col1.metric("Positivity", f"{sent:.2f}")
            col2.metric("Subjectivity", f"{subj:.2f}")
            if subj > 0.5 and sent > 0.2: st.error("🔴 Pollyanna Effect Detected!")
            else: st.success("🔵 Tone seems Objective.")
        else: st.warning("Please provide text.")
