# Frontend (Reference Workbench)  
  
The frontend is an optional reference UI for interacting with the **simple‑legal‑doc** system during development and review workflows.  
  
It is intended as a workbench for humans and agents to inspect, edit, and approve structured semantic inputs prior to document generation and sealing.
  
---  
  
## Purpose  
  
The frontend exists to support:  
  
- structured editing of semantic JSON payloads  
- review and correction of document inputs  
- explicit human approval before document generation or sealing  
- experimentation and integration during development  
  
It demonstrates how automated systems and human reviewers may interact with the backend, but it is not required for backend operation.  
  
---  
  
## Architecture  
  
The frontend is a standalone web application built with:  
  
- React  
- Vite  
- MUI  
  
It communicates exclusively with backend HTTP APIs and holds no private keys, signing credentials, or verification logic.  
  
---  
  
## Running the Frontend  
  
When using the provided `docker-compose.yml`, the frontend is started automatically.  
  
For standalone development, refer to the configuration and scripts in this directory.  
  
---  
  
## Design Principle  
  
The frontend is intentionally optional.  
  
The system is designed to remain fully operable even if the frontend is removed entirely.