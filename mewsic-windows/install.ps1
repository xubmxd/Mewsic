Write-Host "🎵 Welcome to the Mewsic Windows Installer 🎵" -ForegroundColor Cyan

# 1. Clone the repository
Write-Host ">>> Fetching Mewsic repository..." -ForegroundColor Yellow
# We clone the repo, and immediately navigate into the windows version
git clone https://github.com/xubmxd/Mewsic.git
Set-Location Mewsic\mewsic-windows

# 2. Install requirements directly to the base Windows system
Write-Host ">>> Installing Python requirements to base system..." -ForegroundColor Yellow
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
# Install py7zr temporarily to handle the 7z extraction natively in Python
python -m pip install py7zr 

# 3. Extract the .7z archive using Python
Write-Host ">>> Extracting libmpv DLL from archive..." -ForegroundColor Yellow
python -c "
import py7zr, os
archive = [f for f in os.listdir('.') if f.endswith('.7z')][0]
with py7zr.SevenZipFile(archive, mode='r') as z:
    z.extractall()
print('Extraction complete!')
"

# 4. Wrap up and give instructions
Write-Host ""
Write-Host "✅ Installation Complete!" -ForegroundColor Green
Write-Host "Everything is set up in your base system and ready to go."
Write-Host ""
Write-Host "To start Mewsic, run the following commands:" -ForegroundColor Cyan
Write-Host "cd Mewsic\mewsic-windows"
Write-Host "python mewsic.py"
