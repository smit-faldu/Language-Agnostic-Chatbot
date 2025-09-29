from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from llama_index.core import load_index_from_storage, StorageContext, Settings
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.llms.google_genai import GoogleGenAI
from llama_index.core.chat_engine import CondensePlusContextChatEngine
import os
from dotenv import load_dotenv
import json
import datetime
from collections import defaultdict
from typing import List, Dict


load_dotenv()

app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Set embedding model
Settings.embed_model = HuggingFaceEmbedding(model_name="all-MiniLM-L6-v2")

# Load the index
storage_context = StorageContext.from_defaults(persist_dir="./storage/college_index")
index = load_index_from_storage(storage_context)
print("Index loaded successfully")

# Set up Gemini LLM
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
if GEMINI_API_KEY:
    llm = GoogleGenAI(api_key=GEMINI_API_KEY, model="gemini-2.5-flash")
else:
    llm = None

# Dictionary to store chat engines per session
chat_engines = {}

# Chat history storage
chat_history: List[Dict] = []
try:
    with open('chat_history.json', 'r') as f:
        chat_history = json.load(f)
except FileNotFoundError:
    pass

class ChatRequest(BaseModel):
    query: str
    session_id: str

@app.get("/")
def chat_page():
    return FileResponse("static/chat.html", media_type="text/html")

@app.get("/data/{filename}")
def get_pdf(filename: str):
    path = os.path.join("data", filename)
    if os.path.exists(path):
        return FileResponse(path, media_type='application/pdf')
    else:
        raise HTTPException(status_code=404, detail="File not found")

@app.get("/admin/stats")
def get_admin_stats():
    total = len(chat_history)
    failed = sum(1 for c in chat_history if c['failed'])
    success = total - failed
    recent = chat_history[-10:] if chat_history else []
    failed_questions = [c['query'] for c in chat_history if c['failed']]
    # Daily stats
    daily_stats = defaultdict(int)
    for c in chat_history:
        date = c['timestamp'][:10]  # YYYY-MM-DD
        daily_stats[date] += 1
    return {
        "total_queries": total,
        "successful": success,
        "failed": failed,
        "recent_queries": recent,
        "failed_questions": failed_questions,
        "daily_stats": dict(daily_stats)
    }

@app.get("/admin")
def admin_page():
    return FileResponse("static/admin.html", media_type="text/html")

@app.post("/chat")
def chat(request: ChatRequest):
    session_id = request.session_id
    query = request.query
    original_language = 'en'

    try:
        if llm:
            # 1. Detect language and translate to English
            prompt = f"Detect the language of the following text and translate it to English. Return ONLY a JSON object with 'language' (e.g., 'en', 'hi', 'gu') and 'translated_text' keys. Text: '{query}'"
            response = llm.complete(prompt)
            
            try:
                # The response might contain markdown characters like ```json ... ```
                cleaned_response = response.text.strip().replace('```json', '').replace('```', '')
                translation_data = json.loads(cleaned_response)
                original_language = translation_data.get('language', 'en')
                translated_query = translation_data.get('translated_text', query)
            except (json.JSONDecodeError, AttributeError) as e:
                print(f"Could not parse translation response: {response.text}, error: {e}")
                original_language = 'en'
                translated_query = query

            if session_id not in chat_engines:
                chat_engines[session_id] = CondensePlusContextChatEngine.from_defaults(
                    retriever=index.as_retriever(),
                    llm=llm
                )
            chat_engine = chat_engines[session_id]
            print(f"Using chat engine with LLM for query: {translated_query}")
            response = chat_engine.chat(translated_query)
        else:
            # Use query engine for basic retrieval without session memory
            print(f"Using basic query engine for query: {query}")
            query_engine = index.as_query_engine()
            response = query_engine.query(query)

        answer = response.response

        # 2. Translate answer back to original language
        if original_language != 'en' and llm:
            prompt = f"Translate the following English text to {original_language}: '{answer}'"
            response = llm.complete(prompt)
            answer = response.text.strip()

        # Extract source info
        sources = []
        if hasattr(response, 'source_nodes'):
            for node in response.source_nodes:
                sources.append({
                    'filename': node.metadata.get('source_filename'),
                    'page': node.metadata.get('page_number')
                })
        # Generate summary if LLM available
        if llm:
            summary_prompt = f"Summarize the following answer concisely: {answer}"
            summary_response = llm.complete(summary_prompt)
            summary = summary_response.text.strip()
        else:
            summary = answer[:200] + "..." if len(answer) > 200 else answer

        # Log to history
        chat_entry = {
            'query': query,
            'answer': answer,
            'session_id': session_id,
            'timestamp': datetime.datetime.now().isoformat(),
            'sources': sources,
            'summary': summary,
            'failed': False
        }
        chat_history.append(chat_entry)
        with open('chat_history.json', 'w') as f:
            json.dump(chat_history, f)

        return {
            "answer": answer,
            "sources": sources,
            "summary": summary
        }
    except Exception as e:
        print(f"Error during chat: {str(e)}")
        answer = "Sorry, I could not find an answer. Please contact the office."
        # Log failed query
        chat_entry = {
            'query': query,
            'answer': answer,
            'session_id': session_id,
            'timestamp': datetime.datetime.now().isoformat(),
            'sources': [],
            'summary': "",
            'failed': True
        }
        chat_history.append(chat_entry)
        with open('chat_history.json', 'w') as f:
            json.dump(chat_history, f)
        return {
            "answer": answer,
            "sources": [],
            "summary": ""
        }
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
