import os
import logging
from typing import List
from openai import OpenAI
from dotenv import load_dotenv
from getDocuments import Article
from dataclasses import dataclass
import PyPDF2
import requests

load_dotenv()

@dataclass
class Article:
    title: str
    pdf_link: str 
    abstract_link: str
    article_id: str
    pdf_content: str
    summary: str = "" 

def extract_pdf_text(pdf_path: str) -> str:
    """Extract text content from PDF file"""
    try:
        text = ""
        with open(pdf_path, 'rb') as file:
            reader = PyPDF2.PdfReader(file)
            for page in reader.pages:
                text += page.extract_text() or ""
        logging.debug(f"Extracted text from {pdf_path}")
        return text[:4000]  # Truncate to fit token limits
    except Exception as e:
        logging.error(f"Error extracting PDF text: {e}")
        return ""

def create_summaries(articles: List[Article], use_openai: bool = False, llm: str = 'openai') -> List[Article]:
    """Generate summaries for articles using specified LLM"""
    
    # Set default URLs if environment variables are not set
    fuelix_api_url = os.getenv('FUELIX_API_URL', 'https://proxy.fuelix.com')
    fuelix_api_key = os.getenv('FUELIX_API_KEY', '')
    fuelix_model = os.getenv('FUELIX_MODEL', '')
    ollama_api_url = os.getenv('OLLAMA_API_URL', 'http://localhost:11434/api/chat')
    ollama_model = os.getenv('OLLAMA_MODEL', 'mistral')
    lm_studio_api_url = os.getenv('LM_STUDIO_API_URL', 'http://localhost:1234/v1')
    openai_model = os.getenv('OPENAI_MODEL', 'gpt-4o-mini')
    openai_api_key = os.getenv('OPENAI_API_KEY', '')


    system_prompt = """You are a research assistant that provides concise summaries of academic papers.
    Focus on:
    1. Key findings and contributions
    2. Methodology and approach
    3. Main conclusions and implications
    4. Respond with a basic string, no formatting, titles, heading etc. is required."""
    
    for article in articles:
        try:
            if not os.path.exists(article.pdf_content):
                logging.error(f"PDF not found: {article.pdf_content}")
                continue
            
            # Extract PDF text
            pdf_text = extract_pdf_text(article.pdf_content)
            if not pdf_text:
                continue
            else:
                logging.debug(f"Extracted text from {article.title}")
                logging.debug(f"First 100 chars of extracted text: {pdf_text[:100]}")
            
            match llm:
                case 'local':
                    # Use local LM Studio
                    headers = {"Content-Type": "application/json"}
                    payload = {
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": f"""Please summarize this paper:
                            Title: {article.title}
                            Content: {pdf_text}"""}
                        ],
                        "temperature": 0.3,
                        "max_tokens": 1000
                    }
                    
                    try:
                        response = requests.post(
                            f"{lm_studio_api_url}/chat/completions",
                            headers=headers,
                            json=payload
                        )
                        response.raise_for_status()
                        article.summary = response.json()["choices"][0]["message"]["content"]
                        logging.debug(f"Generated summary using local LLM for: {article.title}")
                    except requests.exceptions.RequestException as e:
                        logging.error(f"Error calling local LLM API: {str(e)}")
                        article.summary = ""

                case 'ollama':
                    logging.debug(f"Model: {ollama_model}")
                    # Use Ollama
                    headers = {"Content-Type": "application/json"}
                    payload = {
                        "model": ollama_model,
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": f"""Please summarize this paper:
                            Title: {article.title}
                            Content: {pdf_text}"""}
                        ],
                        "stream": False
                    }
                    
                    try:
                        logging.debug(f"Calling Ollama API at {ollama_api_url}")
                        response = requests.post(
                            ollama_api_url,
                            headers=headers,
                            json=payload
                        )
                        response.raise_for_status()
                        article.summary = response.json()["message"]["content"]
                        logging.debug(f"Generated summary using Ollama for: {article.title}")
                    except requests.exceptions.RequestException as e:
                        logging.error(f"Error calling Ollama API: {str(e)}")
                        article.summary = ""

                case 'fuelix':
                    logging.debug(f"Model: {fuelix_model}")
                    client = OpenAI(api_key=fuelix_api_key,
                                    base_url="https://proxy.fuelix.ai")
                    try:
                        response = client.chat.completions.create(
                            model=fuelix_model,
                            messages=[
                                {"role": "system", "content": system_prompt},
                                {"role": "user", "content": f"""Please summarize this paper:
                                Title: {article.title}
                                Content: {pdf_text}"""}
                            ],
                            temperature=0.3,
                            max_tokens=1000
                        )
                        article.summary = response.choices[0].message.content
                        logging.debug(f"Generated summary using FuelIX for: {article.title}")
                    except Exception as e:
                        logging.error(f"Error calling FuelIX API: {str(e)}")
                        article.summary = ""

                case _:  # Default case (openai)
                    logging.debug(f"Model: {openai_model}")
                    # Use OpenAI API
                    client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
                    try:
                        response = client.chat.completions.create(
                            model=openai_model,
                            messages=[
                                {"role": "system", "content": system_prompt},
                                {"role": "user", "content": f"""Please summarize this paper:
                                Title: {article.title}
                                Content: {pdf_text}"""}
                            ],
                            temperature=0.3,
                            max_tokens=1000
                        )
                        article.summary = response.choices[0].message.content
                        logging.debug(f"Generated summary using OpenAI for: {article.title}")
                    except Exception as e:
                        logging.error(f"Error calling OpenAI API: {str(e)}")
                        article.summary = ""
            
        except Exception as e:
            logging.error(f"Error processing {article.title}: {str(e)}")
            article.summary = ""
            
    return articles
