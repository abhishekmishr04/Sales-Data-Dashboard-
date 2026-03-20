import streamlit as st
import pandas as pd
import json
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload
import io

# --- CONFIG & AUTH ---
st.set_page_config(layout="wide", page_title="Shell Organics Dashboard")

# IMPORTANT: Replace this with your Google Drive Folder ID
FOLDER_ID = 'YOUR_GOOGLE_DRIVE_FOLDER_ID_HERE' 

def get_drive_service():
    # This pulls your JSON key from the Streamlit "Secrets" setting
    creds_info = st.secrets["gcp_service_account"]
    creds = service_account.Credentials.from_service_account_info(
        creds_info, scopes=['https://www.googleapis.com/auth/drive']
    )
    return build('drive', 'v3', credentials=creds)

# --- CUSTOM UI STYLING ---
st.markdown("""
    <style>
    [data-testid="stMetric"] {
        background-color: #ffffff;
        border-radius: 10px;
        padding: 15px;
        border-top: 5px solid #ff9900;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    .main-header {
        background-color: #ff9900;
        color: white;
        padding: 15px;
        border-radius: 5px;
        text-align: center;
        font-weight: bold;
        font-size: 24px;
        margin-bottom: 20px;
    }
    </style>
""", unsafe_allow_html=True)

# --- DRIVE OPERATIONS ---
def upload_json_to_drive(data_dict):
    service = get_drive_service()
    json_content = json.dumps(data_dict)
    file_metadata = {'name': 'dashboard_data.json', 'parents': [FOLDER_ID]}
    media = MediaFileUpload(io.BytesIO(json_content.encode()), mimetype='application/json', resumable=True)
    
    results = service.files().list(q=f"name='dashboard_data.json' and '{FOLDER_ID}' in parents").execute()
    files = results.get('files', [])
    
    if files:
        service.files().update(fileId=files[0]['id'], media_body=media).execute()
    else:
        service.files().create(body=file_metadata, media_body=media, fields='id').execute()

def load_json_from_drive():
    try:
        service = get_drive_service()
        results = service.files().list(q=f"name='dashboard_data.json' and '{FOLDER_ID}' in parents").execute()
        files = results.get('files', [])
        if not files: return None
        
        request = service.files().get_media(fileId=files[0]['id'])
        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()
        return json.loads(fh.getvalue().decode())
    except Exception as e:
        return None

# --- SIDEBAR: UPLOAD ---
st.sidebar.title("🛠️ Data Upload")
uploaded_file = st.sidebar.file_uploader("Upload Excel", type=["xlsx"])

if uploaded_file:
    if st.sidebar.button("Sync to Google Drive"):
        # We read the Excel and clean column names to match the dashboard
        df_upload = pd.read_excel(uploaded_file)
        upload_json_to_drive(df_upload.to_dict(orient='records'))
        st.sidebar.success("Data Saved Successfully!")
        st.rerun()

# --- MAIN CONTENT: DASHBOARD ---
data = load_json_from_drive()

if data:
    df = pd.DataFrame(data)
    st.markdown("<div class='main-header'>Shell Organics Performance Dashboard</div>", unsafe_allow_html=True)
    
    # Calculate Metrics (Adjust column names if your Excel varies)
    sales_col = 'Sales Value' if 'Sales Value' in df.columns else df.columns[1]
    ads_col = 'Ads Spend' if 'Ads Spend' in df.columns else df.columns[2]
    
    total_sales = df[sales_col].sum()
    total_ads = df[ads_col].sum()
    roas = total_sales / total_ads if total_ads > 0 else 0
    
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("TOTAL SALES", f"₹{total_sales:,.0f}")
    c2.metric("TOTAL ADS SPEND", f"₹{total_ads:,.0f}")
    c3.metric("MTD ROAS", f"{roas:.2f}x")
    c4.metric("CHANNELS", len(df))

    st.write("### Channel Breakdown")
    st.dataframe(
        df.style.format({sales_col: '₹{:,.0f}', ads_col: '₹{:,.0f}'})
        .background_gradient(subset=[sales_col], cmap='YlOrBr'),
        use_container_width=True
    )
else:
    st.info("👋 Welcome! Please upload your daily Sales Excel file in the sidebar to populate the dashboard.")
