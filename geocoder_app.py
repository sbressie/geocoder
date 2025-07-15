import streamlit as st
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError
import pandas as pd
import io
from shapely import wkt # Import shapely for WKT parsing
from shapely.errors import GEOSException # Import specific exception for shapely

# --- Streamlit App Configuration ---
st.set_page_config(
    page_title="Reverse Geocoding App",
    page_icon="📍",
    layout="centered",
    initial_sidebar_state="collapsed",
)

# --- Title and Description ---
st.title("📍 Reverse Geocoding Application")
st.markdown(
    """
    Enter latitude and longitude coordinates below to find the corresponding
    human-readable address. This app uses the Nominatim geocoding service.
    """
)

# --- Input Fields for Single Geocoding ---
st.header("Single Geocoding")

col1, col2 = st.columns(2)

with col1:
    latitude_str = st.text_input("Latitude", value="35.5306", help="e.g., 35.5306")

with col2:
    longitude_str = st.text_input("Longitude", value="-82.6074", help="e.g., -82.6074")

# --- Geocoding Logic for Single Input ---
if st.button("Get Address (Single)"):
    try:
        # Convert string inputs to float
        latitude = float(latitude_str)
        longitude = float(longitude_str)

        # Validate coordinate ranges
        if not (-90 <= latitude <= 90):
            st.error("Latitude must be between -90 and 90.")
        elif not (-180 <= longitude <= 180):
            st.error("Longitude must be between -180 and 180.")
        else:
            st.info(f"Attempting to geocode: Lat {latitude}, Lon {longitude}...")

            # Initialize Nominatim geocoder
            # It's good practice to provide a user_agent for Nominatim
            geolocator = Nominatim(user_agent="streamlit-geocoder-app")

            try:
                # Perform reverse geocoding
                location = geolocator.reverse((latitude, longitude), exactly_one=True, timeout=10)

                if location:
                    st.success("Address Found!")
                    st.write(f"**Full Address:** {location.address}")
                    st.write(f"**Latitude:** {location.latitude}")
                    st.write(f"**Longitude:** {location.longitude}")
                    st.write(f"**Raw Data:**")
                    st.json(location.raw) # Display raw data for more details
                else:
                    st.warning("No address found for the given coordinates.")
            except GeocoderTimedOut:
                st.error("Geocoding service timed out. Please try again.")
            except GeocoderServiceError as e:
                st.error(f"Geocoding service error: {e}. Please check your internet connection or try again later.")
            except Exception as e:
                st.error(f"An unexpected error occurred during geocoding: {e}")

    except ValueError:
        st.error("Invalid input. Please enter valid numerical values for Latitude and Longitude.")
    except Exception as e:
        st.error(f"An unexpected error occurred: {e}")

st.markdown("---")

# --- Batch Geocoding Section ---
st.header("Batch Geocoding")
st.markdown(
    """
    Process multiple geocoordinate pairs. You can either upload a CSV file
    (with 'latitude' and 'longitude' columns, or a 'WKT' column for POINT geometries)
    or enter coordinates directly as a comma-separated list (e.g., `lat1,lon1;lat2,lon2`).
    """
)

batch_option = st.radio(
    "Choose input method:",
    ("Upload CSV", "Enter Coordinates Manually")
)

coordinates_to_process = []

if batch_option == "Upload CSV":
    uploaded_file = st.file_uploader("Upload CSV file", type=["csv"])
    if uploaded_file is not None:
        try:
            dataframe = pd.read_csv(uploaded_file)
            # Prioritize WKT column if present
            if 'WKT' in dataframe.columns:
                st.info("Detected 'WKT' column. Attempting to parse WKT geometries.")
                for index, row in dataframe.iterrows():
                    wkt_string = row['WKT']
                    try:
                        point = wkt.loads(wkt_string)
                        if point.geom_type == 'Point':
                            # WKT Point format is POINT (longitude latitude)
                            coordinates_to_process.append([point.y, point.x])
                        else:
                            st.warning(f"Skipping non-Point WKT geometry at row {index}: {wkt_string}")
                    except GEOSException as e:
                        st.warning(f"Could not parse WKT at row {index} ('{wkt_string}'): {e}")
                    except Exception as e:
                        st.warning(f"An unexpected error occurred parsing WKT at row {index}: {e}")
                if coordinates_to_process:
                    st.success(f"Loaded {len(coordinates_to_process)} valid coordinate pairs from WKT column.")
                else:
                    st.warning("No valid Point WKT geometries found in the 'WKT' column.")
                st.dataframe(dataframe) # Show the original dataframe
            elif 'latitude' in dataframe.columns and 'longitude' in dataframe.columns:
                coordinates_to_process = dataframe[['latitude', 'longitude']].values.tolist()
                st.success(f"Loaded {len(coordinates_to_process)} coordinate pairs from 'latitude' and 'longitude' columns.")
                st.dataframe(dataframe)
            else:
                st.error("CSV must contain either 'latitude' and 'longitude' columns, or a 'WKT' column (for Point geometries).")
        except Exception as e:
            st.error(f"Error reading CSV: {e}")
else: # Enter Coordinates Manually
    manual_coords_input = st.text_area(
        "Enter coordinate pairs (e.g., 35.5306,-82.6074;34.0522,-118.2437)",
        height=100
    )
    if manual_coords_input:
        try:
            # Split by semicolon for pairs, then by comma for lat/lon
            pairs_str = manual_coords_input.split(';')
            for pair_str in pairs_str:
                if ',' in pair_str:
                    lat_str, lon_str = pair_str.strip().split(',')
                    coordinates_to_process.append([float(lat_str), float(lon_str)])
            st.success(f"Parsed {len(coordinates_to_process)} coordinate pairs.")
        except ValueError:
            st.error("Invalid format for manual coordinates. Please use `lat,lon;lat,lon`.")
        except Exception as e:
            st.error(f"An error occurred parsing manual coordinates: {e}")


if st.button("Get Addresses (Batch)"):
    if not coordinates_to_process:
        st.warning("No coordinates to process. Please upload a CSV or enter coordinates.")
    else:
        st.info(f"Starting batch geocoding for {len(coordinates_to_process)} pairs...")
        geolocator = Nominatim(user_agent="streamlit-geocoder-app-batch")
        results = []
        progress_bar = st.progress(0)
        status_text = st.empty()

        for i, (lat, lon) in enumerate(coordinates_to_process):
            status_text.text(f"Processing coordinate {i+1}/{len(coordinates_to_process)}: {lat}, {lon}")
            try:
                if not (-90 <= lat <= 90) or not (-180 <= lon <= 180):
                    results.append({"Latitude": lat, "Longitude": lon, "Address": "Invalid Coordinates", "Status": "Error"})
                    st.warning(f"Skipping invalid coordinates: {lat}, {lon}")
                    continue

                location = geolocator.reverse((lat, lon), exactly_one=True, timeout=10)
                if location:
                    results.append({
                        "Latitude": lat,
                        "Longitude": lon,
                        "Address": location.address,
                        "Status": "Success"
                    })
                else:
                    results.append({
                        "Latitude": lat,
                        "Longitude": lon,
                        "Address": "No address found",
                        "Status": "Warning"
                    })
            except GeocoderTimedOut:
                results.append({
                    "Latitude": lat,
                    "Longitude": lon,
                    "Address": "Geocoding Timed Out",
                    "Status": "Error"
                })
            except GeocoderServiceError as e:
                results.append({
                    "Latitude": lat,
                    "Longitude": lon,
                    "Address": f"Service Error: {e}",
                    "Status": "Error"
                })
            except Exception as e:
                results.append({
                    "Latitude": lat,
                    "Longitude": lon,
                    "Address": f"Unexpected Error: {e}",
                    "Status": "Error"
                })
            progress_bar.progress((i + 1) / len(coordinates_to_process))

        status_text.empty() # Clear status text
        st.success("Batch geocoding complete!")
        if results:
            results_df = pd.DataFrame(results)
            st.dataframe(results_df)

            # Option to download results
            csv_output = results_df.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="Download Results as CSV",
                data=csv_output,
                file_name="geocoding_results.csv",
                mime="text/csv",
            )
        else:
            st.warning("No results to display.")


st.markdown("---")
st.markdown("Built with ❤️ using Streamlit and geopy.")
