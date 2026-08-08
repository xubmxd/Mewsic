Write-Host "🎵 Welcome to the Mewsic Windows Installer 🎵" -ForegroundColor Cyan

# 1. Clone the repository
Write-Host ">>> Fetching Mewsic repository..." -ForegroundColor Yellow
git clone https://github.com/xubmxd/Mewsic.git
Set-Location Mewsic\mewsic-windows

# 2. Install Python requirements to the base system
Write-Host ">>> Installing Python requirements to base system..." -ForegroundColor Yellow
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

# 3. Extract the ZIP archive natively using PowerShell
Write-Host ">>> Extracting libmpv DLL from archive..." -ForegroundColor Yellow
Expand-Archive -Path "libmpv.zip" -DestinationPath "." -Force

# 4. Wrap up and give instructions
Write-Host ""
Write-Host "✅ Installation Complete!" -ForegroundColor Green
Write-Host "Everything is set up in your base system and ready to go."
Write-Host ""
Write-Host "To start Mewsic, run the following commands:" -ForegroundColor Cyan
Write-Host "cd Mewsic\mewsic-windows"
Write-Host "python mewsic.py"
