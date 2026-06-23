import uuid
from datetime import datetime, timezone
from typing import Dict, Any


def generate_port_entry_notification(nomination_id: uuid.UUID, vessel_name: str, eta: str) -> Dict[str, Any]:
    """
    Symuluje generowanie dokumentu PDF z "National Single Window" dla Kapitanatu Portu.
    """
    document_id = str(uuid.uuid4())

    # W rzeczywistości użylibyście np. biblioteki WeasyPrint albo ReportLab
    # do wygenerowania pliku i wrzucenia go na AWS S3.

    s3_mock_url = f"https://s3.eu-central-1.amazonaws.com/sentiport-docs/port_entry_{vessel_name.replace(' ', '_')}_{document_id[:8]}.pdf"

    return {
        "document_id": document_id,
        "nomination_id": str(nomination_id),
        "document_type": "port_entry_notification",
        "status": "generated",
        "file_url": s3_mock_url,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "summary": f"Wygenerowano zawiadomienie o wejściu do portu dla {vessel_name} na dzień {eta}."
    }