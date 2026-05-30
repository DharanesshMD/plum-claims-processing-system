import pytest
from unittest.mock import MagicMock, patch

from app.config import Settings
from app.services.llm_service import extract_document


def test_extract_document_with_nvidia_success():
    # Mock settings
    mock_settings = Settings(
        llm_provider="nvidia",
        nvidia_api_key="mock-nvidia-key",
        nvidia_model="deepseek-ai/deepseek-v4-flash"
    )

    # Mock response structure for OpenAI completions
    mock_completion = MagicMock()
    mock_choice = MagicMock()
    mock_message = MagicMock()
    mock_message.content = """
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
    mock_choice.message = mock_message
    mock_completion.choices = [mock_choice]

    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = mock_completion

    # Mock OpenAI client constructor to return our mock client
    with patch("app.services.llm_service.get_settings", return_value=mock_settings), \
         patch("openai.OpenAI", return_value=mock_client):

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


def test_extract_document_with_nvidia_fallback_on_failure():
    # Mock settings
    mock_settings = Settings(
        llm_provider="nvidia",
        nvidia_api_key="mock-nvidia-key",
        nvidia_model="deepseek-ai/deepseek-v4-flash"
    )

    # Patch OpenAI client constructor to raise an exception
    with patch("app.services.llm_service.get_settings", return_value=mock_settings), \
         patch("openai.OpenAI", side_effect=RuntimeError("NVIDIA NIM API Connection Failed")):

        result = extract_document(
            file_id="F999",
            document_type="PRESCRIPTION",
            file_name="prescription.pdf",
            patient_name_on_doc="Rajesh Kumar"
        )

        # Fallback should be triggered with low confidence (0.4)
        assert result.file_id == "F999"
        assert result.patient_name == "Rajesh Kumar"
        assert result.confidence == 0.4
