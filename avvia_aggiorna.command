#!/bin/bash
# Forza aggiornamento notizie, poi apre il report
cd "$(dirname "$0")"
python3 rassegna_stampa.py --refresh
echo ""
echo "Premi INVIO per chiudere..."
read
