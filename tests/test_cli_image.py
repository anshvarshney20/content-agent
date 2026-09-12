import os
import io
from unittest.mock import patch, MagicMock
from PIL import Image
from initials_agent.config import get_settings

def test_cli_image_generate_missing_api_key(capsys):
    real_settings = get_settings()
    real_settings.image.provider = "dalle"
    real_settings.image.api_key = None
    
    with patch("sys.argv", ["initials_agent", "image", "generate", "--prompt", "test"]):
        with patch("initials_agent.config.get_settings", return_value=real_settings):
            try:
                from initials_agent.__main__ import main
                main()
            except SystemExit as e:
                assert e.code == 1
                
            captured = capsys.readouterr()
            assert "API key for dalle is not configured" in captured.out

def test_cli_image_generate_mock_provider_blocked(capsys):
    real_settings = get_settings()
    real_settings.image.provider = "mock"
    
    with patch("sys.argv", ["initials_agent", "image", "generate", "--prompt", "test"]):
        with patch("initials_agent.config.get_settings", return_value=real_settings):
            try:
                from initials_agent.__main__ import main
                main()
            except SystemExit as e:
                assert e.code == 1
                
            captured = capsys.readouterr()
            assert "MockImageProvider is not allowed for this command" in captured.out

def test_cli_image_generate_success(tmp_path, capsys):
    output_file = tmp_path / "test_img.png"
    
    img = Image.new("RGB", (1080, 1350), color="red")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    valid_png_bytes = buf.getvalue()
    
    real_settings = get_settings()
    real_settings.image.provider = "dalle"
    mock_key = MagicMock()
    mock_key.get_secret_value.return_value = "fake-key"
    real_settings.image.api_key = mock_key
    
    with patch("sys.argv", [
        "initials_agent", "image", "generate", 
        "--prompt", "test image",
        "--width", "1080",
        "--height", "1350",
        "--output", str(output_file)
    ]):
        with patch("initials_agent.config.get_settings", return_value=real_settings):
            with patch("initials_agent.providers.image.dalle.DalleImageProvider.generate_image") as mock_gen:
                mock_gen.return_value = valid_png_bytes
                
                from initials_agent.__main__ import main
                main()
                
                assert os.path.exists(output_file)
                captured = capsys.readouterr()
                assert "Image generated successfully" in captured.out
