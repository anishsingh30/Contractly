from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import datetime

class VendorCreateRequest(BaseModel):
    name: str
    contact_email: str
    contract_count: int = 0
    total_contract_value: float = 0.0
    risk_rating: str = "LOW"
    compliance_rating: int = 100
    sla_performance: str = "100% Target Met"
    open_obligations: int = 0
    critical_issues: int = 0
    soc2_certified: bool = False
    gdpr_compliant: bool = False

class VendorResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    organization_id: str
    name: str
    contact_email: str
    contract_count: int = 0
    total_contract_value: float = 0.0
    risk_rating: str = "LOW"
    compliance_rating: int = 100
    sla_performance: str = "100% Target Met"
    open_obligations: int = 0
    critical_issues: int = 0
    soc2_certified: bool = False
    gdpr_compliant: bool = False
    created_at: datetime
