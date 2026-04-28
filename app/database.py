"""
Database module for storing user settings and analysis history.
"""
import sqlite3
import json
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime

DB_PATH = Path("data/settings.db")


def init_db():
    """Initialize database with required tables."""
    DB_PATH.parent.mkdir(exist_ok=True)
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Settings table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT DEFAULT 'default',
            provider TEXT NOT NULL,
            api_key TEXT,
            model TEXT,
            api_base TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Analysis history table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS analysis_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            document_name TEXT NOT NULL,
            instructions TEXT,
            provider TEXT,
            model TEXT,
            total_chunks INTEGER,
            total_findings INTEGER,
            report_id TEXT,
            input_tokens INTEGER,
            output_tokens INTEGER,
            total_tokens INTEGER,
            estimated_cost REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Instructions templates table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS instruction_templates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT,
            content TEXT NOT NULL,
            category TEXT,
            is_favorite INTEGER DEFAULT 0,
            use_count INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    conn.commit()
    conn.close()


def save_settings(provider: str, api_key: str, model: str, api_base: Optional[str] = None, user_id: str = "default"):
    """Save or update user settings."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Check if settings exist
    cursor.execute("SELECT id FROM settings WHERE user_id = ?", (user_id,))
    existing = cursor.fetchone()
    
    if existing:
        cursor.execute("""
            UPDATE settings 
            SET provider = ?, api_key = ?, model = ?, api_base = ?, updated_at = ?
            WHERE user_id = ?
        """, (provider, api_key, model, api_base, datetime.now(), user_id))
    else:
        cursor.execute("""
            INSERT INTO settings (user_id, provider, api_key, model, api_base)
            VALUES (?, ?, ?, ?, ?)
        """, (user_id, provider, api_key, model, api_base))
    
    conn.commit()
    conn.close()


def get_settings(user_id: str = "default") -> Optional[Dict[str, Any]]:
    """Get user settings."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT provider, api_key, model, api_base, updated_at
        FROM settings 
        WHERE user_id = ?
    """, (user_id,))
    
    row = cursor.fetchone()
    conn.close()
    
    if row:
        return {
            "provider": row[0],
            "api_key": row[1],
            "model": row[2],
            "api_base": row[3],
            "updated_at": row[4]
        }
    return None


def save_analysis_history(document_name: str, instructions: str, provider: str, model: str, 
                          total_chunks: int, total_findings: int, report_id: str,
                          input_tokens: int = 0, output_tokens: int = 0, 
                          total_tokens: int = 0, estimated_cost: float = 0.0):
    """Save analysis to history."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
        INSERT INTO analysis_history 
        (document_name, instructions, provider, model, total_chunks, total_findings, report_id,
         input_tokens, output_tokens, total_tokens, estimated_cost)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (document_name, instructions, provider, model, total_chunks, total_findings, report_id,
          input_tokens, output_tokens, total_tokens, estimated_cost))
    
    conn.commit()
    conn.close()


def get_analysis_history(limit: int = 10) -> list:
    """Get recent analysis history."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT document_name, instructions, provider, model, 
               total_chunks, total_findings, report_id, created_at,
               input_tokens, output_tokens, total_tokens, estimated_cost
        FROM analysis_history
        ORDER BY created_at DESC
        LIMIT ?
    """, (limit,))
    
    rows = cursor.fetchall()
    conn.close()
    
    return [
        {
            "document_name": row[0],
            "instructions": row[1],
            "provider": row[2],
            "model": row[3],
            "total_chunks": row[4],
            "total_findings": row[5],
            "report_id": row[6],
            "created_at": row[7],
            "input_tokens": row[8] or 0,
            "output_tokens": row[9] or 0,
            "total_tokens": row[10] or 0,
            "estimated_cost": row[11] or 0.0
        }
        for row in rows
    ]


def save_instruction_template(name: str, content: str, description: str = "", category: str = "custom"):
    """Save instruction template."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
        INSERT INTO instruction_templates (name, description, content, category)
        VALUES (?, ?, ?, ?)
    """, (name, description, content, category))
    
    conn.commit()
    conn.close()


def get_instruction_templates(category: Optional[str] = None) -> list:
    """Get instruction templates."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    if category:
        cursor.execute("""
            SELECT id, name, description, content, category, is_favorite, use_count, created_at
            FROM instruction_templates
            WHERE category = ?
            ORDER BY is_favorite DESC, use_count DESC, created_at DESC
        """, (category,))
    else:
        cursor.execute("""
            SELECT id, name, description, content, category, is_favorite, use_count, created_at
            FROM instruction_templates
            ORDER BY is_favorite DESC, use_count DESC, created_at DESC
        """)
    
    rows = cursor.fetchall()
    conn.close()
    
    return [
        {
            "id": row[0],
            "name": row[1],
            "description": row[2],
            "content": row[3],
            "category": row[4],
            "is_favorite": bool(row[5]),
            "use_count": row[6],
            "created_at": row[7]
        }
        for row in rows
    ]


def update_instruction_template(template_id: int, name: str = None, content: str = None, 
                                description: str = None, category: str = None, is_favorite: bool = None):
    """Update instruction template."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    updates = []
    params = []
    
    if name is not None:
        updates.append("name = ?")
        params.append(name)
    if content is not None:
        updates.append("content = ?")
        params.append(content)
    if description is not None:
        updates.append("description = ?")
        params.append(description)
    if category is not None:
        updates.append("category = ?")
        params.append(category)
    if is_favorite is not None:
        updates.append("is_favorite = ?")
        params.append(1 if is_favorite else 0)
    
    updates.append("updated_at = ?")
    params.append(datetime.now())
    params.append(template_id)
    
    if updates:
        query = f"UPDATE instruction_templates SET {', '.join(updates)} WHERE id = ?"
        cursor.execute(query, params)
        conn.commit()
    
    conn.close()


def increment_template_use_count(template_id: int):
    """Increment use count for template."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
        UPDATE instruction_templates 
        SET use_count = use_count + 1
        WHERE id = ?
    """, (template_id,))
    
    conn.commit()
    conn.close()


def delete_instruction_template(template_id: int):
    """Delete instruction template."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("DELETE FROM instruction_templates WHERE id = ?", (template_id,))
    
    conn.commit()
    conn.close()


# Initialize database on import
init_db()
