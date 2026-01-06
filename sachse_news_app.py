import streamlit as st
import requests
from bs4 import BeautifulSoup
from pypdf import PdfReader
from io import BytesIO
from duckduckgo_search import DDGS
from openai import OpenAI
import traceback
from datetime import datetime

# Check if Selenium is available
try:
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.chrome.service import Service
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
        
        if debug:
            debug_info = f"URL: {url}\n\n"
            debug_info += f"Response Status: {response.status_code}\n\n"
            debug_info += "=== All links found ===\n"
            all_links = soup.find_all('a', href=True)
            debug_info += f"Total links: {len(all_links)}\n\n"
            
            civicclerk_links = [link for link in all_links if 'civicclerk' in link.get('href', '').lower()]
            debug_info += f"\n=== CivicClerk links ({len(civicclerk_links)}) ===\n"
            for idx, link in enumerate(civicclerk_links[:10]):
                debug_info += f"Link {idx}: {link.get_text(strip=True)[:100]} -> {link.get('href')}\n"
            
            pdf_links = [link for link in all_links if '.pdf' in link.get('href', '').lower()]
            debug_info += f"\n=== PDF links ({len(pdf_links)}) ===\n"
            for idx, link in enumerate(pdf_links[:10]):
                debug_info += f"PDF {idx}: {link.get_text(strip=True)[:100]} -> {link.get('href')}\n"
            
            return None, debug_info
        
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
                    max_pages = min(50, len(reader.pages))
                    for i in range(max_pages):
                        text += reader.pages[i].extract_text()
                    
                    if len(text.strip()) > 100:
                        return text[:15000], None
                except:
                    continue
        
        return None, "City Council uses CivicClerk which requires JavaScript. The site shows agendas at: https://sachsetx.portal.civicclerk.com/ but cannot be scraped with basic tools."
    except Exception as e:
        error_details = f"{str(e)}\n\nTraceback:\n{traceback.format_exc()}"
        return None, error_details


def scrape_school_board_agenda(debug=False):
    """Scrape the latest Garland ISD School Board meeting agenda."""
    try:
        url = "https://meetings.boardbook.org/public/Organization/1084"
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        if debug:
            debug_info = f"URL: {url}\n\n"
            debug_info += f"Response Status: {response.status_code}\n\n"
            debug_info += "=== All Agenda links found ===\n"
            all_links = soup.find_all('a', href=True)
            agenda_links = [link for link in all_links if 'Agenda' in link.get_text()]
            debug_info += f"Found {len(agenda_links)} agenda links\n\n"
            for idx, link in enumerate(agenda_links[:10]):
                debug_info += f"Agenda {idx}: {link.get_text(strip=True)} -> {link.get('href')}\n"
            
            return None, debug_info
        
        all_links = soup.find_all('a', href=True)
        
        for link in all_links:
            link_text = link.get_text(strip=True)
            if link_text == 'Agenda':
                agenda_url = link.get('href')
                if not agenda_url.startswith('http'):
                    agenda_url = f"https://meetings.boardbook.org{agenda_url}"
                
                agenda_response = requests.get(agenda_url, timeout=30)
                agenda_response.raise_for_status()
                agenda_soup = BeautifulSoup(agenda_response.content, 'html.parser')
                
                pdf_links = agenda_soup.find_all('a', href=True)
                
                for pdf_link in pdf_links:
                    href = pdf_link.get('href', '')
                    pdf_text = pdf_link.get_text(strip=True).lower()
                    
                    if '.pdf' in href.lower() or 'download' in pdf_text or 'pdf' in pdf_text:
                        pdf_url = href
                        if not pdf_url.startswith('http'):
                            pdf_url = f"https://meetings.boardbook.org{pdf_url}"
                        
                        pdf_response = requests.get(pdf_url, timeout=60)
                        pdf_response.raise_for_status()
                        
                        if pdf_response.headers.get('content-type', '').lower().startswith('application/pdf'):
                            pdf_file = BytesIO(pdf_response.content)
                            reader = PdfReader(pdf_file)
                            
                            text = ""
                            max_pages = min(50, len(reader.pages))
                            for i in range(max_pages):
                                text += reader.pages[i].extract_text()
                            
                            if len(text.strip()) > 100:
                                return text[:15000], None
                
                main_content = agenda_soup.find('div', class_='main-content') or agenda_soup.find('main')
                if main_content:
                    text = main_content.get_text(separator='\n', strip=True)
                    if len(text) > 100:
                        return text[:15000], None
        
        return None, "No School Board agenda with downloadable content found"
    except Exception as e:
        error_details = f"{str(e)}\n\nTraceback:\n{traceback.format_exc()}"
        return None, error_details


def search_sports_news(debug=False):
    """Search for Sachse High School Mustangs sports news via MaxPreps."""
    try:
        maxpreps_url = "https://www.maxpreps.com/tx/sachse/sachse-mustangs/"
        
        response = requests.get(maxpreps_url, timeout=30, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        if debug:
            debug_info = f"MaxPreps URL: {maxpreps_url}\n\n"
            debug_info += f"Response Status: {response.status_code}\n\n"
            debug_info += f"Page title: {soup.find('title').get_text() if soup.find('title') else 'N/A'}\n\n"
            
            page_text = soup.get_text()
            if "Sachse Scores" in page_text:
                debug_info += "Found 'Sachse Scores' section\n"
            if "Today" in page_text:
                debug_info += "Found 'Today' games\n"
            
            return None, debug_info[:2000]
        
        # Parse text content for game information
        page_text = soup.get_text(separator='\n')
        lines = [line.strip() for line in page_text.split('\n') if line.strip()]
        
        combined_text = "Sachse High School Mustangs - Recent & Upcoming Games:\n\n"
        
        # Track what we're parsing
        in_scores_section = False
        games_found = 0
        current_game = []
        
        for i, line in enumerate(lines):
            # Start capturing when we hit the scores section
            if "Sachse Scores" in line:
                in_scores_section = True
                continue
            
            # Stop if we've moved past the scores section
            if in_scores_section and any(x in line for x in ["Latest Videos", "Pro Photos", "School Info"]):
                break
            
            if in_scores_section and games_found < 15:
                # Detect sport types (V. = Varsity, JV. = Junior Varsity, F. = Freshman)
                if any(sport in line for sport in ['V. Girls Basketball', 'V. Boys Basketball', 'V. Girls Soccer', 'V. Boys Soccer', 'V. Football', 'JV.', 'F.']):
                    if current_game:
                        # Save previous game
                        combined_text += " | ".join(current_game) + "\n"
                        games_found += 1
                        current_game = []
                    current_game.append(line)
                    
                # Capture opponent info
                elif line and len(line) > 2 and not line.isdigit() and current_game:
                    # Skip pure time indicators
                    if 'pm' not in line.lower() and 'am' not in line.lower():
                        if len(current_game) < 4:  # Limit details per game
                            current_game.append(line)
                
                # Capture game time/date
                elif ('Today' in line or 'pm' in line.lower() or 'am' in line.lower() or '/' in line) and current_game:
                    current_game.append(line)
                    # Save complete game
                    combined_text += " | ".join(current_game) + "\n\n"
                    games_found += 1
                    current_game = []
        
        # Add any remaining game
        if current_game:
            combined_text += " | ".join(current_game) + "\n"
        
        if len(combined_text) > 200:
            return combined_text[:8000], None
        
        # Fallback: return generic message with link
        return None, "Unable to parse game information automatically. View schedule at: https://www.maxpreps.com/tx/sachse/sachse-mustangs/"
        
    except Exception as e:
        error_details = f"{str(e)}\n\nTraceback:\n{traceback.format_exc()}"
        error_details += "\n\nView games manually at: https://www.maxpreps.com/tx/sachse/sachse-mustangs/"
        return None, error_details


def summarize_with_llm(client, content, section_type):
    """Use OpenAI to summarize content based on section type."""
    prompts = {
        "city_council": """You are a local news writer. Summarize the following City Council agenda into a "City Hall Updates" section.

Focus on:
- Tax-related items
- Zoning changes or development projects
- Major contracts or expenditures
- Decisions that affect residents

Write in a clear, conversational style. Keep it concise (200-300 words). Use bullet points for key items.

Content:
{content}""",
        
        "school_board": """You are a local education reporter. Summarize the following School Board agenda into a "School Board Updates" section.

Focus on:
- School calendar changes
- Bond projects or facility updates
- Policy decisions affecting Sachse schools specifically
- Budget or staffing matters

Write in a clear, conversational style. Keep it concise (200-300 words). Use bullet points for key items.

Content:
{content}""",
        
        "sports": """You are a high school sports reporter. Write a "Mustang Sports Minute" based on the following game information about Sachse High School athletics.

Focus on:
- Standout performances (if mentioned)
- Upcoming important games this week
- Overall team records and momentum
- Use bullet points to list recent game dates and outcomes with scores

Organize into two sections:
1. **Recent Results** - Summarize recent game outcomes
2. **This Week's Schedule** 
- Use bullet points to list upcoming games
- Include: Day, opponent, time, and sport
- Format: "Day: Sport vs/@ Opponent - Time"

Write in an energetic, positive style. Keep it concise (150-250 words).

Content:
{content}"""
    }
    
    try:
        prompt = prompts[section_type].format(content=content)
        
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a professional local news writer creating content for a community newsletter."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=500
        )
        
        return response.choices[0].message.content
    except Exception as e:
        st.error(f"LLM error for {section_type}: {str(e)}")
        return None


def main():
    st.set_page_config(
        page_title="Sachse News Aggregator",
        page_icon="📰",
        layout="wide"
    )
    
    st.title("Sachse, TX - Local News Aggregator")
    st.markdown("*Automated weekly newsletter generation*")
    
    st.sidebar.header("Configuration")
    
    api_key = st.sidebar.text_input(
        "OpenAI API Key",
        type="password",
        help="Enter your OpenAI API key to generate summaries"
    )
    
    st.sidebar.markdown("---")
    st.sidebar.subheader("Select News Sources")
    
    run_city_council = st.sidebar.checkbox("City Council Updates", value=True)
    
    use_selenium = False
    uploaded_council_pdf = None
    if run_city_council:
        st.sidebar.markdown("**City Council Options:**")
        if SELENIUM_AVAILABLE:
            use_selenium = st.sidebar.checkbox(
                "Use Selenium (full automation)",
                value=True,
                help="Uses browser automation to handle JavaScript"
            )
        else:
            st.sidebar.info("Install Selenium for full automation: pip install selenium webdriver-manager")
        
        if not use_selenium:
            uploaded_council_pdf = st.sidebar.file_uploader(
                "Or upload Council PDF(s) manually",
                type=['pdf'],
                accept_multiple_files=True,
                help="Download from https://sachsetx.portal.civicclerk.com/"
            )
    
    run_school_board = st.sidebar.checkbox("School Board Updates", value=True)
    run_sports = st.sidebar.checkbox("Mustang Sports Minute", value=True)
    
    st.sidebar.markdown("---")
    
    debug_mode = st.sidebar.checkbox("Enable Debug Mode", value=False, help="Show detailed HTML structure for troubleshooting")
    
    st.sidebar.markdown("---")
    
    generate_button = st.sidebar.button("Generate Newsletter", type="primary", use_container_width=True)
    
    if generate_button:
        if not api_key:
            st.error("Please enter your OpenAI API key in the sidebar.")
            return
        
        if not (run_city_council or run_school_board or run_sports):
            st.warning("Please select at least one news source.")
            return
        
        client = OpenAI(api_key=api_key)
        
        newsletter_sections = []
        newsletter_sections.append(f"# Sachse Weekly Newsletter")
        newsletter_sections.append(f"*Generated on {datetime.now().strftime('%B %d, %Y')}*\n")
        
        council_error = None
        school_error = None
        sports_error = None
        
        if run_city_council:
            with st.status("Processing City Council agenda...", expanded=True) as status:
                council_text = None
                
                if uploaded_council_pdf:
                    st.write(f"Processing {len(uploaded_council_pdf)} uploaded PDF(s)...")
                    try:
                        combined_text = ""
                        for pdf_file_upload in uploaded_council_pdf:
                            pdf_file = BytesIO(pdf_file_upload.read())
                            reader = PdfReader(pdf_file)
                            max_pages = min(50, len(reader.pages))
                            for i in range(max_pages):
                                combined_text += reader.pages[i].extract_text()
                        
                        if len(combined_text.strip()) > 100:
                            council_text = combined_text[:15000]
                    except Exception as e:
                        council_error = f"Error processing uploaded PDF: {str(e)}"
                else:
                    st.write("Attempting basic scraping...")
                    council_text, council_error = scrape_city_council_agenda(debug=debug_mode)
                
                if council_text:
                    st.write("Generating summary with AI...")
                    summary = summarize_with_llm(client, council_text, "city_council")
                    if summary:
                        newsletter_sections.append("## City Hall Updates\n")
                        newsletter_sections.append(summary + "\n")
                        status.update(label="City Council: Complete", state="complete")
                    else:
                        newsletter_sections.append("## City Hall Updates\n")
                        newsletter_sections.append("*Unable to generate summary at this time.*\n")
                        status.update(label="City Council: Summary failed", state="error")
                else:
                    newsletter_sections.append("## City Hall Updates\n")
                    if debug_mode:
                        newsletter_sections.append("*Debug mode enabled - see details below*\n")
                        status.update(label="City Council: Debug Info Ready", state="complete")
                    else:
                        newsletter_sections.append("*No agenda PDFs found on the main website. Please upload a PDF manually from [CivicClerk](https://sachsetx.portal.civicclerk.com/)*\n")
                        status.update(label="City Council: Manual upload needed", state="error")
            
            if council_error:
                with st.expander("View City Council Debug/Error Details"):
                    st.code(council_error, language="text")
        
        if run_school_board:
            with st.status("Scraping School Board agenda...", expanded=True) as status:
                st.write("Fetching latest meeting documents...")
                school_text, school_error = scrape_school_board_agenda(debug=debug_mode)
                
                if school_text:
                    st.write("Generating summary with AI...")
                    summary = summarize_with_llm(client, school_text, "school_board")
                    if summary:
                        newsletter_sections.append("## School Board Updates\n")
                        newsletter_sections.append(summary + "\n")
                        status.update(label="School Board: Complete", state="complete")
                    else:
                        newsletter_sections.append("## School Board Updates\n")
                        newsletter_sections.append("*Unable to generate summary at this time.*\n")
                        status.update(label="School Board: Summary failed", state="error")
                else:
                    newsletter_sections.append("## School Board Updates\n")
                    if debug_mode:
                        newsletter_sections.append("*Debug mode enabled - see details below*\n")
                        status.update(label="School Board: Debug Info Ready", state="complete")
                    else:
                        newsletter_sections.append("*Could not retrieve School Board data.*\n")
                        status.update(label="School Board: Data retrieval failed", state="error")
            
            if school_error:
                with st.expander("View School Board Debug/Error Details"):
                    st.code(school_error, language="text")
        
        if run_sports:
            with st.status("Searching for sports news...", expanded=True) as status:
                st.write("Querying DuckDuckGo for Mustang sports...")
                sports_text, sports_error = search_sports_news(debug=debug_mode)
                
                if sports_text:
                    st.write("Generating sports report with AI...")
                    summary = summarize_with_llm(client, sports_text, "sports")
                    if summary:
                        newsletter_sections.append("## Mustang Sports Minute\n")
                        newsletter_sections.append(summary + "\n")
                        status.update(label="Sports: Complete", state="complete")
                    else:
                        newsletter_sections.append("## Mustang Sports Minute\n")
                        newsletter_sections.append("*Unable to generate sports report at this time.*\n")
                        status.update(label="Sports: Summary failed", state="error")
                else:
                    newsletter_sections.append("## Mustang Sports Minute\n")
                    if debug_mode:
                        newsletter_sections.append("*Debug mode enabled - see details below*\n")
                        status.update(label="Sports: Debug Info Ready", state="complete")
                    else:
                        newsletter_sections.append("*Could not retrieve sports data.*\n")
                        status.update(label="Sports: Data retrieval failed", state="error")
            
            if sports_error:
                with st.expander("View Sports Debug/Error Details"):
                    st.code(sports_error, language="text")
        
        newsletter_content = "\n".join(newsletter_sections)
        
        st.markdown("---")
        st.subheader("Your Newsletter")
        st.markdown(newsletter_content)
        
        st.download_button(
            label="Download Newsletter.md",
            data=newsletter_content,
            file_name=f"sachse_newsletter_{datetime.now().strftime('%Y%m%d')}.md",
            mime="text/markdown"
        )
    
    else:
        st.info("Configure your settings in the sidebar and click 'Generate Newsletter' to start.")
        
        st.markdown("""
        ### About This Tool
        
        This application automatically aggregates local news from three sources:
        
        1. **City Council Updates** - Summarizes the latest City Council meeting agenda
        2. **School Board Updates** - Summarizes Garland ISD Board meetings
        3. **Mustang Sports Minute** - Compiles recent Sachse High School sports news
        
        The AI will generate concise, readable summaries focused on information relevant to Sachse residents.
        """)


if __name__ == "__main__":
    main()