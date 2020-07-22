#!/bin/bash
args=()

if [ ! -z "$SERIAL" ]; then
    args+=(--serial $SERIAL)
fi

if [ ! -z "$BAUD" ]; then
    args+=(--baud $BAUD)
fi

if [ ! -z "$CONNECT" ]; then
    args+=(--connect $CONNECT)
fi

nx584_server --listen $LISTEN "${args[@]}"
