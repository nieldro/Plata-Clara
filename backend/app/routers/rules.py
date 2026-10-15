from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import current_user, owned
from ..models import Category, CategoryRule, User
from ..schemas import RuleIn
from ..services import rules as svc

router = APIRouter(tags=["reglas"])


@router.get("/categorize")
def categorize(text: str = Query("", max_length=255), kind: str | None = Query(None, pattern="^(income|expense)$"),
               db: Session = Depends(get_db), user: User = Depends(current_user)):
    """Sugiere una categoría para lo que el usuario está escribiendo en la nota."""
    return {"suggestion": svc.suggest(db, user.id, text, kind)}


@router.get("/rules")
def list_rules(db: Session = Depends(get_db), user: User = Depends(current_user)):
    rows = db.execute(
        select(CategoryRule, Category.name).join(Category, Category.id == CategoryRule.category_id)
        .where(CategoryRule.user_id == user.id)
        .order_by(CategoryRule.manual.desc(), CategoryRule.hits.desc(), CategoryRule.keyword)
        .limit(300)
    ).all()
    return [{"id": r.id, "keyword": r.keyword, "category_id": r.category_id, "category": name,
             "hits": r.hits, "manual": r.manual} for r, name in rows]


@router.post("/rules", status_code=201)
def create_rule(data: RuleIn, db: Session = Depends(get_db), user: User = Depends(current_user)):
    """Regla escrita a mano: toda nota que contenga la palabra se sugiere en esa categoría."""
    owned(db, Category, data.category_id, user)
    toks = svc.tokens(data.keyword)
    if len(toks) != 1:
        raise HTTPException(422, "Escribe una sola palabra de al menos 3 letras (sin números)")
    keyword = toks[0]
    rule = db.scalar(select(CategoryRule).where(
        CategoryRule.user_id == user.id, CategoryRule.keyword == keyword, CategoryRule.category_id == data.category_id))
    if rule:
        rule.manual = True
    else:
        rule = CategoryRule(user_id=user.id, keyword=keyword, category_id=data.category_id, manual=True, hits=1)
        db.add(rule)
    db.commit()
    return {"id": rule.id, "keyword": keyword}


@router.delete("/rules/{rule_id}", status_code=204)
def delete_rule(rule_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    db.delete(owned(db, CategoryRule, rule_id, user))
    db.commit()
