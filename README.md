# readme-analytics

Microservicio de analytics. Ejecuta queries en AWS Athena y expone los resultados como endpoints REST.

## Configuracion

```bash
cp .env.example .env
# Rellenar JWT_SECRET, credenciales AWS y ATHENA_OUTPUT_BUCKET
```

## Desarrollo local

```bash
uv run uvicorn app.main:app --reload --port 8005
```

Documentacion disponible en http://localhost:8005/docs

