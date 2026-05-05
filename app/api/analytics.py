import time

import boto3
from fastapi import APIRouter, Depends, HTTPException

from app.core.config import settings
from app.middleware.auth import get_current_user_id

router = APIRouter(prefix="/api/analytics", tags=["analytics"])

SQL_CATEGORIAS_DEMANDA = """
SELECT c.name as categoria,
       COUNT(DISTINCT b.id) as total_libros,
       COUNT(DISTINCT s.id) as total_solicitudes,
       ROUND(COUNT(DISTINCT s.id) * 1.0 / COUNT(DISTINCT b.id), 2) as solicitudes_por_libro
FROM readme_db.categories c
LEFT JOIN readme_db.books b ON b.category_id = c.id
LEFT JOIN readme_db.solicitudes s ON s.book_id = b.id
GROUP BY c.name
ORDER BY total_solicitudes DESC
"""

SQL_USUARIOS_ACTIVOS_ZONA = """
SELECT z.name as zona, u.name as usuario,
       COUNT(t.id) as total_transacciones
FROM readme_db.users u
JOIN readme_db.zones z ON u.zone_id = z.id
JOIN readme_db.transactions t ON t.buyer_id = u.id
GROUP BY z.name, u.name
ORDER BY total_transacciones DESC
LIMIT 20
"""

SQL_TOP_VENDEDORES_CATEGORIA = """
SELECT categoria, vendedor, ventas, rating
FROM (
  SELECT c.name as categoria, u.name as vendedor,
         COUNT(DISTINCT t.id) as ventas,
         ROUND(AVG(r.rating), 2) as rating,
         ROW_NUMBER() OVER (
           PARTITION BY c.name
           ORDER BY COUNT(DISTINCT t.id) DESC
         ) as rn
  FROM readme_db.books b
  JOIN readme_db.categories c ON b.category_id = c.id
  JOIN readme_db.transactions t ON t.book_id = b.id
  JOIN readme_db.users u ON u.id = t.seller_id
  JOIN readme_db.reviews r ON r.target_user_id = u.id
  GROUP BY c.name, u.name
)
WHERE rn <= 5
ORDER BY categoria, ventas DESC
"""

SQL_TASA_EXITO_ZONA = """
SELECT z.name as zona,
       COUNT(DISTINCT s.id) as total_solicitudes,
       COUNT(DISTINCT t.id) as transacciones_completadas,
       ROUND(COUNT(DISTINCT t.id) * 100.0 / COUNT(DISTINCT s.id), 2) as tasa_exito_pct
FROM readme_db.zones z
LEFT JOIN readme_db.users u ON u.zone_id = z.id
LEFT JOIN readme_db.solicitudes s ON s.buyer_id = u.id
LEFT JOIN readme_db.transactions t ON t.buyer_id = u.id
GROUP BY z.name
ORDER BY tasa_exito_pct DESC
"""

SQL_ZONAS_ACTIVIDAD = "SELECT * FROM readme_db.vista_zonas_actividad"

SQL_CATEGORIAS_VISTA = "SELECT * FROM readme_db.vista_categorias_demanda"


def _athena_client():
    session = boto3.Session(
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID or None,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY or None,
        aws_session_token=settings.AWS_SESSION_TOKEN or None,
        region_name=settings.AWS_REGION,
    )
    return session.client("athena")


def _poll(client, execution_id: str) -> None:
    deadline = time.time() + 30
    while time.time() < deadline:
        status = client.get_query_execution(QueryExecutionId=execution_id)
        state = status["QueryExecution"]["Status"]["State"]
        if state == "SUCCEEDED":
            return
        if state in ("FAILED", "CANCELLED"):
            reason = status["QueryExecution"]["Status"].get("StateChangeReason", "Unknown")
            raise HTTPException(status_code=500, detail=f"Athena error: {reason}")
        time.sleep(1)
    raise HTTPException(status_code=500, detail="Athena query timeout")


def _fetch_results(client, execution_id: str) -> list[dict]:
    kwargs: dict = {"QueryExecutionId": execution_id}
    headers: list[str] | None = None
    rows: list[dict] = []
    while True:
        page = client.get_query_results(**kwargs)
        page_rows = page["ResultSet"]["Rows"]
        start = 0
        if headers is None:
            headers = [col.get("VarCharValue", "") for col in page_rows[0]["Data"]]
            start = 1
        for row in page_rows[start:]:
            rows.append({headers[j]: col.get("VarCharValue", "") for j, col in enumerate(row["Data"])})
        token = page.get("NextToken")
        if not token:
            break
        kwargs["NextToken"] = token
    return rows


def run_query(sql: str) -> list[dict]:
    client = _athena_client()
    resp = client.start_query_execution(
        QueryString=sql,
        QueryExecutionContext={"Database": settings.ATHENA_DATABASE},
        ResultConfiguration={"OutputLocation": settings.ATHENA_OUTPUT_BUCKET},
    )
    execution_id = resp["QueryExecutionId"]
    _poll(client, execution_id)
    return _fetch_results(client, execution_id)


@router.get("/categorias-demanda")
def categorias_demanda(_: int = Depends(get_current_user_id)):
    return run_query(SQL_CATEGORIAS_DEMANDA)


@router.get("/usuarios-activos-zona")
def usuarios_activos_zona(_: int = Depends(get_current_user_id)):
    return run_query(SQL_USUARIOS_ACTIVOS_ZONA)


@router.get("/top-vendedores-categoria")
def top_vendedores_categoria(_: int = Depends(get_current_user_id)):
    return run_query(SQL_TOP_VENDEDORES_CATEGORIA)


@router.get("/tasa-exito-zona")
def tasa_exito_zona(_: int = Depends(get_current_user_id)):
    return run_query(SQL_TASA_EXITO_ZONA)


@router.get("/zonas-actividad")
def zonas_actividad(_: int = Depends(get_current_user_id)):
    return run_query(SQL_ZONAS_ACTIVIDAD)


@router.get("/categorias-vista")
def categorias_vista(_: int = Depends(get_current_user_id)):
    return run_query(SQL_CATEGORIAS_VISTA)
