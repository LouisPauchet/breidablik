from pydantic import BaseModel


class QuoteOut(BaseModel):
    text: str
    author: str
