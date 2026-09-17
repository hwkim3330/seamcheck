#!/bin/zsh
cd ~/seamcheck
for s in PHerc1667 PHerc0814 PHerc1447 PHercMANBp PHerc0841 PHerc1203 \
         PHerc1451 PHercMAN5 PHerc0172 PHercParis4; do
  echo "=== $s ===" >> wind.log
  ~/jev/.venv/bin/python windcheck.py --s3 "$s" --json wind --workers 4 >> wind.log 2>&1
done
echo "WINDDONE" >> wind.log
