from pydantic import BaseModel, EmailStr, Field
from datetime import datetime

# User schemas
class UserBase(BaseModel):
    name: str
    email: EmailStr

class UserCreate(UserBase):
    password: str = Field(..., min_length=6)

class UserRead(UserBase):
    id: int
    created_at: datetime

    class Config:
        orm_mode = True

# Token schemas
class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    user_id: int | None = None

# Medicamento schemas
class MedicamentoBase(BaseModel):
    name: str
    dosage: str

class MedicamentoCreate(MedicamentoBase):
    pass

class MedicamentoRead(MedicamentoBase):
    id: int
    user_id: int
    created_at: datetime

    class Config:
        orm_mode = True

# Alarme schemas
class AlarmeBase(BaseModel):
    medication_id: int
    next_trigger: datetime

class AlarmeCreate(AlarmeBase):
    pass

class AlarmeRead(AlarmeBase):
    id: int
    user_id: int
    active: bool
    created_at: datetime

    class Config:
        orm_mode = True

# Panico schemas
class PanicoBase(BaseModel):
    description: str | None = None

class PanicoCreate(PanicoBase):
    pass

class PanicoRead(PanicoBase):
    id: int
    user_id: int
    timestamp: datetime
    created_at: datetime

    class Config:
        orm_mode = True
