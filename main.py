import base64
import io
import fitz  # PyMuPDF
import sqlite3
import os
from fastapi.staticfiles import StaticFiles
from fastapi import FastAPI, Form
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from fastapi.staticfiles import StaticFiles
import google.generativeai as genai

# ================== CONFIG ======================
current_dir = os.path.dirname(os.path.abspath(__file__))

genai.configure(api_key="AIzaSyCcoQ40u_iM1BIvp26iLqVTWdHp3Ky0TAw")  # Replace with your real key

app = FastAPI()

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =============== DATABASE LOGIC =================

def initialize_db():
    conn = sqlite3.connect("prompts.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS prompts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            prompt_text TEXT
        )
    """)
    cursor.execute("SELECT COUNT(*) FROM prompts")
    if cursor.fetchone()[0] < 3:
        cursor.execute("DELETE FROM prompts")
        cursor.executemany(
            "INSERT INTO prompts (prompt_text) VALUES (?)",
            [
                ("Is the resume tailored to the target job description?",),
                ("Are there any red flags like gaps or poor formatting?",),
                ("What improvements can enhance clarity or impact?",)
            ]
        )
        conn.commit()
    conn.close()
def get_prompts_from_db():
    conn = sqlite3.connect("prompts.db")
    cursor = conn.cursor()
    cursor.execute("SELECT prompt_text FROM prompts ORDER BY id ASC")
    prompts = [row[0] for row in cursor.fetchall()]
    conn.close()
    return prompts

# ================ MAIN ROUTES ===================

@app.post("/evaluate")
async def evaluate_resume(base64_pdf: str = Form(...)):
    try:
        pdf_bytes = base64.b64decode(base64_pdf)
        pdf_doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        first_page = pdf_doc[0].get_pixmap()
        img_byte_arr = io.BytesIO(first_page.tobytes("jpeg"))
        image_base64 = base64.b64encode(img_byte_arr.getvalue()).decode()
    except Exception as e:
        return {"error": f"PDF processing failed: {str(e)}"}

    prompts = get_prompts_from_db()
    if len(prompts) < 3:
        return {"error": "Not enough prompts in database."}

    master_prompt = f"""
You are a highly skilled HR professional, career coach, and ATS expert.

1. {prompts[0]}
2. {prompts[1]}
3. {prompts[2]}

Provide a detailed report that includes:
- Job-fit analysis
- Improvement suggestions
    """

    try:
        model = genai.GenerativeModel("gemini-1.5-flash")
        response = model.generate_content([
            "Analyze this resume carefully:",
            {"mime_type": "image/jpeg", "data": image_base64},
            master_prompt
        ])
        response_text = response.text
    except Exception as e:
        return {"error": f"Gemini API error: {str(e)}"}

    return {"response": response_text}

# ============== ADMIN ROUTE ======================

class PromptUpdate(BaseModel):
    prompt_text: str

@app.post("/update_prompt2")
async def update_prompt2(data: PromptUpdate):
    try:
        conn = sqlite3.connect('prompts.db')
        cursor = conn.cursor()
        cursor.execute("UPDATE prompts SET prompt_text = ? WHERE id = 2", (data.prompt_text,))
        conn.commit()
        conn.close()
        return {"status": "Prompt 2 updated successfully"}
    except Exception as e:
        return {"error": str(e)}

# =============== FRONTEND SERVING ================

app.mount("/", StaticFiles(directory="user-frontend", html=True), name="user")
app.mount(
    "/admin",
    StaticFiles(directory=os.path.join(current_dir, "admin-frontend"), html=True),
    name="admin"
)
# ================ INIT ON START ==================

initialize_db()
