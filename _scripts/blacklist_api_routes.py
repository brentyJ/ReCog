"""
ReCog Entity Blacklist API Routes

These routes need to be added to server.py after the entity_stats endpoint.
Copy the code below into server.py after the ENTITY MANAGEMENT section.

=============================================================================
ENTITY BLACKLIST (False Positive Management)  
=============================================================================
"""

BLACKLIST_ROUTES = '''
# =============================================================================
# ENTITY BLACKLIST (False Positive Management)
# =============================================================================

@app.route("/api/entities/<int:entity_id>/reject", methods=["POST"])
@require_json
def reject_entity(entity_id: int):
    """
    Reject an entity as a false positive (e.g., "Not a Person").
    
    Adds to blacklist and optionally deletes from entity registry.
    
    Body: {
        "reason": "not_a_person",  # or "common_word", "false_positive"
        "delete_entity": true      # Remove from registry (default true)
    }
    """
    data = request.get_json()
    reason = data.get("reason", "not_a_person")
    delete_entity = data.get("delete_entity", True)
    
    # Get entity details first
    entity = entity_registry.get_entity_by_id(entity_id)
    if not entity:
        return api_response(error="Entity not found", status=404)
    
    now = datetime.now(timezone.utc).isoformat() + "Z"
    
    conn = _get_db_connection()
    try:
        # Add to blacklist
        try:
            conn.execute("""
                INSERT INTO entity_blacklist (
                    entity_type, raw_value, normalised_value,
                    rejection_reason, rejected_by, source_context,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, 'user', ?, ?, ?)
            """, (
                entity.get("entity_type"),
                entity.get("raw_value"),
                entity.get("normalised_value") or entity.get("raw_value", "").lower(),
                reason,
                None,  # Could store source context
                now, now
            ))
        except Exception:
            # Already blacklisted - increment count
            conn.execute("""
                UPDATE entity_blacklist 
                SET rejection_count = rejection_count + 1, updated_at = ?
                WHERE entity_type = ? AND normalised_value = ?
            """, (now, entity.get("entity_type"), entity.get("normalised_value")))
        
        # Optionally delete from registry
        if delete_entity:
            conn.execute("DELETE FROM entity_registry WHERE id = ?", (entity_id,))
        
        conn.commit()
        
        # Update runtime blacklist
        from recog_engine.tier0 import add_to_blacklist
        add_to_blacklist(entity.get("normalised_value") or entity.get("raw_value"))
        
        return api_response({
            "rejected": True,
            "entity_id": entity_id,
            "value": entity.get("raw_value"),
            "reason": reason,
            "deleted": delete_entity,
        })
    finally:
        conn.close()


@app.route("/api/entities/blacklist", methods=["GET"])
def list_blacklist():
    """
    List blacklisted entity values.
    
    Query params:
        - type: Filter by entity type (person, phone, email)
        - limit: Max results (default 100)
    """
    entity_type = request.args.get("type", "person")
    limit = int(request.args.get("limit", 100))
    
    conn = _get_db_connection()
    try:
        cursor = conn.execute("""
            SELECT id, entity_type, raw_value, normalised_value,
                   rejection_reason, rejected_by, rejection_count,
                   created_at, updated_at
            FROM entity_blacklist
            WHERE entity_type = ?
            ORDER BY rejection_count DESC, created_at DESC
            LIMIT ?
        """, (entity_type, limit))
        
        items = []
        for row in cursor.fetchall():
            items.append({
                "id": row["id"],
                "entity_type": row["entity_type"],
                "raw_value": row["raw_value"],
                "normalised_value": row["normalised_value"],
                "rejection_reason": row["rejection_reason"],
                "rejected_by": row["rejected_by"],
                "rejection_count": row["rejection_count"],
                "created_at": row["created_at"],
            })
        
        return api_response({
            "blacklist": items,
            "count": len(items),
        })
    finally:
        conn.close()


@app.route("/api/entities/blacklist/<int:blacklist_id>", methods=["DELETE"])
def remove_from_blacklist(blacklist_id: int):
    """Remove an entry from the blacklist (un-reject)."""
    conn = _get_db_connection()
    try:
        row = conn.execute(
            "SELECT normalised_value FROM entity_blacklist WHERE id = ?",
            (blacklist_id,)
        ).fetchone()
        
        if not row:
            return api_response(error="Blacklist entry not found", status=404)
        
        conn.execute("DELETE FROM entity_blacklist WHERE id = ?", (blacklist_id,))
        conn.commit()
        
        return api_response({
            "removed": True,
            "blacklist_id": blacklist_id,
        })
    finally:
        conn.close()


@app.route("/api/entities/blacklist/reload", methods=["POST"])
def reload_blacklist():
    """Reload blacklist from database into runtime memory."""
    from recog_engine.tier0 import load_blacklist_from_db
    
    blacklist = load_blacklist_from_db(Config.DB_PATH)
    
    return api_response({
        "reloaded": True,
        "count": len(blacklist),
    })
'''

print("Copy the BLACKLIST_ROUTES content into server.py")
print("Location: After @app.route('/api/entities/stats') and before ENTITY GRAPH section")
