from fastapi import APIRouter

from app.schemas import PriceExtractionRequest, PriceExtractionResponse
from app.services import ai_extractor

router = APIRouter(prefix="/ai", tags=["ai"])


@router.post("/extract-prices", response_model=PriceExtractionResponse)
def extract_prices(payload: PriceExtractionRequest) -> PriceExtractionResponse:
    """Extract fuel prices from a gas station pylon photo (demo simulation or Gemini Vision)."""
    return ai_extractor.extract_prices_from_image(payload)
