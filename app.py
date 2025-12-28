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
    # Securely ask for API Key
    openai_api_key = st.text_input("OpenAI API Key (Optional)", type="password", help="Paste your key here for Smart Extraction. If empty, tool uses Basic Regex.")
    
    st.write("---")
    st.markdown("### 🔧 Data Settings")
    header_row_val = st.number_input("Header Row Number (in Excel)", min_value=1, value=1, step=1) - 1

# --- Helper: Extract Text from PDF Upload ---
def extract_pdf_text(uploaded_file):
    all_text = ""
    with pdfplumber.open(uploaded_file) as pdf:
        # Scan first 20 pages (usually enough for Financial Highlights)
        for page in pdf.pages[:20]:
            text = page.extract_text()
            if text: all_text += text + "\n"
    return all_text

# --- Helper: GPT EXTRACTION (THE NEW AI POWER) ---
def extract_data_with_gpt(text, api_key):
    client = openai.OpenAI(api_key=api_key)
    
    # We truncate text to 15,000 chars to fit in context window and save cost
    truncated_text = text[:15000]
    
    prompt = f"""
    You are a Forensic Accounting AI. Extract the following specific financial figures from the provided Annual Report text.
    Return the output strictly as a JSON object. Do not add markdown formatting.
    
    Fields to Extract (Find the Consolidated figures for the latest available year):
    1. Sales (Revenue from Operations)
    2. EBITDA (Operating Profit)
    3. CFO (Net Cash from Operating Activities)
    4. Receivables (Trade Receivables)
    5. Inventory
    6. Total_Assets
    7. Non_Current_Assets
    8. Pledge_Pct (Promoter Shares Pledged %) - If not found, return 0.
    9. RPT_Vol (Total Related Party Transactions Value) - If not found, return 0.
    
    Text Data:
    {truncated_text}
    
    JSON Format:
    {{
        "Company": "Name",
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
            model="gpt-3.5-turbo", # Or "gpt-4" for better results
            messages=[
                {"role": "system", "content": "You are a helpful financial assistant. Output only JSON."},
                {"role": "user", "content": prompt}
            ],
            temperature=0
        )
        content = response.choices[0].message.content
        return json.loads(content)
    except Exception as e:
        return {"Error": str(e)}

# --- Helper: OLD REGEX FINDER (FALLBACK) ---
def find_value_regex(text, keywords):
    lines = text.split('\n')
    candidates = []
    for keyword in keywords:
        for i, line in enumerate(lines):
            if keyword.lower() in line.lower():
                search_text = line
                if i + 1 < len(lines): search_text += " " + lines[i+1]
                numbers = re.findall(r'(?<!Note\s)(?<!\d)[\d,]+\.\d{2}|(?<!Note\s)(?<!\d)[\d,]{3,}', search_text)
                for num_str in numbers:
                    try:
                        val = float(num_str.replace(',', ''))
                        if val > 100 and val not in [2022, 2023, 2024, 2025]: candidates.append(val)
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

# ==========================================
# MODULE 1: QUANTITATIVE SCORECARD
# ==========================================
if app_mode == "1. Quantitative Forensic Scorecard":
    st.header("📊 Module 1: Quantitative Analysis")
    st.info("Batch Analysis Module (Please go to Module 2 for GenAI PDF Scanning).")

# ==========================================
# MODULE 2: PDF SCANNER (GenAI Powered)
# ==========================================
elif app_mode == "2. Single Company Auto-Analysis (PDF)":
    st.header("⚡ Single Company Deep Dive (AI Powered)")
    
    if not openai_api_key:
        st.warning("⚠️ **No API Key detected.** Using Basic Regex Mode (Low Accuracy). To unlock Smart AI Mode, enter OpenAI Key in Sidebar.")
    else:
        st.success("🟢 **GenAI Mode Active:** Using GPT-3.5 for Smart Extraction.")

    pdf_file = st.file_uploader("Upload Annual Report", type=["pdf"])
    
    if pdf_file:
        with st.spinner("Extracting Text & Analyzing..."):
            text = extract_pdf_text(pdf_file)
            
            extracted_data = {}
            
            # --- BRANCH: GEN AI vs REGEX ---
            if openai_api_key:
                # 1. Use GPT
                try:
                    gpt_response = extract_data_with_gpt(text, openai_api_key)
                    if "Error" in gpt_response:
                        st.error(f"OpenAI Error: {gpt_response['Error']}")
                        st.stop()
                    
                    # Convert JSON to Lists for DataFrame
                    for k, v in gpt_response.items():
                        extracted_data[k] = [v]
                        
                except Exception as e:
                    st.error(f"AI Extraction Failed: {e}")
            else:
                # 2. Use Old Regex (Fallback)
                detected = {
                    'Company': ['Detected Company'], 
                    'Pledge_Pct': [find_value_regex(text, ['Shares Pledged', 'Encumbered', 'Pledge'])],
                    'Sales': [find_value_regex(text, ['Revenue from Operations', 'Total Income'])],
                    'Receivables': [find_value_regex(text, ['Trade Receivables', 'Debtors'])],
                    'Inventory': [find_value_regex(text, ['Inventories', 'Stock-in-trade'])],
                    'CFO': [find_value_regex(text, ['Net Cash from Operating'])],
                    'EBITDA': [find_value_regex(text, ['EBITDA', 'Operating Profit'])],
                    'Total_Assets': [find_value_regex(text, ['Total Assets'])],
                    'Non_Current_Assets': [find_value_regex(text, ['Non-current assets'])],
                    'RPT_Vol': [find_value_regex(text, ['Related Party', 'RPT'])]
                }
                extracted_data = detected

            # Show Data Editor
            st.success("Extraction Complete! Please verify values below.")
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
                else:
                    st.markdown("- ✅ Financials appear robust.")

# ==========================================
# MODULE 3: SENTIMENT SCANNER
# ==========================================
elif app_mode == "3. Qualitative Sentiment Scanner":
    st.header("🧠 Qualitative Sentiment Scanner")
    # (Same as before)
    # ... [Keep your existing Module 3 code here] ...
