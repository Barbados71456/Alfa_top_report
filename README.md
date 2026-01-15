services:
  - type: web
    name: finance-backend
    env: python
    buildCommand: pip install -r requirements.txt
    startCommand: uvicorn main:app --host 0.0.0.0 --port 10000
    envVars:
      - key: DATABASE_URL
        fromDatabase:
          name: finance-db
          property: connectionString
      - key: SECRET_KEY
        generateValue: true

  - type: web
    name: finance-frontend
    env: static
    buildCommand: npm run build
    staticPublishPath: ./build
    routes:
      - type: rewrite
        source: /api/*
        destination: https://finance-backend.onrender.com/api/*

databases:
  - name: finance-db
    databaseName: finance_db
    user: finance_user# Alfa_Report
# Alfa_Report
