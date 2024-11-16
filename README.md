
# AI Extractor

This project allows you to interact with local csv file or Google Sheets and query data to fetch search results from SerpAPI and use them to extract relevant information.

## Features

- **Caching**: Responses from the SerpAPI are cached to reduce redundant API calls and improve performance.
- **Search Results Extraction**: Automatically extract relevant information (like links, titles, etc.) from the search results.
- **Rate Limiting**: Avoid unnecessary API calls by caching data, ensuring compliance with API rate limits.
- **Error Handling**: Gracefully handle errors from the SerpAPI API and notify the user.
- **Dynamic Querying**: Allows users to search for any query, and the results are displayed along with relevant extracted information.

## Prerequisites

Before setting up the project, ensure you have the following installed:

- Python 3.8 or higher
- Streamlit
- OAuth 2.0 credentials from Google console
- Service account credentials from Google console
- Google API Key 
- Google Cloud Project with Sheets API enabled

## Installation

### 1. Clone the Repository

Clone this repository to your local machine.

```bash
git clone https://github.com/ABW1729e/AI-Extractor.git
cd AI-Extractor
```
### 2.Setup environment and Install packages

```bash
python3 -m venv env
source env/bin/activate
pip install -r requirements.txt
```

### 3.Start app

```bash
streamlit run app.py
```
### App will be available at http://localhost:8501








## Environment Variables

To run this project, you will need to add the following environment variables to your .env file

`OPENAPI_API_KEY`  
`SERPAPI_API_KEY`  
`GROQ_API_KEY`  
`GOOGLE_API_KEY`



Save OAuth credentials as token.json and service account credentials as sheets.json in root of project
## Demo

Loom Video Link for Demo:
https://www.loom.com/share/6464dbce4c7049f49e919185cbffeddd?sid=70652ca9-f651-4e70-9714-b63598867a6e

