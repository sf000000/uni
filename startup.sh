#!/bin/bash
# startup.sh

LOGFILE="startup.log"

# Function to log to both file and console
log() {
  echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a $LOGFILE
}

# Check for necessary files and directories
if [ ! -f "./Lavalink.jar" ]; then
    log "Lavalink.jar not found. Exiting."
    exit 1
fi

if [ ! -d "venv" ]; then
    log "Python virtual environment not found. Exiting."
    exit 1
fi

# Start Lavalink server
log "Starting Lavalink server..."
java -jar ./Lavalink.jar &> "lavalink.log" &
LAVALINK_PID=$!
log "Lavalink server started with PID $LAVALINK_PID."

# Wait for Lavalink to fully start
log "Waiting for Lavalink server to be ready..."
sleep 5  # Adjust this timing as necessary

# Check Lavalink server status
if ! ps -p $LAVALINK_PID > /dev/null
then
   log "Lavalink server failed to start. Check lavalink.log for details."
   exit 1
fi

# Activate Python environment and run the Python script
log "Activating Python virtual environment and starting the bot..."
source venv/bin/activate
python3 main.py &>> $LOGFILE

log "Bot started successfully!"

