import streamlit as st
import requests
from docx import Document
from datetime import date
import io
from PIL import Image
import docx.shared
import os

# --- Helper functions ---
def get_coords_from_eircode(eircode, api_key):
    url = f"https://api.opencagedata.com/geocode/v1/json?q={eircode}&key={api_key}&countrycode=ie&limit=1"
    response = requests.get(url)
    if response.status_code == 200:
        results = response.json()['results']
        if results:
            lat = results[0]['geometry']['lat']
            lng = results[0]['geometry']['lng']
            return lat, lng
    return None, None

def query_gsi_geology(lat, lon):
    url = "https://secure.dccae.gov.ie/gsi-wfs/public"
    params = {
        "service": "WFS",
        "version": "1.1.0",
        "request": "GetFeature",
        "typeName": "bedrock100k",
        "srsName": "EPSG:4326",
        "outputFormat": "application/json",
        "bbox": f"{lon},{lat},{lon},{lat}"
    }
    try:
        response = requests.get(url, params=params)
        data = response.json()
        if data['features']:
            rock = data['features'][0]['properties']['ROCKNAME']
            return f"The underlying bedrock geology is primarily {rock.lower()}."
    except:
        pass
    return "Geological information unavailable."

def get_mapbox_image(lat, lon, mapbox_token):
    zoom = 16
    width, height = 600, 400
    marker = f"pin-l+ff0000({lon},{lat})"
    url = f"https://api.mapbox.com/styles/v1/mapbox/streets-v11/static/{marker}/{lon},{lat},{zoom}/{width}x{height}@2x?access_token={mapbox_token}"
    response = requests.get(url)
    if response.status_code == 200:
        return Image.open(io.BytesIO(response.content))
    return None

# --- Streamlit UI ---
st.set_page_config(page_title="Forensic Subsidence Report Assistant", layout="centered")
st.title("ð ï¸ Forensic Subsidence Report Assistant (2025)")

with st.form("subsidence_form"):
    insurer = st.text_input("Insurer Name")
    claim_ref = st.text_input("Claim Reference")
    address = st.text_area("Property Address")
    inspection_date = st.date_input("Date of Inspection", value=date.today())
    eircode = st.text_input("Eircode")

    historical_photos = st.file_uploader("Upload Historical Photos (optional)", accept_multiple_files=True, type=['png', 'jpg', 'jpeg'])

    submit = st.form_submit_button("Generate Report")

if submit:
    opencage_key = st.secrets.get("OPENCAGE_API_KEY", "")
    mapbox_key = st.secrets.get("MAPBOX_API_KEY", "")
    if not opencage_key or not mapbox_key:
        st.error("Missing API keys in secrets. Please set OPENCAGE_API_KEY and MAPBOX_API_KEY.")
    else:
        lat, lon = get_coords_from_eircode(eircode.strip(), opencage_key)
        if not lat:
            st.error("Unable to resolve Eircode.")
        else:
            st.success(f"Location resolved: {lat:.5f}, {lon:.5f}")
            geology_summary = query_gsi_geology(lat, lon)
            map_image = get_mapbox_image(lat, lon, mapbox_key)

            doc = Document()
            doc.add_heading("Subsidence Report", 0)

            doc.add_heading("1. Property & Claim Info", level=1)
            doc.add_paragraph(f"Insurer: {insurer}")
            doc.add_paragraph(f"Claim Ref: {claim_ref}")
            doc.add_paragraph(f"Address: {address}")
            doc.add_paragraph(f"Eircode: {eircode}")
            doc.add_paragraph(f"Coordinates: {lat:.5f}, {lon:.5f}")
            doc.add_paragraph(f"Inspection Date: {inspection_date.strftime('%d %B %Y')}")

            doc.add_heading("2. Site Location Map", level=1)
            if map_image:
                temp_img_path = "/tmp/mapbox_map.png"
                map_image.save(temp_img_path)
                doc.add_picture(temp_img_path, width=docx.shared.Inches(5.5))
                st.image(map_image, caption="Map Snapshot", use_column_width=True)
            else:
                doc.add_paragraph("Map image unavailable.")

            doc.add_heading("3. Geological Summary", level=1)
            doc.add_paragraph(geology_summary)
            st.info(geology_summary)

            if historical_photos:
                doc.add_heading("4. Historical Photos", level=1)
                for idx, photo in enumerate(historical_photos, start=1):
                    image = Image.open(photo)
                    temp_path = f"/tmp/{photo.name}"
                    image.save(temp_path)
                    doc.add_paragraph(f"Figure {idx}: {photo.name}")
                    doc.add_picture(temp_path, width=docx.shared.Inches(5.5))

            buf = io.BytesIO()
            doc.save(buf)
            st.download_button("ð Download Word Report", data=buf.getvalue(), file_name="subsidence_report.docx")
