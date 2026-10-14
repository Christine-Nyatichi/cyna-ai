# CYNA AI

A full-stack AI chatbot and personal assistant built with Flask, MySQL and vanilla JavaScript.

![CYNA AI chat](docs/chat.png)

## About me

Hi, I'm Christine, a full-stack developer. I built CYNA AI end to end to show my skills across the stack: backend APIs, databases, authentication, AI integration, testing and security. Feedback and ideas are always welcome.

## Features

- **AI chat** powered by Google Gemini, with six modes: General, Study, Coding, Research, Writing and Data Analysis
- **Authentication** with registration, login and JWT-protected routes
- **Conversation history**: create, search, rename and delete chats
- **AI memory**: notes you control, used in every chat (add them in the Memory panel or type "remember that ...")
- **Task manager**: add, complete, edit and delete tasks
- **Document AI**: upload a PDF, DOCX or TXT and ask questions about it
- **Admin dashboard**: usage stats, errors and sign-ups, visible to admin accounts only
- **Security**: password rules, rate limiting, input validation, usage logging and restricted CORS
- **73 automated tests** with pytest

![CYNA AI admin dashboard](docs/admin.png)

## Tech stack

| Layer | Technology |
|-------|------------|
| Backend | Python, Flask, SQLAlchemy, Flask-JWT-Extended, Flask-Limiter |
| Database | MySQL |
| Frontend | HTML, CSS, JavaScript |
| AI | Google Gemini API through a replaceable service layer |
| Documents | pypdf, python-docx |
| Testing | pytest |

## Architecture

```
Browser -> Frontend -> Flask REST API -> Services -> MySQL / AI provider
```

The AI provider lives in `backend/services/ai_service.py`, so it can be swapped without touching the rest of the app.

```
backend/
  app.py            app setup, security headers, usage logging
  models.py         database tables
  extensions.py     database and rate limiter
  routes/           auth, chat, memory, tasks, documents, admin
  services/         ai_service, document_service
  tests/            pytest test suite
frontend/
  index.html, style.css, app.js, tasks.js, documents.js, admin.js
```

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
GEMINI_MODEL=gemini-3.5-flash-lite
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

Open `frontend/index.html` with the VS Code **Live Server** extension (it serves on port 5500), then register an account.

### 6. Make an admin (optional)

Registration never creates admins. Promote an account in MySQL:

```sql
UPDATE users SET role = 'admin' WHERE email = 'you@example.com';
```

Log in again and an **Admin** button appears in the sidebar.

## Running the tests

```
cd backend
python -m pytest -v
```

The tests use a temporary in-memory database and a fake AI, so they need no MySQL, no API key and no internet.

## API overview

| Method | Endpoint | Purpose |
|--------|----------|---------|
| POST | `/api/auth/register` | Create an account |
| POST | `/api/auth/login` | Log in and receive a token |
| GET | `/api/auth/me` | Current user |
| POST | `/api/chat` | Send a message to the AI |
| GET | `/api/conversations` | List conversations (supports `?search=`) |
| GET / PATCH / DELETE | `/api/conversations/<id>` | Open, rename or delete |
| GET / POST / DELETE | `/api/memories` | Manage AI memory |
| DELETE | `/api/memories/<id>` | Delete one memory |
| GET / POST | `/api/tasks` | List and create tasks |
| PATCH / DELETE | `/api/tasks/<id>` | Update or delete a task |
| GET / POST | `/api/documents` | List and upload documents |
| DELETE | `/api/documents/<id>` | Delete a document |
| GET | `/api/admin/stats` | Dashboard statistics (admin only) |
| GET | `/api/health` | Health check |

## Security notes

- Passwords are hashed, never stored in plain text
- Secrets live in `.env`, which is excluded from Git
- Every resource is scoped to the logged-in user
- Login, registration, chat and uploads are rate limited
- Uploads are limited by file type and size
- Usage logs record endpoints and status codes only, never passwords or message text
- Admin access is checked on the server on every request

## Roadmap

- Docker and cloud deployment
- Streaming responses
- Vector search for documents
- Voice input and image analysis
- Chat export
- React frontend