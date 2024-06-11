import streamlit as st
import pandas as pd
import urllib.parse
import subprocess
from dotenv import load_dotenv
import os
import streamlit_authenticator as stauth
import pickle
from pathlib import Path

# Load environment variables
load_dotenv()


CURL_KEY = os.getenv("CURL_KEY")


# Load hashed passwords
file_path = Path(__file__).parent / "hashed_pw.pkl"
with file_path.open("rb") as file:
    hashed_passwords = pickle.load(file)

names = ["Bruno Szubally", "kristof Szentes"]
usernames = ["bruno.szubally", "kristof.szentes"]

credentials = {
    "usernames": {
        usernames[0]: {"name": names[0], "password": hashed_passwords[0]},
        usernames[1]: {"name": names[1], "password": hashed_passwords[1]},
    }
}

authenticator = stauth.Authenticate(
    credentials,
    "flowergpt",
    "abcdef",
    cookie_expiry_days=30
)

name, authentication_status, username = authenticator.login('main', fields={
    'Form name': 'Belépés', 'Username': 'Felhasználónév', 'Password': 'Jelszó', 'Login': 'Belépés'})

if authentication_status == False:
    st.error("Username/password is incorrect")

if authentication_status == None:
    st.warning("Add meg az adataidat!")

if authentication_status:
    st.sidebar.title(f"PlazmaSMS!")
    authenticator.logout("Kilépés", "sidebar")

    st.title("SMS Küldés Vérplazma Donációhoz")

    css = '''
    <style>
    [data-testid="stFileUploaderDropzone"] div div::before { content:"Tallózd be az Excel fájlt!"}
    [data-testid="stFileUploaderDropzone"] div div span{display:none;}
    [data-testid="stFileUploaderDropzone"] div div::after { content:""}
    [data-testid="stFileUploaderDropzone"] div div small{display:none;}
    [data-testid="stFileUploaderDropzone"] button{display:none;}
    </style>
    '''
    st.markdown(css, unsafe_allow_html=True)

    # Select message template
    message_template = st.radio(
        "Válassz egy üzenetet",
        ('donation', 'appointment'),
        format_func=lambda x: "Vérplazma donáció" if x == 'donation' else "Alkalmassági vizsgálat"
    )

    uploaded_file = st.file_uploader("Töltsd fel az Excel fájlt (xlsx formátumban)", type=["xlsx"])

    if uploaded_file is not None:
        # Load the Excel file
        data = pd.read_excel(uploaded_file, header=None)

        # Manually set the column names
        data.columns = ['name', 'phone', 'datetime'] + [f'col_{i}' for i in range(3, data.shape[1])]

        # Extracting the necessary columns based on our requirement
        data = data[['name', 'phone', 'datetime']]

        # Apply transformations
        data['first_name'] = data['name'].apply(get_first_name)
        data['formatted_phone'] = data['phone'].apply(convert_phone_number)
        data['formatted_time'] = data['datetime'].apply(format_datetime)

        # Filter out rows with empty first names, phone numbers, or formatted time
        data = data[(data['first_name'] != "") & (data['formatted_phone'] != "") & (data['formatted_time'] != "")]

        # Construct the curl command for each entry
        data['curl_command'] = data.apply(lambda row: construct_curl_command(row, message_template), axis=1)

        st.write("Adatok feldolgozva. Nyomd meg a 'Küldés' gombot az SMS-ek elküldéséhez.")

        if st.button("Küldés"):
            success = True
            for command in data['curl_command']:
                result = subprocess.run(command, shell=True, capture_output=True, text=True)
                if "error" in result.stdout.lower() or "error" in result.stderr.lower():
                    st.write(f"Command: {command}")
                    st.write(f"Return code: {result.returncode}")
                    st.write(f"Output: {result.stdout}")
                    st.write(f"Error: {result.stderr}")
                    success = False
            if success:
                st.success("Az összes üzenet sikeresen elküldve!")
            else:
                st.error("Hiba történt az üzenetek küldése közben.")

# Function to verify user login
def login(username, password):
    if username in USER_CREDENTIALS and USER_CREDENTIALS[username] == password:
        return True
    return False

# Function to extract the second part of the name, handling empty cells
def get_first_name(full_name):
    if pd.notna(full_name):
        parts = full_name.split()
        if len(parts) > 1:
            return parts[1]
    return ""

# Function to convert phone number to required format, handling empty cells
def convert_phone_number(phone):
    if pd.notna(phone):
        phone = str(phone).split('.')[0]  # Remove any decimal points
        if phone.startswith('06'):
            return phone.replace('06', '+36', 1)
        elif phone.startswith('6'):
            return '+36' + phone[1:]
    return ""

# Function to format the datetime, handling invalid or empty values
def format_datetime(dt):
    try:
        return pd.to_datetime(dt).strftime('%H:%M')
    except ValueError:
        return ""

# Function to construct the curl command with URL encoding
def construct_curl_command(row, message_template):
    if message_template == 'donation':
        message = f"{row['first_name']}, ne felejtsd, hogy a holnapi nap várunk téged vérplazma donációra az OkosPlazmába, {row['formatted_time']}-ra! Mátészalka, Bajcsy-Zsilinszky u. 17."
    else:
        message = f"{row['first_name']}, holnap várunk alkalmassági vizsgálatra az OkosPlazmába {row['formatted_time']}-ra, és 5.000 Ft-ot adunk a sikeres vizsgálatért! Bajcsy-Zsilinszky u. 17."
    
    encoded_message = urllib.parse.quote(message)
    return f'curl -s "https://seeme.hu/gateway?key={CURL_KEY}&message={encoded_message}&number={row["formatted_phone"]}&callback=4,6,7&format=json"'