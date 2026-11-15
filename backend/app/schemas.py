from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.domain.consensus import (
    MAX_PRICE_PLN,
    MIN_PRICE_PLN,
    PriceStatus,
    ReportSource,
    VoteType,
)

FuelTypeLiteral = Literal["PB95", "PB98", "ON", "LPG"]


class BenefitBase(BaseModel):
    brand: str = Field(min_length=1, max_length=80)
    app_name: str = Field(min_length=1, max_length=120)
    fuel_type: FuelTypeLiteral | None = None
    discount_per_liter: float = Field(gt=0, le=5.0)
    max_liters: float | None = Field(default=None, gt=0, le=500.0)
    active_weekdays: list[int] | None = None
    start_hour: int | None = Field(default=None, ge=0, le=23)
    end_hour: int | None = Field(default=None, ge=0, le=24)
    valid_from: datetime
    valid_to: datetime
    description: str = Field(default="", max_length=255)

    @model_validator(mode="after")
    def validate_schedule_and_dates(self) -> "BenefitBase":
        if self.valid_to < self.valid_from:
            raise ValueError("valid_to must be greater than or equal to valid_from")
        if self.active_weekdays is not None:
            if not self.active_weekdays:
                raise ValueError("active_weekdays cannot be an empty list; use null for all days")
            if any(day < 0 or day > 6 for day in self.active_weekdays):
                raise ValueError("active_weekdays values must be between 0 (Mon) and 6 (Sun)")
        return self


class BenefitCreate(BenefitBase):
    pass


class BenefitUpdate(BenefitBase):
    pass


class BenefitRead(BaseModel):
    id: int
    owner_id: int | None = None
    is_own: bool = False
    brand: str
    app_name: str
    fuel_type: FuelTypeLiteral | None
    discount_per_liter: float
    max_liters: float | None
    active_weekdays: list[int] | None
    start_hour: int | None
    end_hour: int | None
    valid_from: datetime
    valid_to: datetime
    checked_at: datetime
    description: str


class FuelPriceSummary(BaseModel):
    fuel_type: FuelTypeLiteral
    price: float | None
    status: PriceStatus
    support: int
    confirmations_count: int
    rejections_count: int
    reported_at: datetime | None
    age_hours: float | None
    winning_report_id: int | None
    needs_warning: bool


class StationBase(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    brand: str = Field(min_length=1, max_length=80)
    address: str = Field(min_length=1, max_length=200)
    district: str = Field(min_length=1, max_length=80)
    latitude: float = Field(ge=-90.0, le=90.0)
    longitude: float = Field(ge=-180.0, le=180.0)


class StationCreate(StationBase):
    pass


class StationUpdate(StationBase):
    pass


class StationRead(StationBase):
    id: int
    created_at: datetime
    prices: dict[FuelTypeLiteral, FuelPriceSummary]
    active_benefits: list[BenefitRead]


class PriceReportCreate(BaseModel):
    fuel_type: FuelTypeLiteral
    price: float = Field(ge=MIN_PRICE_PLN, le=MAX_PRICE_PLN)
    source: ReportSource = ReportSource.MANUAL


class PriceReportRead(BaseModel):
    id: int
    station_id: int
    fuel_type: FuelTypeLiteral
    price: float
    user_id: str
    source: ReportSource
    reported_at: datetime
    confirmations_count: int
    rejections_count: int


class PriceVoteRead(BaseModel):
    id: int
    report_id: int
    user_id: str
    vote_type: VoteType
    created_at: datetime


class CorrectionCreate(BaseModel):
    price: float = Field(ge=MIN_PRICE_PLN, le=MAX_PRICE_PLN)


class CorrectionRead(BaseModel):
    rejected_report_id: int
    vote: PriceVoteRead
    new_report: PriceReportRead


class DealItemRead(BaseModel):
    station: StationRead
    fuel_type: FuelTypeLiteral
    pump_price: float
    effective_price_per_liter: float
    applied_benefit: BenefitRead | None
    total_discount: float
    distance_km: float
    extra_km: float
    detour_cost: float
    savings: float
    net_gain: float
    min_liters: float | None
    is_profitable: bool
    is_reference_station: bool
    price_status: PriceStatus
    price_age_hours: float | None
    needs_warning: bool
    warning_message: str | None


class DealsResponse(BaseModel):
    fuel_type: FuelTypeLiteral
    liters: float
    consumption_per_100km: float
    reference_station_id: int | None
    reference_station_name: str | None
    reference_price: float | None
    deals: list[DealItemRead]


class PriceExtractionRequest(BaseModel):
    image_base64: str = Field(min_length=1)
    mime_type: str = Field(default="image/jpeg", max_length=64)
    filename: str | None = Field(default=None, max_length=200)


class PriceExtractionResponse(BaseModel):
    mode: str
    prices: dict[FuelTypeLiteral, float | None]
    confidence_note: str


class AdminLoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=1, max_length=256)


class AdminLoginResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    username: str
    expires_at: datetime


class AdminSessionRead(BaseModel):
    username: str
    is_admin: bool


class UserRegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=60, pattern=r"^[a-zA-Z0-9_.-]+$")
    password: str = Field(min_length=4, max_length=128)


class UserLoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=60)
    password: str = Field(min_length=1, max_length=128)


class AuthTokenResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    username: str
    role: Literal["user", "admin"]
    user_id: int | None = None
    expires_at: datetime


class AuthSessionRead(BaseModel):
    username: str
    role: Literal["user", "admin"]
    user_id: int | None = None
