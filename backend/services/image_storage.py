from models.meme_image import MemeImage


def save_image(db, digest, content_type, content):
    # ON CONFLICT handles concurrent/repeated uploads without duplicating bytes.
    dialect = db.get_bind().dialect.name
    if dialect == "postgresql":
        from sqlalchemy.dialects.postgresql import insert
    elif dialect == "sqlite":
        from sqlalchemy.dialects.sqlite import insert
    else:
        raise RuntimeError("Unsupported image-storage database")
    statement = insert(MemeImage).values(sha256=digest, content_type=content_type, content=content)
    db.execute(statement.on_conflict_do_nothing(index_elements=["sha256"]))
