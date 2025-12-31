# Sentient AI

A modern RAG (Retrieval-Augmented Generation) powered AI assistant with a NotebookLM-inspired interface.

## Architecture

```
sentient/
├── api.py                  # FastAPI backend server
├── npc_brain.py            # Core brain logic
├── logic/
│   ├── ingestion.py        # Document ingestion with FAISS
│   ├── persona.py          # AI persona configuration
│   └── rag_engine.py       # RAG engine implementation
├── data/                   # Document storage & FAISS index
└── frontend/               # Next.js + shadcn UI
    ├── src/
    │   ├── app/            # Next.js App Router
    │   ├── components/     # React components
    │   ├── hooks/          # Custom hooks
    │   ├── lib/            # Utilities & API client
    │   └── types/          # TypeScript types
    └── package.json
```

## Quick Start

### 1. Backend Setup

### 1. Backend Setup

```bash
# Install dependencies using uv (Recommended)
uv sync

# OR using pip
# pip install fastapi uvicorn python-multipart python-dotenv langchain-openai langchain-community faiss-cpu sentence-transformers

# Set environment variables
cp .env.example .env
# Edit .env with your API keys (OPENAI_API_KEY or OPENROUTER_API_KEY)

# Start backend server
uv run uvicorn api:app --reload
```

### 2. Frontend Setup

```bash
cd frontend

# Install dependencies
bun install

# Start development server
bun run dev
```

### 3. Open App

Visit [http://localhost:5173](http://localhost:5173)

## Environment Variables

### Backend (.env)

```env
OPENROUTER_API_KEY=your_api_key
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
MODEL_NAME=openai/gpt-4o-mini
```

### Frontend (frontend/.env.local)

```env
NEXT_PUBLIC_API_URL=http://localhost:8000
```

## API Endpoints

| Method | Endpoint                 | Description               |
| ------ | ------------------------ | ------------------------- |
| GET    | `/health`                | Health check              |
| POST   | `/v1/chat`               | Send chat message         |
| POST   | `/v1/upload`             | Upload document (PDF/TXT) |
| GET    | `/v1/sources`            | List uploaded sources     |
| DELETE | `/v1/sources/{filename}` | Delete a source           |

## Features

- 📁 **Document Upload** - PDF and TXT file support
- 🔍 **Semantic Search** - FAISS vector store with HuggingFace embeddings
- 💬 **Conversational AI** - LangChain RAG pipeline
- 🎨 **Modern UI** - NotebookLM-inspired dark theme
- ⚡ **Fast** - Next.js 16 + Bun runtime

## Tech Stack

**Backend:**

- FastAPI
- LangChain
- FAISS
- HuggingFace Embeddings

**Frontend:**

- Next.js 16 (App Router)
- Tailwind CSS
- shadcn/ui
- Bun

## License

MIT
