# Sentient

Sentient is a sophisticated RAG (Retrieval-Augmented Generation) based AI NPC system. It empowers developers to bring their game worlds to life by uploading game manuals, custom instructions, and dialogue style PDFs. This data is processed by a robust RAG engine and made accessible via a RESTful API, allowing NPCs to deliver personalized, conversational dialogues that remain contextually accurate to the game's lore and character personas.

## Key Features

- 📁 **Dynamic Document Upload** - Easily ingest game manuals and custom style PDFs to expand NPC knowledge.
- 💬 **Context-Aware Dialogues** - Generation of responses via RESTful API that are grounded in your uploaded documentation.
- 🎮 **Real-time Integration** - Seamlessly connects with live game instances for interactive NPC experiences.
- 🔍 **Semantic Search** - Powerful retrieval using FAISS vector store to find the most relevant lore instantly.
- 🧠 **Personalized Personas** - RAG-driven intelligence that shapes unique character voices and behaviors.

## Tech Stack

- **Backend:** FastAPI (Python), LangChain, FAISS
- **Frontend:** Next.js (TypeScript), Tailwind CSS, shadcn/ui
- **Infrastructure:** RESTful API, Docker-ready

## Achievements & Impact

- **Achievements:** Advanced RAG-based NPC Interaction.
- **Impact:** Revolutionizing In-game NPC Conversationality.

---

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
    │   ├── components/     # React components
    │   ├── hooks/          # Custom hooks
    │   ├── lib/            # Utilities & API client
    │   └── types/          # TypeScript types
    └── package.json
```

## Quick Start

### 1. Backend Setup

```bash
# Install dependencies using uv (Recommended)
uv sync

# OR using pip
# pip install fastapi uvicorn python-multipart python-dotenv langchain-openai langchain-community faiss-cpu sentence-transformers

# Set environment variables
cp .env.example .env
# Edit .env with your API keys (OPENROUTER_API_KEY is preferred)

# Start backend server
uv run uvicorn api:app --reload
```

### 2. Frontend Setup

```bash
cd frontend

# Install dependencies
npm install  # (or bun install / yarn)

# Start development server
npm run dev
```

### 3. Open App

Visit [http://localhost:5173](http://localhost:5173) (if using Vite) or [http://localhost:3000](http://localhost:3000) (if using Next.js).

## Environment Variables

### Backend (.env)

```env
OPENROUTER_API_KEY=your_api_key
MODEL_NAME=openai/gpt-4o-mini
```

## API Endpoints

| Method | Endpoint                 | Description               |
| ------ | ------------------------ | ------------------------- |
| GET    | `/health`                | Health check              |
| POST   | `/v1/chat`               | Send chat message         |
| POST   | `/v1/upload`             | Upload document (PDF/TXT) |
| GET    | `/v1/sources`            | List uploaded sources     |
| DELETE | `/v1/sources/{filename}` | Delete a source           |

## License

MIT
