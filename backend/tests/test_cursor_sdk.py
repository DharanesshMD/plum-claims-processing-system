from unittest.mock import MagicMock, patch

from app.config import Settings
from app.services.llm_service import extract_document_with_cursor


def test_extract_document_with_cursor_success():
    # Mock settings to have a CURSOR_API_KEY
    mock_settings = Settings(
        cursor_api_key="mock-key",
        cursor_model="gpt-5.4-nano"
    )

    # Mock Cursor Agent send & text returning JSON format
    mock_run = MagicMock()
    mock_run.text.return_value = """
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

    mock_agent = MagicMock()
    mock_agent.send.return_value = mock_run
    mock_agent.__enter__.return_value = mock_agent

    # We patch Agent.create and get_settings
    with patch("app.services.llm_service.get_settings", return_value=mock_settings), \
            patch("cursor_sdk.Agent.create", return_value=mock_agent) as mock_create:

        result = extract_document_with_cursor(
            file_id="F999",
            document_type="PRESCRIPTION",
            file_name="prescription.pdf",
            patient_name_on_doc="Rajesh Kumar"
        )

        # Assert mock Agent was created with correct settings
        assert mock_create.call_count == 1
        args, kwargs = mock_create.call_args
        assert kwargs["model"] == "gpt-5.4-nano"
        assert kwargs["api_key"] == "mock-key"

        # Assert data was extracted and mapped correctly
        assert result.file_id == "F999"
        assert result.patient_name == "Rajesh Kumar"
        assert result.doctor_name == "Dr. Arun Sharma"
        assert result.diagnosis == "Viral Fever"
        assert result.total_amount == 1000.0
        assert len(result.line_items) == 1
        assert result.line_items[0].description == "Consultation fee"
        assert result.line_items[0].amount == 1000.0
        assert result.confidence == 0.9


def test_extract_document_with_cursor_fallback_on_failure():
    # Mock settings to have a CURSOR_API_KEY
    mock_settings = Settings(
        cursor_api_key="mock-key",
        cursor_model="gpt-5.4-nano"
    )

    # We patch get_settings, and make Agent.create raise an error
    with patch("app.services.llm_service.get_settings", return_value=mock_settings), \
            patch("cursor_sdk.Agent.create", side_effect=RuntimeError("SDK Connection Failed")):

        result = extract_document_with_cursor(
            file_id="F999",
            document_type="PRESCRIPTION",
            file_name="prescription.pdf",
            patient_name_on_doc="Rajesh Kumar"
        )

        # Assert fallback is used with degraded confidence
        assert result.file_id == "F999"
        assert result.patient_name == "Rajesh Kumar"
        assert result.confidence == 0.4
