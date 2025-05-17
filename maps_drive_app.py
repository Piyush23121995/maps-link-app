import streamlit as st
import pandas as pd
import urllib.parse
import io
import json
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload, MediaFileUpload

st.set_page_config(page_title="Maps Link Generator via Drive")
st.title("📍 Google Maps Link Generator + Google Drive")

# Load credentials from Streamlit secrets
SCOPES = ['https://www.googleapis.com/auth/drive']
service_account_info = json.loads(st.secrets["GOOGLE_SERVICE_ACCOUNT_JSON"])
credentials = service_account.Credentials.from_service_account_info(
    service_account_info, scopes=SCOPES)
drive_service = build('drive', 'v3', credentials=credentials)

# Use folder ID directly
FOLDER_ID = st.secrets["GDRIVE_FOLDER_ID"]

@st.cache_data
def list_files(folder_id):
    query = f"'{folder_id}' in parents and (mimeType='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' or mimeType='text/csv')"
    results = drive_service.files().list(q=query, spaces='drive').execute()
    return results.get('files', [])

def download_file(file_id, filename):
    request = drive_service.files().get_media(fileId=file_id)
    fh = io.BytesIO()
    downloader = MediaIoBaseDownload(fh, request)
    done = False
    while not done:
        status, done = downloader.next_chunk()
    fh.seek(0)
    with open(filename, 'wb') as f:
        f.write(fh.read())
    return filename

def generate_link(location):
    return f"https://www.google.com/maps/search/?api=1&query={urllib.parse.quote(location)}"

def upload_to_drive(df, original_name, folder_id):
    output = io.BytesIO()
    df.to_excel(output, index=False, engine='openpyxl')
    output.seek(0)
    media = MediaFileUpload(io.BytesIO(output.getvalue()), mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    file_metadata = {
        'name': f"{original_name}_with_links.xlsx",
        'parents': [folder_id]
    }
    new_file = drive_service.files().create(body=file_metadata, media_body=media, fields='id').execute()
    return new_file.get('id')

# App Logic
files = list_files(FOLDER_ID)
file_names = [f['name'] for f in files]
selected_file = st.selectbox("Select a file", file_names)

if st.button("Generate Links"):
    file_meta = next((f for f in files if f['name'] == selected_file), None)
    file_path = download_file(file_meta['id'], selected_file)

    if selected_file.endswith(".csv"):
        df = pd.read_csv(file_path)
    else:
        df = pd.read_excel(file_path)

    if 'Location Name' not in df.columns:
        st.error("❌ File must contain 'Location Name' column.")
    else:
        df['Google Maps Link'] = df['Location Name'].apply(generate_link)
        st.success("✅ Links generated!")
        st.dataframe(df.head())

        uploaded_id = upload_to_drive(df, selected_file.split('.')[0], FOLDER_ID)
        st.success(f"✅ Uploaded updated file to Drive (file ID: {uploaded_id})")
