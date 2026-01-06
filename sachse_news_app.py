import streamlit as st
import requests
from bs4 import BeautifulSoup
from pypdf import PdfReader
from io import BytesIO
from duckduckgo_search import DDGS
from openai import OpenAI
import traceback
from datetime import datetime


def scrape_city_council_agenda():
    """Scrape the latest City Council meeting agenda packet."""
    try:
        url = "https://sachsetx.portal.civicclerk.com/"
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Find all meeting rows - looking for City Council meetings
        meeting_rows = soup.find_all('tr', class_='meeting-row')
        
        for row in meeting_rows:
            meeting_title = row.find('td', class_='meeting-title')
            if meeting_title and 'City Council' in meeting_title.get_text():
                # Found a City Council meeting, now find the Agenda Packet link
                links = row.find_all('a')
                for link in links:
                    link_text = link.get_text(strip=True)
                    if 'Agenda Packet' in link_text or 'Packet' in link_text:
                        pdf_url = link.get('href')
                        if not pdf_url.startswith('http'):
                            pdf_url = f"https://sachsetx.portal.civicclerk.com{pdf_url}"
                        
                        # Download and extract PDF text
                        pdf_response = requests.get(pdf_url, timeout=60)
                        pdf_response.raise_for_status()
                        
                        pdf_file = BytesIO(pdf_response.content)
                        reader = PdfReader(pdf_file)
                        
                        # Extract first 50 pages
                        text = ""
                        max_pages = min(50, len(reader.pages))
                        for i in range(max_pages):
                            text += reader.pages[i].extract_text()
                        
                        return text[:15000], None  # Success, no error
        
        return None, "No City Council meeting with Agenda Packet found"
    except Exception as e:
        error_details = f"{str(e)}\n\nTraceback:\n{traceback.format_exc()}"
        return None, error_details


def scrape_school_board_agenda():
    """Scrape the latest Garland ISD School Board meeting agenda."""
    try:
        url = "https://meetings.boardbook.org/public/Organization/1084"
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Look for meeting links - typically "Regular Meeting"
        meeting_links = soup.find_all('a', href=True)
        
        for link in meeting_links:
            link_text = link.get_text(strip=True)
            if 'Regular Meeting' in link_text or 'Board Meeting' in link_text:
                meeting_url = link.get('href')
                if not meeting_url.startswith('http'):
                    meeting_url = f"https://meetings.boardbook.org{meeting_url}"
                
                # Visit the meeting page to find PDF
                meeting_response = requests.get(meeting_url, timeout=30)
                meeting_response.raise_for_status()
                meeting_soup = BeautifulSoup(meeting_response.content, 'html.parser')
                
                # Find PDF links
                pdf_links = meeting_soup.find_all('a', href=True)
                for pdf_link in pdf_links:
                    href = pdf_link.get('href')
                    if '.pdf' in href.lower() or 'agenda' in pdf_link.get_text().lower():
                        pdf_url = href
                        if not pdf_url.startswith('http'):
                            pdf_url = f"https://meetings.boardbook.org{pdf_url}"
                        
                        # Download and extract PDF
                        pdf_response = requests.get(pdf_url, timeout=60)
                        pdf_response.raise_for_status()
                        
                        pdf_file = BytesIO(pdf_response.content)
                        reader = PdfReader(pdf_file)
                        
                        text = ""
                        max_pages = min(50, len(reader.pages))
                        for i in range(max_pages):
                            text += reader.pages[i].extract_text()
                        
                        return text[:15000], None  # Success, no error
        
        return None, "No School Board meeting with agenda found"
    except Exception as e:
        error_details = f"{str(e)}\n\nTraceback:\n{traceback.format_exc()}"
        return None, error_details


def search_sports_news():
    """Search for Sachse High School Mustangs sports news."""
    try:
        ddgs = DDGS()
        query = "Sachse High School Mustangs sports results last week"
        results = ddgs.text(query, max_results=10)
        
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
    run_school_board = st.sidebar.checkbox("School Board Updates", value=True)
    run_sports = st.sidebar.checkbox("Mustang Sports Minute", value=True)
    
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
            with st.status("Scraping City Council agenda...", expanded=True) as status:
                st.write("Fetching latest meeting documents...")
                council_text, error = scrape_city_council_agenda()
                
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
                    newsletter_sections.append("*Could not retrieve City Council data. Please check back later.*\n")
                    status.update(label="City Council: Data retrieval failed", state="error")
                    
                    # Show error details in expander
                    with st.expander("View Error Details"):
                        st.code(error, language="text")
        
        # Agent 2: School Board
        if run_school_board:
            with st.status("Scraping School Board agenda...", expanded=True) as status:
                st.write("Fetching latest meeting documents...")
                school_text, error = scrape_school_board_agenda()
                
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
                    newsletter_sections.append("*Could not retrieve School Board data. Please check back later.*\n")
                    status.update(label="School Board: Data retrieval failed", state="error")
                    
                    # Show error details in expander
                    with st.expander("View Error Details"):
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
