#!/bin/bash
# Doppio click su questo file per avviare la Rassegna Stampa su macOS
cd "$(dirname "$0")"
python3 rassegna_stampa.py
echo ""
echo "Premi INVIO per chiudere..."
read
