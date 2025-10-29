# Project Context

## Purpose
EBookAI is a modern e-book processing platform integrated with AI capabilities. The platform supports multi-format conversion, intelligent typesetting, content generation, and professional publishing. The project is currently in early development with a focus on building an MVP that includes core functionality for format conversion, AI text processing, and basic web interface.

## Tech Stack
- **Backend**: Python 3.11+, FastAPI, SQLAlchemy
- **Asynchronous Processing**: Celery + Redis
- **AI Integration**: OpenAI API, Anthropic Claude (through Provider interface)
- **Format Conversion**: Calibre, pandoc
- **Frontend**: React 18 + TypeScript
- **Database**: PostgreSQL + Redis
- **Deployment**: Docker
- **Testing**: pytest, coverage

## Project Conventions

### Code Style
- Python formatting: Black
- Linting: Pylint
- Follow PEP 8 conventions
- Professional and rigorous code without unnecessary symbols
- Minimal logging unless needed for debugging
- Objective, professional descriptive style without "we" or "I" pronouns

### Architecture Patterns
- Three-layer architecture:
  - Frontend (Web) → API Gateway (FastAPI) → Service Layer
  - Service Layer: Format Conversion, AI Processing, Typesetting
  - Infrastructure Layer: Message Queue (Redis/Celery), Database (PostgreSQL), File Storage (MinIO), Cache (Redis)
- RESTful API design
- Asynchronous processing for long-running tasks via Celery
- KISS principle: Keep It Simple, Stupid - simplicity first, avoid complexity without justification

### Testing Strategy
- pytest framework for all testing
- Focus on high coverage (~85%+)
- Test categories: unit tests, integration tests, API tests
- Test files mirror source structure

### Git Workflow
- Main branch: `main`
- Development branch: `develop`
- Feature branches from develop
- Conventional commits preferred
- All documentation and code must be professional and rigorous

## Domain Context
- E-book formats: EPUB, PDF, MOBI, AZW3
- AI text processing: summarization, translation, content enhancement
- Typesetting requirements for professional publishing
- Batch conversion processing for multiple files
- File cleanup and temporary storage management

## Important Constraints
- Follow Occam's Razor: choose the simplest action
- MVP scope: basic format conversion, simple web interface, basic AI text processing, user system and file management
- Default to <100 lines of new code per change
- Single-file implementations until proven insufficient
- Avoid frameworks without clear justification

## External Dependencies
- OpenAI API for AI capabilities
- Anthropic Claude API for AI capabilities
- Calibre for e-book format conversion
- pandoc for document conversion
- Redis for message queue and cache
- PostgreSQL for persistent storage
- MinIO for object storage
