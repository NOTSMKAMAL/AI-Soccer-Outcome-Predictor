# FUTURE FC (Soccer Outcome Predictor)

**Course**: CS180 Final Project
**Team**: SM Kamal, Brian Garcia

---

## Source Code

| Layer | Path |
|---|---|
| Frontend (Next.js) | [`frontend/src/`](frontend/src/) |
| Backend API (FastAPI) | [`backend/`](backend/) |
| Prediction Engine (Dixon-Coles + Gemini) | [`engine/`](engine/) |
| Storage / SportMonks Client | [`storage/`](storage/) |

---

## Tests

All tests are located in [`tests/`](tests/).

| File | What it covers |
|---|---|
| [`tests/test_prediction_engine.py`](tests/test_prediction_engine.py) | Dixon-Coles math, confidence labels, winner logic, edge cases, regression invariants |
| [`tests/test_sportmonks_client.py`](tests/test_sportmonks_client.py) | SportMonks storage layer (HTTP success, 404 error, team data check) |

Run all tests from the project root:

```bash
pytest tests/
```

---

## Requirements Specification and Design Document

[`docs/requirements_specification.md`](docs/requirements_specification.md)

Covers all three functionalities (User Authentication, Fixture Discovery, Match Prediction) in Lab 4 format:
- **Part A** - Inputs, outputs, success paths, and failure/edge cases
- **Part B** - Architecture mapping (interface / engine / storage responsibilities)
- **Part C** - Interface contracts with exact function signatures, payloads, and failure statuses

---

## Demo Video

Watch the Demo Video: [https://youtu.be/CS180DEMO](https://www.youtube.com/watch?v=s4UfIk_ctJw)


---

## Setup and Execution Instructions

### Prerequisites

- Python 3.11+
- Node.js 18+
- npm 9+

---

### 1. Clone the Repository

```bash
git clone https://github.com/your-org/final-project-sm-kamal-brian-garcia.git
cd final-project-sm-kamal-brian-garcia
```

---

### 2. Backend Setup

#### 2a. Create and activate a virtual environment

```bash
# macOS / Linux
python3 -m venv venv
source venv/bin/activate

# Windows
python -m venv venv
venv\Scripts\activate
```

#### 2b. Install Python dependencies

```bash
pip install -r requirements.txt
```

#### 2c. Configure environment variables

Copy the example file and fill in your keys:

```bash
cp .env.example .env
```

Edit `.env`:

```
SPORTMONKS_API_KEY=your_sportmonks_api_key
GEMINI_API_KEY=your_gemini_api_key
FIREBASE_SERVICE_ACCOUNT_PATH=./serviceAccountKey.json
```

- **SportMonks API key**: sportmonks.com -> Account -> API Tokens
- **Gemini API key**: aistudio.google.com -> Get API key
- **Firebase service account**: Firebase Console -> Project Settings -> Service Accounts -> Generate new private key -> save as serviceAccountKey.json in the project root

#### 2d. Start the backend server

```bash
uvicorn backend.main:app --reload --port 8000
```

The API will be available at http://localhost:8000

---

### 3. Frontend Setup

#### 3a. Install dependencies

```bash
cd frontend
npm install
```

#### 3b. Configure environment variables

```bash
cp .env.example .env.local
```

Edit `frontend/.env.local`:

```
NEXT_PUBLIC_FIREBASE_API_KEY=your_firebase_api_key
NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN=your_project.firebaseapp.com
NEXT_PUBLIC_FIREBASE_PROJECT_ID=your_project_id
NEXT_PUBLIC_FIREBASE_STORAGE_BUCKET=your_project.appspot.com
NEXT_PUBLIC_FIREBASE_MESSAGING_SENDER_ID=your_sender_id
NEXT_PUBLIC_FIREBASE_APP_ID=your_app_id
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
```

All Firebase values are found in Firebase Console -> Project Settings -> Your apps -> Web app -> SDK config.

#### 3c. Start the frontend

```bash
npm run dev
```

The app will be available at http://localhost:3000

---

### 4. Running Both Together

Open two terminals:

**Terminal 1 - Backend:**
```bash
source venv/bin/activate
uvicorn backend.main:app --reload --port 8000
```

**Terminal 2 - Frontend:**
```bash
cd frontend
npm run dev
```

Then open http://localhost:3000 in your browser.

---

### 5. Running Tests

From the project root (with the virtual environment activated):

```bash
pytest tests/
```

To run a specific test file:

```bash
pytest tests/test_prediction_engine.py -v
pytest tests/test_sportmonks_client.py -v
```
