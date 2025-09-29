import os
import pdfplumber
import easyocr
import numpy as np
from llama_index.core import VectorStoreIndex, Document, StorageContext
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
import logging
import google.generativeai as genai 
# Set up logging
logging.basicConfig(filename='./logs/processing.log', level=logging.INFO, format='%(asctime)s - %(message)s')

# Initialize EasyOCR reader for English and Hindi
reader = easyocr.Reader(['en', 'hi'])

# Set Gemini API key
genai.configure(api_key="AIzaSyDAH3gZbmTJQJ_rN2EK1qHpBTUB-WdjTE8")
model = genai.GenerativeModel('gemini-2.5-flash')

def clean_text(text):
    """Clean extracted text using Gemini if available."""
    if model:
        try:
            response = model.generate_content(f"Clean and normalize this text for better readability: {text}")
            return response.text.strip()
        except:
            pass
    return text

def table_to_sentences(table):
    """Convert table rows to natural language sentences."""
    sentences = []
    if not table or len(table) < 2:
        return sentences
    
    # Assume first row is headers
    headers = table[0]
    for row in table[1:]:
        if len(row) == len(headers):
            if len(headers) == 3 and 'day' in headers[0].lower() and 'subject' in headers[1].lower() and 'time' in headers[2].lower():
                sentences.append(f"On {row[0]}, the {row[1]} class is scheduled at {row[2]}.")
            else:
                # General conversion
                fact = ", ".join([f"{h}: {r}" for h, r in zip(headers, row) if r])
                sentences.append(fact)
        else:
            sentences.append(" ".join(row))
    
    # Optionally use Gemini to rewrite
    if model and sentences:
        combined = " ".join(sentences)
        try:
            response = model.generate_content(f"Rewrite this table data into natural language facts: {combined}")
            return [response.text.strip()]
        except:
            pass
    
    return sentences

def summarize_and_keywords(full_text, pdf_name):
    """Generate summary and keywords using Gemini."""
    if not model:
        return "", []
    try:
        # Summary prompt
        summary_prompt = f"Summarize the content of this document titled '{pdf_name}' in 2-3 sentences, focusing on key information."
        summary_response = model.generate_content(summary_prompt + "\n\nContent: " + full_text[:10000])  # Limit content to avoid token limits
        summary = summary_response.text.strip()

        # Keywords prompt
        keywords_prompt = f"Extract 5-10 relevant keywords or phrases from the following document summary and content that would help in searching for this document. Keywords should be comma-separated."
        keywords_response = model.generate_content(keywords_prompt + "\n\nSummary: " + summary + "\n\nContent snippet: " + full_text[:5000])
        keywords_str = keywords_response.text.strip()
        keywords = [kw.strip() for kw in keywords_str.split(',') if kw.strip()]

        logging.info(f"Generated summary for {pdf_name}: {summary[:100]}...")
        return summary, keywords
    except Exception as e:
        logging.error(f"Error generating summary/keywords for {pdf_name}: {e}")
        return "", []

def process_pdf(pdf_path):
    documents = []
    total_pages = 0
    ocr_pages = 0
    table_conversions = 0
    all_full_texts = []

    with pdfplumber.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages, start=1):
            total_pages += 1
            text = page.extract_text()
            if not text or len(text.strip()) < 50:  # Threshold for OCR
                # Apply OCR
                pil_image = page.to_image(resolution=300).original
                image_np = np.array(pil_image)
                ocr_result = reader.readtext(image_np, detail=0)
                text = " ".join(ocr_result)
                text = clean_text(text)
                method = 'ocr'
                ocr_pages += 1
            else:
                method = 'text'

            # Extract tables
            tables = page.extract_tables()
            table_sentences = []
            for table in tables:
                table_sentences.extend(table_to_sentences(table))
                table_conversions += 1

            # Merge text and table sentences
            full_text = text + " " + " ".join(table_sentences)
            all_full_texts.append(full_text)

            # Create document (will be updated later with summary)
            doc = Document(
                text=full_text,
                metadata={
                    'source_filename': os.path.basename(pdf_path),
                    'page_number': page_num,
                    'extraction_method': method
                }
            )
            documents.append(doc)

    # Generate summary and keywords for the entire PDF
    combined_text = " ".join(all_full_texts)
    pdf_name = os.path.basename(pdf_path)
    summary, keywords = summarize_and_keywords(combined_text, pdf_name)

    # Update each document's text to include summary and keywords
    keywords_str = ", ".join(keywords)
    enhanced_text_prefix = f"Document Summary: {summary}\nKeywords: {keywords_str}\n\n"
    enhanced_documents = []
    for doc in documents:
        new_text = enhanced_text_prefix + doc.text
        new_metadata = doc.metadata.copy()
        new_metadata.update({'summary': summary, 'keywords': keywords})
        new_doc = Document(text=new_text, metadata=new_metadata)
        enhanced_documents.append(new_doc)
    documents = enhanced_documents

    logging.info(f"Processed {pdf_path}: {total_pages} pages, {ocr_pages} OCR, {table_conversions} tables")
    return documents, total_pages, ocr_pages, table_conversions

def main():
    pdf_dir = './data'
    all_documents = []
    summary = {'total_pdfs': 0, 'total_pages': 0, 'total_ocr': 0, 'total_tables': 0}
    
    for filename in os.listdir(pdf_dir):
        if filename.lower().endswith('.pdf'):
            pdf_path = os.path.join(pdf_dir, filename)
            docs, pages, ocr, tables = process_pdf(pdf_path)
            all_documents.extend(docs)
            summary['total_pdfs'] += 1
            summary['total_pages'] += pages
            summary['total_ocr'] += ocr
            summary['total_tables'] += tables
    
    # Create embeddings
    embed_model = HuggingFaceEmbedding(model_name="all-MiniLM-L6-v2")
    
    # Create index
    index = VectorStoreIndex.from_documents(all_documents, embed_model=embed_model)
    
    # Persist index
    index.storage_context.persist(persist_dir="./storage/college_index")
    
    print(f"Indexing complete. Summary: {summary}")

if __name__ == "__main__":
    main()