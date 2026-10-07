# WasteAI

Live site: https://wasteai.duckdns.org/

WasteAI is a web app that tells you how to dispose of an item. Upload a photo and it returns a waste category and disposal instructions.

> **Status:** under active development.
> Built as coursework in the Department of Artificial Intelligence, College of Science, Alkafeel University.

---

## Overview

Most people aren't sure which bin an item goes in, and wrong guesses end up contaminating recycling. WasteAI uses a computer vision model to sort items into five categories (recyclable, organic, hazardous, general, e-waste) and shows disposal instructions for each.

Features:

* Classify an item from an uploaded image or a text description.
* A reference section covering segregation rules, recycling symbols, and ways to cut waste.

## Authors

Ali Haidar and Muhammad Najm, Department of Artificial Intelligence, College of Science, Alkafeel University.

---

## Tech Stack

| Layer | Technology |
| --- | --- |
| Frontend | React / Next.js, Tailwind CSS |
| Backend | Node.js (Express) or Python (FastAPI) |
| Database | PostgreSQL or MongoDB |
| ML | TensorFlow or PyTorch, OpenCV |

---

## Getting Started

### Prerequisites

* Node.js 18 or newer
* npm or yarn
* PostgreSQL or MongoDB, depending on your configuration

### Setup

1. Clone the repository:

```bash
   git clone https://github.com/your-username/waste-ai.git
   cd waste-ai
```

2. Copy the example environment files:

```bash
   cp server/.env.example server/.env
   cp client/.env.example client/.env
```

3. Fill in `server/.env`:

```env
   PORT=5000
   DATABASE_URL=mongodb://localhost:27017/wasteai
   JWT_SECRET=your_jwt_secret_key
   ML_MODEL_ENDPOINT=http://localhost:8000/predict
```

### Run locally

1. Install dependencies in both folders:

```bash
   cd server && npm install
   cd ../client && npm install
```

2. Start the backend:

```bash
   cd server
   npm run dev
```

3. In a second terminal, start the frontend:

```bash
   cd client
   npm run dev
```

4. Open http://localhost:3000.

## Roadmap

- [x] Project structure and backend API setup
- [ ] ML image classification integration
- [ ] User dashboard and search history
- [ ] Admin panel for content management
- [ ] Mobile layout and PWA support
- [ ] Multi-language support
