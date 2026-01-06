import streamlit as st
import requests
from bs4 import BeautifulSoup
from pypdf import PdfReader
from io import BytesIO
from duckduckgo_search import DDGS
from openai import OpenAI
import traceback
from datetime import datetime
import re

def scrape_city_council_agenda():
    """Scrape the latest City Council meeting agenda packet."""
    try:
        url = "https://www.cityofsachse.com/328/Agendas-Minutes-and-Videos"
        response = requests.get(url, timeout=30)
        soup = BeautifulSoup(response.content, 'html.parser')
        
        all_links = soup.find_all('a', href=True)
        for link in all_links:
            if 'agenda' in link.get_text().lower() and '.pdf' in link.get('href', '').lower():
                pdf_url = "https://www.cityofsachse.com" + link.get('href')
                pdf_response = requests.get(pdf_url, timeout=60)
                reader = PdfReader(BytesIO(pdf_response.content))
                text = ""
                for i in range(min(30, len(reader.pages))):
                    text += reader.pages[i].extract_text()
                return text[:10000]
        return None
    except Exception as e:
        return None

def scrape_school_board_agenda():
    """Scrape the latest Garland ISD School Board meeting agenda."""
    try:
        url = "https://meetings.boardbook.org/public/Organization/1084"
        response = requests.get(url, timeout=30)
        soup = BeautifulSoup(response.content, 'html.parser')
        
        for link in soup.find_all('a', href=True):
            if 'Agenda' in link.get_text():
                agenda_url = "https://meetings.boardbook.org" + link.get('href')
                agenda_resp = requests.get(agenda_url, timeout=30)
                agenda_soup = BeautifulSoup(agenda_resp.content, 'html.parser')
                # Look for PDF
                for pdf_link in agenda_soup.find_all('a', href=True):
                    if '.pdf' in pdf_link.get('href', '').lower():
                        final_url = "https://meetings.boardbook.org" + pdf_link.get('href')
                        pdf_resp = requests.get(final_url, timeout=60)
                        reader = PdfReader(BytesIO(pdf_resp.content))
                        text = ""
                        for i in range(min(30, len(reader.pages))):
                            text += reader.pages[i].extract_text()
                        return text[:10000]
        return None
    except Exception as e:
        return None

def search_sports_news():
    """Grab RAW text from MaxPreps and let AI parse it."""
    try:
        url = "https://www.maxpreps.com/tx/sachse/sachse-mustangs/events/"
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        response = requests.get(url, headers=headers, timeout=30)
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # KEY CHANGE: Just grab the raw text without trying to be smart
        # We only filter slightly to remove navigation/ads
        raw_text = soup.get_text(separator='\n')
        
        # Filter: Only keep lines that might be relevant (Dates, Sports, Teams, Times)
        relevant_lines = []
        for line in raw_text.split('\n'):
            clean = line.strip()
            if len(clean) > 2: # Skip empty/short lines
                # Keep lines with numbers (dates/times) or Sport keywords
                if any(char.isdigit() for char in clean) or \
                   any(word in clean.lower() for word in ['basketball', 'soccer', 'football', 'baseball', 'volleyball', 'vs', '@', 'sachse', 'mustangs']):
                    relevant_lines.append(clean)
        
        # Return a chunk of relevant text
        return "\n".join(relevant_lines)[:15000] 
        
    except Exception as e:
        return f"Error: {str(e)}"

def summarize_with_llm(client, content, section_type):
    if not content: return None
    
    prompts = {
        "city_council": "Summarize this City Council agenda into bullet points focusing on taxes, zoning, and resident impact.",
        "school_board": "Summarize this School Board agenda into bullet points focusing on calendar, bonds, and student impact.",
        "sports": """
        You are a Sports Editor. I am giving you RAW, MESSY text scraped from a schedule website.
        
        Your Job:
        1. Read through the noise to find the "Upcoming Games" schedule.
        2. Format it into a clean list.
        3. IGNORE past games (games with scores). Look for future dates.
        
        Format the output exactly like this:
        
        **Mustang Sports Minute**
        [Write a 2-sentence intro about the team's season so far]
        
        **This Week's Schedule**
        * **Mon 1/6:** Boys Varsity Basketball vs Naaman Forest @ 6:00 PM
        * **Tue 1/7:** Girls Soccer @ Rowlett @ 7:00 PM
        
        (If a specific detail like Time or Opponent is truly missing in the text, write 'TBD')
        
        RAW TEXT TO PROCESS:
        {content}
        """
    }
    
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a helpful news aggregator assistant."},
                {"role": "user", "content": prompts[section_type].format(content=content)}
            ],
            temperature=0.5
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"AI Error: {str(e)}"

def main():
    st.set_page_config(page_title="Sachse TLDR", page_icon="📰")
    st.title("Sachse TLDR: The Weekly Brief")
    
    with st.sidebar:
        api_key = st.text_input("OpenAI API Key", type="password")
        st.markdown("---")
        run_city = st.checkbox("City Council", value=True)
        run_school = st.checkbox("School Board", value=True)
        run_sports = st.checkbox("Sports", value=True)
        st.markdown("---")
        btn = st.button("Generate Newsletter", type="primary")

    if btn and api_key:
        client = OpenAI(api_key=api_key)
        st.write("### 📰 Generating your Sachse Update...")
        
        # 1. City Council
        if run_city:
            with st.status("Checking City Hall..."):
                data = scrape_city_council_agenda()
                if data:
                    st.markdown(summarize_with_llm(client, data, "city_council"))
                else:
                    st.error("No recent City Council agenda found.")

        # 2. School Board
        if run_school:
            with st.status("Checking School Board..."):
                data = scrape_school_board_agenda()
                if data:
                    st.markdown(summarize_with_llm(client, data, "school_board"))
                else:
                    st.warning("No recent School Board agenda found.")

        # 3. Sports
        if run_sports:
            with st.status("Checking Sports..."):
                data = search_sports_news()
                if data:
                    st.markdown(summarize_with_llm(client, data, "sports"))
                else:
                    st.error("Could not fetch sports data.")

if __name__ == "__main__":
    main()