from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import requests
from bs4 import BeautifulSoup
import pandas as pd
from docx import Document
from io import BytesIO
import zipfile

app = FastAPI()
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")


def create_csv(doc_id):
    url = f"https://docs.google.com/spreadsheets/u/0/d/{doc_id}/htmlview"
    r = requests.get(url)
    soup = BeautifulSoup(r.text, "html.parser")
    doc_name = (
        soup.title.string.replace(".", "").replace("/", "").replace(" ", "_") + ".csv"
    )
    tables = pd.read_html(r.text)

    csv_buffer = BytesIO()
    tables[0].to_csv(csv_buffer, index=False)
    csv_buffer.seek(0)

    return doc_name, csv_buffer


def create_docx(doc_id):
    url = f"https://docs.google.com/document/d/{doc_id}/mobilebasic"
    r = requests.get(url)
    soup = BeautifulSoup(r.text, "html.parser")
    doc_name = (
        soup.title.string.replace(".", "").replace("/", "").replace(" ", "_") + ".docx"
    )

    content_div = soup.find("div", {"class": "doc"})
    if content_div:
        content = content_div.find("div")
        text = content.get_text(separator="\n") if content else ""
    else:
        text = ""

    doc = Document()
    for line in text.split("\n"):
        doc.add_paragraph(line)

    docx_buffer = BytesIO()
    doc.save(docx_buffer)
    docx_buffer.seek(0)

    return doc_name, docx_buffer


@app.get("/")
def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/download")
async def download(request: Request):
    form = await request.form()
    doc_type = form.get("doc_type")
    doc_ids = form.getlist("doc_id[]")

    zip_buffer = BytesIO()
    with zipfile.ZipFile(zip_buffer, "w") as zip_file:
        for doc_id in doc_ids:
            if not doc_id.strip():
                continue
            try:
                if doc_type == "csv":
                    name, buffer = create_docx(doc_id)
                if doc_type == "docx":
                    name, buffer = create_csv(doc_id)
                else:
                    raise ValueError("Invalid document type")
                zip_file.writestr(name, buffer.getvalue())
            except Exception as e:
                print(f"Failed to fetch {doc_id}: {e}")

    zip_buffer.seek(0)
    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers={
            "Content-Disposition": "attachment; filename=google-doc-sheet-bypass.zip"
        },
    )
