import streamlit as st
import requests
from bs4 import BeautifulSoup
from pypdf import PdfReader
from io import BytesIO
from openai import OpenAI
from datetime import datetime

# Check if Selenium is available (Optional)
try:
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.chrome.options import Options
    from webdriver_manager.chrome import ChromeDriverManager
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False


def scrape_city_council_agenda(debug=False, use_selenium=False):
    """Scrape the latest City Council meeting agenda packet."""
    try:
        url = "https://www.cityofsachse.com/328/Agendas-Minutes-and-Videos"
        response = requests.get(url, timeout=30, allow_redirects=True)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        all_links = soup.find_all('a', href=True)
        
        for link in all_links:
            href = link.get('href', '')
            link_text = link.get_text(strip=True).lower()
            
            if '.pdf' in href.lower() and ('agenda' in link_text or 'packet' in link_text):
                pdf_url = href
                if not pdf_url.startswith('http'):
                    pdf_url = f"https://www.cityofsachse.com{pdf_url}"
                
                try:
                    pdf_response = requests.get(pdf_url, timeout=60)
                    pdf_response.raise_for_status()
                    
                    pdf_file = BytesIO(pdf_response.content)
                    reader = PdfReader(pdf_file)
                    
                    text = ""
                    max_pages = min(30, len(reader.pages))
                    for i in range(max_pages):
                        text += reader.pages[i].extract_text()
                    
                    if len(text.strip()) > 100:
                        return text[:15000], None
                except:
                    continue
        
        return None, "City Council uses CivicClerk. Please upload PDF manually or check https://sachsetx.portal.civicclerk.com/"
    except Exception as e:
        return None, str(e)


def scrape_school_board_agenda(debug=False):
    """Scrape the latest Garland ISD School Board meeting agenda."""
    try:
        url = "https://meetings.boardbook.org/public/Organization/1084"
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        all_links = soup.find_all('a', href=True)
        
        for link in all_links:
            link_text = link.get_text(strip=True)
            if link_text == 'Agenda':
                agenda_url = link.get('href')
                if not agenda_url.startswith('http'):
                    agenda_url = f"https://meetings.boardbook.org{agenda_url}"
                
                agenda_response = requests.get(agenda_url, timeout=30)
                agenda_soup = BeautifulSoup(agenda_response.content, 'html.parser')
                
                pdf_links = agenda_soup.find_all('a', href=True)
                
                for pdf_link in pdf_links:
                    href = pdf_link.get('href', '')
                    if '.pdf' in href.lower() or 'download' in pdf_link.get_text(strip=True).lower():
                        pdf_url = href
                        if not pdf_url.startswith('http'):
                            pdf_url = f"https://meetings.boardbook.org{pdf_url}"
                        
                        pdf_response = requests.get(pdf_url, timeout=60)
                        if pdf_response.headers.get('content-type', '').lower().startswith('application/pdf'):
                            pdf_file = BytesIO(pdf_response.content)
                            reader = PdfReader(pdf_file)
                            text = ""
                            max_pages = min(30, len(reader.pages))
                            for i in range(max_pages):
                                text += reader.pages[i].extract_text()
                            if len(text.strip()) > 100:
                                return text[:15000], None
                                
                main = agenda_soup.find('div', class_='main-content') or agenda_soup.find('main')
                if main:
                    return main.get_text(separator='\n')[:15000], None
        
        return None, "No School Board agenda found."
    except Exception as e:
        return None, str(e)


def search_sports_news(debug=False):
    """
    AI-FIRST APPROACH (UNFILTERED):
    Grab EVERY piece of text from the page. Do not filter lines.
    This ensures times like '6:00' (without PM) are not deleted.
    """
    try:
        events_url = "https://www.maxpreps.com/tx/sachse/sachse-mustangs/events/"
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        
        response = requests.get(events_url, headers=headers, timeout=30)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Grab strictly text, separating by newline
        # Use a distinctive separator so the AI knows where lines break
        full_text = soup.get_text(separator='\n')
        
        # Clean up excessive whitespace but KEEP ALL CONTENT
        lines = [line.strip() for line in full_text.split('\n') if len(line.strip()) > 0]
        
        # Rejoin with newlines
        final_text = "\n".join(lines)
        
        # Limit to 30,000 chars (approx 7k tokens) - GPT-4o can handle this easily
        return final_text[:30000], None 
        
    except Exception as e:
        return None, str(e)


def summarize_with_llm(client, content, section_type):
    """Use OpenAI to summarize content."""
    
    if section_type == "city_council":
        prompt = f"""You are a local news reporter. Summarize this City Council agenda.
        Focus on taxes, zoning, and resident impact. Keep it to 3-4 bullet points.
        Content: {content}"""

    elif section_type == "school_board":
        prompt = f"""You are an education reporter. Summarize this School Board agenda.
        Focus on calendar changes, bonds, and student impact. Keep it to 3-4 bullet points.
        Content: {content}"""

    elif section_type == "sports":
        # UPDATED PROMPT: AGGRESSIVE TIME FINDING
        prompt = f"""You are a Sports Editor. I am providing you with RAW text from a schedule website.

        **Your Goal:** Extract the upcoming game schedule into a clean Markdown table.

        **CRITICAL RULES:**
        1. **Find the Time:** The time might be listed simply as "6:00" or "7:30" without "pm". It might be inside a "Preview" line. LOOK HARD FOR NUMBERS formatted like times.
        2. **Infer Opponents:** If you see "vs" or "@" followed by a name, that is the opponent.
        3. **Future Only:** Ignore past games with scores. Only list upcoming dates.
        
        **Output Format:**
        
        **Mustang Sports Minute**
        [Write 2 sentences about the team's momentum]

        **This Week's Schedule**
        
        | Date | Sport | Opponent | Time |
        |---|---|---|---|
        | [Date] | [Sport] | [Opponent] | [Time] |

        **Raw Text:**
        {content}"""
    
    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are a professional local news writer."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3, 
            max_tokens=1500
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"Error generating summary: {str(e)}"


def main():
    st.set_page_config(page_title="Sachse News Aggregator", page_icon="📰", layout="wide")
    
    st.title("Sachse, TX - Local News Aggregator")
    st.markdown("*Automated weekly newsletter generation*")
    
    st.sidebar.header("Configuration")
    api_key = st.sidebar.text_input("OpenAI API Key", type="password")
    
    st.sidebar.markdown("---")
    run_council = st.sidebar.checkbox("City Council", value=True)
    
    uploaded_council_pdf = None
    if run_council:
        uploaded_council_pdf = st.sidebar.file_uploader("Or upload Council PDF manually", type=['pdf'], accept_multiple_files=True)

    run_school = st.sidebar.checkbox("School Board", value=True)
    run_sports = st.sidebar.checkbox("Sports", value=True)
    
    st.sidebar.markdown("---")
    debug_mode = st.sidebar.checkbox("Debug Mode", value=False)
    
    if st.sidebar.button("Generate Newsletter", type="primary"):
        if not api_key:
            st.error("Please enter your OpenAI API Key.")
            return
            
        client = OpenAI(api_key=api_key)
        newsletter = [f"# Sachse Weekly Newsletter\n*{datetime.now().strftime('%B %d, %Y')}*\n"]
        
        # --- CITY COUNCIL ---
        if run_council:
            with st.status("Processing City Council..."):
                text = None
                if uploaded_council_pdf:
                    text = ""
                    for pdf in uploaded_council_pdf:
                        reader = PdfReader(BytesIO(pdf.read()))
                        for page in reader.pages: text += page.extract_text()
                else:
                    text, err = scrape_city_council_agenda(debug=debug_mode)
                
                if text:
                    summary = summarize_with_llm(client, text, "city_council")
                    newsletter.append("## City Hall Updates\n" + summary + "\n")
                else:
                    newsletter.append("## City Hall Updates\n*No agenda found.*\n")
        
        # --- SCHOOL BOARD ---
        if run_school:
            with st.status("Processing School Board..."):
                text, err = scrape_school_board_agenda(debug=debug_mode)
                if text:
                    summary = summarize_with_llm(client, text, "school_board")
                    newsletter.append("## School Board Updates\n" + summary + "\n")
                else:
                    newsletter.append("## School Board Updates\n*No agenda found.*\n")

        # --- SPORTS ---
        if run_sports:
            with st.status("Processing Sports..."):
                text, err = search_sports_news(debug=debug_mode)
                if text:
                    summary = summarize_with_llm(client, text, "sports")
                    newsletter.append(summary + "\n")
                    if debug_mode: st.text_area("Raw Sports Text", text[:1000])
                else:
                    newsletter.append("## Mustang Sports Minute\n*Could not retrieve sports data.*\n")

        # --- FINAL OUTPUT ---
        st.markdown("---")
        full_content = "\n".join(newsletter)
        st.markdown(full_content)
        st.download_button("Download Newsletter", data=full_content, file_name="sachse_newsletter.md")

if __name__ == "__main__":
    main()