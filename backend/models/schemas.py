from pydantic import BaseModel, Field


class Product(BaseModel):

    id: int

    name: str

    price: str

    image: str

    url: str

    stock: str

    category: str

    description: str

    rating: str = "0"

    rating_count: int = 0


class ChatRequest(BaseModel):

    message: str

    context: dict = Field(default_factory=dict)


class ChatResponse(BaseModel):

    reply: str

    total_products: int

    query: dict

    products: list[Product]

    context: dict = Field(default_factory=dict)
