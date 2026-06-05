import json
import os


projects_data = [
    {
        "name": "Pricesphere_web",
        "description": "Next.js price tracking and prediction platform utilizing Flask and Hugging Face models.",
        "language": "TypeScript",
        "url": "https://github.com/Piyush0049/Pricesphere_web",
        "created_at": "2024-06-01T12:00:00Z",
        "readme": """# PriceSphere - AI Price Tracking Platform

PriceSphere is an advanced web application that scrapes product prices, tracks history, and uses machine learning to predict future price trends.

## Tech Stack
* **Frontend:** Next.js, TypeScript, Tailwind CSS, Shadcn UI
* **Backend:** Flask, Python (ML / Prediction service), Node.js (Core API)
* **ML/AI:** Hugging Face Models, Scikit-learn
* **Database:** MongoDB

## Design Tradeoffs
* **Database Choice:** Chose MongoDB over PostgreSQL because scraped product details have varied structures across different e-commerce platforms. Document store allows schema flexibility.
* **Separation of Services:** Put the web scraping and ML prediction service in a Flask app, separate from the primary Node.js/Next.js API. This prevents Python dependencies from blocking frontend server scaling.

## What I'd Do Differently
* Use a vector database to match similar products across different e-commerce platforms instead of relying entirely on text-based match logic.
* Implement serverless tasks (e.g. AWS Lambda) for scraping rather than a single running server process to avoid IP bans and improve scalability.
"""
    },
    {
        "name": "blink-blog",
        "description": "Next.js blogging platform integrated with AI speech-to-text and content generation.",
        "language": "JavaScript",
        "url": "https://github.com/Piyush0049/blink-blog",
        "created_at": "2024-06-03T17:58:33Z",
        "readme": """# Blink & Blog - AI Blogging Platform

An interactive platform allowing users to generate articles, convert speech to text, and customize layouts dynamically.

## Tech Stack
* **Frontend/Backend:** Next.js (MERN context)
* **APIs:** Gemini AI (content generation), AssemblyAI (voice-to-text)
* **Database:** MongoDB
* **Styling:** Framer Motion, Tailwind CSS

## Design Tradeoffs
* **Speech API:** Integrated AssemblyAI for voice-to-text due to its superior punctuation handling and speaker identification over standard browser speech APIs.
* **Next.js Route Handlers:** Used Next.js server actions and API route handlers instead of a separate Express.js server, making it a single consolidated deployment.

## What I'd Do Differently
* Implement dynamic caching on generated blogs using Redis.
* Build a collaborative writing editor (like Google Docs) using Y.js and WebSockets so multiple authors can write blogs in real-time.
"""
    },
    {
        "name": "Aerosafe-AI-based-stimulator",
        "description": "UAV simulation and airspace safety tracker rendering dynamic 3D paths in the browser.",
        "language": "TypeScript",
        "url": "https://github.com/Piyush0049/Aerosafe-AI-based-stimulator",
        "created_at": "2025-10-07T13:30:09Z",
        "readme": """# AeroSafe - AI UAV Safety Simulator

A 3D simulation platform for tracking Unmanned Aerial Vehicles (UAVs) in restricted airspaces. It triggers alerts for safety boundary violations using collision algorithms.

## Tech Stack
* **Frontend:** Next.js, React Three Fiber, Three.js, WebGL
* **Language:** TypeScript
* **State Management:** Zustand

## Design Tradeoffs
* **R3F vs raw Three.js:** Used React Three Fiber (R3F) to manage 3D meshes as declarative React elements. It increased developer velocity and simplified state binding (Zustand), though it adds a tiny overhead over native WebGL.

## What I'd Do Differently
* Offload collision calculations from the main JavaScript thread into Web Workers or WebAssembly (Wasm compiled from Rust) to maintain a locked 60 FPS frame rate under high UAV counts.
"""
    },
    {
        "name": "Luxe_Next.js",
        "description": "Luxury catalog and landing page using server-rendered Next.js with rich layout animations.",
        "language": "JavaScript",
        "url": "https://github.com/Piyush0049/Luxe_Next.js",
        "created_at": "2024-05-10T10:00:00Z",
        "readme": """# Luxe - Luxury Product Catalog

A luxury e-commerce catalog page highlighting fluid page transitions and optimized web graphics.

## Tech Stack
* **Framework:** Next.js
* **Styling:** Tailwind CSS, Framer Motion

## Design Tradeoffs
* **SSG:** Used Static Site Generation (SSG) for catalog listings to achieve near-zero loading times and exceptional SEO rating, trading off real-time inventory updates (which can be fetched client-side).

## What I'd Do Differently
* Integrate Stripe checkout and dynamic webhook listeners directly into the Next.js backend.
"""
    },
    {
        "name": "Devpulse",
        "description": "Developer productivity metrics dashboard displaying git activity, tasks, and system performance.",
        "language": "TypeScript",
        "url": "https://github.com/Piyush0049/Devpulse",
        "created_at": "2025-11-15T09:00:00Z",
        "readme": """# DevPulse - Developer Productivity Tracker

A real-time dashboard displaying system states, code logs, and task boards.

## Tech Stack
* **Framework:** React.js, Tailwind CSS
* **Language:** TypeScript
* **State Management:** Redux

## Design Tradeoffs
* **State:** Used Redux to manage complex global developer states (tasks, git events, notification streams) instead of simple React Context to avoid re-rendering issues.

## What I'd Do Differently
* Create a dedicated desktop menu utility using Electron.js to collect local git metrics automatically.
"""
    },
    {
        "name": "ShabdGPT",
        "description": "Hindi learning assistant with speech assessment and automated conversational practice.",
        "language": "TypeScript",
        "url": "https://github.com/Piyush0049/ShabdGPT",
        "created_at": "2024-08-20T14:00:00Z",
        "readme": """# ShabdGPT - Hindi Pronunciation Learning Assistant

ShabdGPT helps non-native speakers learn Hindi by validating pronunciation via audio and providing context-aware AI text conversations.

## Tech Stack
* **Framework:** Next.js, TypeScript
* **AI/ML:** Gemini AI, AssemblyAI (Audio intelligence)

## Design Tradeoffs
* **API Choice:** Used Gemini API for its low latency and native multilingual text generation capabilities, which performs excellently in translating and processing Hindi transcripts.

## What I'd Do Differently
* Add a gamified progression tree and offline speech-to-text models to support students without active internet connections.
"""
    },
    {
        "name": "Snap_N_Shop_Frontend",
        "description": "E-commerce portal featuring visual shopping and persistent cart configurations.",
        "language": "JavaScript",
        "url": "https://github.com/Piyush0049/Snap_N_Shop_Frontend",
        "created_at": "2024-02-15T15:30:00Z",
        "readme": """# Snap & Shop - Visual MERN Shopping Portal

MERN stack e-commerce web application featuring user auth, search filters, and an interactive purchase funnel.

## Tech Stack
* **Frontend:** React, Redux, Tailwind CSS
* **Backend:** Node.js, Express.js (MERN)
* **Auth:** Google OAuth 2.0

## Design Tradeoffs
* **Redux:** Used Redux to keep the shopping cart state persistent across page transitions and route reloads.

## What I'd Do Differently
* Integrate an AI vector-search endpoint using a model like CLIP to let users search products by uploading images.
"""
    },
    {
        "name": "Lottery_Frontend",
        "description": "Smart contract decentralized lottery client built with React and Ethers.js v6.",
        "language": "JavaScript",
        "url": "https://github.com/Piyush0049/Lottery_Frontend",
        "created_at": "2024-03-10T16:00:00Z",
        "readme": """# CryptoLottery - Blockchain Lottery Platform

Decentralized application (dApp) that allows users to enter token lottery draws verified by Ethereum Smart Contracts.

## Tech Stack
* **Frontend:** React.js, CSS3
* **Blockchain:** Ethers.js v6, Smart Contracts (Solidity)

## Design Tradeoffs
* **Direct RPC calls:** Connected to the smart contract directly using provider RPC nodes (MetaMask) without a centralized backend database. This maximizes security and preserves trustless operation.

## What I'd Do Differently
* Deploy on a Layer-2 EVM chain (like Arbitrum or Polygon) to minimize gas fees for entrants, as gas on Ethereum mainnet makes micro-lotteries expensive.
"""
    },
    {
        "name": "HexaCode_IDE",
        "description": "Web-based code editor and compiler environment with multi-file management support.",
        "language": "JavaScript",
        "url": "https://github.com/Piyush0049/HexaCode_IDE",
        "created_at": "2024-09-01T11:00:00Z",
        "readme": """# HexaCode IDE - Web Code Editor

A responsive, browser-based editor featuring code compilation, a clean file directory tree, and output panels.

## Tech Stack
* **Core:** React, Tailwind CSS
* **Editor Component:** Monaco Editor

## Design Tradeoffs
* **Monaco Editor integration:** Utilized VS Code's core editor engine (Monaco) which brings linting, formatting, and syntax trees out of the box, rather than building custom textareas.

## What I'd Do Differently
* Create secure backend sandbox runners (using Docker containers) to run user-submitted code in multiple runtimes safely.
"""
    },
    {
        "name": "meetsync_docs",
        "description": "Browser extension connecting online meetings and notes directly to calendar services.",
        "language": "JavaScript",
        "url": "https://github.com/Piyush0049/meetsync_docs",
        "created_at": "2024-07-15T09:00:00Z",
        "readme": """# MeetSync - Meeting Schedule Extension

A Chrome extension that parses online meeting calendar links, updates note templates, and syncs status logs.

## Tech Stack
* **Core:** Vanilla JavaScript, HTML5, CSS3, Chrome Extensions V3 API

## Design Tradeoffs
* **Extension Local Storage:** Used Chrome's extension sync storage to keep configuration tokens safe without requiring user accounts on a separate web database.

## What I'd Do Differently
* Expand target platforms to support Firefox and Safari extensions.
"""
    },
    {
        "name": "newsapp-piyush",
        "description": "React news aggregator showing live global stories with filter options.",
        "language": "JavaScript",
        "url": "https://github.com/Piyush0049/newsapp-piyush",
        "created_at": "2024-04-18T10:00:00Z",
        "readme": """# PulsePoint News - News Aggregator

React web app displaying real-time global news categories from various API aggregators.

## Tech Stack
* **Core:** React.js, NewsAPI, Bootstrap CSS

## Design Tradeoffs
* **Bootstrap:** Used Bootstrap for quick, responsive alignment, trading off the design customizability of Tailwind.

## What I'd Do Differently
* Store article cache logs in the browser using IndexedDB to enable reading news offline.
"""
    },
    {
        "name": "LinkHub",
        "description": "Developer profile bio page directory and link tracking platform built on Next.js.",
        "language": "JavaScript",
        "url": "https://github.com/Piyush0049/LinkHub",
        "created_at": "2024-08-01T15:00:00Z",
        "readme": """# LinkHub - Developer Profile Sharing

Next.js bookmark dashboard to manage public links, portfolio details, and contact coordinates.

## Tech Stack
* **Framework:** Next.js, Tailwind CSS
* **Database:** MongoDB

## Design Tradeoffs
* **MongoDB:** Stored developer profile layout settings in MongoDB, which easily fits dynamic schema parameters.

## What I'd Do Differently
* Implement deep link analytics tracking clicks, referrers, and geolocation of profile visitors.
"""
    },
    {
        "name": "DESTION_PIYUSHJOSHI",
        "description": "Glassmorphic creative agency landing page featuring framer motion transitions.",
        "language": "JavaScript",
        "url": "https://destion-piyushjoshi.vercel.app/",
        "created_at": "2024-05-01T08:00:00Z",
        "readme": """# Destion Design - Agency Landing Page

Creative agency landing site utilizing modern layout design and glassmorphic aesthetics.

## Tech Stack
* **Framework:** React.js, Vercel
* **Styling:** CSS3, Framer Motion

## Design Tradeoffs
* **Focus on Visuals:** Prioritized custom animation styling and fluid layout load times over building backends, as it is purely a visual design representation.

## What I'd Do Differently
* Migrate to Next.js to leverage server-side rendering for better SEO performance.
"""
    },
    {
        "name": "unfluke-design",
        "description": "Trading dashboard leaderboard mock design with instant client filtering.",
        "language": "JavaScript",
        "url": "https://leaderboardunflukepiyushjoshi-piyush-joshis-projects.vercel.app/",
        "created_at": "2024-06-15T09:00:00Z",
        "readme": """# UnFluke - Leaderboard Dashboard UI

A trading statistics dashboard featuring paginated tables, search sorting, and clean profile metrics.

## Tech Stack
* **Core:** React.js, Tailwind CSS

## Design Tradeoffs
* **Client-side Filter:** Performed all sorting and pagination logic client-side for immediate UI transitions, assuming a medium dataset limit.

## What I'd Do Differently
* Implement server-side lazy loading and search pagination to support datasets with more than 10,000 traders.
"""
    },
    {
        "name": "vrvsecurity-design",
        "description": "Security console design illustrating user access role permissions and dashboard logs.",
        "language": "JavaScript",
        "url": "https://vrv-security-gamma.vercel.app/",
        "created_at": "2024-08-30T10:00:00Z",
        "readme": """# VRV Security - Admin Console

Dashboard designed to visualize Role-Based Access Control (RBAC), user logs, and security parameters.

## Tech Stack
* **Core:** React.js, CSS3

## Design Tradeoffs
* **Mock States:** Implemented client-side state manipulation to showcase user creation and permission toggling instantly.

## What I'd Do Differently
* Connect the UI to a live RBAC Express API with JWT permission scopes.
"""
    },
    {
        "name": "todoapp",
        "description": "Task tracker application using local storage logs for persistence.",
        "language": "JavaScript",
        "url": "https://to-do-app-frontend-0049-dcgz.vercel.app/",
        "created_at": "2024-01-10T12:00:00Z",
        "readme": """# ToDoApp - Personal Task Tracker

Task management dashboard tracking priorities and status fields.

## Tech Stack
* **Framework:** React.js, CSS3
* **Persistence:** Browser LocalStorage

## Design Tradeoffs
* **LocalStorage:** Used local storage to avoid backend dependencies, keeping the application entirely serverless and fast for single-device users.

## What I'd Do Differently
* Sync tasks with external APIs like Google Tasks or Notion API.
"""
    },
    {
        "name": "fastone",
        "description": "Logistics delivery website landing page featuring transport calculators.",
        "language": "JavaScript",
        "url": "https://fastoneglobal.vercel.app/",
        "created_at": "2024-03-20T14:00:00Z",
        "readme": """# Fastone - Logistics Landing Page

Logistics landing page showcasing shipping quotes, maps, and package tracking states.

## Tech Stack
* **Core:** React.js, CSS3

## Design Tradeoffs
* **Static Assets:** Kept the site fully static with pre-rendered landing blocks for maximum loading speeds.

## What I'd Do Differently
* Integrate Google Maps API to show live delivery route routes.
"""
    },
    {
        "name": "TextUtils",
        "description": "Text editing and analysis tool processing inputs completely inside the client browser.",
        "language": "JavaScript",
        "url": "https://github.com/Piyush0049/TextUtils",
        "created_at": "2024-02-05T09:00:00Z",
        "readme": """# TextUtils - Text Analyzer

Text formatting and metrics analyzer calculating word counts, spaces, and casing.

## Tech Stack
* **Core:** React.js, CSS3

## Design Tradeoffs
* **Client-Only:** Performed all operations inside browser memory so user texts are never sent to external servers, protecting privacy.

## What I'd Do Differently
* Add Markdown rendering support and PDF download triggers.
"""
    },
    {
        "name": "dashboard",
        "description": "E-commerce administrative dashboard layout with responsive widgets.",
        "language": "JavaScript",
        "url": "https://dashboard-design-umber.vercel.app/",
        "created_at": "2024-04-01T10:00:00Z",
        "readme": """# E-Commerce Admin Dashboard

Analytics panel showing metrics charts, transaction histories, and visual notification logs.

## Tech Stack
* **Core:** React.js, Tailwind CSS
* **Charts:** Chart.js

## Design Tradeoffs
* **Tailwind CSS:** Used utility classes for fast layout structure alignment, keeping bundle size small.

## What I'd Do Differently
* Add live SSE / WebSocket notifications for incoming sales.
"""
    },
    {
        "name": "bluphlux_ui",
        "description": "Trading application UI displaying currency charts and transaction histories.",
        "language": "JavaScript",
        "url": "https://github.com/Piyush0049/bluphlux_ui",
        "created_at": "2024-07-20T15:00:00Z",
        "readme": """# BluPhlux UI - Trading Platform Layout

Financial portfolio dashboard detailing charts and coin transactions.

## Tech Stack
* **Core:** React.js, Redux, Tailwind CSS
* **State Persistence:** Redux Persist

## Design Tradeoffs
* **Redux Persist:** Used to persist custom dashboard layouts and dark/light settings in browser storage.

## What I'd Do Differently
* Connect trading graphs to live currency WebSockets.
"""
    }
]

# Write to file
output_path = os.path.abspath("data/github_repos.json")
with open(output_path, "w", encoding="utf-8") as f:
    json.dump(projects_data, f, indent=2, ensure_ascii=False)

print(f"Successfully populated {len(projects_data)} projects to {output_path}")
