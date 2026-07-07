# DevIntelliFlow Frontend

Next.js frontend for DevIntelliFlow, an AI-assisted project management system with requirement generation and requirement classification workflows.

## Features

- User authentication with Firebase.
- Project dashboard and project workspace.
- Requirement generation/classification UI connected to the backend API.
- Project metrics, calendar, settings, and profile screens.

## Tech Stack

- Next.js 15
- React 19
- TypeScript
- Firebase
- Tailwind CSS
- Framer Motion
- Lucide icons

## Setup

```powershell
cd Frontend
npm install
copy .env.example .env.local
```

Update `.env.local` with your Firebase configuration and backend API URL.

Required backend API variable:

```env
NEXT_PUBLIC_REQUIREMENT_API_BASE=http://localhost:8000
```

## Development

```powershell
npm run dev
```

Development URL:

```text
http://localhost:3000
```

## Production Build

```powershell
npm run build
npm start
```

## Backend Dependency

Run the requirement categorization feature before using requirement generation or classification:

```powershell
cd "..\Requirement Categorization Feature"
python api_server.py
```

Backend API URL:

```text
http://localhost:8000
```
