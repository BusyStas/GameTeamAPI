"""Azure SQL Database connection module.

This module provides connection helpers and stored procedure execution
for the db-PersonalAssistants database using the GameTeam schema.
"""

import os
import logging
import pyodbc
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

# Schema name constant for all GameTeam stored procedures
GAMETEAM_SCHEMA = "GameTeam"


def get_azure_connection_string() -> str:
    """Build and return the Azure SQL connection string from environment variables."""
    server = os.environ.get('AZURE_SQL_SERVER_NAME')
    database = os.environ.get('AZURE_SQL_DATABASE_NAME')
    username = os.environ.get('AZURE_SQL_USER_NAME')
    password = os.environ.get('AZURE_SQL_USER_PASSWORD')

    if not all([server, database, username, password]):
        raise ValueError("Missing Azure SQL connection environment variables")

    return (
        f"DRIVER={{ODBC Driver 17 for SQL Server}};"
        f"SERVER={server};"
        f"DATABASE={database};"
        f"UID={username};"
        f"PWD={password};"
        f"Encrypt=yes;"
        f"TrustServerCertificate=no;"
        f"Connection Timeout=30;"
    )


def get_azure_connection(autocommit: bool = False):
    """Get a new Azure SQL connection."""
    conn = pyodbc.connect(get_azure_connection_string())
    conn.autocommit = autocommit
    return conn


def _wvarchar_input_sizes(values):
    """Return a setinputsizes list that forces every Python str to bind as
    SQL_WVARCHAR (Unicode/UCS-2). Without this, pyodbc on ODBC Driver 17 may
    fall back to SQL_VARCHAR, which truncates non-Latin characters before they
    reach NVARCHAR columns or NVARCHAR procedure parameters.
    """
    sizes = []
    for v in values:
        if isinstance(v, str):
            sizes.append((pyodbc.SQL_WVARCHAR, 0, 0))
        else:
            sizes.append(None)
    return sizes


def execute_sproc(sproc_name: str, params: Dict[str, Any] = None) -> List[Dict[str, Any]]:
    """Execute a GameTeam stored procedure and return results as a list of dictionaries.

    Args:
        sproc_name: Name of the stored procedure (without schema prefix)
        params: Dictionary of parameter names and values

    Returns:
        List of dictionaries representing rows
    """
    full_sproc_name = f"{GAMETEAM_SCHEMA}.{sproc_name}"
    conn = None
    cursor = None

    try:
        # Use autocommit=True to avoid wrapping the sproc in a transaction
        conn = get_azure_connection(autocommit=True)
        cursor = conn.cursor()

        if params:
            param_placeholders = ", ".join([f"@{k} = ?" for k in params.keys()])
            values = list(params.values())
            cursor.setinputsizes(_wvarchar_input_sizes(values))
            cursor.execute(f"EXEC {full_sproc_name} {param_placeholders}", values)
        else:
            cursor.execute(f"EXEC {full_sproc_name}")

        # Skip result sets that are not queries (e.g. INSERT/UPDATE row counts)
        while cursor.description is None:
            if not cursor.nextset():
                return []

        columns = [column[0] for column in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]

    except pyodbc.Error as e:
        logger.error(f"ODBC error in {full_sproc_name}: {str(e)}")
        raise Exception(f"ODBC error in {full_sproc_name}: {str(e)}") from e
    except Exception as e:
        logger.error(f"Unexpected error in {full_sproc_name}: {type(e).__name__}: {str(e)}")
        raise
    finally:
        if cursor:
            try:
                cursor.close()
            except Exception:
                pass
        if conn:
            try:
                conn.close()
            except Exception:
                pass


def execute_sproc_single(sproc_name: str, params: Dict[str, Any] = None) -> Optional[Dict[str, Any]]:
    """Execute a stored procedure and return a single row as a dictionary."""
    results = execute_sproc(sproc_name, params)
    return results[0] if results else None


def execute_sproc_scalar(sproc_name: str, params: Dict[str, Any] = None) -> Any:
    """Execute a stored procedure and return a single scalar value."""
    results = execute_sproc(sproc_name, params)
    if results and results[0]:
        return list(results[0].values())[0]
    return None


def check_connection() -> Dict[str, Any]:
    """Verify Azure SQL connectivity and return the visible GameTeam object count."""
    conn = None
    cursor = None
    try:
        conn = get_azure_connection(autocommit=True)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT COUNT(*) FROM sys.objects o "
            "JOIN sys.schemas s ON o.schema_id = s.schema_id WHERE s.name = ?",
            [GAMETEAM_SCHEMA],
        )
        count = cursor.fetchone()[0]
        return {"status": "db_ok", "schema": GAMETEAM_SCHEMA, "object_count": int(count)}
    except Exception as e:
        logger.error(f"DB health check failed: {str(e)}")
        return {"status": "db_error", "message": str(e)}
    finally:
        if cursor:
            try:
                cursor.close()
            except Exception:
                pass
        if conn:
            try:
                conn.close()
            except Exception:
                pass
