# CYNA AI

A full-stack AI chatbot and personal assistant built with Flask, MySQL and vanilla JavaScript.

## Features

- **AI chat** powered by Google Gemini, with six modes: General, Study, Coding, Research, Writing and Data Analysis
- **Authentication** with registration, login and JWT-protected routes
- **Conversation history**: create, search, rename and delete chats
- **AI memory**: notes you control, used in every chat (add them in the Memory panel or type "remember that ...")
- **Task manager**: add, complete, edit and delete tasks
- **Document AI**: upload a PDF, DOCX or TXT and ask questions about it

## Tech stack

| Layer | Technology |
|-------|------------|
| Backend | Python, Flask, SQLAlchemy, Flask-JWT-Extended |
| Database | MySQL |
| Frontend | HTML, CSS, JavaScript |
| AI | Google Gemini API through a replaceable service layer |
| Documents | pypdf, python-docx |

## Architecture

```
Browser -> Frontend -> Flask REST API -> Services -> MySQL / AI provider
```

The AI provider lives in `backend/services/ai_service.py`, so it can be swapped without touching the rest of the app.

## Getting started

### 1. Clone the project

```
git clone https://github.com/Christine-Nyatichi/cyna-ai.git
cd cyna-ai
```

### 2. Create the database

```sql
CREATE DATABASE cyna_ai CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

### 3. Set up the backend

```
cd backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

Copy `.env.example` to `.env` and fill in your values:

```
DATABASE_URL=mysql+pymysql://root:YOUR_PASSWORD@localhost/cyna_ai
JWT_SECRET_KEY=a-long-random-string
GEMINI_API_KEY=your-gemini-api-key
GEMINI_MODEL=gemini-3.8-flash
```

Generate a secret key with:

```
python -c "import secrets; print(secrets.token_hex(32))"
```

Get a free Gemini API key at https://aistudio.google.com/apikey

### 4. Run the backend

```
python app.py
```

The API runs at `http://127.0.0.1:5001`. Check `http://127.0.0.1:5001/api/health`.

### 5. Run the frontend

Open `frontend/index.html` with the VS Code **Live Server** extension, then register an account.

## API overview

| Method | Endpoint | Purpose |
|--------|----------|---------|
| POST | `/api/auth/register` | Create an account |
| POST | `/api/auth/login` | Log in and receive a token |
| GET | `/api/auth/me` | Current user |
| POST | `/api/chat` | Send a message to the AI |
| GET | `/api/conversations` | List conversations |
| GET / PATCH / DELETE | `/api/conversations/<id>` | Open, rename or delete |
| GET / POST / DELETE | `/api/memories` | Manage AI memory |
| GET / POST | `/api/tasks` | List and create tasks |
| PATCH / DELETE | `/api/tasks/<id>` | Update or delete a task |
| GET / POST | `/api/documents` | List and upload documents |
| DELETE | `/api/documents/<id>` | Delete a document |
| GET | `/api/health` | Health check |

## Roadmap

- Streaming responses
- Vector search for documents
- Voice input and image analysis
- Admin dashboard
- Automated tests
- Docker and cloud deployment
- React frontend

## Security notes

- Passwords are hashed, never stored in plain text
- Secrets live in `.env`, which is excluded from Git
- Every resource is scoped to the logged-in user
- Uploads are limited by file type and size