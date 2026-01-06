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


def scrape_city_council_agenda_selenium():
    """Scrape City Council agenda using Selenium (JavaScript rendering)."""
    if not SELENIUM_AVAILABLE:
        return None, "Selenium not installed. Install with: pip install selenium webdriver-manager"
    
    try:
        # Setup headless Chrome for Streamlit Cloud compatibility
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--disable-software-rasterizer")
        chrome_options.add_argument("--disable-extensions")
        chrome_options.add_argument("--disable-setuid-sandbox")
        chrome_options.add_argument("--remote-debugging-port=9222")
        
        # Try to use system Chrome on Streamlit Cloud
        chrome_options.binary_location = "/usr/bin/chromium"
        
        try:
            # Try without webdriver-manager first (for Streamlit Cloud)
            service = Service("/usr/bin/chromedriver")
            driver = webdriver.Chrome(service=service, options=chrome_options)
        except:
            # Fallback to webdriver-manager (for local)
            service = Service(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=chrome_options)
        
        try:
            # Navigate to CivicClerk portal
            url = "https://sachsetx.portal.civicclerk.com/"
            driver.get(url)
            
            # Wait for content to load
            wait = WebDriverWait(driver, 10)
            wait.until(EC.presence_of_element_located((By.TAG_NAME, "a")))
            
            # Find the first City Council meeting link
            links = driver.find_elements(By.TAG_NAME, "a")
            
            for link in links:
                link_text = link.text.lower()
                href = link.get_attribute("href") or ""
                
                if "city council" in link_text and "event" in href:
                    # Click the meeting link
                    meeting_url = href
                    driver.get(meeting_url)
                    
                    # Wait for page to load
                    wait.until(EC.presence_of_element_located((By.TAG_NAME, "a")))
                    
                    # Find PDF download links
                    pdf_links = driver.find_elements(By.TAG_NAME, "a")
                    
                    for pdf_link in pdf_links:
                        pdf_href = pdf_link.get_attribute("href") or ""
                        pdf_text = pdf_link.text.lower()
                        
                        if ".pdf" in pdf_href and ("agenda" in pdf_text or "packet" in pdf_text):
                            # Download the PDF
                            pdf_response = requests.get(pdf_href, timeout=60)
                            pdf_response.raise_for_status()
                            
                            pdf_file = BytesIO(pdf_response.content)
                            reader = PdfReader(pdf_file)
                            
                            text = ""
                            max_pages = min(50, len(reader.pages))
                            for i in range(max_pages):
                                text += reader.pages[i].extract_text()
                            
                            if len(text.strip()) > 100:
                                return text[:15000], None
                    
                    break
            
            return None, "No City Council agenda PDF found"
            
        finally:
            driver.quit()
            
    except Exception as e:
        error_details = f"{str(e)}\n\nTraceback:\n{traceback.format_exc()}"
        return None, error_details


def scrape_city_council_agenda(debug=False, use_selenium=False):
    """Scrape the latest City Council meeting agenda packet."""
    try:
        # Try the main Sachse website agendas page first
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
        
        # Look for links to CivicClerk or direct PDF agenda links
        all_links = soup.find_all('a', href=True)
        
        # First try to find direct PDF links on this page
        for link in all_links:
            href = link.get('href', '')
            link_text = link.get_text(strip=True).lower()
            
            if '.pdf' in href.lower() and ('agenda' in link_text or 'packet' in link_text):
                pdf_url = href
                if not pdf_url.startswith('http'):
                    pdf_url = f"https://www.cityofsachse.com{pdf_url}"
                
                # Download and extract PDF
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
        
        # If no PDFs found, look for CivicClerk link to follow
        for link in all_links:
            href = link.get('href', '')
            if 'civicclerk' in href.lower():
                # This is a link to the CivicClerk portal
                # Note: CivicClerk requires JavaScript, so we can't scrape it directly
                return None, "City Council uses CivicClerk which requires JavaScript. The site shows agendas at: https://sachsetx.portal.civicclerk.com/ but cannot be scraped with basic tools."
        
        return None, "No City Council agenda found on the main website."
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
        
        # Find the first "Agenda" link (most recent meeting)
        all_links = soup.find_all('a', href=True)
        
        for link in all_links:
            link_text = link.get_text(strip=True)
            if link_text == 'Agenda':  # Exact match for "Agenda" link
                agenda_url = link.get('href')
                if not agenda_url.startswith('http'):
                    agenda_url = f"https://meetings.boardbook.org{agenda_url}"
                
                # Visit the agenda page
                agenda_response = requests.get(agenda_url, timeout=30)
                agenda_response.raise_for_status()
                agenda_soup = BeautifulSoup(agenda_response.content, 'html.parser')
                
                # Look for PDF download links on the agenda page
                pdf_links = agenda_soup.find_all('a', href=True)
                
                for pdf_link in pdf_links:
                    href = pdf_link.get('href', '')
                    pdf_text = pdf_link.get_text(strip=True).lower()
                    
                    # Look for PDF downloads
                    if '.pdf' in href.lower() or 'download' in pdf_text or 'pdf' in pdf_text:
                        pdf_url = href
                        if not pdf_url.startswith('http'):
                            pdf_url = f"https://meetings.boardbook.org{pdf_url}"
                        
                        # Download and extract PDF
                        pdf_response = requests.get(pdf_url, timeout=60)
                        pdf_response.raise_for_status()
                        
                        # Check if it's actually a PDF
                        if pdf_response.headers.get('content-type', '').lower().startswith('application/pdf'):
                            pdf_file = BytesIO(pdf_response.content)
                            reader = PdfReader(pdf_file)
                            
                            text = ""
                            max_pages = min(50, len(reader.pages))
                            for i in range(max_pages):
                                text += reader.pages[i].extract_text()
                            
                            if len(text.strip()) > 100:
                                return text[:15000], None
                
                # If no PDF found on agenda page, try to extract HTML content
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
    """Search for Sachse High School Mustangs sports news."""
    try:
        ddgs = DDGS()
        query = "Sachse High School Mustangs sports results last week"
        results = ddgs.text(query, max_results=10)
        
        if debug:
            debug_info = f"Query: {query}\n\n"
            debug_info += f"Number of results: {len(results) if results else 0}\n\n"
            if results:
                debug_info += "=== Search Results ===\n"
                for i, result in enumerate(results, 1):
                    debug_info += f"\nResult {i}:\n"
                    debug_info += f"  Title: {result.get('title', 'N/A')}\n"
                    debug_info += f"  URL: {result.get('href', 'N/A')}\n"
                    debug_info += f"  Body: {result.get('body', 'N/A')[:200]}\n"
            return None, debug_info
        
        if not results:
            return None, "No search results returned"
        
        # Combine search snippets
        combined_text = ""
        for i, result in enumerate(results, 1):
            combined_text += f"Source {i}: {result.get('title', '')}\n"
            combined_text += f"{result.get('body', '')}\n\n"
        
        return combined_text[:8000], None  # Success, no error
    except Exception as e:
        error_details = f"{str(e)}\n\nTraceback:\n{traceback.format_exc()}"
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
        
        "sports": """You are a high school sports reporter. Write a "Mustang Sports Minute" based on the following search results about Sachse High School athletics.

Focus on:
- Recent game scores and highlights
- Standout player performances
- Upcoming important games
- Team standings or playoff implications

Write in an energetic, positive style. Keep it concise (150-200 words).

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
    
    # Sidebar configuration
    st.sidebar.header("Configuration")
    
    api_key = st.sidebar.text_input(
        "OpenAI API Key",
        type="password",
        help="Enter your OpenAI API key to generate summaries"
    )
    
    st.sidebar.markdown("---")
    st.sidebar.subheader("Select News Sources")
    
    run_city_council = st.sidebar.checkbox("City Council Updates", value=True)
    
    # Options for City Council scraping
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
                "Or upload Council PDF manually",
                type=['pdf'],
                help="Download from https://sachsetx.portal.civicclerk.com/"
            )
    
    run_school_board = st.sidebar.checkbox("School Board Updates", value=True)
    run_sports = st.sidebar.checkbox("Mustang Sports Minute", value=True)
    
    st.sidebar.markdown("---")
    
    debug_mode = st.sidebar.checkbox("Enable Debug Mode", value=False, help="Show detailed HTML structure for troubleshooting")
    
    st.sidebar.markdown("---")
    
    generate_button = st.sidebar.button("Generate Newsletter", type="primary", use_container_width=True)
    
    # Main content area
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
        
        # Agent 1: City Council
        if run_city_council:
            with st.status("Processing City Council agenda...", expanded=True) as status:
                council_text = None
                error = None
                
                # Priority 1: Use Selenium if enabled
                if use_selenium and SELENIUM_AVAILABLE:
                    st.write("Using Selenium to render JavaScript...")
                    council_text, error = scrape_city_council_agenda_selenium()
                
                # Priority 2: Check if user uploaded a PDF
                elif uploaded_council_pdf:
                    st.write("Processing uploaded PDF...")
                    try:
                        pdf_file = BytesIO(uploaded_council_pdf.read())
                        reader = PdfReader(pdf_file)
                        
                        text = ""
                        max_pages = min(50, len(reader.pages))
                        for i in range(max_pages):
                            text += reader.pages[i].extract_text()
                        
                        if len(text.strip()) > 100:
                            council_text = text[:15000]
                    except Exception as e:
                        error = f"Error processing uploaded PDF: {str(e)}"
                
                # Priority 3: Try basic scraping (will likely fail)
                else:
                    st.write("Attempting basic scraping...")
                    council_text, error = scrape_city_council_agenda(debug=debug_mode, use_selenium=False)
                
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
                    if debug_mode:
                        newsletter_sections.append("## City Hall Updates\n")
                        newsletter_sections.append("*Debug mode enabled - see details below*\n")
                        status.update(label="City Council: Debug Info Ready", state="complete")
                    else:
                        newsletter_sections.append("## City Hall Updates\n")
                        newsletter_sections.append("*City Council data not available. Enable Selenium or upload PDF manually.*\n")
                        status.update(label="City Council: Manual action needed", state="error")
                    
                    # Show error/debug details in expander
                    if error:
                        with st.expander("View Debug/Error Details"):
                            st.code(error, language="text")
        
        # Agent 2: School Board
        if run_school_board:
            with st.status("Scraping School Board agenda...", expanded=True) as status:
                st.write("Fetching latest meeting documents...")
                school_text, error = scrape_school_board_agenda(debug=debug_mode)
                
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
                    if debug_mode:
                        newsletter_sections.append("## School Board Updates\n")
                        newsletter_sections.append("*Debug mode enabled - see details below*\n")
                        status.update(label="School Board: Debug Info Ready", state="complete")
                    else:
                        newsletter_sections.append("## School Board Updates\n")
                        newsletter_sections.append("*Could not retrieve School Board data. Please check back later.*\n")
                        status.update(label="School Board: Data retrieval failed", state="error")
                    
                    # Show error/debug details in expander
                    with st.expander("View Debug/Error Details"):
                        st.code(error, language="text")
        
        # Agent 3: Sports
        if run_sports:
            with st.status("Searching for sports news...", expanded=True) as status:
                st.write("Querying DuckDuckGo for Mustang sports...")
                sports_text, error = search_sports_news()
                
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
                    newsletter_sections.append("*Could not retrieve sports data. Please check back later.*\n")
                    status.update(label="Sports: Data retrieval failed", state="error")
                    
                    # Show error details in expander
                    with st.expander("View Error Details"):
                        st.code(error, language="text")
        
        # Display final newsletter
        newsletter_content = "\n".join(newsletter_sections)
        
        st.markdown("---")
        st.subheader("Your Newsletter")
        st.markdown(newsletter_content)
        
        # Download button
        st.download_button(
            label="Download Newsletter.md",
            data=newsletter_content,
            file_name=f"sachse_newsletter_{datetime.now().strftime('%Y%m%d')}.md",
            mime="text/markdown"
        )
    
    else:
        # Welcome message
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