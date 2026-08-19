// Runtime configuration for the frontend.
//
// By default the frontend assumes the backend is published on localhost:8000
// (the port docker-compose exposes it on). If you deploy the backend
// elsewhere, override this before app.js loads — e.g. by editing this file
// or injecting a different value at container start.
window.RAG_CONFIG = {
  API_BASE: (window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1")
    ? `${window.location.protocol}//${window.location.hostname}:8000/api/v1`
    : `${window.location.protocol}//${window.location.hostname}:8000/api/v1`,
};
