"""
OCR Agent - Extracts data from receipts images using Langgraph

Flow: 
load_image ->extract_text (tesseract) ->prase_data (llamaAPI) -> save_to_db


"""

import pytesseract
from app.core.config import Settings,settings
from PIL import Image
from langchain_core.runnables import RunnableConfig
from langgraph.graph import StateGraph,START,END
from typing import Optional,TypedDict
from sqlalchemy.orm import Session
from app.models.models import Receipt
from uuid import UUID
from datetime import datetime
import re
import json
from groq import Groq
from dotenv import load_dotenv
from pdf2image import convert_from_path
import os
# Tell pytesseract where tessereact.exe is
pytesseract.pytesseract.tesseract_cmd= r"D:/Program Files/Tesseract-OCR/tesseract.exe"


# Poppler path

POPPLER_PATH =r"D:\Users\yashw\Downloads\Release-26.02.0-0\poppler-26.02.0\Library\bin"


# Building State
# This dict flows through every node in the graph
class OCRState(TypedDict):
  receipt_id:str
  file_path:str
  raw_text:str
  extracted_amount:Optional[float]
  extracted_merchant:Optional[str]
  extracted_date:Optional[int]
  ocr_confidence:Optional[float]
  error:Optional[str]
  

# Node 1: Extract text with tesseract
def extract_text(state:OCRState)->OCRState:
  """Run tesseract OCR on the image/PDF and get raw text"""
  
  try:
     file_path = state["file_path"]
     
     # PDF support
     if file_path.lower().endswith(".pdf"):
        pages = convert_from_path(file_path,poppler_path=POPPLER_PATH)
        if not pages:
         return {**state, "error":"PDF has no pages"}
        image = pages[0] #use first page only
        print(f"PDF converted to image ({len(pages)} page(s)) ")
     else:
       image = Image.open(file_path)
               
    
    #get raw text
     raw_text = pytesseract.image_to_string(image)
    
    
    #Get confidence score (0-100) -> normalize to 0.0-1.0
     data = pytesseract.image_to_data(image,output_type=pytesseract.Output.DICT)
     confidences = [int(c) for c in data["conf"] if str(c) !="-1"]
     confidence =  sum(confidences) / len(confidences) / 100 if confidences else 0.0
    
     print(f" Raw OCR text:\n{raw_text}")
     print(f"Confidence :{confidence:2f}")
    
     return {**state, "raw_text":raw_text, "ocr_confidence":confidence}
  
  except Exception as e:
    return {**state, "error":f"OCR failed:{str(e)}"}
  
  
  
# Node 2: parse with Groq llama models
def parse_data(state: OCRState) ->OCRState:
  """send raw ocr text to Groq llama and extract structured fields"""
  
  if state.get("error"):
    return state  #skip if previous node fail
  
  try:
    client = Groq(api_key=settings.GROQ_API_KEY)
    
    prompt = f"""Extract the following fields from this receipt text.
Return ONLY a JSON object with these extract keys.
- merchant (string: shop/vendor name)
- amount (number : total amount paid, no currency symbol)
- date (string: in YYYY-MM-DD format)

If a field cannot be found, use null.

Receipt text:
{state["raw_text"]}

Return ONLY the JSON, no explantion.

    """
    response = client.chat.completions.create(
      model="llama-3.3-70b-versatile",
      messages=[{"role":"user","content":prompt}],
      temperature=0.0,
      max_tokens =200,
      response_format = {"type":"json_object"},
    )
    
    content =  response.choices[0].message.content.strip()
    print(f"Groq reponse: {content}")
    
    parsed = json.loads(content)
    
    return {
      **state,
      "extracted_merchant":parsed.get("merchant"),
      "extracted_amount":parsed.get("amount"),
      "extracted_date":parsed.get("date"),
    }
  
  except Exception as e:
    print(f"GROQ Error: {str(e)}")
    return {**state, "error":f"Parsing failed: {str(e)}"}
  
  

# Node 3: save to DB
# DB session passed via Langrpahh config, not lamada
def save_to_db(state:OCRState, config:RunnableConfig)->OCRState:
  """ write extracted fields back to the receipts row"""
  db:Session = config["configurable"].get("db")
  
  
  try:
    receipt = db.query(Receipt).filter(
      Receipt.id == state["receipt_id"]
    ).first()
    
    if not receipt:
      return {**state, "error":"Receipt not found in DB"}
    
    receipt.extracted_merchant = state.get("extracted_merchant")
    receipt.extracted_amount= state.get("extracted_amount")
    receipt.ocr_confidence = state.get("ocr_confidence")
    
    
    # parse date string -> python date
    date_str = state.get("extracted_date")
    if date_str:
      try:
        receipt.extracted_date = datetime.strptime(date_str,"%Y-%m-%d").date()
      except ValueError:
        pass    # leave as NOne if date format is worng
      
      
    db.commit()
    db.refresh(receipt)
    print(f"Saved OCR data for receipt {state['receipt_id']}")
    return state
  
  except Exception as e:
    return {**state, "error":f"DB save failed: {str(e)}"}
  
  

# Conditional router
def check_errors(state:OCRState):
  """ ROute to END immediately if an error occurred, else continue"""
  if state.get("error"):
    return "failed"
  return "continue"

     
# Build graph
def build_ocr_graph(db:Session):
  """Build and complie the langgraph OCR pipeline"""

  graph = StateGraph(OCRState)
  
  graph.add_node("extract_text",extract_text)
  graph.add_node("parse_data",parse_data)
  graph.add_node("save_to_db", save_to_db)
  
  
  graph.set_entry_point("extract_text")
  
  # coditional edges - skip remaining nodes on erro
  graph.add_conditional_edges(
    "extract_text",
    check_errors,
    {
      "continue":"parse_data",
      "failed":END,
    }
  )
  
  graph.add_conditional_edges(
    "parse_data",
    check_errors,
    {
      "continue":"save_to_db",
      "failed":END,
    }
  )
  graph.add_edge("save_to_db",END)
  return graph.compile()




# Main entry point
def run_ocr_agent(receipt_id: UUID, file_path:str,db:Session)->dict:
  """Call this from the router to trigger the full OCR pipeline"""
  
  pipeline = build_ocr_graph(db)
  
  
  result = pipeline.invoke({
    "receipt_id":str(receipt_id),
    "file_path":file_path,
    "raw_text":"",
    "extracted_amount":None,
    "extracted_date":None,
    "extracted_merchant":None,
    "ocr_confidence":None,
    "error":None,
  },
   config={"configurable":{"db":db}}                     
  )
  
  
  if result.get("error"):
     raise ValueError(result["error"])
   
  return {
    "merchant":result["extracted_merchant"],
    "amount":result["extracted_amount"],
    "date":result["extracted_date"],
    "confidence":result["ocr_confidence"],
    
  }


