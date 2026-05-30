import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.config import Settings
from app.services.llm_service import extract_document


def test_extract_document_with_antigravity_success():
    # Mock settings
    mock_settings = Settings(
        llm_provider="antigravity",
        antigravity_api_key="mock-antigravity-key",
        antigravity_model="gemini-2.5-flash"
    )

    # Mock response and chat
    mock_response = AsyncMock()
    mock_response.text.return_value = """
    ```json
    {
        "patient_name": "Rajesh Kumar",
        "doctor_name": "Dr. Arun Sharma",
        "doctor_registration": "KA/45678/2015",
        "hospital_name": "Apollo Hospital",
        "diagnosis": "Viral Fever",
        "treatment": "Consultation",
        "date": "2024-11-01",
        "medicines": ["Paracetamol 650mg"],
        "tests_ordered": ["CBC"],
        "line_items": [
            {"description": "Consultation fee", "amount": 1000.0}
        ],
        "total": 1000.0
    }
    ```
    """

    mock_agent = AsyncMock()
    mock_agent.chat.return_value = mock_response

    # The mock agent instance returned by async context manager
    mock_agent_class = MagicMock()
    # Support `async with Agent(config) as agent:`
    mock_agent_class.return_value.__aenter__.return_value = mock_agent

    with patch("app.services.llm_service.get_settings", return_value=mock_settings), \
         patch("google.antigravity.Agent", mock_agent_class):

        result = extract_document(
            file_id="F999",
            document_type="PRESCRIPTION",
            file_name="prescription.pdf",
            patient_name_on_doc="Rajesh Kumar"
        )

        assert result.file_id == "F999"
        assert result.patient_name == "Rajesh Kumar"
        assert result.doctor_name == "Dr. Arun Sharma"
        assert result.diagnosis == "Viral Fever"
        assert result.total_amount == 1000.0
        assert len(result.line_items) == 1
        assert result.confidence == 0.9


def test_extract_document_with_antigravity_fallback_on_failure():
    # Mock settings
    mock_settings = Settings(
        llm_provider="antigravity",
        antigravity_api_key="mock-antigravity-key",
        antigravity_model="gemini-2.5-flash"
    )

    # Patch google.antigravity.Agent to raise an error
    mock_agent_class = MagicMock()
    mock_agent_class.return_value.__aenter__.side_effect = RuntimeError("Antigravity SDK Connection Failed")

    with patch("app.services.llm_service.get_settings", return_value=mock_settings), \
         patch("google.antigravity.Agent", mock_agent_class):

        result = extract_document(
            file_id="F999",
            document_type="PRESCRIPTION",
            file_name="prescription.pdf",
            patient_name_on_doc="Rajesh Kumar"
        )

        # Fallback should be triggered with low confidence
        assert result.file_id == "F999"
        assert result.patient_name == "Rajesh Kumar"
        assert result.confidence == 0.4
