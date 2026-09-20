#!/bin/zsh
# Start or stop the local Jev server (snapjudge) on this Mac's LAN address.
#
#   localjev/serve.sh start    # bind, wait for the model, print the health line
#   localjev/serve.sh stop
#   localjev/serve.sh status
#
# Bound to the LAN address only, never 0.0.0.0: the loopback address is deliberately
# not served, so the Mac and the PC measure the same socket path. The Bearer key lives
# in ~/.jev-local-key (0600) and is passed through the environment, never argv, so it
# does not show up in `ps`.
set -u
HERE=${0:A:h}
VENV=$HERE/../.localjev/.venv
MODEL=${SO_MODEL:-mlx-community/Qwen3.6-35B-A3B-4bit}
PORT=${PORT:-8724}
KEYFILE=${KEYFILE:-$HOME/.jev-local-key}
LOG=$HERE/../.localjev/serve.log
PIDFILE=$HERE/../.localjev/serve.pid
# The one LAN address, from the default route's interface. Do not hard-code it: it moves.
IP=${IP:-$(ipconfig getifaddr $(route -n get default | awk '/interface:/{print $2}'))}

case ${1:-start} in
start)
  [[ -f $PIDFILE ]] && kill -0 $(cat $PIDFILE) 2>/dev/null && { echo "already running on $IP:$PORT (pid $(cat $PIDFILE))"; exit 0 }
  [[ -f $KEYFILE ]] || { echo "no key at $KEYFILE: openssl rand -hex 16 > $KEYFILE && chmod 600 $KEYFILE"; exit 1 }
  # niced: this Mac has no efficiency cores, so a model server must not outrank the desktop
  # uvicorn directly, not snapjudge-serve: its CLI cannot set --timeout-keep-alive, and
  # uvicorn's 5 s default closes the agent's kept-alive connection during any quiet stretch,
  # which costs a tick. This is the invocation snapjudge's own server.py docstring gives.
  SO_MODEL="$MODEL" SO_NAME=jev-local SO_API_KEY="$(cat $KEYFILE)" \
  nohup nice -n 5 $VENV/bin/uvicorn snapjudge.server:app \
    --host "$IP" --port "$PORT" --timeout-keep-alive 3600 --log-level warning >$LOG 2>&1 &
  echo $! > $PIDFILE
  echo "starting on $IP:$PORT (pid $(cat $PIDFILE)), loading $MODEL ..."
  # The model load is the slow part; /health answers only once the engine is up.
  for i in {1..120}; do
    curl -s --max-time 2 "http://$IP:$PORT/health" && { echo; echo "ready: JEV_URL=http://$IP:$PORT/v1/systemone"; exit 0 }
    kill -0 $(cat $PIDFILE) 2>/dev/null || { echo "died, see $LOG"; tail -5 $LOG; exit 1 }
    sleep 2
  done
  echo "not ready after 240 s, see $LOG"; exit 1
  ;;
stop)
  [[ -f $PIDFILE ]] || { echo "not running"; exit 0 }
  kill $(cat $PIDFILE) 2>/dev/null && echo "stopped pid $(cat $PIDFILE)"
  rm -f $PIDFILE
  ;;
status)
  if [[ -f $PIDFILE ]] && kill -0 $(cat $PIDFILE) 2>/dev/null; then
    echo "pid $(cat $PIDFILE), rss $(ps -o rss= -p $(cat $PIDFILE) | awk '{printf "%.1f GB", $1/1048576}')"
    curl -s --max-time 2 "http://$IP:$PORT/health"; echo
  else
    echo "not running"
  fi
  ;;
*) echo "usage: serve.sh {start|stop|status}"; exit 2 ;;
esac
