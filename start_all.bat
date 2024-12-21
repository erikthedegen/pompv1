@echo off

REM WebSocket Listener
start cmd /k "cd /d C:\Users\erase\Desktop\pumptrader\pompv1 && python websocketlistener.py"

REM Queue Manager
start cmd /k "cd /d C:\Users\erase\Desktop\pumptrader\pompv1 && python queue_manager.py"

REM Image Processor
start cmd /k "cd /d C:\Users\erase\Desktop\pumptrader\pompv1 && python image_processor.py"

REM Pruner
start cmd /k "cd /d C:\Users\erase\Desktop\pumptrader\pompv1 && python pruner.py"

REM Puppeteer (npm start)
start cmd /k "cd /d C:\Users\erase\Desktop\pumptrader\puppeteer && npm start"

REM New Coin Check (in root directory)
start cmd /k "cd /d C:\Users\erase\Desktop\pumptrader && python newcoincheck.py"

REM RTMP Server (npm start)
start cmd /k "cd /d C:\Users\erase\Desktop\pumptrader\rtmp_server && npm start"

REM Optional: Pause to keep the batch script window open
timeout /t 5
