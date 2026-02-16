# Posture Analysis Engine
A comprehensive system for analyzing posture data and generating recommendations using AI-powered insights. This project combines an input collector for processing logs with a FastAPI-based backend recommendation engine.
## Project Structure
Project/
├── input_collector/          # Log collection and processing module
│   ├── main.py              # Main entry point
│   ├── models.py            # Data models
│   ├── log_parser.py        # Log parsing utilities
│   ├── storage.py           # Data storage operations
│   ├── generate_2hr_session.py
│   ├── requirements.txt
│   └── data/
│       └── flutter_raw_logs.jsonl
├── posture_engine/          # FastAPI backend service
│   ├── app/
│   │   ├── main.py          # FastAPI application entry
│   │   ├── config.py        # Configuration settings
│   │   ├── models.py        # API data models
│   │   ├── scoring.py       # Posture scoring logic
│   │   ├── utils.py         # Utility functions
│   │   └── recommendation/  # AI recommendation engine
│   └── requirements.txt
└── env/                      # Python virtual environment
## Prerequisites
- Python 3.8+
- Virtual environment (included as `env/`)

## Installation

### 1. Activate Virtual Environment

**Windows (PowerShell):**
```powershell
.\env\Scripts\Activate.ps1
```

**Windows (CMD):**
```cmd
.\env\Scripts\activate.bat
```

**Linux/macOS:**
```bash
source env/bin/activate
```

### 2. Install Dependencies

**For Input Collector:**
```bash
cd input_collector
pip install -r requirements.txt
cd ..
```

**For Posture Engine:**
```bash
cd posture_engine
pip install -r requirements.txt
cd ..
```

## How to Run

### Quick Start Guide

#### Step 1: Activate Virtual Environment
```powershell
# Windows PowerShell
.\env\Scripts\Activate.ps1
```

#### Step 2: Set Up Environment Variables
Create a `.env` file in the project root:
```
OPENAI_API_KEY=your_api_key
GROQ_API_KEY=your_api_key
```

#### Step 3: Run Input Collector (Optional)
To process and collect posture logs:
```powershell
cd input_collector
python main.py
```

#### Step 4: Run Posture Engine API
In a new terminal with the virtual environment activated:
```powershell
cd posture_engine
uvicorn app.main:app --reload
```

#### Step 5: Access the API
- **Web Interface**: Open your browser and go to `http://localhost:8000/docs`
- **API Base URL**: `http://localhost:8000`

### Complete Running Workflow

**Terminal 1 - Input Collector:**
```powershell
.\env\Scripts\Activate.ps1
cd input_collector
python main.py
```

**Terminal 2 - Posture Engine API:**
```powershell
.\env\Scripts\Activate.ps1
cd posture_engine
uvicorn app.main:app --reload
```

## Usage

### Input Collector

Processes and collects posture-related logs:

```bash
cd input_collector
python main.py
```

### Posture Engine API
Start the FastAPI server:
```bash
cd posture_engine
uvicorn app.main:app --reload
```

The API will be available at `http://localhost:8000`
- API Documentation: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## Dependencies

Key packages included:
- **FastAPI** - Modern web framework
- **Uvicorn** - ASGI server
- **Pydantic** - Data validation
- **OpenAI/Groq** - AI integration
- **NumPy** - Numerical computing
- **Requests** - HTTP client
- **Python-dotenv** - Environment variable management

## Configuration

### Environment Variables

Create a `.env` file in the project root to configure:
```
OPENAI_API_KEY=your_key_here
GROQ_API_KEY=your_key_here
# Add other configuration as needed
```

## Contributing
1. Activate the virtual environment
2. Install requirements from the relevant module
3. Make your changes
4. Test thoroughly

