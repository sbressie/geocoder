import streamlit as st
import pandas as pd
from geopy.geocoders import Nominatim
from geopy.extra.rate_limiter import RateLimiter
import json
import io

# --- Streamlit App Configuration ---
st.set_page_config(
    page_title="Address Geocoder App",
    page_icon="📍",
    layout="centered"
)

# --- Initialize Geocoder ---
# Using Nominatim from OpenStreetMap.
# Be respectful of their usage policy by providing a unique user_agent.
# RateLimiter helps prevent hitting usage limits too quickly.
geolocator = Nominatim(user_agent="my-streamlit-geocoder-app")
geocode = RateLimiter(geolocator.geocode, min_delay_seconds=1)

# --- Helper Functions ---

def load_data(uploaded_file):
    """
    Loads data from an uploaded CSV or GeoJSON file.
    Expects CSV to have an 'address' column.
    Expects GeoJSON features to have a 'properties' dictionary with an 'address' key.
    """
    if uploaded_file.type == "text/csv":
        try:
            df = pd.read_csv(uploaded_file)
            if 'address' not in df.columns:
                st.error("CSV file must contain an 'address' column.")
                return None
            return df
        except Exception as e:
            st.error(f"Error reading CSV: {e}")
            return None
    elif uploaded_file.type == "application/json": # Covers .geojson
        try:
            geojson_data = json.load(uploaded_file)
            if "type" not in geojson_data or geojson_data["type"] != "FeatureCollection":
                st.error("GeoJSON file must be a FeatureCollection.")
                return None

            # Extract addresses from GeoJSON features
            addresses = []
            for feature in geojson_data.get("features", []):
                if "properties" in feature and "address" in feature["properties"]:
                    addresses.append(feature["properties"]["address"])
                else:
                    st.warning("Skipping a GeoJSON feature with missing 'properties.address'.")

            if not addresses:
                st.error("No 'address' property found in any GeoJSON feature.")
                return None

            df = pd.DataFrame(addresses, columns=['address'])
            return df, geojson_data # Return both for later GeoJSON reconstruction
        except Exception as e:
            st.error(f"Error reading GeoJSON: {e}")
            return None
    else:
        st.error("Unsupported file type. Please upload a CSV or GeoJSON file.")
        return None

def geocode_addresses(df):
    """
    Geocodes addresses in a DataFrame and adds 'latitude', 'longitude', 'geocoded_address' columns.
    """
    st.info("Geocoding addresses... This may take a while for large files.")

    # Create empty lists to store results
    latitudes = []
    longitudes = []
    geocoded_addresses = []

    # Use st.progress for visual feedback
    progress_bar = st.progress(0)

    for i, address in enumerate(df['address']):
        try:
            location = geocode(address) # Apply rate limiter here
            if location:
                latitudes.append(location.latitude)
                longitudes.append(location.longitude)
                geocoded_addresses.append(location.address)
            else:
                latitudes.append(None)
                longitudes.append(None)
                geocoded_addresses.append("Not Found")
        except Exception as e:
            st.warning(f"Could not geocode '{address}': {e}")
            latitudes.append(None)
            longitudes.append(None)
            geocoded_addresses.append(f"Error: {e}")

        # Update progress bar
        progress_bar.progress((i + 1) / len(df) if len(df) > 0 else 1.0)

    df['latitude'] = latitudes
    df['longitude'] = longitudes
    df['geocoded_address'] = geocoded_addresses

    st.success("Geocoding complete!")
    return df

def df_to_geojson(df):
    """
    Converts a DataFrame with 'latitude' and 'longitude' columns to a GeoJSON FeatureCollection.
    Original columns are included in 'properties'.
    """
    features = []
    for index, row in df.iterrows():
        # Ensure lat/lon are not None before creating point
        if pd.notna(row['latitude']) and pd.notna(row['longitude']):
            feature = {
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [row['longitude'], row['latitude']] # GeoJSON is [longitude, latitude]
                },
                "properties": row.drop(['latitude', 'longitude']).to_dict() # All other columns as properties
            }
            features.append(feature)

    geojson_output = {
        "type": "FeatureCollection",
        "features": features
    }
    return geojson_output

# --- Streamlit UI ---

st.title("📍 Address Geocoder")
st.markdown("""
Upload a CSV or GeoJSON file containing addresses, and this app will geocode them
to latitude and longitude coordinates using OpenStreetMap's Nominatim service.
""")

uploaded_file = st.file_uploader(
    "Upload your file (CSV with 'address' column or GeoJSON FeatureCollection)",
    type=["csv", "json", "geojson"] # Allow both .json and .geojson
)

processed_df = None
original_geojson_data = None # To preserve original geojson structure if applicable

if uploaded_file is not None:
    file_type = uploaded_file.type
    st.write(f"File uploaded: {uploaded_file.name} (Type: {file_type})")

    if file_type == "text/csv":
        data_to_geocode = load_data(uploaded_file)
    elif file_type == "application/json":
        data_loaded = load_data(uploaded_file)
        if data_loaded:
            data_to_geocode, original_geojson_data = data_loaded
        else:
            data_to_geocode = None
    else:
        data_to_geocode = None

    if data_to_geocode is not None:
        st.subheader("Original Data Preview (First 5 rows)")
        st.dataframe(data_to_geocode.head())

        if st.button("Geocode Addresses"):
            with st.spinner("Geocoding in progress..."):
                processed_df = geocode_addresses(data_to_geocode.copy()) # Use a copy to avoid modifying original df state

            if processed_df is not None:
                st.subheader("Geocoded Data Preview (First 5 rows)")
                st.dataframe(processed_df.head())

                st.subheader("Download Results")

                # --- Download as CSV ---
                csv_buffer = io.StringIO()
                processed_df.to_csv(csv_buffer, index=False)
                st.download_button(
                    label="Download as CSV",
                    data=csv_buffer.getvalue(),
                    file_name="geocoded_addresses.csv",
                    mime="text/csv"
                )

                # --- Download as GeoJSON ---
                geojson_output = df_to_geojson(processed_df)
                st.download_button(
                    label="Download as GeoJSON",
                    data=json.dumps(geojson_output, indent=2),
                    file_name="geocoded_addresses.geojson",
                    mime="application/json"
                )

                # --- Shapefile Explanation ---
                st.info("""
                **Note on Shapefile Output (.shp):**
                Direct Shapefile output from a web application like Streamlit is more complex
                because it requires specialized libraries like `fiona` and `shapely`, which
                often have system-level dependencies (like GDAL).

                For local development, you would typically install these:
                `pip install fiona shapely`

                Then, you would use `fiona` to write the GeoJSON-like data to a Shapefile:
                ```python
                import fiona
                from shapely.geometry import Point, mapping

                # ... (after geocoding `processed_df`) ...

                # Define the schema for the Shapefile
                schema = {
                    'geometry': 'Point',
                    'properties': {
                        'address': 'str',
                        'latitude': 'float',
                        'longitude': 'float',
                        # Add other properties as needed
                    },
                }

                # Define the CRS (Coordinate Reference System)
                crs = 'EPSG:4326' # WGS 84 geographic coordinate system

                # Prepare features for Fiona
                fiona_features = []
                for index, row in processed_df.iterrows():
                    if pd.notna(row['latitude']) and pd.notna(row['longitude']):
                        point = Point(row['longitude'], row['latitude'])
                        properties = row.drop(['latitude', 'longitude']).to_dict()
                        fiona_features.append({
                            'geometry': mapping(point),
                            'properties': properties,
                        })

                # Create an in-memory buffer for the zip file (Shapefiles are collections of files)
                # In a real app, you might write to disk or a more robust memory solution
                # with tempfile and shutil.make_archive. This is conceptual.

                # Example of writing (requires setting up a temporary directory)
                # with fiona.open(
                #     'geocoded_addresses.shp', 'w',
                #     driver='ESRI Shapefile',
                #     crs=crs,
                #     schema=schema
                # ) as collection:
                #     for feature in fiona_features:
                #         collection.write(feature)

                st.warning("Shapefile generation requires specific library installations and handling of multiple files (e.g., as a .zip archive). The GeoJSON output is often a good alternative for geographic data interchange.")
                ```
                For deployment, you would need to ensure these libraries and their underlying system dependencies are correctly configured in your deployment environment (e.g., Docker for Streamlit Cloud).
                """)
