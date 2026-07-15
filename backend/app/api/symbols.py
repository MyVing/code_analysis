import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.core.exceptions import ProjectNotFoundError, SymbolNotFoundError
from app.models.file import File
from app.models.symbol import Symbol, SymbolKind
from app.schemas.symbol import SymbolQuery, SymbolRead

router = APIRouter(prefix="/symbols", tags=["symbols"])


@router.get("/", response_model=list[SymbolRead])
async def query_symbols(
    name: str | None = None,
    kind: SymbolKind | None = None,
    file_id: uuid.UUID | None = None,
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Symbol)
    if name:
        stmt = stmt.where(Symbol.name.ilike(f"%{name}%"))
    if kind:
        stmt = stmt.where(Symbol.kind == kind)
    if file_id:
        stmt = stmt.where(Symbol.file_id == file_id)
    stmt = stmt.order_by(Symbol.start_line)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/{symbol_id}", response_model=SymbolRead)
async def get_symbol(symbol_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    symbol = await db.get(Symbol, symbol_id)
    if not symbol:
        raise SymbolNotFoundError()
    return symbol


@router.get("/file/{file_id}", response_model=list[SymbolRead])
async def get_file_symbols(file_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    stmt = select(Symbol).where(Symbol.file_id == file_id).order_by(Symbol.start_line)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/{symbol_id}/children", response_model=list[SymbolRead])
async def get_symbol_children(symbol_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    symbol = await db.get(Symbol, symbol_id)
    if not symbol:
        raise SymbolNotFoundError()
    stmt = (
        select(Symbol)
        .where(Symbol.parent_id == symbol_id)
        .order_by(Symbol.start_line)
    )
    result = await db.execute(stmt)
    return result.scalars().all()
