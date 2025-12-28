import streamlit as st
import pandas as pd
import plotly.express as px
from textblob import TextBlob
import pdfplumber
import re
import requests
from bs4 import BeautifulSoup
import io

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
    header_row_val = st.number_input("Header Row Number (in Excel)", min_value=1, value=1, step=1) - 1

# --- Helper: Extract Text from PDF Upload ---
def extract_pdf_text(uploaded_file):
    all_text = ""
    with pdfplumber.open(uploaded_file) as pdf:
        # Scan first 50 pages (usually where Financial Statements are)
        for page in pdf.pages[:50]:
            text = page.extract_text()
            if text: all_text += text + "\n"
    return all_text

# --- Helper: Extract Text from URL ---
def extract_url_text(url):
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
        response = requests.get(url, headers=headers, timeout=15, stream=True)
        
        if response.status_code != 200:
            return f"⚠️ Error: Website returned Status Code {response.status_code}."

        first_bytes = next(response.iter_content(chunk_size=4))
        if first_bytes.startswith(b'%PDF') or url.lower().endswith('.pdf'):
            try:
                pdf_data = io.BytesIO(response.content)
                with pdfplumber.open(pdf_data) as pdf:
                    all_text = ""
                    for page in pdf.pages[:30]:
                        txt = page.extract_text()
                        if txt: all_text += txt + "\n"
                    return all_text if len(all_text) > 0 else "⚠️ PDF found but no text extracted."
            except Exception as e: return f"⚠️ PDF Error: {e}"
        else:
            soup = BeautifulSoup(response.content, 'html.parser')
            for el in soup(['script', 'style', 'header', 'footer', 'nav', 'aside', 'form']): el.decompose()
            content = soup.find('main') or soup.body
            if content:
                text = content.get_text(separator=' ', strip=True)
                lines = [line for line in text.split('\n') if len(line.split()) > 3]
                return " ".join(lines)
            return "⚠️ No content found."
    except Exception as e: return f"⚠️ Network Error: {e}"

# --- Helper: SMART VALUE FINDER V3 (WIDE NET) ---
def find_value_in_text(text, keywords):
    best_guess = 0.0
    
    for keyword in keywords:
        # 1. Find the keyword in the messy text
        pattern = re.compile(re.escape(keyword), re.IGNORECASE)
        match = pattern.search(text)
        
        if match:
            # 2. Grab a HUGE chunk of text after the keyword (800 chars to cover wide tables)
            start_idx = match.end()
            end_idx = min(len(text), start_idx + 800)
            window_text = text[start_idx:end_idx]
            
            # 3. Find ALL numbers in that chunk
            # Matches: 10,000.00 | 500 | 12.5
            numbers = re.findall(r'[\d,]+\.\d+|[\d,]+', window_text)
            
            candidates = []
            for num_str in numbers:
                try:
                    # Clean the number (remove commas)
                    clean_num = num_str.replace(',', '')
                    val = float(clean_num)
                    
                    # Filter out Years (2023, 2024) and small Note numbers (<100)
                    if val > 100 and val not in [2022, 2023, 2024, 2025]:
                        candidates.append(val)
                except:
                    continue
            
            # 4. Heuristic: The financial value is usually the LARGEST number in the row
            # (e.g. Note 5 | Year 2024 | Value 50,000 -> 50,000 is max)
            if candidates:
                return max(candidates)
                
    return best_guess

# --- Helper: Smart Column Mapper ---
def smart_map_columns(df):
    df.columns = df.columns.astype(str).str.strip().str.replace('\n', ' ')
    mapping_rules = {
        'Company': ['company', 'entity', 'name'],
        'Pledge_Pct': ['pledge', 'encumbered'],
        'Sales': ['sales', 'revenue', 'turnover', 'income'],
        'Receivables': ['receivables', 'debtors'],
        'Inventory': ['inventory', 'stock'],
        'CFO': ['cfo', 'operating cash', 'cash flow from operating'],
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

# --- Helper: Risk Logic ---
def calculate_risk(df):
    cols = ['Sales', 'Receivables', 'Inventory', 'CFO', 'EBITDA', 'Pledge_Pct', 'Total_Assets', 'Non_Current_Assets', 'RPT_Vol']
    for c in cols: df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0)
    
    df['DSO'] = df.apply(lambda x: (x['Receivables']/x['Sales']*365) if x['Sales']>0 else 0, axis=1).round(1)
    df['Cash_Quality'] = df.apply(lambda x: (x['CFO']/x['EBITDA']) if x['EBITDA']>0 else 0, axis=1).round(2)
    df['RPT_Intensity'] = df.apply(lambda x: (x['RPT_Vol']/x['Sales']*100) if x['Sales']>0 else 0, axis=1).round(1)
    
    # Simple Bucket Logic for PDF Scanner
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
# APP UI
# ==========================================
if app_mode == "1. Quantitative Forensic Scorecard":
    st.header("📊 Module 1: Quantitative Analysis")
    st.info("Please go to Module 2 to test PDF Extraction.")

# ==========================================
# MODULE 2: PDF SCANNER (IMPROVED V3)
# ==========================================
elif app_mode == "2. Single Company Auto-Analysis (PDF)":
    st.header("⚡ Single Company Deep Dive")
    st.info("Upload an Annual Report PDF. The tool will scan for Keywords and extract values.")
    
    pdf_file = st.file_uploader("Upload Annual Report", type=["pdf"])
    
    if pdf_file:
        with st.spinner("Scanning PDF tables... (Using Wide-Net Search)"):
            text = extract_pdf_text(pdf_file)
            
            # --- DEBUG VIEW ---
            with st.expander("🛠️ Debug: View Raw Extracted Text"):
                st.text(text[:5000]) # Show first 5000 chars for user to check
            
            # --- IMPROVED KEYWORD LIST ---
            detected = {
                'Company': ['Detected Company'], 
                'Pledge_Pct': [find_value_in_text(text, ['Shares Pledged', 'Encumbered', 'Promoter Pledge'])],
                'Sales': [find_value_in_text(text, ['Revenue from Operations', 'Total Income', 'Sale of Products', 'Turnover'])],
                'Receivables': [find_value_in_text(text, ['Trade Receivables', 'Current Trade Receivables', 'Debtors'])],
                'Inventory': [find_value_in_text(text, ['Inventories', 'Stock-in-trade'])],
                'CFO': [find_value_in_text(text, ['Net Cash from Operating', 'Net cash generated from operating', 'Cash flow from operating'])],
                'EBITDA': [find_value_in_text(text, ['EBITDA', 'Profit before tax', 'Operating Profit'])],
                'Total_Assets': [find_value_in_text(text, ['Total Assets', 'Total Equity and Liabilities'])],
                'Non_Current_Assets': [find_value_in_text(text, ['Non-current assets', 'Total Non-Current Assets'])],
                'RPT_Vol': [find_value_in_text(text, ['Related Party', 'RPT'])]
            }
            
            st.success("Extraction Complete! Verify numbers below.")
            st.caption("ℹ️ Note: If values are 0, the PDF format might be image-based or tables are too complex. Please type manually.")
            
            # Allow user to edit
            verified_df = st.data_editor(pd.DataFrame(detected))
            
            if st.button("Analyze PDF Data"):
                res, _ = calculate_risk(verified_df)
                row = res.iloc[0]
                
                st.write("---")
                score = row['Forensic_Score']
                if score > 50: st.error(f"**Verdict:** {row['Verdict']} (Score: {score})")
                else: st.success(f"**Verdict:** {row['Verdict']} (Score: {score})")
                
                st.markdown("#### **📝 AI Interpretation:**")
                if row['Detailed_Report']:
                    for line in row['Detailed_Report']: st.markdown(f"- {line}")
                else:
                    st.markdown("- ✅ Financials appear robust.")

# ==========================================
# MODULE 3: SENTIMENT SCANNER
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
            st.metric("Subjectivity", f"{blob.sentiment.subjectivity:.2f}")
            if blob.sentiment.subjectivity > 0.5: st.error("Pollyanna Effect Detected!")
            else: st.success("Objective Tone.")
        else: st.warning("No text found.")
