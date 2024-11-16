import streamlit as st
import pandas as pd
import requests
import openai
from ratelimit import limits, sleep_and_retry
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from dotenv import load_dotenv  # Import dotenv to load environment variables
import os



OPENAI_API_KEY =st.secrets['OPENAI_API_KEY']
GOOGLE_API_KEY = st.secrets['GOOGLE_API_KEY']
SERPAPI_API_KEY =st.secrets['SERPAPI_API_KEY']
GROQ_API_KEY = st.secrets['GROQ_API_KEY']


# Set OpenAI API key
openai.api_key = OPENAI_API_KEY  # Ensure your OpenAI API key is securely stored()

# Google Sheets authentication
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']

# Function to authenticate Google Sheets
def authenticate_google_sheets():
    creds = None
    if os.path.exists('sheets.json'):
        creds = service_account.Credentials.from_service_account_file('sheets.json', scopes=SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file('token.json', SCOPES)
            creds = flow.run_local_server(port=3000)
    return creds

@sleep_and_retry
@limits(calls=60, period=60)
# Function to get Google Sheets data
def get_google_sheet_data(sheet_id, range_name):
    try:
        service = build('sheets', 'v4', developerKey=GOOGLE_API_KEY)
        sheet = service.spreadsheets()
        result = sheet.values().get(spreadsheetId=sheet_id, range=range_name).execute()
        values = result.get('values', [])
        return pd.DataFrame(values[1:], columns=values[0])
    except HttpError as err:
        st.error(f"Error fetching Google Sheets data: {err}")
        return None


@sleep_and_retry
@limits(calls=60, period=60)
@st.cache_data(ttl=3600)
# Function to get search results using SerpAPI
def get_search_results(query):
    try:
        api_key = SERPAPI_API_KEY 
        url = f"https://serpapi.com/search?q={query}&api_key={api_key}"
        response = requests.get(url)
        return response.json()
    except requests.exceptions.RequestException as e:
        st.error(f"Error in SerpAPI request: {e}")
        return {}



@sleep_and_retry
@limits(calls=5, period=10)
# Function to extract information from results using Groq API
def extract_information_from_results(results, query):
    # Define the messages as expected by the Groq API
    
    messages = [
        {"role": "user", "content": f"Extract the information for {query} from the following web results: {results}.
        Extract only the requested information from the following web results.
        If the user asks for email addresses, return only the email addresses in a python list, with no extra context, labels, or explanations.
        Just provide the response to the query asked without any additional statements pointing to the response
        .Don't write any unnecessary statements not relevant to the query asked."}
    ]

    # Define the payload with the model and messages
    payload = {
        "model": "llama3-8b-8192",  # Update if Groq offers other model choices
        "messages": messages
    }

    # Set up the headers with the Groq API key for authorization
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {GROQ_API_KEY}"
    }

    # Send the POST request to Groq's API endpoint
    response = requests.post("https://api.groq.com/openai/v1/chat/completions", json=payload, headers=headers)

    # Check if the response was successful
    if response.status_code == 200:
        result = response.json()
        extracted_content=result.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
        if not extract_information_from_response(extracted_content,query):
            return "No results found"
        else:
            return extract_information_from_response(extracted_content,query)
        
    else:
        # Handle errors
        print(f"Error: {response.status_code} - {response.text}")
        return None




@sleep_and_retry
@limits(calls=5, period=10)
def extract_information_from_response(response, query):
    # Define the messages as expected by the Groq API
    chat_llm=ChatOpenAI(temperature=0.0)
    template_string = """
    You are an information extractor. Analyse the query: {query} and the response: {response}.
    Your task is to extract the required attributes from the response text, omitting irrelevant labels and context.
    For example, if the query is "Get the email address of Ford" and the response text is "Here is the available information, the emails are ford@ford.com.",
    Your response should be only ford@ford.com AND NO OTHER TEXT. If it's not found, return the string "No results found".Separate multiple results by commas
    """
    prompt_template=ChatPromptTemplate.from_template(template_string)
    res=prompt_template.format_messages(response=response,query=query)
    final_response=chat_llm(res)
    return final_response.content



def normalize_column(data_column):
    return [x if isinstance(x, list) else [x] for x in data_column]

# Function to update Google Sheets with extracted data (batch processing)
def update_google_sheet(sheet_id, data, sheet_name, range, creds):
    try:
        service = build('sheets', 'v4', credentials=creds)
        sheet = service.spreadsheets()
        range = f"'{sheet_name}'!{range}"
        body = {"values": data}
        result = sheet.values().update(spreadsheetId=sheet_id, range=range, valueInputOption="RAW", body=body).execute()
        return result
    except HttpError as err:
        st.error(f"Error updating Google Sheet: {err}")
        return None


def update_selected_rows(sheet_id, selected_data, sheet_name, write_range, creds):
    try:
        service = build('sheets', 'v4', credentials=creds)
        sheet = service.spreadsheets()
        body = {"values": selected_data}
        result = sheet.values().update(
            spreadsheetId=sheet_id, range=f"{sheet_name}!{write_range}", 
            valueInputOption="RAW", body=body
        ).execute()
        return result
    except HttpError as err:
        st.error(f"Error updating Google Sheet: {err}")
        return None
    
    
# Streamlit UI for file upload or Google Sheets connection
st.title("AI Agent for Web Search and Information Extraction")

# File Upload
uploaded_file = st.file_uploader("Choose a CSV file", type=["csv"])
google_sheet_id = st.text_input("Google Sheet ID")
sheet_name = st.text_input("Sheet Name (e.g., Sheet1)")
read_range = st.text_input("Read-Range (e.g., A1:B10)")
write_range = st.text_input("Write-Range (e.g., A1:B10)")

# Initialize df as None
df = None
st.session_state.column_name = None
st.session_state.data=None

def convert_df(data):
    
        df_with_selections = data.copy()
        df_with_selections.insert(0, "Select", False)

        # Add a 'Select All' checkbox at the top of the 'Select' column
        select_all = st.checkbox("Select All Rows", value=False)

        # If 'Select All' is checked, set all values in the 'Select' column to True
        if select_all:
            df_with_selections["Select"] = True
        else:
            df_with_selections["Select"] = False

        # Editable data with checkboxes
        edited_data = st.data_editor(
            df_with_selections, use_container_width=True,
            hide_index=True, disabled=data.columns
        )

        # Filter selected rows for further processing
        st.session_state.data = edited_data[edited_data.Select]
        df = st.session_state.data
        
# Google Sheets connection
if google_sheet_id and read_range and sheet_name:
    try:
        # Fetch data from Google Sheets
        data = get_google_sheet_data(google_sheet_id, read_range)
        df=data
        convert_df(data)
    except Exception as err:
        st.error(f"Error fetching Google Sheets data: {err}")
        
elif uploaded_file:
    df = pd.read_csv(uploaded_file)
    convert_df(df)

# Ensure column name is selected
if df is not None:
    available_columns = [col for col in df.columns if col != "Select"]  # Exclude "Select" column
    st.session_state.column_name = st.selectbox("Select the column with entities (e.g., company names)",available_columns)
    st.write(f"Selected column: {st.session_state.column_name}")
else:
    st.warning("Please upload a CSV file or connect to a Google Sheet.")

# Dynamic Query Input
query_template = st.text_input("Enter your search query", "Get me the email address of {column_name}")

# Web search and information extraction (batch processing for large datasets)
if st.button("Start Search and Extraction") and df is not None and st.session_state.column_name:
    extracted_data = []

    # Process only selected rows (this is where the selection matters)
    for index, row in st.session_state.data.iterrows():
        print(st.session_state.data)
        entity = row[st.session_state.column_name]
        query = query_template.replace("{column_name}", entity)
        print(query)

        # Get search results
        results = get_search_results(query)
        search_results = results.get('organic_results', [])
        result_text = "\n".join([r['snippet'] for r in search_results if 'snippet' in r])

        # Extract information from results
        extracted_info = extract_information_from_results(result_text, query)
        extracted_data.append([entity, extracted_info])

    st.session_state.extracted_data = extracted_data
    # Display extracted data in a table
    extracted_df = pd.DataFrame(extracted_data, columns=["Entity", "Extracted Info"])
    st.write("Extracted Data:", extracted_df)

    # Option to download extracted data as CSV
    csv = extracted_df.to_csv(index=False)
    st.download_button("Download CSV", csv, "extracted_data.csv")

# Handle previously extracted data
if "extracted_data" in st.session_state and st.session_state.extracted_data:
    extracted_df = pd.DataFrame(st.session_state.extracted_data, columns=["Entity", "Extracted Info"])
    


    # Display "Update Google Sheet" button only if data is extracted
    if st.button("Update Google Sheet with Selected Rows"):
        selected_data = extracted_df.values.tolist()

        if selected_data:
            creds = authenticate_google_sheets()
            if creds and google_sheet_id and write_range:
                response = update_selected_rows(google_sheet_id, selected_data, sheet_name, write_range, creds)
                if response:
                    st.success("Google Sheet updated successfully.")
                else:
                    st.error("Failed to update Google Sheet.")
        else:
            st.warning("No rows selected to update.")

