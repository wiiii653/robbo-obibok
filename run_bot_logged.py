#!/usr/bin/env python3
"""Start the bot with token from runner.py base64, logs to file."""
import os, sys, base64, subprocess

# Decode token the same way runner.py does
token = base64.b64decode(
    b'TVRVeE5qTTJPRGd3TnpVNU5qRXpORFE0TUEuRy1tTWlDLnY3ZURHMX'
    b'pLODh5RlVmOE1uYTFmdFVkYlY1ZFRwWUQ1YURfc3ow'
).decode()

os.environ['DISCORD_BOT_TOKEN'] = token
os.chdir(os.path.expanduser('~/robbo-obibot'))
venv_python = os.path.expanduser('~/robbo-obibot/venv/bin/python3')
log = open(os.path.expanduser('~/robbo-obibot/bot_output.log'), 'a')

proc = subprocess.Popen(
    [venv_python, '-u', 'asma-bot.py'],
    stdout=log,
    stderr=subprocess.STDOUT,
    close_fds=True
)

print(f"STARTED PID={proc.pid}")
sys.stdout.flush()

try:
    proc.wait()
except KeyboardInterrupt:
    proc.terminate()
finally:
    log.close()
