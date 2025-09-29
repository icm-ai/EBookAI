# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is EBookAI, a modern e-book processing platform integrated with AI capabilities. The platform supports multi-format conversion, intelligent typesetting, content generation, and professional publishing.

The project is currently in the early planning stages with a focus on building a Minimum Viable Product (MVP) that includes core functionality for format conversion, AI text processing, and basic web interface.

## High-Level Architecture

Based on the simplified project outline, the intended architecture is:

```plaintext
Frontend (Web)
    ↓
API Gateway (FastAPI)
    ↓
Service Layer
    ├── Format Conversion Service
    ├── AI Processing Service
    └── Typesetting Service
    ↓
Infrastructure Layer
    ├── Message Queue (Redis/Celery)
    ├── Database (PostgreSQL)
    ├── File Storage (MinIO)
    └── Cache (Redis)
```

## Core Technology Stack

- **Backend**: Python 3.11+, FastAPI, SQLAlchemy
- **Asynchronous Processing**: Celery + Redis
- **AI Integration**: OpenAI API, Anthropic Claude (through Provider interface)
- **Format Conversion**: Calibre, pandoc
- **Frontend**: React 18 + TypeScript
- **Database**: PostgreSQL + Redis
- **Deployment**: Docker

## Planned Directory Structure

```plaintext
ebook-ai-platform/
├── README.md
├── LICENSE
├── docker-compose.yml
├── requirements.txt
├── pyproject.toml
│
├── backend/
│   ├── src/
│   │   ├── __init__.py
│   │   ├── main.py                 # FastAPI application entry
│   │   ├── config/                 # Configuration management
│   │   ├── api/                    # API routes
│   │   │   ├── v1/
│   │   │   │   ├── conversion.py
│   │   │   │   ├── ai.py
│   │   │   │   └── typesetting.py
│   │   ├── services/               # Business logic
│   │   │   ├── conversion/
│   │   │   ├── ai/
│   │   │   └── typesetting/
│   │   ├── models/                 # Data models
│   │   ├── schemas/                # Pydantic schemas
│   │   ├── database/               # Database related
│   │   ├── utils/                  # Utility functions
│   │   └── workers/                # Celery tasks
│   ├── tests/
│   └── docs/
│
├── frontend/
│   ├── web/                        # React Web application
│   │   ├── src/
│   │   │   ├── components/
│   │   │   ├── pages/
│   │   │   ├── services/
│   │   │   └── utils/
│   │   ├── public/
│   │   └── package.json
│
├── deployment/
│   └── docker/
│
└── docs/                           # Project documentation
```

## Development Guidelines

At this early stage, the repository contains primarily documentation outlining the planned project structure and features. When implementing code:

1. Follow the simplified directory structure as outlined above
2. Focus on implementing the MVP features:
   - Basic format conversion (EPUB ↔ PDF ↔ MOBI)
   - Simple web interface
   - Basic AI text processing
   - User system and file management

3. Use FastAPI for backend services with proper RESTful API design
4. Implement asynchronous processing with Celery for long-running tasks
5. Follow standard Python code quality tools (Black, Pylint, pytest)
6. Write tests using pytest framework

## Commands (to be implemented)

Once the project structure is implemented, the following commands will be commonly used:

### Backend Development

- `uvicorn src.main:app --reload` - Run the FastAPI development server
- `pytest` - Run all tests
- `pytest tests/test_module.py::test_function` - Run a specific test
- `black .` - Format code with Black
- `pylint src/` - Run pylint for code analysis

### Frontend Development

- `npm start` - Run the React development server
- `npm test` - Run frontend tests
- `npm run build` - Build the production frontend

### Docker

- `docker-compose up -d` - Start all services in detached mode
- `docker-compose down` - Stop all services

## Next Steps

The project is in early planning stages. Implementation should begin with:

1. Setting up the basic project structure
2. Implementing the backend API structure
3. Creating the core format conversion services
4. Building a simple web interface
5. Integrating basic AI processing capabilities

The architecture has been simplified to follow the KISS (Keep It Simple, Stupid) principle while maintaining extensibility for future features.
