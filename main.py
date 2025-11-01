# main.py
from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from typing import Optional, List

import models, schemas, config
from database import Base, engine, SessionLocal

# Create tables (idempotent because models use extend_existing)
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Article Co-Author & Locking App", version="1.0")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Helper: find user by email or raise 404
def get_user_by_email(db: Session, email: str):
    user = db.query(models.User).filter(models.User.email == email).first()
    if not user:
        raise HTTPException(status_code=404, detail=f"User not found: {email}")
    return user


# Helper: join co_authors inputs
def normalize_coauthors(co_authors_str: Optional[str], co_authors_list: Optional[List[str]]):
    if co_authors_list:
        cleaned = [x.strip() for x in co_authors_list if x and x.strip()]
        return ",".join(cleaned) if cleaned else None
    if co_authors_str:
        cleaned = [x.strip() for x in co_authors_str.split(",") if x.strip()]
        return ",".join(cleaned) if cleaned else None
    return None


# Lock expiry check
def lock_expired(article: models.Article) -> bool:
    if not article.locked_by:
        return True  # no lock
    if not article.last_seen:
        return True  # treat as expired
    now = datetime.utcnow()
    timeout = timedelta(minutes=config.LOCK_TIMEOUT_MINUTES)
    return (now - article.last_seen) > timeout


# --- Root ---
@app.get("/", response_class=HTMLResponse)
def homepage():
    return """
    <html><head><title>Articles</title></head>
    <body>
      <h1>Article App Running</h1>
      <p>Use /docs to interact with API.</p>
    </body></html>
    """


# --- User endpoints (for testing) ---
@app.post("/users/", response_model=schemas.UserOut)
def create_user(u: schemas.UserCreate, db: Session = Depends(get_db)):
    existing = db.query(models.User).filter(models.User.email == u.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    user = models.User(email=u.email, name=u.name)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@app.get("/users/", response_model=List[schemas.UserOut])
def list_users(db: Session = Depends(get_db)):
    return db.query(models.User).all()


# --- Create article ---
@app.post("/articles/", response_model=schemas.ArticleOut)
def create_article(payload: schemas.ArticleCreate, db: Session = Depends(get_db)):
    # author must exist (create_user must be used earlier)
    author = get_user_by_email(db, payload.author_email)

    co_auth = normalize_coauthors(payload.co_authors, payload.co_authors_list)
    db_article = models.Article(
        title=payload.title,
        content=payload.content,
        author_id=author.id,
        co_authors=co_auth,
        locked_by=None,
        locked_at=None,
        last_seen=None,
    )
    db.add(db_article)
    db.commit()
    db.refresh(db_article)
    return db_article


# --- Read article ---
@app.get("/articles/{article_id}", response_model=schemas.ArticleOut)
def get_article(article_id: int, db: Session = Depends(get_db)):
    a = db.query(models.Article).filter(models.Article.id == article_id).first()
    if not a:
        raise HTTPException(status_code=404, detail="Article not found")
    return a


# --- Open for editing (acquire lock) ---
@app.post("/articles/{article_id}/open")
def open_for_edit(article_id: int, user_email: str = Query(...), db: Session = Depends(get_db)):
    user = get_user_by_email(db, user_email)
    article = db.query(models.Article).filter(models.Article.id == article_id).first()
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")

    # if locked by someone else and not expired => deny
    if article.locked_by and (article.locked_by != user.id) and (not lock_expired(article)):
        locker = db.query(models.User).get(article.locked_by)
        raise HTTPException(status_code=403, detail=f"Article locked by {locker.email}")

    # acquire lock
    article.locked_by = user.id
    article.locked_at = datetime.utcnow()
    article.last_seen = datetime.utcnow()
    db.commit()
    db.refresh(article)
    return {"msg": "lock acquired", "locked_by": user.email, "locked_at": article.locked_at}


# --- Heartbeat (update last_seen while editing) ---
@app.post("/articles/{article_id}/heartbeat")
def heartbeat(article_id: int, user_email: str = Query(...), db: Session = Depends(get_db)):
    user = get_user_by_email(db, user_email)
    article = db.query(models.Article).filter(models.Article.id == article_id).first()
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")

    if article.locked_by != user.id:
        raise HTTPException(status_code=403, detail="You do not hold the lock")

    article.last_seen = datetime.utcnow()
    db.commit()
    return {"msg": "heartbeat recorded", "last_seen": article.last_seen}


# --- Save edits (release lock on save) ---
@app.put("/articles/{article_id}/edit", response_model=schemas.ArticleOut)
def save_edit(article_id: int, content: str, user_email: str = Query(...), db: Session = Depends(get_db)):
    user = get_user_by_email(db, user_email)
    article = db.query(models.Article).filter(models.Article.id == article_id).first()
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")

    # If locked by someone else and not expired -> deny
    if article.locked_by and (article.locked_by != user.id) and (not lock_expired(article)):
        locker = db.query(models.User).get(article.locked_by)
        raise HTTPException(status_code=403, detail=f"Article locked by {locker.email}")

    # Save (last-writer-wins in BASIC if multiple saved)
    article.content = content
    # on save we release lock (requirement: lock remains until user saves)
    article.locked_by = None
    article.locked_at = None
    article.last_seen = None
    db.commit()
    db.refresh(article)
    return article


# --- Force unlock by original author (optional story) ---
@app.post("/articles/{article_id}/force-unlock")
def force_unlock(article_id: int, author_email: str = Query(...), db: Session = Depends(get_db)):
    author = get_user_by_email(db, author_email)
    article = db.query(models.Article).filter(models.Article.id == article_id).first()
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")
    if article.author_id != author.id:
        raise HTTPException(status_code=403, detail="Only original author can force-unlock")

    # record previous locker info to return (the client side should show pop-up to the co-author)
    locker = None
    if article.locked_by:
        locker = db.query(models.User).get(article.locked_by)
        locker_info = {"id": locker.id, "email": locker.email, "name": locker.name}
    else:
        locker_info = None

    article.locked_by = None
    article.locked_at = None
    article.last_seen = None
    db.commit()
    return {"msg": "force-unlocked", "previous_locker": locker_info, "current_article": {
        "id": article.id,
        "title": article.title,
        "content": article.content
    }}


# --- List articles (for convenience) ---
@app.get("/articles/", response_model=List[schemas.ArticleOut])
def list_articles(db: Session = Depends(get_db)):
    return db.query(models.Article).all()
