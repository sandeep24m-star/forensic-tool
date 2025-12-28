# 🕵️‍♂️ Forensic Risk Engine: Auto-Adaptive

### **AI-Powered Financial Fraud Detection System**
*An Automated Forensic Auditing Tool for Indian Corporate Governance*

---

## 📖 Project Overview
This tool is a Python-based forensic engine designed to detect **Earnings Manipulation** and **Governance Risks** in Indian listed companies. Unlike traditional solvency models (like Altman Z-Score), this engine focuses on the **"Motive"** (Promoter Pledging) and the **"Method"** (Aggressive Revenue Recognition).

It integrates **Quantitative Ratios** (Beneish M-Score logic) with **Qualitative AI Analysis** (NLP) to provide a 360-degree view of a company's financial integrity.

---

## 🚀 Key Features

### **1. 📊 Quantitative Scorecard (Batch Analysis)**
* **Input:** Excel/CSV file with raw financial data (Sales, EBITDA, Pledging, etc.).
* **Logic:** Applies a **Weighted-Attribute Risk Model (WARM)**.
* **Smart Features:** * **Auto-Column Mapping:** Automatically detects headers like "Revenue" or "Net Sales".
    * **Adaptive Grouping:** Switches between Binary (Red/Green) and Traffic Light (Red/Yellow/Green) grouping based on sample size (N < 30 vs N > 30).
* **Output:** Forensic Score (0-100), Risk Verdict, and Interactive Plotly Charts.

### **2. ⚡ Single Company Deep Dive (GenAI Powered)**
* **Input:** Annual Report PDF.
* **Technology:** * **Hybrid Engine:** Uses **OpenAI GPT-3.5** for semantic data extraction (if API Key provided).
    * **Fallback Engine:** Uses robust **Regex (Regular Expressions)** for offline extraction.
* **Goal:** Verifies third-party data errors by extracting "Source of Truth" numbers directly from the Annual Report.

### **3. 🧠 Qualitative Sentiment Scanner (NLP)**
* **Input:** Text from MD&A / Director's Report or News URLs.
* **Logic:** Uses **`TextBlob`** to analyze "Subjectivity" vs "Polarity".
* **Forensic Goal:** Detects the **"Pollyanna Effect"**—where management uses vague, flowery language to mask poor financial performance.

---

## 🛠️ Tech Stack
* **Frontend:** Streamlit (Python)
* **Data Processing:** Pandas, NumPy
* **Visualization:** Plotly Express
* **AI/NLP:** OpenAI API, TextBlob, PDFPlumber
* **Web Scraping:** BeautifulSoup4, Requests

---

## ⚙️ How to Run Locally
1.  Clone the repository:
    ```bash
    git clone [https://github.com/your-username/your-repo-name.git](https://github.com/your-username/your-repo-name.git)
    ```
2.  Install dependencies:
    ```bash
    pip install -r requirements.txt
    ```
3.  Run the app:
    ```bash
    streamlit run app.py
    ```

---

## 📝 Forensic Logic & Thresholds
| Parameter | Threshold | Risk Penalty | Logic |
| :--- | :--- | :--- | :--- |
| **Promoter Pledging** | > 50% | +25 Pts | High pledging creates pressure to maintain stock price. |
| **DSO (Days Sales)** | > 120 Days | +20 Pts | Indicates aggressive revenue recognition (Channel Stuffing). |
| **Cash Quality (CFO/EBITDA)** | < 0.8 | +15 Pts | Earnings are not backed by actual cash collection. |
| **RPT Intensity** | > 10% | +10 Pts | Risk of capital leakage via Related Party Transactions. |

---

## 📜 Disclaimer
This tool is for **academic and educational purposes only**. It does not constitute financial or investment advice. The "Forensic Score" is a statistical probability derived from public data, not a legal accusation of fraud.
