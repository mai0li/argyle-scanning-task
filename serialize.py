from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel

class Address(BaseModel):
    line1: Optional[str] = None
    line2: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    postal_code: Optional[str] = None
    country: Optional[str] = None

class User(BaseModel):
    id: str
    account: str
    employer: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    first_name: str
    last_name: str
    full_name: str
    email: str
    phone_number: Optional[str] = None
    birth_date: Optional[str] = None
    picture_url: str
    address: Optional[Address] = None
    ssn: Optional[str] = None
    marital_status: Optional[str] = None
    gender: Optional[str] = None
    metadata: Optional[str]

