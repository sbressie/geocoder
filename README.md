Address Geocoder Streamlit App

This is a simple Streamlit web application designed to geocode addresses from CSV or GeoJSON files into latitude and longitude coordinates. It utilizes the OpenStreetMap Nominatim service for geocoding.
Features

    Input Formats: Accepts CSV files (with an 'address' column) and GeoJSON FeatureCollections (where each feature's properties contain an 'address' key).

    Geocoding: Converts addresses to geographic coordinates (latitude and longitude).

    Output Formats: Provides options to download the geocoded data as CSV or GeoJSON.

    Rate Limiting: Includes a rate limiter to respect the usage policy of the Nominatim service.

    User Feedback: Displays progress and status messages during the geocoding process.
