import subprocess
import sys

def test_health_command():
    result = subprocess.run(
        [sys.executable, "-m", "initials_agent", "health"],
        capture_output=True,
        text=True
    )
    assert result.returncode == 0
    assert "OK" in result.stdout
